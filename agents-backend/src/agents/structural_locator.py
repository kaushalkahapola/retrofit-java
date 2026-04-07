"""
Agent 2: Structural Locator (The Navigator)

H-MABS Phase 2 — Full Implementation.

Goal: Find the exact insertion points in the target repository for both fix
code and test cases, overcoming structural divergence (renamed files, split
classes, moved methods). Produces ConsistencyMap and MappedTargetContext.

Pipeline:
  1. Hunk Segregation: split patch_analysis into code_changes / test_changes.
  2. Per code file:
     a. Check if the file exists at the same path in target repo.
     b. If not: EnsembleRetriever.find_candidates() + match_structure().
     c. For each modified method: get_class_context() → exact name match.
        Fallback: find_method_match() using 4-tier MethodFingerprinter.
     d. Extract start_line/end_line from get_class_context() output.
     e. Reflection: verify dependent_apis from blueprint appear in body.
        If divergence too high → re-search (max 2 attempts per file).
  3. Per test file: locate target test directory or mark as null.
  4. Build ConsistencyMap and MappedTargetContext.
  5. Write structural_locator_trace.md.
"""

import json
import logging
import os
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from state import AgentState
from utils.patch_analyzer import PatchAnalyzer

try:
    from langgraph.errors import GraphRecursionError
except ImportError:  # Compatibility fallback for older langgraph versions

    class GraphRecursionError(Exception):
        pass


from agents.reasoning_tools import ReasoningToolkit
from utils.llm_provider import get_llm
from utils.method_discovery import JavaStructureLocator
from utils.retrieval.ensemble_retriever import EnsembleRetriever

logger = logging.getLogger(__name__)

PHASE2_DETERMINISTIC_FIRST = (
    os.getenv("PHASE2_DETERMINISTIC_FIRST", "true").strip().lower() == "true"
)
PHASE2_DISABLE_LLM = os.getenv("PHASE2_DISABLE_LLM", "false").strip().lower() == "true"
PHASE2_MAX_DIFF_CHARS = int(os.getenv("PHASE2_MAX_DIFF_CHARS", "8000"))
PHASE2_RECURSION_LIMIT = int(os.getenv("PHASE2_RECURSION_LIMIT", "18"))


def _looks_like_test(path: str) -> bool:
    p = (path or "").lower()
    return "test" in p or p.endswith("test.java")


def _is_java_code_file(path: str) -> bool:
    p = (path or "").lower()
    return p.endswith(".java") and not _looks_like_test(p)


_AGENT_SYSTEM = """You are an expert software engineer mapping code from a new mainline patch to an older target repository.
You need to find the exact target file and target method corresponding to a modified mainline file and methods, determining the start and end lines.
You also need to identify if any methods were renamed.

INVESTIGATION STRATEGY:
1. Path Match is a HYPOTHESIS: Just because a file exists at the same path doesn't mean the logic is there. Always verify.
2. Verify Logic: Use `get_class_context` or `read_file` to confirm the mainline code exists in the target file.
3. If Logic is MISSING: Do NOT anchor to random lines. Use the discovery loop:
   a. `grep_repo`: Search for exact strings or unique identifiers from the hunk anywhere in the repository.
   b. `git_pickaxe`: Trace the history of a specific snippet to see where it moved or what it was renamed to.
   c. `get_dependency_graph`: Find architectural neighbors of the original file. Logic often moves to related classes.
4. Support Splits: Different hunks from the same mainline file may now live in DIFFERENT target files.

You have tools:
- `search_candidates(file_path)`: Find a moved/renamed file in the target repo.
- `match_structure(mainline_file_path, candidate_paths)`: Compare structural similarity.
- `get_class_context(file_path, method_name)`: Get method boundaries and code in the target repo.
- `get_dependency_graph(file_paths)`: Find relations.
- `read_file(file_path)`: Read a file from target repo.
- `grep_repo(search_text, is_regex)`: Search the entire repository for a snippet.
- `find_symbol_locations(symbol_name)`: Find where a symbol is declared across the project.
- `git_pickaxe(file_path, snippet)`: Trace the history of a specific code snippet.
- `git_log_follow(file_path)`: Check git history for renames.

When you find the mapping, output precisely this JSON:
{
    "mappings": [
        {
            "mainline_method": "<methodName>",
            "target_file": "<path/in/target/repo>",
            "target_method": "<methodName in target repo>",
            "start_line": <int or null>,
            "end_line": <int or null>,
            "code_snippet": "<the code snippet of the method>"
        }
    ],
    "consistency_map_entries": {"oldName": "newName"}
}
If a method cannot be found anywhere, set its target_file and target_method to null.
Do not include markdown or explanations outside the JSON."""

_DIRECT_MAPPING_SYSTEM = """You are an expert at mapping patch hunks to methods in an older codebase.
Return ONLY valid JSON with this schema:
{
  "mappings": [
    {
      "mainline_method": "<methodName>",
      "target_file": "<path/in/target/repo>",
      "target_method": "<methodName or <import> or null>",
      "start_line": <int or null>,
      "end_line": <int or null>,
      "code_snippet": "<string>"
    }
  ],
  "consistency_map_entries": {"oldName": "newName"}
}
No markdown. No explanation. Only JSON."""


# ---------------------------------------------------------------------------
# Line-range parser for get_class_context output
# ---------------------------------------------------------------------------


def _extract_line_range(context_output) -> tuple[int | None, int | None, str]:
    """
    Parses the output of get_class_context() (an MCP tool response) to extract
    the method start/end line numbers and raw code snippet.

    The MCP tool now returns a dict like:
        {"context": "...", "start_line": 42, "end_line": 88, "file_path": "...", "method_name": "..."}

    Returns:
        (start_line, end_line, code_snippet)
    """
    if isinstance(context_output, dict):
        # PRIORITY 1: Try direct extraction from JSON fields (new format)
        start = context_output.get("start_line")
        end = context_output.get("end_line")
        snippet = context_output.get("context", context_output.get("body", ""))

        # Check if we got valid integers
        if start is not None and end is not None:
            try:
                return int(start), int(end), str(snippet)
            except (ValueError, TypeError):
                pass

        # PRIORITY 2: Try parsing from the context string (embedded comments)
        # Look for patterns like "// [FOCUS] Full Body (Lines 42-88)"
        snippet_str = str(snippet)

        # Pattern: "// [FOCUS] Full Body (Lines 42-88)"
        m = re.search(r"// \[FOCUS\] Full Body \(Lines (\d+)-(\d+)\)", snippet_str)
        if m:
            start = int(m.group(1))
            end = int(m.group(2))
            return start, end, snippet_str

        # Pattern: "// Line 42" (for individual methods)
        lines_found = re.findall(r"// Line (\d+)", snippet_str)
        if lines_found:
            try:
                start = int(lines_found[0])
                end = int(lines_found[-1])
                return start, end, snippet_str
            except (ValueError, IndexError):
                pass

        # PRIORITY 3: Fallback - try old format patterns
        m = re.search(r"/\*\s*L(\d+)", snippet_str)
        if m:
            start = int(m.group(1))
        m2 = re.search(r"//\s*end\s*L(\d+)", snippet_str)
        if m2:
            end = int(m2.group(1))
        return start, end, snippet_str

    # Fallback: raw string
    return None, None, str(context_output)


