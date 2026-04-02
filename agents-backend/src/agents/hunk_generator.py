"""
Agent 3: Hunk Generator (The Surgeon)

H-MABS Phase 3 — Full Implementation.

Goal: Rewrite the mainline patch hunks surgically, hunk-by-hunk, to fit the
target repository's structure and naming conventions.

Key inputs from state:
  - semantic_blueprint:     Fix intent (Agent 1)
  - consistency_map:        Symbol renames (Agent 2)
  - mapped_target_context:  Exact insertion points (Agent 2)
  - patch_analysis:         Original FileChange list
  - patch_diff:             Raw diff text
  - validation_attempts:    Retry counter (0 = fresh run)
  - validation_error_context: Error logs injected on retry

Key outputs to state:
  - adapted_code_hunks:   list[AdaptedHunk]
  - adapted_test_hunks:   list[AdaptedHunk]
"""

import re
import json
import os
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.errors import GraphRecursionError
from state import AgentState, AdaptedHunk, SemanticBlueprint
from utils.patch_analyzer import PatchAnalyzer
from utils.llm_provider import get_llm
from utils.retrieval.ensemble_retriever import EnsembleRetriever
from agents.validation_tools import ValidationToolkit
from agents.hunk_generator_tools import HunkGeneratorToolkit


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

_HUNK_REWRITE_SYSTEM = """You are an expert Java patch adapter specializing in backporting security fixes.

Your task is to rewrite a single unified diff hunk so it applies cleanly to an older version of a Java file.

Rules (follow ALL of them strictly):
1. You may adapt context (` ` lines) and removed (`-` lines) so the hunk matches the target file's actual layout.
2. Keep edits minimal and focused: preserve fix behavior and avoid unrelated modifications.
3. Apply every symbol rename from the ConsistencyMap exactly.
4. Preserve the fix intent described in the SemanticBlueprint — this fix MUST still work.
5. Adjust the @@ line numbers to match the target file's insertion_line and body counts.
6. Output ONLY the unified diff hunk. Start with @@ and end with the last changed line.
7. Do NOT include any explanation, markdown fences, or comments outside the hunk."""

_HUNK_REWRITE_SYSTEM_TOOLS = """You are an expert Java patch adapter specializing in backporting security fixes.
You have access to tools that let you read the real target file before generating a diff hunk.

MANDATORY WORKFLOW — follow these steps IN ORDER for every hunk:

STEP 1 — PLAN (use manage_todo)
  Add one todo per context-gathering task you need to perform. At minimum add:
    - "Read file window around insertion_line to verify surrounding context"
  Also add todos for any specific context lines you are unsure about.

STEP 2 — GATHER CONTEXT (use read_file_window, grep_in_file, get_exact_lines, verify_context_at_line)
  For EVERY context line (' ' lines) in the hunk, verify it exists at the expected line number
  in the target file using verify_context_at_line. If it doesn't match, use grep_in_file to
  find where it actually is, and read_file_window to see the real surrounding lines.
  Complete each todo as you finish the corresponding tool call.

STEP 3 — GENERATE (emit the final hunk)
  Only after ALL todos are completed, emit the final adapted unified diff hunk.
  The context lines you write MUST exactly match the lines you verified in STEP 2.
  The @@ header line numbers MUST reflect the actual target file lines you found.

Rules (follow ALL of them strictly):
1. Context lines (' ' lines) MUST match the real target file content exactly (character-for-character).
2. Keep edits minimal: preserve fix behavior, avoid unrelated changes.
3. Apply every symbol rename from the ConsistencyMap to '+' lines.
4. Preserve the fix intent — this fix MUST still work.
5. Adjust the @@ line numbers to match the VERIFIED insertion line in the target file.
6. Output ONLY the unified diff hunk at the end. Start with @@ and end with the last changed line.
7. Do NOT include any explanation, markdown fences, or extra comments outside the hunk.
8. If you cannot verify context (file unreadable, line not found), emit the best hunk you can
   and explain the issue in a single comment line BEFORE the @@ block like:
   # WARNING: Could not verify context at line N — using best-effort"""


_HUNK_REWRITE_USER = """\
## Mainline Hunk (what you need to adapt)
```diff
{mainline_hunk}
```

## Target Method Body (where this hunk will be inserted)
```java
{target_method_body}
```

## Current Imports in Target File (for import hunks only)
{target_imports_context}

## ConsistencyMap (apply these renames to + lines)
{consistency_map}

## Fix Intent (SemanticBlueprint)
- Fix Logic: {fix_logic}
- Dependent APIs: {dependent_apis}

## Insertion Point in Target File
Line {insertion_line} in `{target_file}`

## Developer Auxiliary Hunk Signals (tests/non-Java file ops)
{developer_aux_context}

{retry_context}
Rewrite the hunk now. Output ONLY the unified diff block starting with @@."""


_TEST_HUNK_REWRITE_USER = """\
## Mainline Test Hunk (what you need to adapt)
```diff
{mainline_hunk}
```

## Target Test File Location
`{target_test_file}`

## ConsistencyMap (apply these renames)
{consistency_map}

## Root Cause Being Fixed (the test must target this)
{root_cause}

## Developer Auxiliary Hunk Signals (tests/non-Java file ops)
{developer_aux_context}

{retry_context}
Rewrite the test hunk to exercise the same vulnerability in the target codebase.
Output ONLY the unified diff block starting with @@."""


_BLUEPRINT_CHECK_SYSTEM = """You are a code reviewer verifying that a patch hunk preserves a specific fix intent.
Answer ONLY "YES" if the hunk correctly implements the fix logic, or "NO: <one-line reason>" if it does not."""


_BLUEPRINT_CHECK_USER = """\
## Generated Hunk
```diff
{generated_hunk}
```

## Expected Fix Logic
{fix_logic}

## Critical APIs That Must Appear
{dependent_apis}

Does the generated hunk correctly implement the fix logic? Answer YES or NO."""


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _extract_hunk_block(raw: str) -> str | None:
    """
    Extracts the first unified diff hunk (@@-prefixed block) from an LLM response.
    Strips markdown fences if present. Returns None if no valid hunk found.

    Important: Preserves all context lines and trailing whitespace needed for a valid patch.
    """
    if not raw:
        return None

    # Strip markdown code fences
    text = raw.strip()
    if "```" in text:
        # Extract content between first and last fence
        inner_lines = []
        in_fence = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                inner_lines.append(line)
        text = "\n".join(inner_lines).strip()

    # Find the first @@ line
    lines = text.splitlines()
    hunk_start = None
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            hunk_start = i
            break

    if hunk_start is None:
        return None

    # Collect hunk lines from @@ onwards
    # A hunk ends when we encounter a new file header OR when we've consumed all valid diff lines
    hunk_lines = []
    for line in lines[hunk_start:]:
        # Stop at new file/section headers (but these shouldn't appear in valid LLM output)
        if line.startswith("diff --git"):
            if hunk_lines:  # only break if we already have some hunk content
                break
        hunk_lines.append(line)

    if not hunk_lines:
        return None

    result = "\n".join(hunk_lines)
    # Ensure the result ends with a newline for proper unified diff format
    if not result.endswith("\n"):
        result += "\n"
    return result


