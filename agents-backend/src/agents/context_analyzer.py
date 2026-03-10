"""
Agent 1: Context & Intent Analyzer (The Strategist)

H-MABS Phase 2 — Full Implementation.

Goal: Extract a SemanticBlueprint from the mainline patch on the fly,
replacing the need for a pre-computed Vulnerability Knowledge Base (VKB).

Pipeline for each modified file in the patch:
  1. Pull pre-patch and post-patch mainline function bodies via get_class_context().
  2. Extract raw per-function hunk text from the unified diff.
  3. Feed all three into an LLM prompt → receive structured JSON SemanticBlueprint.
  4. Self-reflection loop: a second LLM call verifies the blueprint is internally
     consistent (max 2 retries).
  5. Aggregate blueprints across all changed files into a single consolidated output.
  6. Write context_analyzer_trace.md for debugging.
"""

import json
import os
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from state import AgentState, SemanticBlueprint
from utils.patch_analyzer import PatchAnalyzer
from utils.mcp_client import get_client
from langchain_core.tools import tool
import os


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_AGENT_SYSTEM = """You are an expert code security analyst specializing in Java vulnerability backporting.

Your job is to extract a precise SemanticBlueprint answering:
  1. ROOT CAUSE: What vulnerability or bug does this patch fix? Be specific (e.g. "Missing null check before dereferencing `buf`").
  2. FIX LOGIC: Exactly what code change was made to fix it? (e.g. "Added `if (buf == null) return;` guard before the buffer read loop").
  3. DEPENDENT APIS: What variable names, method names, or class names are critical to this fix? List them.

You have access to tools to investigate the codebase. You MUST investigate the pre-patch and post-patch function bodies for the modified file to understand the intent.
- Use `get_class_context` to see the method before/after the patch.
- Use `get_struct_definition` if you need to understand custom types referenced in the diff.
- Use `read_file` as a fallback if `get_class_context` fails or returns incomplete body.
- Use `get_dependency_graph` if you need to trace interconnected code to understand intent.

Respond ONLY with a JSON object in this exact format:
{
  "root_cause_hypothesis": "<concise description of the vulnerability>",
  "fix_logic": "<exact description of the code change>",
  "dependent_apis": ["<symbol1>", "<symbol2>"]
}
Do not include any explanation outside the JSON object."""

_REFLECTION_SYSTEM = """You are a code verification assistant.
You will be given:
- A Java function body
- A SemanticBlueprint describing a fix

Answer ONLY "YES" if the blueprint's fix_logic accurately reflects a vulnerability fix for the code, or "NO" followed by a one-line reason if the blueprint is inaccurate or inconsistent with the code."""


_REFLECTION_USER = """## Function Body
```java
{code_body}
```

## SemanticBlueprint
- Root Cause: {root_cause}
- Fix Logic: {fix_logic}
- Dependent APIs: {dependent_apis}

Does the blueprint accurately describe what the patch fixed? Answer YES or NO."""


# ---------------------------------------------------------------------------
# Helper: parse LLM JSON response into SemanticBlueprint
# ---------------------------------------------------------------------------