def _parse_mapping_json(raw_content: str) -> dict | None:
    """Extract and parse JSON mapping payload from potentially noisy LLM output."""
    text = str(raw_content or "").strip()
    if not text:
        return None

    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group(0)

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        text_clean = re.sub(
            r"```(?:json)?\n?(.*?)\n?```", r"\1", text, flags=re.DOTALL
        ).strip()
        try:
            parsed = json.loads(text_clean)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _load_target_file_lines(target_repo_path: str, target_file: str) -> list[str]:
    """Load target file lines for deterministic anchor realignment."""
    if not target_repo_path or not target_file:
        return []

    full_path = os.path.join(target_repo_path, target_file)
    if not os.path.exists(full_path):
        return []

    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().splitlines()
    except Exception:
        return []


def _find_line_in_target(target_lines: list[str], needle: str) -> int | None:
    """Find first matching line (exact/trimmed/substring) and return 1-based index."""
    if not target_lines or not needle:
        return None

    stripped = needle.strip()
    if not stripped:
        return None

    # Pass 1: exact line match
    for idx, line in enumerate(target_lines, start=1):
        if line == needle:
            return idx

    # Pass 2: trimmed exact match
    for idx, line in enumerate(target_lines, start=1):
        if line.strip() == stripped:
            return idx

    # Pass 3: substring fallback for short/partial snippets
    for idx, line in enumerate(target_lines, start=1):
        if stripped in line:
            return idx

    return None


def _extract_hunk_anchor_candidates(raw_hunk: str) -> list[str]:
    """Extract anchor candidates from a raw unified hunk (prefer removed/context lines)."""
    if not raw_hunk:
        return []

    removed: list[str] = []
    context: list[str] = []
    for i, line in enumerate(raw_hunk.splitlines()):
        if i == 0 and line.startswith("@@"):
            continue
        if not line:
            continue
        if line.startswith("-") and not line.startswith("---"):
            cand = line[1:].strip()
            if cand:
                removed.append(cand)
        elif line.startswith(" "):
            cand = line[1:].strip()
            if cand:
                context.append(cand)

    return removed + context


def _build_window_snippet(
    target_lines: list[str], center_line: int, radius: int = 20
) -> str:
    """Build a compact surrounding snippet around center_line (1-based)."""
    if not target_lines or center_line is None:
        return ""
    start = max(1, center_line - radius)
    end = min(len(target_lines), center_line + radius)
    if start > end:
        return ""
    return "\n".join(target_lines[start - 1 : end])


def _infer_anchor_confidence(
    target_repo_path: str,
    target_file: str,
    start_line: int | None,
    target_method: str | None,
) -> tuple[str, str]:
    """Infer mapping confidence for downstream planning/routing."""
    lines = _load_target_file_lines(target_repo_path, target_file)
    if not lines:
        return "low", "target_file_missing_or_unreadable"
    if not isinstance(start_line, int) or start_line < 1 or start_line > len(lines):
        return "low", "start_line_out_of_range"
    if target_method is None:
        return "medium", "line_resolved_method_unresolved"
    return "high", "line_and_method_resolved"


def _is_unresolved_target_method(value: Any) -> bool:
    s = str(value or "").strip()
    if not s:
        return True
    lowered = s.lower()
    return lowered in {"none", "null", "?"} or s.startswith("hunk_")


def _recover_with_structure_locator(
    *,
    target_repo_path: str,
    target_file: str,
    raw_hunk: str,
    target_method: str | None,
    start_line: int | None,
    end_line: int | None,
    code_snippet: str,
) -> tuple[str | None, int | None, int | None, str, str]:
    """
    Recover missing structural anchors (method/constructor/field/class) via
    JavaStructureLocator when LLM/deterministic mapping yields no target_method.
    """
    target_lines = _load_target_file_lines(target_repo_path, target_file)
    if not target_lines:
        return target_method, start_line, end_line, code_snippet, "target_unreadable"

    file_content = "\n".join(target_lines)
    locator = JavaStructureLocator(file_content)

    line_hint = start_line
    if not isinstance(line_hint, int) or line_hint < 1 or line_hint > len(target_lines):
        line_hint = _extract_target_start_from_hunk(raw_hunk)
    if not isinstance(line_hint, int) or line_hint < 1:
        line_hint = 1

    end_hint = end_line
    if not isinstance(end_hint, int) or end_hint < line_hint:
        end_hint = line_hint

    recovered = locator.find_enclosing_structure(line_hint, end_hint)
    if not recovered:
        return target_method, start_line, end_line, code_snippet, "no_structure_match"

    recovered_type = str(recovered.get("type") or "unknown")
    recovered_name = str(recovered.get("name") or "").strip() or target_method
    recovered_line = recovered.get("line")

    new_start = start_line
    new_end = end_line
    if (not isinstance(new_start, int) or new_start < 1) and isinstance(
        recovered_line, int
    ):
        new_start = recovered_line
        new_end = recovered_line
    elif isinstance(new_start, int) and (
        not isinstance(new_end, int) or new_end < new_start
    ):
        new_end = new_start

    new_snippet = str(code_snippet or "")
    if (not new_snippet.strip()) and isinstance(new_start, int):
        new_snippet = _build_window_snippet(target_lines, new_start)

    return (
        recovered_name,
        new_start,
        new_end,
        new_snippet,
        f"java_structure_locator:{recovered_type}",
    )


def _realign_mapping_to_target(
    *,
    target_repo_path: str,
    target_file: str,
    snippet: str,
    raw_hunk: str,
    current_start: int | None,
    current_end: int | None,
) -> tuple[int | None, int | None, str]:
    """
    Realign a mapping's start/end line to the actual target file using deterministic anchors.

        Priority:
            1) Removed lines from raw hunk
            2) Context lines from raw hunk
            3) Existing snippet (first non-empty line)
            4) Added lines (pure-insertion hunk fallback) — search for the NEIGHBORING line
               that immediately precedes or follows the insertion block in the target file.
               For a class-field insertion just inside a class/method opening brace, search
               for that opening brace and return the line just after it.
    """
    target_lines = _load_target_file_lines(target_repo_path, target_file)
    if not target_lines:
        # File does not exist on disk — return None so callers trigger LLM fallback
        # instead of silently anchoring to hunk-header line offsets for a ghost file.
        return None, None, snippet

    candidates: list[str] = []

    # Prefer target-grounded anchors from removed/context lines.
    candidates.extend(_extract_hunk_anchor_candidates(raw_hunk))

    snippet_first = ""
    for line in str(snippet or "").splitlines():
        if line.strip():
            snippet_first = line.strip()
            break
    if snippet_first:
        candidates.append(snippet_first)

    found_line = None
    for cand in candidates:
        found_line = _find_line_in_target(target_lines, cand)
        if found_line is not None:
            break

    if found_line is None:
        # Pure-insertion hunk fallback: no removed/context lines to anchor on.
        # Strategy: try to locate the *surrounding* lines visible in the raw hunk's
        # @@ header neighbourhood.  The header tells us the mainline target-side start
        # line; try to find the line just before that position in the target (it may
        # still exist unchanged) or the first line of any added block's prefix context
        # that was encoded as part of the snippet.
        #
        # Concretely: iterate the added lines and look for each one in the target.
        # The first one found means the insertion already landed (skip) or an adjacent
        # unchanged line can serve as the anchor.
        added_lines = _extract_added_lines_from_hunk(raw_hunk)
        # Search for added lines in target only as a last resort anchor:
        # if the added line already exists in target (e.g. a field that's already there),
        # use that position.  Otherwise the loop produces nothing and we fall through.
        for added in added_lines:
            stripped = added.strip()
            if stripped:
                found = _find_line_in_target(target_lines, stripped)
                if found is not None:
                    found_line = found
                    break

        # If still nothing, do NOT fallback to header line numbers.
        # This prevents "mapping hallucinations" where we anchor to unrelated code.
        return None, None, snippet

    span = 0
    if (
        isinstance(current_start, int)
        and isinstance(current_end, int)
        and current_end >= current_start
    ):
        # Keep previous span when available, but avoid absurd ranges.
        span = min(current_end - current_start, 200)

    new_start = found_line
    new_end = found_line + span if span > 0 else found_line
    new_snippet = snippet
    if not str(snippet or "").strip() or len(str(snippet).splitlines()) < 5:
        new_snippet = _build_window_snippet(target_lines, found_line)

    return new_start, new_end, new_snippet