async def _check_intent(
    llm,
    hunk_text: str,
    blueprint: SemanticBlueprint,
) -> bool:
    """
    Sends a short verification prompt to the LLM asking if the generated hunk
    preserves the SemanticBlueprint's fix intent. Returns True on YES, False on NO.
    Fails open (returns True) on exception.
    """
    messages = [
        SystemMessage(content=_BLUEPRINT_CHECK_SYSTEM),
        HumanMessage(
            content=_BLUEPRINT_CHECK_USER.format(
                generated_hunk=hunk_text[:1500],
                fix_logic=blueprint.get("fix_logic", ""),
                dependent_apis=", ".join(blueprint.get("dependent_apis", [])),
            )
        ),
    ]
    try:
        response = await llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip().upper().startswith("YES")
    except Exception as e:
        print(f"    Agent 3: Blueprint check LLM call failed ({e}) — failing open.")
        return True


def _format_consistency_map(cm: dict) -> str:
    """
    Pretty-prints a ConsistencyMap for injection into an LLM prompt.
    Returns '(none)' if the map is empty.
    """
    if not cm:
        return "(none — no renames detected)"
    lines = [f"  {old} → {new}" for old, new in cm.items()]
    return "\n".join(lines)


def _rewrite_hunk_symbols(hunk_text: str, consistency_map: dict) -> str:
    """
    Deterministic pre-pass: applies ConsistencyMap renames to the + lines of a hunk.
    This reduces LLM hallucination by giving it pre-renamed text to refine.

    Only replaces whole-word occurrences to avoid partial matches.
    """
    if not consistency_map or not hunk_text:
        return hunk_text

    result_lines = []
    for line in hunk_text.splitlines():
        if line.startswith("+"):
            for old, new in consistency_map.items():
                line = re.sub(rf"\b{re.escape(old)}\b", new, line)
        result_lines.append(line)
    return "\n".join(result_lines) + "\n"


def _adjust_hunk_header(hunk_text: str, target_start_line: int) -> str:
    """
    Rewrites the @@ header of a hunk to anchor it at target_start_line.
    Recalculates the line counts (-count/+count) based on actual hunk content.
    """
    if not hunk_text or target_start_line is None:
        return hunk_text

    lines = hunk_text.splitlines()
    if not lines or not lines[0].startswith("@@"):
        return hunk_text

    # Parse existing header: @@ -a,b +c,d @@  <optional context>
    header = lines[0]
    m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", header)
    if not m:
        return hunk_text

    ctx = m.group(5)  # trailing comment

    # Count actual diff lines from body
    removed_count = 0
    added_count = 0
    context_count = 0

    for line in lines[1:]:
        if line.startswith("-"):
            removed_count += 1
        elif line.startswith("+"):
            added_count += 1
        elif line.startswith(" "):
            context_count += 1
        # Empty lines within the hunk body (just "") are part of the hunk, skip trailing empty

    # Calculate the correct counts
    src_count = context_count + removed_count
    tgt_count = context_count + added_count

    # Handle edge case: if counts are 0, default to 1
    if src_count == 0:
        src_count = 1
    if tgt_count == 0:
        tgt_count = 1

    new_header = (
        f"@@ -{target_start_line},{src_count} +{target_start_line},{tgt_count} @@{ctx}"
    )
    return "\n".join([new_header] + lines[1:]) + "\n"


def _extract_target_start_line(hunk_text: str) -> int | None:
    """
    Extracts the target-side start line from a unified hunk header.
    """
    if not hunk_text:
        return None
    first_line = hunk_text.splitlines()[0] if hunk_text.splitlines() else ""
    m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", first_line)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _extract_added_lines(hunk_text: str) -> list[str]:
    """
    Returns all '+' body lines from a hunk (excluding the @@ header).
    """
    if not hunk_text:
        return []
    lines = hunk_text.splitlines()
    if not lines:
        return []
    return [line for line in lines[1:] if line.startswith("+")]


def _is_import_only_hunk(hunk_text: str) -> bool:
    """
    Detects if a hunk contains ONLY import statements (no other code).
    Used to identify hunks that should be handled conservatively without LLM rewriting.
    """
    if not hunk_text:
        return False
    lines = hunk_text.splitlines()
    if not lines or not lines[0].startswith("@@"):
        return False

    # Check if all non-header, non-whitespace lines are import statements or empty
    for line in lines[1:]:
        stripped = line.lstrip()
        if not stripped:  # empty line
            continue
        if stripped.startswith("//"):  # comment
            continue
        # Check if line is an import statement (in any of +, -, or space formats)
        content = (
            stripped[1:].strip()
            if len(stripped) > 1 and stripped[0] in {"+", "-", " "}
            else stripped
        )
        if content and not content.startswith("import "):
            return False

    return True


def _extract_imports_from_body(target_body: str) -> str:
    """
    Extracts all import statements from a Java file body snippet for reference.
    This provides context to the LLM so it knows what imports already exist.
    """
    if not target_body:
        return "(No imports found in target context)"

    imports = []
    for line in target_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            imports.append(stripped)

    if not imports:
        return "(No imports found in target context)"

    return "Existing imports:\n- " + "\n- ".join(imports)


def _read_target_window(
    target_repo_path: str,
    target_file: str,
    insertion_line: int,
    radius: int = 50,
) -> str:
    """Reads a local context window from target file around insertion_line."""
    if not target_repo_path or not target_file:
        return ""
    try:
        full_path = os.path.normpath(
            os.path.join(target_repo_path, _normalize_rel_path(target_file))
        )
        if not os.path.isfile(full_path):
            return ""
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
        if not lines:
            return ""

        center = max(1, int(insertion_line or 1))
        start = max(1, center - radius)
        end = min(len(lines), center + radius)
        if start > end:
            return ""
        return "\n".join(lines[start - 1 : end])
    except Exception:
        return ""


def _load_target_file_lines(target_repo_path: str, target_file: str) -> list[str]:
    if not target_repo_path or not target_file:
        return []
    try:
        full_path = os.path.normpath(
            os.path.join(target_repo_path, _normalize_rel_path(target_file))
        )
        if not os.path.isfile(full_path):
            return []
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().splitlines()
    except Exception:
        return []


def _find_line_in_target(target_lines: list[str], needle: str) -> int | None:
    if not target_lines or not needle:
        return None
    stripped = needle.strip()
    if not stripped:
        return None

    for idx, line in enumerate(target_lines, start=1):
        if line == needle:
            return idx
    for idx, line in enumerate(target_lines, start=1):
        if line.strip() == stripped:
            return idx
    for idx, line in enumerate(target_lines, start=1):
        if stripped in line:
            return idx
    return None


