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

import os
import re
import json
from langchain_core.messages import HumanMessage
from state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from state import AgentState
from utils.retrieval.ensemble_retriever import EnsembleRetriever
from agents.reasoning_tools import ReasoningToolkit

_AGENT_SYSTEM = """You are an expert software engineer mapping code from a new mainline patch to an older target repository.
You need to find the exact target file and target method corresponding to a modified mainline file and methods, determining the start and end lines.
You also need to identify if any methods were renamed.

You have tools:
- `search_candidates(file_path)`: Find a moved/renamed file in the target repo.
- `match_structure(mainline_file_path, candidate_paths)`: Compare structural similarity.
- `get_class_context(file_path, method_name)`: Get method boundaries and code in the target repo.
- `get_dependency_graph(file_paths)`: Find relations.
- `read_file(file_path)`: Read a file from target repo if you need to manually inspect string matches.
- `git_log_follow(file_path)`: Check git history for renames.

Investigate to find where the mainline changes should be applied in the target repo.
When you find it, output precisely this JSON:
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
If a method cannot be found, set its target_file and target_method to null.
Do not include markdown or explanations outside the JSON."""


# ---------------------------------------------------------------------------
# Line-range parser for get_class_context output
# ---------------------------------------------------------------------------

def _extract_line_range(context_output) -> tuple[int | None, int | None, str]:
    """
    Parses the output of get_class_context() (an MCP tool response) to extract
    the method start/end line numbers and raw code snippet.

    The MCP tool typically returns a dict like:
        {"context": "...", "start_line": 42, "end_line": 88}
    or embeds the line numbers in the context string as comments.

    Returns:
        (start_line, end_line, code_snippet)
    """
    if isinstance(context_output, dict):
        start = context_output.get("start_line") or context_output.get("startLine")
        end = context_output.get("end_line") or context_output.get("endLine")
        snippet = context_output.get("context", context_output.get("body", ""))
        if start and end:
            return int(start), int(end), str(snippet)

        # Try parsing from the context string itself (e.g. "/* L42 */ void foo() {")
        snippet_str = str(snippet)
        m = re.search(r"/\*\s*L(\d+)", snippet_str)
        if m:
            start = int(m.group(1))
        m2 = re.search(r"//\s*end\s*L(\d+)", snippet_str)
        if m2:
            end = int(m2.group(1))
        return start, end, snippet_str

    # Fallback: raw string
    return None, None, str(context_output)


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
      - mapped_target_context:    { file_path: { method, start_line, end_line, code_snippet } }
    """
    print("Agent 2 (Structural Locator): Starting target location mapping...")

    semantic_blueprint = state.get("semantic_blueprint")
    patch_analysis = state.get("patch_analysis", [])
    target_repo_path = state.get("target_repo_path", "")
    mainline_repo_path = state.get("mainline_repo_path", "")

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
    code_changes = [fc for fc in patch_analysis if not (fc.is_test_file if hasattr(fc, 'is_test_file') else fc.get("is_test_file", False))]
    test_changes = [fc for fc in patch_analysis if (fc.is_test_file if hasattr(fc, 'is_test_file') else fc.get("is_test_file", False))]

    print(f"  Agent 2: {len(code_changes)} code file(s), {len(test_changes)} test file(s)")
    trace += f"## Hunk Segregation\n- Code files: {len(code_changes)}\n- Test files: {len(test_changes)}\n\n"

    dependent_apis = set(semantic_blueprint.get("dependent_apis", []))

    # Output accumulators
    consistency_map: dict[str, str] = {}
    mapped_target_context: dict[str, dict] = {}

    # Setup a lightweight retriever (no index build — Agent 2 uses the already-built index from Phase 0)
    try:
        retriever = EnsembleRetriever(mainline_repo_path, target_repo_path)
        toolkit = ReasoningToolkit(retriever, target_repo_path, mainline_repo_path, patch_analysis)
    except Exception as e:
        print(f"  Agent 2: Warning — could not init retriever: {e}")
        retriever = None
        toolkit = None

    # Setup LLM Agent
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    tools = [
        t for t in toolkit.get_tools() if t.name in [
            "search_candidates", "match_structure", "get_dependency_graph",
            "read_file", "get_class_context", "git_log_follow", "git_blame_lines"
        ]
    ] if toolkit else []
    
    agent = create_react_agent(llm, tools=tools, state_modifier=_AGENT_SYSTEM)

    # ------------------------------------------------------------------
    # 2. Process code files
    # ------------------------------------------------------------------
    trace += "## Code File Mappings\n\n"

    for change in code_changes:
        mainline_file = change.file_path if hasattr(change, "file_path") else change.get("file_path")
        print(f"  Agent 2: Locating target for {mainline_file}...")

        trace += f"### `{mainline_file}`\n\n"
        modified_methods = _infer_modified_methods(change)
        
        input_msg = f"Mainline File: {mainline_file}\nChanged Methods: {modified_methods}\nBlueprint:\n{json.dumps(semantic_blueprint, indent=2)}\nFind the target file and methods."
        input_data = {"messages": [("user", input_msg)]}
        
        mapping_result = None
        for attempt in range(2):
            try:
                result = await agent.ainvoke(input_data)
                raw_content = result["messages"][-1].content
                
                text = raw_content.strip()
                if "```" in text:
                    lines = text.splitlines()
                    inside = False
                    json_lines = []
                    for line in lines:
                        if line.startswith("```"):
                            inside = not inside
                            continue
                        if inside:
                            json_lines.append(line)
                    text = "\n".join(json_lines).strip()
                
                mapping_result = json.loads(text)
                
                trace += f"**Agent Tool Steps:**\n\n"
                for m in result["messages"]:
                    if m.type == "tool":
                        trace += f"  - `Tool: {m.name}` -> {str(m.content)[:100]}...\n"
                break
            except Exception as e:
                print(f"  Agent 2: LLM call error (attempt {attempt+1}/2): {e}")

        if mapping_result and isinstance(mapping_result, dict):
            for k, v in mapping_result.get("consistency_map_entries", {}).items():
                consistency_map[k] = v
                
            mappings = mapping_result.get("mappings", [])
            for m in mappings:
                trace += f"| Mainline Method | Target Method | Lines |\n"
                trace += f"|---|---|---|\n"
                trace += (
                    f"| `{m.get('mainline_method', '?')}` | `{m.get('target_method', '?')}` "
                    f"| {m.get('start_line', '?')}–{m.get('end_line', '?')} |\n\n"
                )
                
                mapped_target_context[mainline_file] = {
                    "target_file": m.get("target_file"),
                    "method": m.get("target_method"),
                    "start_line": m.get("start_line"),
                    "end_line": m.get("end_line"),
                    "code_snippet": m.get("code_snippet", ""),
                }
        else:
            trace += f"❌ Failed to extract mapping.\n\n"

    # ------------------------------------------------------------------
    # 3. Process test files
    # ------------------------------------------------------------------
    trace += "## Test File Mappings\n\n"

    for change in test_changes:
        mainline_test = change.file_path if hasattr(change, "file_path") else change.get("file_path")
        target_test = _find_target_test_file(mainline_test, target_repo_path)

        if target_test:
            mapped_target_context[f"test:{mainline_test}"] = {
                "target_file": target_test,
                "method": None,
                "start_line": None,
                "end_line": None,
                "code_snippet": "",
            }
            trace += f"- `{mainline_test}` → `{target_test}` ✅\n"
            print(f"  Agent 2: Test file mapped: {mainline_test} → {target_test}")
        else:
            mapped_target_context[f"test:{mainline_test}"] = {
                "target_file": None,
                "method": None,
                "start_line": None,
                "end_line": None,
                "code_snippet": "",
            }
            trace += f"- `{mainline_test}` → **null** (test synthesis required by Agent 4) ⚠️\n"
            print(f"  Agent 2: Test file not found for {mainline_test}. Agent 4 will synthesize.")

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

    print(f"Agent 2: Complete. Mapped {len(mapped_target_context)} location(s). "
          f"ConsistencyMap has {len(consistency_map)} rename(s).")

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
                cand_paths = [c.get("file_path") or c.get("path", "") for c in candidates if isinstance(c, dict)]
                cand_paths = [p for p in cand_paths if p]
                if cand_paths:
                    match_json = toolkit.match_structure(mainline_file, cand_paths)
                    match_data = json.loads(match_json) if isinstance(match_json, str) else match_json
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
    skip = {"if", "for", "while", "switch", "catch", "new", "return", "else", "do", "try"}
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
        for m in pattern.finditer(line):
            name = m.group(1)
            if name not in skip and name not in found:
                found.append(name)

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
    target_method = mainline_method  # assume identity
    start_line = None
    end_line = None
    code_snippet = ""
    divergence = "unknown"

    for attempt in range(max_attempts + 1):
        # --- A. Try direct name match ---
        try:
            ctx = mcp.call_tool("get_class_context", {
                "target_repo_path": target_repo_path,
                "file_path": target_file,
                "focus_method": target_method,
            })
            start_line, end_line, code_snippet = _extract_line_range(ctx)
        except Exception as e:
            print(f"    Agent 2: get_class_context error (attempt {attempt+1}): {e}")
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
                    match_result = json.loads(match_result_str) if isinstance(match_result_str, str) else match_result_str
                    matched = match_result.get("match")
                    if matched:
                        found_name = matched.get("simpleName", mainline_method)
                        if found_name != mainline_method:
                            consistency_map[mainline_method] = found_name
                            print(f"    Agent 2: Renamed method — {mainline_method} → {found_name}")
                        target_method = found_name
                        # Re-fetch with new name
                        try:
                            ctx2 = mcp.call_tool("get_class_context", {
                                "target_repo_path": target_repo_path,
                                "file_path": target_file,
                                "focus_method": target_method,
                            })
                            start_line, end_line, code_snippet = _extract_line_range(ctx2)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"    Agent 2: find_method_match error: {e}")

        # --- C. Reflection: verify dependent_apis are present ---
        if code_snippet and dependent_apis:
            missing = [api for api in dependent_apis if api not in code_snippet]
            if missing:
                divergence = f"missing: {missing}"
                print(f"    Agent 2: Reflection fail (attempt {attempt+1}) — missing APIs: {missing}")
                if attempt < max_attempts:
                    # Try to broaden search via candidates
                    print(f"    Agent 2: Retrying with broader candidate search...")
                    continue
                else:
                    print(f"    Agent 2: Max reflection attempts reached. Using best-effort result.")
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