def _extract_target_start_from_hunk(raw_hunk: str) -> int | None:
    """Extract target-side start line from unified diff header."""
    if not raw_hunk:
        return None
    lines = raw_hunk.splitlines()
    if not lines:
        return None
    m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", lines[0])
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _extract_added_lines_from_hunk(raw_hunk: str) -> list[str]:
    """Return added body lines from a unified diff hunk (excluding header path lines)."""
    if not raw_hunk:
        return []
    out: list[str] = []
    for i, line in enumerate(raw_hunk.splitlines()):
        if i == 0 and line.startswith("@@"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line[1:])
    return out


def _guess_method_from_hunk(raw_hunk: str, hunk_role: str) -> str | None:
    """Best-effort method/class/import role inference from hunk content."""
    added = [l.strip() for l in _extract_added_lines_from_hunk(raw_hunk) if l.strip()]
    if hunk_role == "declaration":
        if added and all(l.startswith("import ") for l in added):
            return "<import>"
        return "<class_declaration>"

    method_decl_pattern = re.compile(
        r"^(?:public|private|protected|static|final|synchronized|abstract|native|strictfp|default|\s)+"
        r"[\w<>\[\],?\s]+\s+(\w+)\s*\([^;]*\)\s*(?:\{|$)"
    )

    # Prefer context/removed lines because added method declarations may not exist yet in target.
    for line in raw_hunk.splitlines()[1:]:
        if line.startswith(" ") or (
            line.startswith("-") and not line.startswith("---")
        ):
            content = line[1:].strip()
            m = method_decl_pattern.search(content)
            if m:
                name = m.group(1)
                if name not in {
                    "if",
                    "for",
                    "while",
                    "switch",
                    "catch",
                    "return",
                    "new",
                }:
                    return name

    for line in added:
        m = method_decl_pattern.search(line)
        if m:
            name = m.group(1)
            if name not in {"if", "for", "while", "switch", "catch", "return", "new"}:
                return name
    return None


def _deterministic_map_hunks_for_file(
    *,
    file_hunks: list,
    raw_hunks_for_file: list[str],
    target_file: str,
    target_repo_path: str,
) -> list[dict] | None:
    """
    Deterministically map hunks using raw diff anchors and target file contents.

    Returns None when confidence is low (so caller can fall back to LLM mapping).
    """
    if (
        not file_hunks
        or not raw_hunks_for_file
        or len(raw_hunks_for_file) < len(file_hunks)
    ):
        return None

    deterministic: list[dict] = []
    for idx, hunk_meta in enumerate(file_hunks):
        raw_hunk = raw_hunks_for_file[idx]
        hunk_idx = hunk_meta.get("hunk_index", idx)
        hunk_role = hunk_meta.get("role", "")

        method_guess = _guess_method_from_hunk(raw_hunk, hunk_role)
        added_lines = [
            l.strip() for l in _extract_added_lines_from_hunk(raw_hunk) if l.strip()
        ]
        snippet_guess = added_lines[0] if added_lines else ""
        header_start = _extract_target_start_from_hunk(raw_hunk)

        start_line, end_line, snippet = _realign_mapping_to_target(
            target_repo_path=target_repo_path,
            target_file=target_file,
            snippet=snippet_guess,
            raw_hunk=raw_hunk,
            current_start=header_start,
            current_end=header_start,
        )

        if start_line is None:
            return None

        deterministic.append(
            {
                "mainline_method": method_guess
                or ("<import>" if hunk_role == "declaration" else f"hunk_{hunk_idx}"),
                "target_file": target_file,
                "target_method": method_guess,
                "start_line": start_line,
                "end_line": end_line,
                "code_snippet": snippet,
            }
        )

    return deterministic


def _normalize_rel_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/").lstrip("/")
    while p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p


# ---------------------------------------------------------------------------
# Core Agent Node
# ---------------------------------------------------------------------------