def _extract_anchor_candidates_from_hunk(raw_hunk: str) -> list[str]:
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


def _locate_insertion_line_in_target(
    target_repo_path: str,
    target_file: str,
    raw_hunk: str,
) -> int | None:
    target_lines = _load_target_file_lines(target_repo_path, target_file)
    if not target_lines:
        return None

    for cand in _extract_anchor_candidates_from_hunk(raw_hunk):
        found = _find_line_in_target(target_lines, cand)
        if found is not None:
            return found

    return None


def _extract_added_imports(raw_hunk: str) -> list[str]:
    imports: list[str] = []
    for i, line in enumerate((raw_hunk or "").splitlines()):
        if i == 0 and line.startswith("@@"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            if content.startswith("import "):
                imports.append(content)
    # Preserve order, remove duplicates.
    return list(dict.fromkeys(imports))


def _build_import_hunk_for_target(
    *,
    target_repo_path: str,
    target_file: str,
    raw_hunk: str,
    insertion_line: int | None,
) -> str | None:
    target_lines = _load_target_file_lines(target_repo_path, target_file)
    if not target_lines:
        return None

    imports_to_add = _extract_added_imports(raw_hunk)
    if not imports_to_add:
        return None

    existing_imports = {
        line.strip() for line in target_lines if line.strip().startswith("import ")
    }
    imports_to_add = [imp for imp in imports_to_add if imp not in existing_imports]
    if not imports_to_add:
        return None

    import_lines = [
        i + 1
        for i, line in enumerate(target_lines)
        if line.strip().startswith("import ")
    ]
    if not import_lines:
        return None

    preferred_anchor_import = None
    raw_lines = (raw_hunk or "").splitlines()
    for i, line in enumerate(raw_lines):
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            if content.startswith("import "):
                for j in range(i - 1, -1, -1):
                    prev = raw_lines[j]
                    if prev.startswith(" "):
                        prev_content = prev[1:].strip()
                        if prev_content.startswith("import "):
                            preferred_anchor_import = prev_content
                            break
                break

    if preferred_anchor_import:
        anchor_line_no = _find_line_in_target(target_lines, preferred_anchor_import)
    else:
        anchor_line_no = None

    if anchor_line_no is None:
        if insertion_line is None:
            anchor_line_no = import_lines[-1]
        else:
            prior_imports = [ln for ln in import_lines if ln <= insertion_line]
            anchor_line_no = prior_imports[-1] if prior_imports else import_lines[0]

    # Build with two-sided context for robust git-apply matching.
    start_line = max(1, anchor_line_no)
    context_before = target_lines[start_line - 1]
    has_after = start_line < len(target_lines)
    context_after = target_lines[start_line] if has_after else ""

    old_count = 2 if has_after else 1
    new_count = old_count + len(imports_to_add)
    header = f"@@ -{start_line},{old_count} +{start_line},{new_count} @@"
    body = [f" {context_before}"] + [f"+{imp}" for imp in imports_to_add]
    if has_after:
        body.append(f" {context_after}")
    return "\n".join([header] + body) + "\n"


def _extract_auxiliary_signals(
    developer_aux_hunks: list[dict[str, Any]],
) -> tuple[dict[str, str], str]:
    """
    Derive conservative rename/file-op hints from developer auxiliary hunks.
    """
    if not developer_aux_hunks:
        return {}, "(none)"

    extra_map: dict[str, str] = {}
    lines: list[str] = []

    for h in developer_aux_hunks:
        op = (h.get("file_operation") or "MODIFIED").upper()
        new_path = _normalize_rel_path(h.get("target_file") or "")
        old_path = _normalize_rel_path(
            h.get("old_target_file") or h.get("mainline_file") or ""
        )
        hunk_text = h.get("hunk_text") or ""

        if op == "RENAMED" and old_path and new_path and old_path != new_path:
            old_stem = os.path.splitext(os.path.basename(old_path))[0]
            new_stem = os.path.splitext(os.path.basename(new_path))[0]
            if old_stem and new_stem and old_stem != new_stem:
                extra_map.setdefault(old_stem, new_stem)
            lines.append(f"- `{op}`: `{old_path}` -> `{new_path}`")
        elif new_path:
            lines.append(f"- `{op}`: `{new_path}`")

        if hunk_text:
            removed_class = None
            added_class = None
            for raw_line in hunk_text.splitlines():
                s = raw_line.strip()
                m_removed = re.match(
                    r"^-\s*public\s+(?:final\s+)?(?:class|interface|enum)\s+(\w+)\b",
                    s,
                )
                if m_removed:
                    removed_class = m_removed.group(1)
                m_added = re.match(
                    r"^\+\s*public\s+(?:final\s+)?(?:class|interface|enum)\s+(\w+)\b",
                    s,
                )
                if m_added:
                    added_class = m_added.group(1)
            if removed_class and added_class and removed_class != added_class:
                extra_map.setdefault(removed_class, added_class)

    return extra_map, ("\n".join(lines[:10]) if lines else "(none)")


def _stabilize_hunk_structure(base_hunk: str, candidate_hunk: str) -> str:
    """
    Keeps the original hunk structure and replaces only '+' lines with candidate '+'.

    This prevents malformed hunks when LLM output drops diff prefixes on context lines.
    If candidate '+' count does not match base '+', falls back to base_hunk.
    """
    if not base_hunk:
        return candidate_hunk or base_hunk

    base_lines = base_hunk.splitlines()
    if not base_lines or not base_lines[0].startswith("@@"):
        return candidate_hunk or base_hunk

    candidate_plus = _extract_added_lines(candidate_hunk or "")
    base_plus_count = sum(1 for line in base_lines[1:] if line.startswith("+"))

    if base_plus_count == 0:
        return base_hunk if base_hunk.endswith("\n") else base_hunk + "\n"

    if len(candidate_plus) != base_plus_count:
        return base_hunk if base_hunk.endswith("\n") else base_hunk + "\n"

    out = [base_lines[0]]
    plus_idx = 0
    for line in base_lines[1:]:
        if line.startswith("+"):
            out.append(candidate_plus[plus_idx])
            plus_idx += 1
        else:
            out.append(line)

    stabilized = "\n".join(out)
    if not stabilized.endswith("\n"):
        stabilized += "\n"
    return stabilized


def _normalize_rel_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/").lstrip("/")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p


def _is_test_file(file_path: str) -> bool:
    """
    Simple heuristic to determine if a file is a test file.
    """
    lower_path = (file_path or "").lower()
    return "test" in lower_path or lower_path.endswith("test.java")


def _exists_file(repo_path: str, rel_path: str) -> bool:
    if not repo_path or not rel_path:
        return False
    full_path = os.path.normpath(os.path.join(repo_path, _normalize_rel_path(rel_path)))
    return os.path.isfile(full_path)


def _exists_dir(repo_path: str, rel_path: str) -> bool:
    if not repo_path:
        return False
    rel = _normalize_rel_path(rel_path)
    full_path = os.path.normpath(os.path.join(repo_path, rel)) if rel else repo_path
    return os.path.isdir(full_path)


def _first_candidate_path(candidates: list[dict[str, Any]] | None) -> str | None:
    for cand in candidates or []:
        if not isinstance(cand, dict):
            continue
        p = cand.get("file") or cand.get("file_path") or cand.get("path")
        if p:
            return _normalize_rel_path(str(p))
    return None


def _find_candidate_target_path(
    retriever: EnsembleRetriever | None,
    file_path: str,
    original_commit: str,
) -> str | None:
    if not retriever:
        return None
    p = _normalize_rel_path(file_path)
    if not p:
        return None
    try:
        candidates = retriever.find_candidates(p, original_commit or "HEAD")
        return _first_candidate_path(candidates)
    except Exception:
        return None


def _infer_target_directory_from_siblings(
    mainline_file: str,
    mainline_repo_path: str,
    retriever: EnsembleRetriever | None,
    original_commit: str,
) -> str | None:
    if not retriever or not mainline_repo_path:
        return None

    file_path = _normalize_rel_path(mainline_file)
    parent = os.path.dirname(file_path)
    if not parent:
        return None

    parent_abs = os.path.join(mainline_repo_path, parent)
    if not os.path.isdir(parent_abs):
        return None

    sibling_dirs: list[str] = []
    try:
        for name in os.listdir(parent_abs):
            if not name.endswith(".java"):
                continue
            sibling_rel = _normalize_rel_path(os.path.join(parent, name))
            if sibling_rel == file_path:
                continue
            mapped = _find_candidate_target_path(
                retriever, sibling_rel, original_commit
            )
            if mapped:
                sibling_dirs.append(os.path.dirname(mapped))
            if len(sibling_dirs) >= 3:
                break
    except Exception:
        return None

    if not sibling_dirs:
        return None

    return max(set(sibling_dirs), key=sibling_dirs.count)


def _resolve_operation_plan(
    *,
    change_type: str,
    mainline_file: str,
    previous_mainline_file: str | None,
    target_repo_path: str,
    mainline_repo_path: str,
    retriever: EnsembleRetriever | None,
    original_commit: str,
) -> dict[str, Any]:
    op = (change_type or "MODIFIED").upper()
    mainline_file = _normalize_rel_path(mainline_file)
    previous_mainline_file = _normalize_rel_path(previous_mainline_file or "") or None

    def resolve_existing(path_hint: str) -> str | None:
        p = _normalize_rel_path(path_hint)
        if p and _exists_file(target_repo_path, p):
            return p
        return _find_candidate_target_path(retriever, p, original_commit)

    plan: dict[str, Any] = {
        "target_file": mainline_file,
        "old_target_file": None,
        "effective_operation": op,
        "operation_required": True,
        "reason": "default",
    }

    if op == "ADDED":
        target_file = mainline_file
        parent_dir = os.path.dirname(target_file)
        if parent_dir and not _exists_dir(target_repo_path, parent_dir):
            inferred_dir = _infer_target_directory_from_siblings(
                mainline_file=mainline_file,
                mainline_repo_path=mainline_repo_path,
                retriever=retriever,
                original_commit=original_commit,
            )
            if inferred_dir:
                target_file = _normalize_rel_path(
                    os.path.join(inferred_dir, os.path.basename(mainline_file))
                )
                plan["reason"] = "added_file_sibling_directory_inference"

        existing_match = resolve_existing(target_file)
        if existing_match:
            plan.update(
                {
                    "target_file": existing_match,
                    "effective_operation": "MODIFIED",
                    "operation_required": True,
                    "reason": "added_file_already_exists_in_target",
                }
            )
            return plan

        plan.update(
            {
                "target_file": target_file,
                "effective_operation": "ADDED",
                "operation_required": True,
            }
        )
        return plan

    if op == "DELETED":
        delete_target = resolve_existing(mainline_file)
        if not delete_target:
            return {
                "target_file": mainline_file,
                "old_target_file": None,
                "effective_operation": "DELETED",
                "operation_required": False,
                "reason": "delete_target_not_found",
            }

        return {
            "target_file": delete_target,
            "old_target_file": None,
            "effective_operation": "DELETED",
            "operation_required": _exists_file(target_repo_path, delete_target),
            "reason": "delete_target_mapped",
        }

    if op == "RENAMED":
        old_hint = previous_mainline_file or mainline_file
        old_target = resolve_existing(old_hint)
        new_target = mainline_file
        new_parent = os.path.dirname(new_target)
        if new_parent and not _exists_dir(target_repo_path, new_parent):
            inferred_dir = _infer_target_directory_from_siblings(
                mainline_file=mainline_file,
                mainline_repo_path=mainline_repo_path,
                retriever=retriever,
                original_commit=original_commit,
            )
            if inferred_dir:
                new_target = _normalize_rel_path(
                    os.path.join(inferred_dir, os.path.basename(new_target))
                )

        existing_new = resolve_existing(new_target)
        if existing_new:
            new_target = existing_new

        old_exists = bool(old_target and _exists_file(target_repo_path, old_target))
        new_exists = bool(new_target and _exists_file(target_repo_path, new_target))

        if old_exists and not new_exists:
            return {
                "target_file": new_target,
                "old_target_file": old_target,
                "effective_operation": "RENAMED",
                "operation_required": True,
                "reason": "rename_required_old_exists_new_missing",
            }
        if not old_exists and new_exists:
            return {
                "target_file": new_target,
                "old_target_file": old_target,
                "effective_operation": "MODIFIED",
                "operation_required": True,
                "reason": "rename_already_applied_in_target",
            }
        if old_exists and new_exists:
            return {
                "target_file": new_target,
                "old_target_file": old_target,
                "effective_operation": "MODIFIED",
                "operation_required": True,
                "reason": "both_old_and_new_exist_skip_explicit_rename",
            }
        return {
            "target_file": new_target,
            "old_target_file": old_target,
            "effective_operation": "RENAMED",
            "operation_required": False,
            "reason": "rename_no_viable_target",
        }

    # MODIFIED and fallback
    mapped_target = resolve_existing(mainline_file)
    if mapped_target:
        plan["target_file"] = mapped_target
        plan["reason"] = "modified_target_mapped"
    return plan


# ---------------------------------------------------------------------------
# Core Agent Node
# ---------------------------------------------------------------------------


async def hunk_generator_node(state: AgentState, config) -> dict:
    """
    Agent 3 node function.

    Iterates over every modified hunk in the patch, rewrites it for the target
    via LLM, validates format (dry-run) and intent (blueprint check), and
    stores the results as AdaptedHunk lists.

    IMPORTANT: The insertion_line field in each AdaptedHunk is critical for proper
    application order. When multiple hunks target the same file, they are assembled
    in top-to-bottom order and applied as one per-file patch section so standard patch
    engines can resolve offsets as earlier hunks are applied.
    """
    print("Agent 3 (Hunk Generator): Starting surgical hunk rewrite...")

    consistency_map: dict = state.get("consistency_map") or {}
    mapped_target_context: dict = state.get("mapped_target_context") or {}
    semantic_blueprint: SemanticBlueprint = state.get("semantic_blueprint")
    patch_analysis: list = state.get("patch_analysis") or []
    patch_diff: str = state.get("patch_diff") or ""
    target_repo_path: str = state.get("target_repo_path", "")
    mainline_repo_path: str = state.get("mainline_repo_path", "")
    original_commit: str = state.get("original_commit", "HEAD")
    validation_attempts: int = state.get("validation_attempts") or 0
    error_context: str = state.get("validation_error_context") or ""
    retry_files_raw = state.get("validation_retry_files") or []
    with_test_changes: bool = state.get("with_test_changes", False)
    developer_aux_hunks: list[dict[str, Any]] = (
        state.get("developer_auxiliary_hunks") or []
    )
    retry_files = {_normalize_rel_path(p) for p in retry_files_raw if p}
    aux_consistency_map, aux_context = _extract_auxiliary_signals(developer_aux_hunks)
    if aux_consistency_map:
        merged_cm = dict(consistency_map)
        for old, new in aux_consistency_map.items():
            merged_cm.setdefault(old, new)
        consistency_map = merged_cm

    if not semantic_blueprint:
        msg = "Agent 3 Error: No semantic_blueprint in state. Agents 1 & 2 must run first."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    if not patch_diff:
        msg = "Agent 3 Error: No patch_diff in state."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # Retry feedback injection
    retry_context_str = ""
    if validation_attempts > 0 and error_context:
        retry_files_note = (
            f"Impacted files from previous validation: {sorted(retry_files)}\n"
            if retry_files
            else ""
        )
        retry_context_str = (
            f"## RETRY #{validation_attempts} — Previous Validation Failed\n"
            f"```\n{error_context[:600]}\n```\n"
            f"{retry_files_note}"
            f"Adjust the hunk to fix the above error.\n"
        )
        print(
            f"  Agent 3: Retry #{validation_attempts} — injecting validation error into prompts."
        )

    # ------------------------------------------------------------------
    # Setup tools
    # ------------------------------------------------------------------
    # Setup LLM
    llm = get_llm(temperature=0)

    analyzer = PatchAnalyzer()
    raw_hunks_by_file = (
        analyzer.extract_raw_hunks(patch_diff, with_test_changes=with_test_changes)
        if patch_diff
        else {}
    )
    file_only_ops = (
        analyzer.extract_file_only_operations(
            patch_diff, with_test_changes=with_test_changes
        )
        if patch_diff
        else []
    )
    toolkit = ValidationToolkit(target_repo_path) if target_repo_path else None
    hg_toolkit = HunkGeneratorToolkit(target_repo_path) if target_repo_path else None
    hg_react_agent = (
        create_react_agent(
            llm, tools=hg_toolkit.get_tools(), prompt=_HUNK_REWRITE_SYSTEM_TOOLS
        )
        if hg_toolkit
        else None
    )
    retriever = None
    if target_repo_path and mainline_repo_path:
        try:
            retriever = EnsembleRetriever(mainline_repo_path, target_repo_path)
        except Exception as e:
            print(
                f"  Agent 3: Warning — retriever unavailable for file-op mapping: {e}"
            )

    fix_logic = semantic_blueprint.get("fix_logic", "")
    dependent_apis = semantic_blueprint.get("dependent_apis", [])
    root_cause = semantic_blueprint.get("root_cause_hypothesis", "")
    cm_formatted = _format_consistency_map(consistency_map)

    # ------------------------------------------------------------------
    # Segregate changes
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
        f"  Agent 3: {len(code_changes)} code file(s), {len(test_changes)} test file(s) to process."
    )

    # --- Early Exit: If Agent 2 produced no mappings and we're on a retry, abort ---
    # If there are code files but no mapped context, and this is a retry, don't loop endlessly.
    if code_changes and not mapped_target_context and validation_attempts > 0:
        print(
            f"  Agent 3: Aborting retry — Agent 2 has no target context and retrying won't help."
        )
        return {
            "messages": [
                HumanMessage(
                    content="Agent 3: No target context from Agent 2. Cannot proceed."
                )
            ],
            "adapted_code_hunks": [],
            "adapted_test_hunks": [],
            "validation_passed": False,  # Signal validation failure to exit loop
            "validation_attempts": validation_attempts,
            "validation_error_context": "Agent 3 Early Exit: Agent 2 failed to map files. No source context available for hunk generation.",
        }

    adapted_code_hunks: list[AdaptedHunk] = []
    adapted_test_hunks: list[AdaptedHunk] = []
    trace = "# Hunk Generator Trace\n\n"
    trace += f"| target_file | hunk_index | dry_run | intent_ok |\n|---|---|---|---|\n"

    # ------------------------------------------------------------------
    # Code hunk processing
    # ------------------------------------------------------------------
    for change in code_changes:
        mainline_file = (
            change.file_path
            if hasattr(change, "file_path")
            else change.get("file_path", "?")
        )
        change_type = (
            change.change_type
            if hasattr(change, "change_type")
            else change.get("change_type", "MODIFIED")
        )
        previous_mainline_file = (
            change.previous_file_path
            if hasattr(change, "previous_file_path")
            else change.get("previous_file_path")
        )
        op_plan = _resolve_operation_plan(
            change_type=change_type,
            mainline_file=mainline_file,
            previous_mainline_file=previous_mainline_file,
            target_repo_path=target_repo_path,
            mainline_repo_path=mainline_repo_path,
            retriever=retriever,
            original_commit=original_commit,
        )

        if not op_plan.get("operation_required", True) and not raw_hunks_by_file.get(
            mainline_file, []
        ):
            print(
                f"  Agent 3: Skipping {change_type} for {mainline_file} "
                f"(reason={op_plan.get('reason')})"
            )
            continue
        # Get list of mappings for this file (now returns list instead of single dict)
        mapped_ctx_list = mapped_target_context.get(mainline_file, [])
        raw_hunks = raw_hunks_by_file.get(mainline_file, [])

        if retry_files:
            candidate_paths = {
                _normalize_rel_path(mainline_file),
                _normalize_rel_path(op_plan.get("target_file") or ""),
            }
            if mapped_ctx_list:
                candidate_paths.add(
                    _normalize_rel_path(
                        (mapped_ctx_list[0] or {}).get("target_file", "")
                    )
                )
            if not any(p for p in candidate_paths if p in retry_files):
                continue

        if not mapped_ctx_list:
            print(
                f"  Agent 3: Skipping {mainline_file} — no target context from Agent 2."
            )
            continue

        print(
            f"  Agent 3: Processing {len(raw_hunks)} hunk(s) for {mainline_file} with {len(mapped_ctx_list)} mapping(s)"
        )

        for hunk_idx, raw_hunk in enumerate(raw_hunks):
            # Get the mapping for this hunk (or reuse first one if not enough mappings)
            mapped_ctx = mapped_ctx_list[min(hunk_idx, len(mapped_ctx_list) - 1)]

            target_file = _normalize_rel_path(
                mapped_ctx.get("target_file", mainline_file)
            )
            planned_target_file = op_plan.get("target_file")
            if planned_target_file:
                target_file = planned_target_file
            insertion_line = mapped_ctx.get("start_line")
            target_body = mapped_ctx.get("code_snippet", "")

            # Never trust mainline hunk headers for target insertion lines.
            # If Phase 2 did not provide a valid target line, recover using target-file anchors.
            if not isinstance(insertion_line, int) or insertion_line <= 0:
                insertion_line = _locate_insertion_line_in_target(
                    target_repo_path=target_repo_path,
                    target_file=target_file,
                    raw_hunk=raw_hunk,
                )

            if not isinstance(insertion_line, int) or insertion_line <= 0:
                print(
                    f"    Agent 3: Skipping {target_file}[{hunk_idx}] — unable to locate target insertion line"
                )
                trace += f"| `{target_file}` | {hunk_idx} | ❌ | ❌ |\n"
                continue

            # If Agent 2 returned only a short snippet, enrich prompt context from target file.
            if len(str(target_body or "").splitlines()) < 8:
                enriched_body = _read_target_window(
                    target_repo_path=target_repo_path,
                    target_file=target_file,
                    insertion_line=insertion_line,
                    radius=70,
                )
                if enriched_body:
                    target_body = enriched_body

            # Deterministic symbol substitution pre-pass
            pre_rewritten = _rewrite_hunk_symbols(raw_hunk, consistency_map)

            # For import-only hunks, skip LLM rewriting to avoid corruption
            # Import statements are fragile and LLM tends to duplicate existing imports
            if _is_import_only_hunk(raw_hunk):
                adapted_hunk_text = _build_import_hunk_for_target(
                    target_repo_path=target_repo_path,
                    target_file=target_file,
                    raw_hunk=raw_hunk,
                    insertion_line=insertion_line,
                )
                if adapted_hunk_text:
                    print(
                        f"    Agent 3: Built import-aware hunk for {target_file}[{hunk_idx}]"
                    )
                else:
                    print(
                        f"    Agent 3: Skipping import-only hunk {target_file}[{hunk_idx}] — no new imports or no import anchor"
                    )
                    trace += f"| `{target_file}` | {hunk_idx} | ❌ | ❌ |\n"
                    continue
            else:
                # ReAct tool loop (intelligent hunk generation) or simple LLM rewrite fallback
                adapted_hunk_text = None

                if hg_react_agent:
                    # ----------------------------------------------------------
                    # PRIMARY PATH: ReAct agent with file-reading tools.
                    # The agent will call read_file_window / grep_in_file /
                    # verify_context_at_line before producing the final hunk,
                    # ensuring context lines match the actual target file.
                    # ----------------------------------------------------------
                    # Reset the toolkit's todo list for this hunk so todos from
                    # a previous hunk don't carry over.
                    if hg_toolkit:
                        hg_toolkit._todos = []
                        hg_toolkit._todo_counter = 0

                    react_prompt = _HUNK_REWRITE_USER.format(
                        mainline_hunk=pre_rewritten,
                        target_method_body=target_body,
                        target_imports_context=_extract_imports_from_body(target_body),
                        consistency_map=cm_formatted,
                        fix_logic=fix_logic,
                        dependent_apis=", ".join(dependent_apis),
                        insertion_line=insertion_line,
                        target_file=target_file,
                        developer_aux_context=aux_context,
                        retry_context=retry_context_str,
                    )

                    for attempt in range(2):
                        try:
                            react_result = await hg_react_agent.ainvoke(
                                {"messages": [("user", react_prompt)]},
                                config={"recursion_limit": 30},
                            )
                            raw_content = react_result["messages"][-1].content
                            # Strip leading WARNING comment if present (allowed by system prompt)
                            raw_content_clean = re.sub(
                                r"^#\s*WARNING:.*\n",
                                "",
                                raw_content,
                                flags=re.MULTILINE,
                            ).strip()
                            extracted = _extract_hunk_block(
                                raw_content_clean
                            ) or _extract_hunk_block(raw_content)
                            if extracted:
                                direct_candidate = (
                                    extracted
                                    if extracted.endswith("\n")
                                    else extracted + "\n"
                                )
                                adjusted_candidate = _adjust_hunk_header(
                                    direct_candidate, insertion_line
                                )
                                stabilized = _stabilize_hunk_structure(
                                    pre_rewritten, extracted
                                )
                                stabilized_candidate = _adjust_hunk_header(
                                    stabilized, insertion_line
                                )

                                if toolkit:
                                    dr_direct = toolkit.apply_hunk_dry_run(
                                        target_file, direct_candidate
                                    )
                                    if dr_direct.get("success"):
                                        adapted_hunk_text = direct_candidate
                                        print(
                                            f"    Agent 3: ReAct hunk passed dry-run (direct) for {target_file}[{hunk_idx}]"
                                        )
                                        break

                                    dr_adjusted = toolkit.apply_hunk_dry_run(
                                        target_file, adjusted_candidate
                                    )
                                    if dr_adjusted.get("success"):
                                        adapted_hunk_text = adjusted_candidate
                                        print(
                                            f"    Agent 3: ReAct hunk passed dry-run (adjusted) for {target_file}[{hunk_idx}]"
                                        )
                                        break

                                    dr_stable = toolkit.apply_hunk_dry_run(
                                        target_file, stabilized_candidate
                                    )
                                    if dr_stable.get("success"):
                                        adapted_hunk_text = stabilized_candidate
                                        print(
                                            f"    Agent 3: ReAct hunk passed dry-run (stabilized) for {target_file}[{hunk_idx}]"
                                        )
                                        break

                                    print(
                                        f"    Agent 3: ReAct candidates failed dry-run for {target_file}[{hunk_idx}] "
                                        f"(attempt {attempt + 1}/2)"
                                    )
                                else:
                                    adapted_hunk_text = direct_candidate
                                    break
                            else:
                                print(
                                    f"    Agent 3: ReAct hunk parse failed (attempt {attempt + 1}/2)"
                                )
                        except GraphRecursionError as e:
                            print(
                                f"    Agent 3: ReAct recursion limit on {target_file}[{hunk_idx}] "
                                f"(attempt {attempt + 1}/2): {e}"
                            )
                        except Exception as e:
                            print(
                                f"    Agent 3: ReAct error on {target_file}[{hunk_idx}] "
                                f"(attempt {attempt + 1}/2): {e}"
                            )

                else:
                    # ----------------------------------------------------------
                    # FALLBACK PATH: simple single LLM call (no tools).
                    # Used when target_repo_path is unavailable (local dev mode).
                    # ----------------------------------------------------------
                    for attempt in range(2):
                        prompt = _HUNK_REWRITE_USER.format(
                            mainline_hunk=pre_rewritten,
                            target_method_body=target_body,
                            target_imports_context=_extract_imports_from_body(
                                target_body
                            ),
                            consistency_map=cm_formatted,
                            fix_logic=fix_logic,
                            dependent_apis=", ".join(dependent_apis),
                            insertion_line=insertion_line,
                            target_file=target_file,
                            developer_aux_context=aux_context,
                            retry_context=retry_context_str,
                        )
                        try:
                            response = await llm.ainvoke(
                                [
                                    SystemMessage(content=_HUNK_REWRITE_SYSTEM),
                                    HumanMessage(content=prompt),
                                ]
                            )
                            raw_content = (
                                response.content
                                if hasattr(response, "content")
                                else str(response)
                            )
                            extracted = _extract_hunk_block(raw_content)
                            if extracted:
                                direct_candidate = (
                                    extracted
                                    if extracted.endswith("\n")
                                    else extracted + "\n"
                                )
                                adjusted_candidate = _adjust_hunk_header(
                                    direct_candidate, insertion_line
                                )
                                stabilized = _stabilize_hunk_structure(
                                    pre_rewritten, extracted
                                )
                                stabilized_candidate = _adjust_hunk_header(
                                    stabilized, insertion_line
                                )

                                if toolkit:
                                    dr_direct = toolkit.apply_hunk_dry_run(
                                        target_file, direct_candidate
                                    )
                                    if dr_direct.get("success"):
                                        adapted_hunk_text = direct_candidate
                                        break

                                    dr_adjusted = toolkit.apply_hunk_dry_run(
                                        target_file, adjusted_candidate
                                    )
                                    if dr_adjusted.get("success"):
                                        adapted_hunk_text = adjusted_candidate
                                        break

                                    dr_stable = toolkit.apply_hunk_dry_run(
                                        target_file, stabilized_candidate
                                    )
                                    if dr_stable.get("success"):
                                        adapted_hunk_text = stabilized_candidate
                                        break

                                    print(
                                        f"    Agent 3: Both direct/stabilized candidates failed dry-run on hunk {hunk_idx} (attempt {attempt + 1}/2)"
                                    )
                                else:
                                    adapted_hunk_text = direct_candidate
                                    break
                            print(
                                f"    Agent 3: Hunk parse failed (attempt {attempt + 1}/2)"
                            )
                        except Exception as e:
                            print(
                                f"    Agent 3: LLM error on hunk {hunk_idx} (attempt {attempt + 1}/2): {e}"
                            )

                if not adapted_hunk_text:
                    # Last fallback: deterministic symbol-rewrite header adjustment.
                    adapted_hunk_text = _adjust_hunk_header(
                        pre_rewritten, insertion_line
                    )
                    print(
                        f"    Agent 3: Fallback candidate generated for {target_file}[{hunk_idx}]"
                    )

            # Dry-run validation (CLAW-inspired: collect errors, don't drop hunks)
            dry_run_ok = False
            dry_run_error_info = None
            if toolkit:
                dr = toolkit.apply_hunk_dry_run(target_file, adapted_hunk_text)
                dry_run_ok = dr["success"]
                if not dry_run_ok:
                    print(
                        f"    Agent 3: Dry-run failed for {target_file}[{hunk_idx}]: {dr['output'][:150]}"
                    )
                    trace += f"| `{target_file}` | {hunk_idx} | ❌ | ❌ |\n"
                    # Store error info for Phase 4/retry (CLAW pattern: don't drop, enrich)
                    dry_run_error_info = {
                        "error_message": dr.get("output", "Unknown dry-run error"),
                        "tool": "git-apply-check",
                        "timestamp": str(__import__("datetime").datetime.now()),
                    }
            else:
                dry_run_ok = True  # No toolkit → assume ok (local dev mode)

            # Blueprint intent check
            intent_ok = await _check_intent(llm, adapted_hunk_text, semantic_blueprint)
            if not intent_ok:
                print(
                    f"    Agent 3: Blueprint check failed for {target_file}[{hunk_idx}] — flagging."
                )

            hunk: AdaptedHunk = {
                "target_file": target_file,
                "mainline_file": mainline_file,
                "hunk_text": adapted_hunk_text,
                "insertion_line": insertion_line,
                "intent_verified": intent_ok,
                "file_operation": op_plan.get("effective_operation", change_type),
                "old_target_file": op_plan.get("old_target_file"),
                "file_operation_required": op_plan.get("operation_required", True),
                "path_resolution_reason": op_plan.get("reason", "unknown"),
            }
            # Attach error info if dry-run failed (Phase 4 will see this)
            if dry_run_error_info:
                hunk["dry_run_error"] = dry_run_error_info
                hunk["dry_run_error_message"] = dry_run_error_info["error_message"]

            adapted_code_hunks.append(hunk)
            trace += (
                f"| `{target_file}` | {hunk_idx} | "
                f"{'✅' if dry_run_ok else '❌'} | {'✅' if intent_ok else '❌'} |\n"
            )

    # ------------------------------------------------------------------
    # Test hunk processing
    # ------------------------------------------------------------------
    for change in test_changes:
        mainline_test = (
            change.file_path
            if hasattr(change, "file_path")
            else change.get("file_path", "?")
        )
        previous_mainline_file = (
            change.previous_file_path
            if hasattr(change, "previous_file_path")
            else change.get("previous_file_path")
        )
        change_type = (
            change.change_type
            if hasattr(change, "change_type")
            else change.get("change_type", "MODIFIED")
        )
        op_plan = _resolve_operation_plan(
            change_type=change_type,
            mainline_file=mainline_test,
            previous_mainline_file=previous_mainline_file,
            target_repo_path=target_repo_path,
            mainline_repo_path=mainline_repo_path,
            retriever=retriever,
            original_commit=original_commit,
        )
        # Get list of mappings for this test file
        mapped_ctx_list = mapped_target_context.get(mainline_test, [])
        raw_hunks = raw_hunks_by_file.get(mainline_test, [])

        if not mapped_ctx_list:
            print(
                f"  Agent 3: Skipping test {mainline_test} — no target test file (Agent 4 will synthesize)."
            )
            continue

        # For test files, typically only one mapping
        mapped_ctx = mapped_ctx_list[0]
        target_test_file = _normalize_rel_path(mapped_ctx.get("target_file") or "")
        planned_target_test_file = _normalize_rel_path(op_plan.get("target_file") or "")
        if planned_target_test_file:
            target_test_file = planned_target_test_file

        if not target_test_file:
            print(
                f"  Agent 3: Skipping test {mainline_test} — target test file is null (Agent 4 will synthesize)."
            )
            continue

        print(
            f"  Agent 3: Rewriting {len(raw_hunks)} test hunk(s) for {mainline_test} → {target_test_file}"
        )

        for hunk_idx, raw_hunk in enumerate(raw_hunks):
            pre_rewritten = _rewrite_hunk_symbols(raw_hunk, consistency_map)

            adapted_hunk_text = None
            for attempt in range(2):
                prompt = _TEST_HUNK_REWRITE_USER.format(
                    mainline_hunk=pre_rewritten,
                    target_test_file=target_test_file,
                    consistency_map=cm_formatted,
                    root_cause=root_cause,
                    developer_aux_context=aux_context,
                    retry_context=retry_context_str,
                )
                try:
                    response = await llm.ainvoke(
                        [
                            SystemMessage(content=_HUNK_REWRITE_SYSTEM),
                            HumanMessage(content=prompt),
                        ]
                    )
                    raw_content = (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    )
                    extracted = _extract_hunk_block(raw_content)
                    if extracted:
                        adapted_hunk_text = extracted
                        break
                    print(
                        f"    Agent 3: Test hunk parse failed (attempt {attempt + 1}/2)"
                    )
                except Exception as e:
                    print(
                        f"    Agent 3: LLM error on test hunk {hunk_idx} (attempt {attempt + 1}/2): {e}"
                    )

            if not adapted_hunk_text:
                adapted_hunk_text = pre_rewritten

            # Test hunk dry-run validation (CLAW-inspired: collect errors, don't drop)
            dry_run_ok = False
            dry_run_error_info = None
            if toolkit:
                dr = toolkit.apply_hunk_dry_run(target_test_file, adapted_hunk_text)
                dry_run_ok = dr["success"]
                if not dry_run_ok:
                    dry_run_error_info = {
                        "error_message": dr.get("output", "Unknown dry-run error"),
                        "tool": "git-apply-check",
                        "timestamp": str(__import__("datetime").datetime.now()),
                    }
            else:
                dry_run_ok = True

            hunk: AdaptedHunk = {
                "target_file": target_test_file,
                "mainline_file": mainline_test,
                "hunk_text": adapted_hunk_text,
                "insertion_line": 1,
                "intent_verified": True,  # Tests don't undergo blueprint check
                "file_operation": op_plan.get("effective_operation", change_type),
                "old_target_file": op_plan.get("old_target_file"),
                "file_operation_required": op_plan.get("operation_required", True),
                "path_resolution_reason": op_plan.get("reason", "unknown"),
            }
            # Attach error info if dry-run failed
            if dry_run_error_info:
                hunk["dry_run_error"] = dry_run_error_info
                hunk["dry_run_error_message"] = dry_run_error_info["error_message"]

            adapted_test_hunks.append(hunk)
            trace += (
                f"| `{target_test_file}` (test) | {hunk_idx} | "
                f"{'✅' if dry_run_ok else '❌'} | — |\n"
            )

    # ------------------------------------------------------------------
    # File-only operations processing (rename, pure delete, etc.)
    # ------------------------------------------------------------------
    for op in file_only_ops:
        file_path = op.get("file_path", "?")
        change_type = op.get("change_type", "MODIFIED")
        is_test = op.get("is_test_file", False)
        new_path = op.get("new_path", file_path)
        previous_mainline_file = file_path if change_type == "RENAMED" else None

        op_plan = _resolve_operation_plan(
            change_type=change_type,
            mainline_file=new_path if change_type == "RENAMED" else file_path,
            previous_mainline_file=previous_mainline_file,
            target_repo_path=target_repo_path,
            mainline_repo_path=mainline_repo_path,
            retriever=retriever,
            original_commit=original_commit,
        )

        if not op_plan.get("operation_required", True):
            print(
                f"  Agent 3: Skipping structural {change_type} for {file_path} "
                f"(reason={op_plan.get('reason')})"
            )
            continue

        # Skip test file operations if not requested
        if is_test and not with_test_changes:
            continue

        # Create a minimal AdaptedHunk for structural operations
        # These have no hunk_text since they're metadata-only
        hunk: AdaptedHunk = {
            "target_file": op_plan.get("target_file")
            or (new_path if change_type == "RENAMED" else file_path),
            "mainline_file": file_path,
            "hunk_text": "",  # No hunks for structural operations
            "insertion_line": 0,
            "intent_verified": True,  # No intent check needed for renames
            "file_operation": op_plan.get("effective_operation", change_type),
            "old_target_file": op_plan.get("old_target_file"),
            "file_operation_required": op_plan.get("operation_required", True),
            "path_resolution_reason": op_plan.get("reason", "unknown"),
        }

        if is_test:
            adapted_test_hunks.append(hunk)
        else:
            adapted_code_hunks.append(hunk)

        trace += f"| `{hunk['target_file']}` ({hunk['file_operation']}) | — | — | — |\n"
        print(
            f"  Agent 3: Added {hunk['file_operation']} operation for {file_path} "
            f"(target={hunk['target_file']}, reason={hunk.get('path_resolution_reason')})"
        )

    # ------------------------------------------------------------------
    # Write trace and finalize
    # ------------------------------------------------------------------
    print(
        f"Agent 3: Complete. {len(adapted_code_hunks)} code hunk(s), "
        f"{len(adapted_test_hunks)} test hunk(s) generated."
    )
    try:
        with open("hunk_generator_trace.md", "w", encoding="utf-8") as f:
            f.write(trace)
        print("  Agent 3: Trace written to hunk_generator_trace.md")
    except Exception as e:
        print(f"  Agent 3: Warning — could not write trace: {e}")

    return {
        "messages": [
            HumanMessage(
                content=(
                    f"Agent 3 complete. {len(adapted_code_hunks)} code hunk(s) and "
                    f"{len(adapted_test_hunks)} test hunk(s) adapted."
                )
            )
        ],
        "adapted_code_hunks": adapted_code_hunks,
        "adapted_test_hunks": adapted_test_hunks,
    }


def extract_hunk_context(hunk_text: str) -> tuple[str, str]:
    """
    Extract the old_string and new_string from a unified diff hunk.

    This parses a standard unified diff hunk and reconstructs the exact
    strings that need to match for the patch to apply. Used for CLAW-style
    exact string matching approach.

    Args:
        hunk_text: Unified diff hunk starting with @@

    Returns:
        Tuple of (old_string, new_string) - exact text to match and replace
    """
    lines = hunk_text.strip().split("\n")

    if not lines or not lines[0].startswith("@@"):
        return "", ""

    old_lines_list = []
    new_lines_list = []

    for line in lines[1:]:
        if line.startswith("-") and not line.startswith("---"):
            # Removed line
            old_lines_list.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            # Added line
            new_lines_list.append(line[1:])
        elif line.startswith(" "):
            # Context line (appears in both old and new)
            old_lines_list.append(line[1:])
            new_lines_list.append(line[1:])
        elif line.startswith("\\"):
            # "\ No newline at end of file" marker - skip
            continue

    old_string = "\n".join(old_lines_list)
    new_string = "\n".join(new_lines_list)

    return old_string, new_string