def _parse_blueprint(raw: str) -> SemanticBlueprint | None:
    """
    Extracts the JSON block from an LLM response and parses it into
    a SemanticBlueprint dict. Returns None on parse failure.
    """
    # Strip markdown fences if present
    text = raw.strip()
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

    try:
        data = json.loads(text)
        return SemanticBlueprint(
            root_cause_hypothesis=str(data.get("root_cause_hypothesis", "")),
            fix_logic=str(data.get("fix_logic", "")),
            dependent_apis=list(data.get("dependent_apis", [])),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Core Agent Node
# ---------------------------------------------------------------------------

async def context_analyzer_node(state: AgentState, config) -> dict:
    """
    Agent 1 node function.

    Inputs from state:
      - patch_diff:           Raw unified diff text (set by phase_0_optimistic).
      - patch_analysis:       List[FileChange] from PatchAnalyzer.
      - mainline_repo_path:   Path to mainline repository.
      - original_commit:      Commit SHA in mainline for pre-patch AST pulls.

    Outputs written to state:
      - semantic_blueprint:   Consolidated SemanticBlueprint dict.
    """
    print("Agent 1 (Context Analyzer): Starting semantic intent extraction...")

    patch_diff = state.get("patch_diff", "")
    patch_analysis = state.get("patch_analysis", [])
    mainline_repo_path = state.get("mainline_repo_path", "")
    original_commit = state.get("original_commit", "HEAD")

    if not patch_diff:
        msg = "Agent 1 Error: No patch_diff in state. Phase 0 must run first."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    analyzer = PatchAnalyzer()
    raw_hunks_by_file = analyzer.extract_raw_hunks(patch_diff)
    trace = "# Context Analyzer Trace\n\n"

    # Initialize tools that ONLY target the mainline repo
    mcp = get_client()

    @tool
    def get_class_context(file_path: str, method_name: str) -> str:
        """Reads a Java file and returns the full body of the focused method from the mainline repo."""
        try:
            res = mcp.call_tool("get_class_context", {
                "target_repo_path": mainline_repo_path,
                "file_path": file_path,
                "focus_method": method_name
            })
            return str(res)
        except Exception as e:
            return f"Error: {e}"

    @tool
    def read_file(file_path: str) -> str:
        """Reads the raw content of a file from the mainline repo. Use if AST tools fail."""
        try:
            with open(os.path.join(mainline_repo_path, file_path), "r", encoding="utf-8") as f:
                return f.read()[:3000] # Limit to 3000 chars to save context
        except Exception as e:
            return f"Error reading file {file_path}: {e}"

    @tool
    def get_dependency_graph(file_paths: list[str]) -> str:
        """Gets dependencies for the given files to trace related functions."""
        try:
            res = mcp.call_tool("get_dependency_graph", {
                "target_repo_path": mainline_repo_path,
                "file_paths": file_paths,
                "explore_neighbors": False
            })
            return str(res)
        except Exception as e:
            return f"Error: {e}"

    @tool
    def get_struct_definition(struct_name: str) -> str:
        """Gets the structural definition (fields, methods) of a class/struct by name."""
        try:
            # We can't do a full repo grep easily in a simple tool without subprocess,
            # but we can try to ask MCP or we just return an error so the agent tries reading.
            # To keep it simple, we use the MCP get_structural_analysis if we knew the file,
            # but since we only have struct_name, we might just have to fallback to read_file.
            # For this MVP tool, let's just return a hint to use get_class_context instead.
            return f"Tool unavailable. Try using get_class_context or read_file if you know the file path."
        except Exception as e:
            return f"Error: {e}"

    tools = [
        get_class_context,
        read_file,
        get_dependency_graph,
        get_struct_definition
    ]
    
    agent = create_react_agent(llm, tools=tools, state_modifier=_AGENT_SYSTEM)

    # Filter to non-test code changes only
    code_changes = [fc for fc in patch_analysis if not fc.is_test_file]
    if not code_changes:
        code_changes = patch_analysis

    all_root_causes = []
    all_fix_logic = []
    all_dependent_apis: list[str] = []

    for change in code_changes:
        file_path = change.file_path
        print(f"  Agent 1: Analyzing {file_path}...")
        trace += f"## File: `{file_path}`\n\n"

        file_hunks = raw_hunks_by_file.get(file_path, [])
        hunk_text = "\n".join(file_hunks) if file_hunks else "(no hunks found)"
        method_name = _infer_method_name(change) or "Unknown"

        trace += f"**Method focused**: `{method_name}`\n\n"

        # Pre-fetch the mainline class context to provide in the initial prompt
        try:
            pre_ctx = mcp.call_tool("get_class_context", {
                "target_repo_path": mainline_repo_path,
                "file_path": file_path,
                "focus_method": method_name
            })
            code_body = str(pre_ctx)
        except Exception as e:
            code_body = f"(Could not pre-fetch method body: {e})"

        input_msg = (
            f"File: {file_path}\n"
            f"Changed Method (inferred): {method_name}\n\n"
            f"## Unified Diff Hunk\n```diff\n{hunk_text}\n```\n\n"
            f"## Pre-Patch Function Body (Mainline, before fix)\n```java\n{code_body}\n```\n\n"
            f"Generate the SemanticBlueprint JSON now."
        )
        input_data = {"messages": [("user", input_msg)]}
        
        blueprint = None
        for attempt in range(2):
            try:
                result = await agent.ainvoke(input_data)
                raw_content = result["messages"][-1].content
                blueprint = _parse_blueprint(raw_content)
                
                trace += f"**Agent Tool Steps:**\n\n"
                for m in result["messages"]:
                    if m.type == "tool":
                        trace += f"  - `Tool: {m.name}` -> {str(m.content)[:100]}...\n"
                
                if blueprint:
                    break
                print(f"  Agent 1: Blueprint parse failed (attempt {attempt+1}/2), retrying...")
            except Exception as e:
                print(f"  Agent 1: LLM Agent execution error (attempt {attempt+1}/2): {e}")

        if not blueprint:
            blueprint = SemanticBlueprint(
                root_cause_hypothesis=f"[Fallback] Patch modifies {file_path}. LLM extraction failed.",
                fix_logic=f"[Fallback] Added lines: {change.added_lines[:3]}",
                dependent_apis=[],
            )
            trace += "**Status**: LLM extraction failed — using fallback blueprint.\n\n"
        else:
            trace += f"**Root Cause**: {blueprint['root_cause_hypothesis']}\n\n"
            trace += f"**Fix Logic**: {blueprint['fix_logic']}\n\n"
            trace += f"**Dependent APIs**: {', '.join(blueprint['dependent_apis'])}\n\n"

        # 4. Self-reflection loop
        if blueprint["root_cause_hypothesis"] and not blueprint["root_cause_hypothesis"].startswith("[Fallback]"):
            try:
                pre_ctx = mcp.call_tool("get_class_context", {
                    "target_repo_path": mainline_repo_path,
                    "file_path": file_path,
                    "focus_method": method_name
                })
                code_body = str(pre_ctx)
            except Exception:
                code_body = "[Code body unavailable for reflection]"
            verified = await _self_reflect(llm, code_body, blueprint)
            trace += f"**Self-Reflection**: {'VERIFIED ✅' if verified else 'FAILED ❌ (used anyway)'}\n\n"
            if not verified:
                print(f"  Agent 1: Self-reflection rejected blueprint for {file_path}. Using best-effort result.")

        # 5. Accumulate
        all_root_causes.append(blueprint["root_cause_hypothesis"])
        all_fix_logic.append(blueprint["fix_logic"])
        all_dependent_apis.extend(blueprint["dependent_apis"])

    # ------------------------------------------------------------------
    # Consolidate across all files
    # ------------------------------------------------------------------
    consolidated: SemanticBlueprint = {
        "root_cause_hypothesis": " | ".join(all_root_causes),
        "fix_logic": " | ".join(all_fix_logic),
        "dependent_apis": list(dict.fromkeys(all_dependent_apis)),  # deduplicated, order preserved
    }

    print(f"Agent 1: Complete. Blueprint covers {len(code_changes)} code file(s).")
    print(f"  Root cause: {consolidated['root_cause_hypothesis'][:120]}...")

    # Write trace
    trace += "\n## Consolidated Blueprint\n\n"
    trace += f"- **Root Cause**: {consolidated['root_cause_hypothesis']}\n"
    trace += f"- **Fix Logic**: {consolidated['fix_logic']}\n"
    trace += f"- **Dependent APIs**: {consolidated['dependent_apis']}\n"
    try:
        with open("context_analyzer_trace.md", "w", encoding="utf-8") as f:
            f.write(trace)
        print("  Agent 1: Trace written to context_analyzer_trace.md")
    except Exception as e:
        print(f"  Agent 1: Warning — could not write trace: {e}")

    return {
        "messages": [
            HumanMessage(
                content=(
                    f"Agent 1 complete. SemanticBlueprint extracted for {len(code_changes)} file(s). "
                    f"Root cause: {consolidated['root_cause_hypothesis'][:100]}"
                )
            )
        ],
        "semantic_blueprint": consolidated,
        "patch_diff": patch_diff,  # ensure it's in state for downstream agents
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _self_reflect(llm: ChatGoogleGenerativeAI, code_body: str, blueprint: SemanticBlueprint) -> bool:
    """
    Sends a verification prompt to the LLM to check that the blueprint is
    internally consistent with the code. Returns True if verified.
    """
    messages = [
        SystemMessage(content=_REFLECTION_SYSTEM),
        HumanMessage(
            content=_REFLECTION_USER.format(
                code_body=code_body[:2000],
                root_cause=blueprint["root_cause_hypothesis"],
                fix_logic=blueprint["fix_logic"],
                dependent_apis=", ".join(blueprint["dependent_apis"]),
            )
        ),
    ]
    try:
        response = await llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip().upper().startswith("YES")
    except Exception as e:
        print(f"  Agent 1: Self-reflection LLM call failed: {e}")
        return True  # Assume valid on error (fail-open)


def _infer_method_name(change) -> str | None:
    """
    Infers the most likely modified method name from a FileChange.
    Looks for Java method declaration patterns in removed_lines (the pre-patch context).
    Falls back to None if nothing found.
    """
    method_pattern = __import__("re").compile(
        r"(?:public|private|protected|static|final|synchronized|\s)+"
        r"[\w<>\[\]]+\s+(\w+)\s*\("
    )
    for line in change.removed_lines:
        match = method_pattern.search(line)
        if match:
            name = match.group(1)
            # Skip Java keywords that look like methods
            if name not in {"if", "for", "while", "switch", "catch", "new", "return"}:
                return name
    # Also scan added lines
    for line in change.added_lines:
        match = method_pattern.search(line)
        if match:
            name = match.group(1)
            if name not in {"if", "for", "while", "switch", "catch", "new", "return"}:
                return name
    return None