async def structural_locator_node(state: AgentState, config) -> dict:
    """
    Agent 2 node function.

    Inputs from state:
      - semantic_blueprint:   From Agent 1.
      - patch_analysis:       List[FileChange] from PatchAnalyzer.
      - target_repo_path:     Path to target (older) repository.
      - mainline_repo_path:   Path to mainline (newer) repository.

    Outputs written to state:
      - consistency_map:          { mainline_symbol: target_symbol }
      - mapped_target_context:    { file_path: [{ hunk_index, mainline_method, target_file, target_method, start_line, end_line, code_snippet }, ...] }
    """
    print("Agent 2 (Structural Locator): Starting target location mapping...")
    logger.info("Agent 2 start: structural locator node invoked")

    semantic_blueprint = state.get("semantic_blueprint")
    patch_analysis = state.get("patch_analysis", [])
    patch_diff = state.get("patch_diff", "")
    target_repo_path = state.get("target_repo_path", "")
    mainline_repo_path = state.get("mainline_repo_path", "")
    with_test_changes = state.get("with_test_changes", False)

    if not semantic_blueprint:
        msg = "Agent 2 Error: No semantic_blueprint in state. Agent 1 must run first."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    if not target_repo_path:
        msg = "Agent 2 Error: No target_repo_path in state."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    trace = "# Structural Locator Trace\n\n"
    trace += f"## Blueprint Summary\n- **Root Cause**: {semantic_blueprint.get('root_cause_hypothesis', '')}\n\n"

    # ------------------------------------------------------------------
    # 1. Hunk Segregation
    # ------------------------------------------------------------------
    code_changes = [
        fc
        for fc in patch_analysis
        if not (
            fc.is_test_file
            if hasattr(fc, "is_test_file")
            else fc.get("is_test_file", False)
        )
    ]
    test_changes = [
        fc
        for fc in patch_analysis
        if (
            fc.is_test_file
            if hasattr(fc, "is_test_file")
            else fc.get("is_test_file", False)
        )
    ]

    # Filter test changes based on with_test_changes flag
    if not with_test_changes:
        test_changes = []

    print(
        f"  Agent 2: {len(code_changes)} code file(s), {len(test_changes)} test file(s)"
    )
    logger.info(
        "Hunk segregation complete: code_files=%d test_files=%d",
        len(code_changes),
        len(test_changes),
    )
    trace += f"## Hunk Segregation\n- Code files: {len(code_changes)}\n- Test files: {len(test_changes)}\n\n"

    dependent_apis = set(semantic_blueprint.get("dependent_apis", []))

    # Raw hunk map used for deterministic anchor-based line realignment.
    raw_hunks_by_file: dict[str, list[str]] = {}
    if patch_diff:
        try:
            analyzer = PatchAnalyzer()
            raw_hunks_by_file = analyzer.extract_raw_hunks(patch_diff)
        except Exception as e:
            logger.warning("Could not extract raw hunks for line realignment: %s", e)

    # Output accumulators
    consistency_map: dict[str, str] = {}
    # Changed to support multiple hunks per file: dict[file_path] = list[hunk_mappings]
    mapped_target_context: dict[str, list] = {}
    git_match_method: str = ""
    git_match_reason: str = ""

    # Setup a lightweight retriever (lazy index build — only when Phase 2 git methods fail)
    try:
        retriever = EnsembleRetriever(mainline_repo_path, target_repo_path)
        # NOTE: Index building is now lazy - it will only be built when Phase 2 ensemble search
        # is actually needed (i.e., when Phase 1 git-based retrieval fails)

        toolkit = ReasoningToolkit(
            retriever,
            target_repo_path,
            mainline_repo_path,
            patch_analysis,
            state.get("original_commit", "HEAD"),
        )
        logger.debug("Retriever/toolkit initialized successfully")
    except Exception as e:
        print(f"  Agent 2: Warning — could not init retriever: {e}")
        logger.exception("Retriever/toolkit initialization failed")
        retriever = None
        toolkit = None

    # Setup LLM Agent only when fallback is enabled.
    llm = None
    agent = None
    if not PHASE2_DISABLE_LLM:
        llm = get_llm(temperature=0)
        tools = (
            [
                t
                for t in toolkit.get_tools()
                if t.name
                in [
                    "search_candidates",
                    "match_structure",
                    "get_dependency_graph",
                    "read_file",
                    "get_class_context",
                    "git_log_follow",
                    "git_blame_lines",
                    "grep_repo",
                    "find_symbol_locations",
                    "git_pickaxe",
                ]
            ]
            if toolkit
            else []
        )
        agent = create_react_agent(llm, tools=tools, prompt=_AGENT_SYSTEM)

    # ------------------------------------------------------------------
    # 2. Process hunks from hunk_chain (from semantic_blueprint)
    # ------------------------------------------------------------------
    trace += "## Code File Mappings\n\n"

    # Extract hunk_chain from semantic_blueprint
    hunk_chain = semantic_blueprint.get("hunk_chain", [])
    print(f"  Agent 2: Found {len(hunk_chain)} hunk(s) in hunk_chain")
    logger.info("Processing hunk_chain: total_hunks=%d", len(hunk_chain))

    # Group hunks by file for efficient processing
    hunks_by_file: dict[str, list] = {}
    for hunk in hunk_chain:
        file = hunk.get("file", "")
        if file and _is_java_code_file(file):
            if file not in hunks_by_file:
                hunks_by_file[file] = []
            hunks_by_file[file].append(hunk)
    logger.debug("Grouped hunks into %d file bucket(s)", len(hunks_by_file))

    # Process hunks grouped by file
    for mainline_file, file_hunks in hunks_by_file.items():
        print(
            f"  Agent 2: Locating target for {mainline_file} ({len(file_hunks)} hunk(s))..."
        )
        logger.info("Locating target file=%s hunks=%d", mainline_file, len(file_hunks))
        trace += f"### `{mainline_file}`\n\n"
        trace += f"**Hunks in this file**: {len(file_hunks)}\n\n"
        raw_hunks_for_file = raw_hunks_by_file.get(mainline_file, [])

        # STEP 1: Try git-based resolution first (no LLM call)
        git_candidates = None
        if toolkit:
            try:
                git_candidates = toolkit.search_candidates(
                    mainline_file, state.get("original_commit", "HEAD")
                )
                logger.debug(
                    "Git candidate search returned %d candidate(s) for %s",
                    len(git_candidates or []),
                    mainline_file,
                )
                if git_candidates:
                    git_target = git_candidates[0]["file"]
                    git_method = str(git_candidates[0].get("method") or "")
                    git_reason = str(git_candidates[0].get("reason") or "")
                    if not git_match_method:
                        git_match_method = git_method
                    if not git_match_reason:
                        git_match_reason = git_reason
                    print(f"  Agent 2: Git resolution found target: {git_target}")
                    logger.info(
                        "Git resolution selected target=%s for file=%s",
                        git_target,
                        mainline_file,
                    )
                    trace += f"**Git Resolution**: Found `{git_target}`\n\n"
            except Exception as e:
                print(f"  Agent 2: Git resolution failed: {e}")
                logger.exception("Git resolution failed for file=%s", mainline_file)
                trace += f"⚠️ Git resolution failed: {e}\n\n"

        # STEP 2: Extract target file (prefer git resolution result)
        target_file = mainline_file
        if git_candidates:
            target_file = git_candidates[0]["file"]
            # If the resolved file does not actually exist on disk at the
            # checked-out target HEAD, discard the git candidates entirely.
            # This forces the LLM agent to search for the real equivalent
            # (e.g. AlterTableClient → AlterTableOperation rename).
            _candidate_full_path = (
                os.path.join(target_repo_path, _normalize_rel_path(target_file))
                if target_repo_path
                else None
            )
            if _candidate_full_path and not os.path.exists(_candidate_full_path):
                print(
                    f"  Agent 2: Git candidate `{target_file}` is absent from "
                    "target working tree — discarding to trigger LLM search."
                )
                logger.warning(
                    "Git candidate absent from disk: file=%s candidate=%s; forcing LLM search",
                    mainline_file,
                    target_file,
                )
                git_candidates = None
                target_file = mainline_file

        mapping_result = None
        used_deterministic = False
        llm_failed = False

        if PHASE2_DETERMINISTIC_FIRST:
            deterministic_mappings = _deterministic_map_hunks_for_file(
                file_hunks=file_hunks,
                raw_hunks_for_file=raw_hunks_for_file,
                target_file=target_file,
                target_repo_path=target_repo_path,
            )
            if deterministic_mappings:
                mapping_result = {
                    "mappings": deterministic_mappings,
                    "consistency_map_entries": {},
                }
                used_deterministic = True
                trace += "**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).\n\n"
                logger.info(
                    "Deterministic mapping used for file=%s hunks=%d",
                    mainline_file,
                    len(deterministic_mappings),
                )

        # Build LLM prompt only when deterministic path did not produce a usable mapping.
        if mapping_result is None and not PHASE2_DISABLE_LLM:
            file_diff = ""
            try:
                pa = PatchAnalyzer()
                raw_hunks = pa.extract_raw_hunks(state.get("patch_diff", ""))
                file_diff = "\n".join(raw_hunks.get(mainline_file, []))
            except Exception:
                file_diff = "Diff not available."

            if len(file_diff) > PHASE2_MAX_DIFF_CHARS:
                file_diff = file_diff[:PHASE2_MAX_DIFF_CHARS] + "\n...[TRUNCATED]..."

            # Build hunk details for LLM - CRITICAL: include hunk_index for proper ordering
            hunk_details = "Hunk Details (in order):\n"
            for idx, hunk in enumerate(file_hunks):
                hunk_idx = hunk.get("hunk_index", idx)
                role = hunk.get("role", "?")
                summary = hunk.get("summary", "")
                hunk_details += f"  - Hunk {hunk_idx} (role={role}): {summary}\n"

            # Simplified blueprint for LLM (avoid redundant info)
            simple_blueprint = {
                "root_cause_hypothesis": semantic_blueprint.get(
                    "root_cause_hypothesis", ""
                ),
                "fix_logic": semantic_blueprint.get("fix_logic", ""),
                "dependent_apis": semantic_blueprint.get("dependent_apis", []),
            }

            # If the mainline file does not exist at HEAD in the target repo, tell the
            # LLM explicitly so it skips the pointless "verify at same path" step and
            # goes straight to searching.  This is derived entirely from an on-disk
            # existence check — no reliance on the developer's backport answer.
            file_missing_hint = ""
            if not _load_target_file_lines(target_repo_path, mainline_file):
                file_missing_hint = (
                    f"\n⚠️ FILE NOT FOUND AT HEAD: `{mainline_file}` does NOT exist on the target branch.\n"
                    f"  The class was likely renamed, split, or refactored between branches.\n"
                    f"  You MUST search for the equivalent logic — do NOT anchor to this path:\n"
                    f"  1. `grep_repo` — search for unique method/class names or code snippets from the diff\n"
                    f"  2. `git_pickaxe` — trace history of a specific code snippet from the mainline hunks\n"
                    f"  3. `find_symbol_locations` — locate key method or field names from the diff\n"
                    f"  4. `git_log_follow` — check whether the file was renamed in git history\n"
                    f"  5. `get_dependency_graph` — find classes related to `{mainline_file.split('/')[-1]}`\n"
                    f"  DO NOT output a mapping until you have confirmed the target logic exists there.\n\n"
                )

            input_msg = (
                f"Mainline File: {mainline_file}\n"
                f"{file_missing_hint}"
                f"Target File (path-match hypothesis): {target_file}\n"
                f"{hunk_details}\n"
                f"Semantic Blueprint:\n{json.dumps(simple_blueprint, indent=2)}\n\n"
                f"Patch Diff for this file:\n```diff\n{file_diff}\n```\n\n"
                f"MISSION: Locate where each of the {len(file_hunks)} hunks above applies in the target repository.\n"
                f"1. VERIFY if the logic still lives in '{target_file}' using `get_class_context` or `read_file`.\n"
                f"2. IF LOGIC IS MISSING/MOVED: Use `grep_repo` for unique strings, `git_pickaxe` for history, or `get_dependency_graph` to find architectural neighbors.\n"
                f"3. REPORT: Return a JSON with 'mappings' array, one entry per hunk in the SAME ORDER as listed above.\n"
                f"   Each entry can have a different 'target_file' if the logic was split or relocated."
            )
            input_data = {"messages": [("user", input_msg)]}

            for attempt in range(2):
                try:
                    logger.debug(
                        "Invoking structural locator LLM for file=%s attempt=%d",
                        mainline_file,
                        attempt + 1,
                    )
                    result = await agent.ainvoke(
                        input_data,
                        config={"recursion_limit": PHASE2_RECURSION_LIMIT},
                    )
                    raw_content = result["messages"][-1].content
                    mapping_result = _parse_mapping_json(raw_content)

                    if not mapping_result:
                        trace += f"⚠️ **LLM Mapping Extraction Failed**\n\nRaw Response:\n```\n{raw_content}\n```\n\n"
                        llm_failed = True
                        logger.warning(
                            "LLM JSON parse failed for file=%s attempt=%d",
                            mainline_file,
                            attempt + 1,
                        )

                    if mapping_result:
                        trace += f"**Agent Tool Steps:**\n\n"
                        for m in result.get("messages", []):
                            if m.type == "tool":
                                trace += f"  - `Tool: {m.name}` -> {str(m.content)[:200]}...\n"
                            elif m.type == "ai" and m.tool_calls:
                                for tc in m.tool_calls:
                                    trace += f"  - `Agent calls {tc['name']}` with `{json.dumps(tc['args'])}`\n"
                        trace += "\n"
                    break
                except GraphRecursionError as e:
                    print(
                        f"  Agent 2: Recursion limit reached in tool loop (attempt {attempt + 1}/2): {e}"
                    )
                    logger.warning(
                        "Recursion limit reached for file=%s attempt=%d; falling back to direct no-tool mapping",
                        mainline_file,
                        attempt + 1,
                    )
                    llm_failed = True

                    fallback_messages = [
                        ("system", _DIRECT_MAPPING_SYSTEM),
                        ("user", input_msg),
                    ]
                    try:
                        fallback_resp = await llm.ainvoke(fallback_messages)
                        fallback_content = getattr(
                            fallback_resp, "content", str(fallback_resp)
                        )
                        mapping_result = _parse_mapping_json(fallback_content)
                        if mapping_result:
                            trace += "**Fallback Mode**: direct no-tool LLM mapping used after recursion limit.\n\n"
                            break
                        trace += (
                            "⚠️ **Fallback Mapping Extraction Failed**\n\n"
                            f"Raw Response:\n```\n{fallback_content}\n```\n\n"
                        )
                        logger.warning(
                            "Fallback direct mapping JSON parse failed for file=%s attempt=%d",
                            mainline_file,
                            attempt + 1,
                        )
                    except Exception as fallback_exc:
                        logger.exception(
                            "Fallback direct mapping invocation failed for file=%s attempt=%d",
                            mainline_file,
                            attempt + 1,
                        )
                        trace += f"⚠️ Direct fallback mapping failed: {fallback_exc}\n\n"
                    if attempt == 0:
                        print("  Waiting 30 seconds before retry...")
                        time.sleep(30)
                except Exception as e:
                    print(f"  Agent 2: LLM call error (attempt {attempt + 1}/2): {e}")
                    logger.exception(
                        "LLM call failed for file=%s attempt=%d",
                        mainline_file,
                        attempt + 1,
                    )
                    llm_failed = True
                    if attempt == 0:
                        print("  Waiting 30 seconds before retry...")
                        time.sleep(30)
        elif mapping_result is None and PHASE2_DISABLE_LLM:
            llm_failed = True
            trace += "**LLM Disabled**: deterministic mapping unavailable; falling back to git-only mapping.\n\n"

        # STEP 3: Use LLM result if successful, otherwise fallback to git resolution
        if mapping_result and isinstance(mapping_result, dict):
            if used_deterministic:
                logger.info(
                    "Deterministic mapping finalized for file=%s mappings=%d",
                    mainline_file,
                    len(mapping_result.get("mappings", [])),
                )
            else:
                logger.info(
                    "LLM mapping succeeded for file=%s mappings=%d consistency_entries=%d",
                    mainline_file,
                    len(mapping_result.get("mappings", [])),
                    len(mapping_result.get("consistency_map_entries", {})),
                )
            # LLM provided detailed mappings
            for k, v in mapping_result.get("consistency_map_entries", {}).items():
                consistency_map[k] = v

            mappings = mapping_result.get("mappings", [])
            # Initialize list for this file if not present
            if mainline_file not in mapped_target_context:
                mapped_target_context[mainline_file] = []

            # Match each mapping to corresponding hunk by considering order
            # Mappings should be in the same order as file_hunks
            trace += f"| Hunk Idx | Role | Mainline Method | Target Method | Lines |\n"
            trace += f"|---|---|---|---|---|\n"

            for hunk_idx_in_hunks, hunk in enumerate(file_hunks):
                hunk_idx = hunk.get("hunk_index", hunk_idx_in_hunks)
                hunk_role = hunk.get("role", "")
                fallback_anchor_reason = ""

                # Get the mapping for this hunk (should be at same index)
                if hunk_idx_in_hunks < len(mappings):
                    m = mappings[hunk_idx_in_hunks]
                else:
                    # Not enough mappings returned by LLM - create default
                    logger.warning(
                        "LLM returned fewer mappings than hunks for file=%s (hunks=%d mappings=%d); synthesizing default mapping for hunk_index=%s",
                        mainline_file,
                        len(file_hunks),
                        len(mappings),
                        hunk_idx,
                    )
                    m = {
                        "mainline_method": "<import>"
                        if hunk_role == "declaration"
                        else f"hunk_{hunk_idx}",
                        "target_file": target_file,
                        "target_method": "<import>"
                        if hunk_role == "declaration"
                        else None,
                        "start_line": None,
                        "end_line": None,
                        "code_snippet": "",
                    }

                # Ensure target_file is set from our git resolution
                if not m.get("target_file"):
                    m["target_file"] = target_file

                # Deterministic post-processing: align guessed lines to real target anchors.
                raw_hunk = (
                    raw_hunks_for_file[hunk_idx_in_hunks]
                    if hunk_idx_in_hunks < len(raw_hunks_for_file)
                    else ""
                )
                old_start = m.get("start_line")
                old_end = m.get("end_line")
                new_start, new_end, new_snippet = _realign_mapping_to_target(
                    target_repo_path=target_repo_path,
                    target_file=str(m.get("target_file") or target_file),
                    snippet=str(m.get("code_snippet", "")),
                    raw_hunk=raw_hunk,
                    current_start=old_start,
                    current_end=old_end,
                )
                if new_start != old_start or new_end != old_end:
                    logger.info(
                        "Realigned hunk line range file=%s hunk_index=%s from %s-%s to %s-%s",
                        mainline_file,
                        hunk_idx,
                        old_start,
                        old_end,
                        new_start,
                        new_end,
                    )
                    trace += (
                        f"  - Realigned hunk {hunk_idx} lines: "
                        f"{old_start}-{old_end} -> {new_start}-{new_end}\n"
                    )
                m["start_line"] = new_start
                m["end_line"] = new_end
                if new_snippet:
                    m["code_snippet"] = new_snippet

                # Second-chance line recovery when realignment left no anchor (short hunks / drift).
                if m.get("start_line") is None and raw_hunk:
                    _tl = _load_target_file_lines(
                        target_repo_path, str(m.get("target_file") or target_file)
                    )
                    if _tl:
                        for _cand in _extract_hunk_anchor_candidates(raw_hunk):
                            _s = (_cand or "").strip()
                            if len(_s) < 16:
                                continue
                            _hit = _find_line_in_target(_tl, _s)
                            if _hit is not None:
                                m["start_line"] = _hit
                                m["end_line"] = _hit
                                m["code_snippet"] = _build_window_snippet(_tl, _hit)
                                trace += (
                                    f"  - Recovered start_line for hunk {hunk_idx} via "
                                    f"context anchor (len={len(_s)})\n"
                                )
                                break

                # CRITICAL: For import hunks, we need to ensure proper line numbers
                # Without proper start_line/end_line, hunk_generator will fall back to original mainline line numbers,
                # which won't match the target file. The sorting in apply_adapted_hunks depends on correct insertion_line values.
                if hunk_role == "declaration" and m.get("start_line") is None:
                    # For imports, try to at least suggest where imports should be
                    # This is a fallback - the LLM mapping should ideally have provided this
                    trace += f"  ⚠️ Import hunk {hunk_idx} has no target start_line. Hunk generator will extract from hunk header.\n"

                # Final structural fallback when method anchor is unresolved.
                target_method_raw = m.get("target_method")
                is_import_mapping = str(target_method_raw or "").strip() == "<import>"
                if not is_import_mapping and _is_unresolved_target_method(
                    target_method_raw
                ):
                    (
                        recovered_method,
                        recovered_start,
                        recovered_end,
                        recovered_snippet,
                        fallback_anchor_reason,
                    ) = _recover_with_structure_locator(
                        target_repo_path=target_repo_path,
                        target_file=str(m.get("target_file") or target_file),
                        raw_hunk=raw_hunk,
                        target_method=str(target_method_raw or "") or None,
                        start_line=m.get("start_line"),
                        end_line=m.get("end_line"),
                        code_snippet=str(m.get("code_snippet", "")),
                    )

                    if recovered_method and recovered_method != target_method_raw:
                        m["target_method"] = recovered_method
                        logger.info(
                            "Recovered target_method via JavaStructureLocator file=%s hunk_index=%s method=%s",
                            mainline_file,
                            hunk_idx,
                            recovered_method,
                        )
                        trace += (
                            f"  - JavaStructureLocator recovered target_method for hunk {hunk_idx}: "
                            f"{recovered_method} ({fallback_anchor_reason})\n"
                        )

                    if recovered_start != m.get("start_line"):
                        m["start_line"] = recovered_start
                        m["end_line"] = recovered_end
                    if recovered_snippet and not str(m.get("code_snippet", "")).strip():
                        m["code_snippet"] = recovered_snippet

                trace += (
                    f"| {hunk_idx} | {hunk_role} | `{m.get('mainline_method', '?')}` | "
                    f"`{m.get('target_method', '?')}` | {m.get('start_line', '?')}–{m.get('end_line', '?')} |\n"
                )

                # Append mapping for this hunk
                anchor_confidence, anchor_reason = _infer_anchor_confidence(
                    target_repo_path,
                    str(m.get("target_file") or target_file),
                    m.get("start_line"),
                    m.get("target_method"),
                )
                anchor_strategy = (
                    "deterministic_realign" if used_deterministic else "llm_realign"
                )
                if fallback_anchor_reason.startswith("java_structure_locator:"):
                    anchor_reason = f"{anchor_reason}; {fallback_anchor_reason}"
                    anchor_strategy += "+structure_locator"
                mapped_target_context[mainline_file].append(
                    {
                        "hunk_index": hunk_idx,
                        "mainline_method": m.get("mainline_method"),
                        "target_file": m.get("target_file"),
                        "target_method": m.get("target_method"),
                        "start_line": m.get("start_line"),
                        "end_line": m.get("end_line"),
                        "code_snippet": m.get("code_snippet", ""),
                        "anchor_confidence": anchor_confidence,
                        "anchor_reason": anchor_reason,
                        "anchor_strategy": anchor_strategy,
                    }
                )
                print(
                    f"  Agent 2: Mapped hunk {hunk_idx} ({m.get('mainline_method', '?')}) to {m.get('target_method', '?')} at lines {m.get('start_line', '?')}-{m.get('end_line', '?')}"
                )
        elif git_candidates:
            # LLM failed, but git resolution succeeded — use it as fallback
            git_target = git_candidates[0]["file"]
            logger.warning(
                "Using git-only fallback mapping for file=%s target=%s llm_failed=%s",
                mainline_file,
                git_target,
                llm_failed,
            )
            trace += f"**Fallback**: Using git resolution result (LLM refinement failed).\n\n"

            if mainline_file not in mapped_target_context:
                mapped_target_context[mainline_file] = []

            # Create fallback mappings for each hunk
            for idx, hunk in enumerate(file_hunks):
                hunk_idx = hunk.get("hunk_index", idx)
                hunk_role = hunk.get("role", "")
                raw_hunk = (
                    raw_hunks_for_file[idx] if idx < len(raw_hunks_for_file) else ""
                )
                start_line, end_line, snippet = _realign_mapping_to_target(
                    target_repo_path=target_repo_path,
                    target_file=git_target,
                    snippet="",
                    raw_hunk=raw_hunk,
                    current_start=None,
                    current_end=None,
                )

                if hunk_role == "declaration":
                    # Import statements
                    anchor_confidence, anchor_reason = _infer_anchor_confidence(
                        target_repo_path,
                        git_target,
                        start_line,
                        "<import>",
                    )
                    mapped_target_context[mainline_file].append(
                        {
                            "hunk_index": hunk_idx,
                            "mainline_method": "<import>",
                            "target_file": git_target,
                            "target_method": "<import>",
                            "start_line": start_line,
                            "end_line": end_line,
                            "code_snippet": snippet,
                            "anchor_confidence": anchor_confidence,
                            "anchor_reason": anchor_reason,
                            "anchor_strategy": "git_fallback_realign",
                        }
                    )
                    print(
                        f"  Agent 2: Fallback mapped hunk {hunk_idx} (import) to {git_target}"
                    )
                else:
                    # Regular hunks
                    (
                        recovered_method,
                        recovered_start,
                        recovered_end,
                        recovered_snippet,
                        fallback_anchor_reason,
                    ) = _recover_with_structure_locator(
                        target_repo_path=target_repo_path,
                        target_file=git_target,
                        raw_hunk=raw_hunk,
                        target_method=None,
                        start_line=start_line,
                        end_line=end_line,
                        code_snippet=str(snippet or ""),
                    )
                    if recovered_start != start_line:
                        start_line = recovered_start
                        end_line = recovered_end
                    if recovered_snippet and not str(snippet or "").strip():
                        snippet = recovered_snippet

                    anchor_confidence, anchor_reason = _infer_anchor_confidence(
                        target_repo_path,
                        git_target,
                        start_line,
                        recovered_method,
                    )
                    anchor_strategy = "git_fallback_realign"
                    if fallback_anchor_reason.startswith("java_structure_locator:"):
                        anchor_reason = f"{anchor_reason}; {fallback_anchor_reason}"
                        anchor_strategy += "+structure_locator"
                    mapped_target_context[mainline_file].append(
                        {
                            "hunk_index": hunk_idx,
                            "mainline_method": f"hunk_{hunk_idx}",
                            "target_file": git_target,
                            "target_method": recovered_method,
                            "start_line": start_line,
                            "end_line": end_line,
                            "code_snippet": snippet,
                            "anchor_confidence": anchor_confidence,
                            "anchor_reason": anchor_reason,
                            "anchor_strategy": anchor_strategy,
                        }
                    )
                    print(f"  Agent 2: Fallback mapped hunk {hunk_idx} to {git_target}")
        else:
            trace += f"❌ Failed to locate target — neither LLM nor git resolution provided results.\n\n"
            print(f"  Agent 2: Could not map {mainline_file} — skipping.")
            logger.error(
                "Failed to map file=%s no LLM mapping and no git candidates",
                mainline_file,
            )

    # ------------------------------------------------------------------
    # 3. Process test files
    # ------------------------------------------------------------------
    trace += "## Test File Mappings\n\n"

    for change in test_changes:
        mainline_test = (
            change.file_path
            if hasattr(change, "file_path")
            else change.get("file_path")
        )
        target_test = _find_target_test_file(mainline_test, target_repo_path)

        if mainline_test not in mapped_target_context:
            mapped_target_context[mainline_test] = []

        if target_test:
            mapped_target_context[mainline_test].append(
                {
                    "hunk_index": 0,
                    "target_file": target_test,
                    "method": None,
                    "start_line": None,
                    "end_line": None,
                    "code_snippet": "",
                }
            )
            trace += f"- `{mainline_test}` → `{target_test}` ✅\n"
            print(f"  Agent 2: Test file mapped: {mainline_test} → {target_test}")
        else:
            mapped_target_context[mainline_test].append(
                {
                    "hunk_index": 0,
                    "target_file": None,
                    "method": None,
                    "start_line": None,
                    "end_line": None,
                    "code_snippet": "",
                }
            )
            trace += f"- `{mainline_test}` → **null** (test synthesis required by Agent 4) ⚠️\n"
            print(
                f"  Agent 2: Test file not found for {mainline_test}. Agent 4 will synthesize."
            )

    # ------------------------------------------------------------------
    # 4. Finalize trace & output
    # ------------------------------------------------------------------
    trace += "\n## Consistency Map\n\n"
    if consistency_map:
        trace += "| Mainline Symbol | Target Symbol |\n|---|---|\n"
        for k, v in consistency_map.items():
            trace += f"| `{k}` | `{v}` |\n"
    else:
        trace += "_No renames detected — identity mapping assumed._\n"

    try:
        with open("structural_locator_trace.md", "w", encoding="utf-8") as f:
            f.write(trace)
        print("  Agent 2: Trace written to structural_locator_trace.md")
    except Exception as e:
        print(f"  Agent 2: Warning — could not write trace: {e}")

    print(
        f"Agent 2: Complete. Mapped {len(mapped_target_context)} file(s). "
        f"Total hunk mappings: {sum(len(v) for v in mapped_target_context.values())}. "
        f"ConsistencyMap has {len(consistency_map)} rename(s)."
    )
    logger.info(
        "Agent 2 complete: mapped_files=%d total_hunk_mappings=%d consistency_map_entries=%d",
        len(mapped_target_context),
        sum(len(v) for v in mapped_target_context.values()),
        len(consistency_map),
    )

    return {
        "messages": [
            HumanMessage(
                content=(
                    f"Agent 2 complete. Mapped {len(mapped_target_context)} location(s), "
                    f"{len(consistency_map)} method rename(s) in ConsistencyMap."
                )
            )
        ],
        "consistency_map": consistency_map,
        "mapped_target_context": mapped_target_context,
        "structural_locator_git_match_method": git_match_method,
        "structural_locator_git_match_reason": git_match_reason,
        "token_usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated": PHASE2_DISABLE_LLM,
            "reason": "deterministic_no_llm"
            if PHASE2_DISABLE_LLM
            else "llm_usage_not_collected_in_this_node",
        },
    }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _find_target_file(mainline_file: str, target_repo_path: str, toolkit) -> str | None:
    """
    Finds the equivalent of mainline_file in the target repository.
    1. Try exact same path → if exists, return it.
    2. Try filename-only match (handles moved files).
    3. Use EnsembleRetriever.find_candidates() + match_structure() (if toolkit available).
    Returns relative path or None.
    """
    # 1. Exact path
    full_exact = os.path.join(target_repo_path, mainline_file)
    if os.path.exists(full_exact):
        return mainline_file

    # 2. Filename-only match (walk the target tree)
    filename = os.path.basename(mainline_file)
    for root, _, files in os.walk(target_repo_path):
        if ".git" in root:
            continue
        for f in files:
            if f == filename:
                rel = os.path.relpath(os.path.join(root, f), target_repo_path)
                return rel

    # 3. EnsembleRetriever candidates + structural match
    if toolkit:
        try:
            candidates = toolkit.search_candidates(mainline_file)
            if candidates:
                cand_paths = [
                    c.get("file_path") or c.get("path", "")
                    for c in candidates
                    if isinstance(c, dict)
                ]
                cand_paths = [p for p in cand_paths if p]
                if cand_paths:
                    match_json = toolkit.match_structure(mainline_file, cand_paths)
                    match_data = (
                        json.loads(match_json)
                        if isinstance(match_json, str)
                        else match_json
                    )
                    matches = match_data.get("matches", [])
                    if matches:
                        return matches[0].get("file_path")
        except Exception as e:
            print(f"  Agent 2: Retriever fallback error: {e}")

    return None


def _find_target_test_file(mainline_test: str, target_repo_path: str) -> str | None:
    """
    Locates a test file in the target repository.
    Tries exact path, then basename match restricted to test directories.
    """
    full_exact = os.path.join(target_repo_path, mainline_test)
    if os.path.exists(full_exact):
        return mainline_test

    filename = os.path.basename(mainline_test)
    for root, _, files in os.walk(target_repo_path):
        if ".git" in root:
            continue
        # Only look in test directories
        rel_root = os.path.relpath(root, target_repo_path)
        if "test" not in rel_root.lower():
            continue
        if filename in files:
            return os.path.relpath(os.path.join(root, filename), target_repo_path)

    return None


def _infer_modified_methods(change) -> list[str]:
    """
    Infers method names that were modified in a FileChange by scanning
    removed_lines and added_lines for Java method declaration patterns.
    Returns a deduplicated list of method names.
    """
    pattern = re.compile(
        r"(?:public|private|protected|static|final|synchronized|\s)+"
        r"[\w<>\[\],\s]+\s+(\w+)\s*\("
    )
    skip = {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "new",
        "return",
        "else",
        "do",
        "try",
    }
    found = []
    lines = []
    if hasattr(change, "removed_lines"):
        lines.extend(change.removed_lines)
    elif isinstance(change, dict):
        lines.extend(change.get("removed_lines", []))
    if hasattr(change, "added_lines"):
        lines.extend(change.added_lines)
    elif isinstance(change, dict):
        lines.extend(change.get("added_lines", []))

    for line in lines:
        # Search for method patterns (e.g., "void foo()", "int bar(String x)")
        for m in pattern.finditer(line):
            name = m.group(1)
            if name not in skip and name not in found:
                found.append(name)

    # Fallback/Improvement: If no methods found, try searching in context lines if available
    # However, since FileChange doesn't have context lines, we'll rely on the LLM seeing the full diff.

    return found


def _locate_method_with_reflection(
    mcp,
    toolkit,
    target_file: str,
    mainline_method: str,
    target_repo_path: str,
    dependent_apis: set,
    consistency_map: dict,
    trace_lines: list,
    max_attempts: int = 2,
) -> dict:
    """
    Locates a method in the target file and validates it passes the reflection check.
    Fills consistency_map with renames discovered via find_method_match().

    Returns a dict with: target_method, start_line, end_line, code_snippet, divergence.
    """
    # Guard: if mainline_method is None or empty, return early
    if not mainline_method or not isinstance(mainline_method, str):
        trace_lines.append(f"⚠️ Cannot locate None/empty method in {target_file}")
        return {
            "target_method": None,
            "start_line": None,
            "end_line": None,
            "code_snippet": "",
            "divergence": "method_not_identified",
        }

    target_method = mainline_method  # assume identity
    start_line = None
    end_line = None
    code_snippet = ""
    divergence = "unknown"

    for attempt in range(max_attempts + 1):
        # --- A. Try direct name match ---
        try:
            ctx = mcp.call_tool(
                "get_class_context",
                {
                    "target_repo_path": target_repo_path,
                    "file_path": target_file,
                    "focus_method": target_method,
                },
            )
            start_line, end_line, code_snippet = _extract_line_range(ctx)
        except Exception as e:
            print(f"    Agent 2: get_class_context error (attempt {attempt + 1}): {e}")
            ctx = None

        # --- B. Fallback: fingerprinting if method not found ---
        if not code_snippet or "[not found]" in str(code_snippet).lower():
            if toolkit:
                try:
                    match_result_str = toolkit.find_method_match(
                        target_file_path=target_file,
                        old_method_name=mainline_method,
                        old_signature="",
                        old_calls=[],
                    )
                    match_result = (
                        json.loads(match_result_str)
                        if isinstance(match_result_str, str)
                        else match_result_str
                    )
                    matched = match_result.get("match")
                    if matched:
                        found_name = matched.get("simpleName", mainline_method)
                        if found_name != mainline_method:
                            consistency_map[mainline_method] = found_name
                            print(
                                f"    Agent 2: Renamed method — {mainline_method} → {found_name}"
                            )
                        target_method = found_name
                        # Re-fetch with new name
                        try:
                            ctx2 = mcp.call_tool(
                                "get_class_context",
                                {
                                    "target_repo_path": target_repo_path,
                                    "file_path": target_file,
                                    "focus_method": target_method,
                                },
                            )
                            start_line, end_line, code_snippet = _extract_line_range(
                                ctx2
                            )
                        except Exception:
                            pass
                except Exception as e:
                    print(f"    Agent 2: find_method_match error: {e}")

        # --- C. Reflection: verify dependent_apis are present ---
        if code_snippet and dependent_apis:
            missing = [api for api in dependent_apis if api not in code_snippet]
            if missing:
                divergence = f"missing: {missing}"
                print(
                    f"    Agent 2: Reflection fail (attempt {attempt + 1}) — missing APIs: {missing}"
                )
                if attempt < max_attempts:
                    # Try to broaden search via candidates
                    print(f"    Agent 2: Retrying with broader candidate search...")
                    continue
                else:
                    print(
                        f"    Agent 2: Max reflection attempts reached. Using best-effort result."
                    )
            else:
                divergence = "ok"
        else:
            divergence = "no-apis-to-check" if not dependent_apis else "no-snippet"

        break  # Passed reflection or gave up

    return {
        "target_method": target_method,
        "start_line": start_line,
        "end_line": end_line,
        "code_snippet": code_snippet,
        "divergence": divergence,
    }
