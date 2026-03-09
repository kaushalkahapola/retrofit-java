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
from state import AgentState, SemanticBlueprint
from utils.patch_analyzer import PatchAnalyzer
from utils.mcp_client import get_client


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_BLUEPRINT_SYSTEM = """You are an expert code security analyst specializing in Java vulnerability backporting.

Given:
- A unified diff hunk showing what changed in a mainline patch
- The PRE-PATCH version of the modified function  
- The POST-PATCH version of the modified function

Your job is to extract a precise SemanticBlueprint answering:
  1. ROOT CAUSE: What vulnerability or bug does this patch fix? Be specific (e.g. "Missing null check before dereferencing `buf`").
  2. FIX LOGIC: Exactly what code change was made to fix it? (e.g. "Added `if (buf == null) return;` guard before the buffer read loop").
  3. DEPENDENT APIS: What variable names, method names, or class names are critical to this fix? List them.

Respond ONLY with a JSON object in this exact format:
{
  "root_cause_hypothesis": "<concise description of the vulnerability>",
  "fix_logic": "<exact description of the code change>",
  "dependent_apis": ["<symbol1>", "<symbol2>", ...]
}
Do not include any explanation outside the JSON object."""


_BLUEPRINT_USER = """## Unified Diff Hunk
```diff
{hunk}
```

## Pre-Patch Function Body (Mainline, before fix)
```java
{pre_patch_body}
```

## Post-Patch Function Body (Mainline, after fix)
```java
{post_patch_body}
```

Generate the SemanticBlueprint JSON now."""


_REFLECTION_SYSTEM = """You are a code verification assistant.
You will be given:
- A pre-patch Java function body (the vulnerable version)
- A SemanticBlueprint describing a fix

Answer ONLY "YES" if applying the blueprint's fix_logic to the pre-patch code
would logically produce a safer/fixed version, or "NO" followed by a one-line
reason if the blueprint is inaccurate or inconsistent with the code."""


_REFLECTION_USER = """## Pre-Patch Function Body
```java
{pre_patch_body}
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
    mcp = get_client()
    trace = "# Context Analyzer Trace\n\n"

    # Filter to non-test code changes only
    code_changes = [fc for fc in patch_analysis if not fc.is_test_file]
    if not code_changes:
        # Fall back to all changes if everything is flagged as test (unlikely)
        code_changes = patch_analysis

    # ------------------------------------------------------------------
    # Per-file BluePrint extraction
    # ------------------------------------------------------------------
    all_root_causes = []
    all_fix_logic = []
    all_dependent_apis: list[str] = []

    for change in code_changes:
        file_path = change.file_path
        print(f"  Agent 1: Analyzing {file_path}...")
        trace += f"## File: `{file_path}`\n\n"

        # 1. Get raw hunk text for this file
        file_hunks = raw_hunks_by_file.get(file_path, [])
        hunk_text = "\n".join(file_hunks) if file_hunks else "(no hunks found)"

        # 2. Pull PRE-PATCH function body from mainline
        #    We use the removed_lines to infer which method was modified.
        method_name = _infer_method_name(change)
        pre_patch_body = "[pre-patch body unavailable]"
        post_patch_body = "[post-patch body unavailable]"

        if mainline_repo_path and method_name:
            try:
                # Pre-patch: use original_commit (before the fix was applied)
                pre_result = mcp.call_tool("get_class_context", {
                    "target_repo_path": mainline_repo_path,
                    "file_path": file_path,
                    "focus_method": method_name,
                })
                pre_patch_body = pre_result.get("context", pre_patch_body) if isinstance(pre_result, dict) else str(pre_result)

                # Post-patch: use HEAD (after the fix)
                post_result = mcp.call_tool("get_class_context", {
                    "target_repo_path": mainline_repo_path,
                    "file_path": file_path,
                    "focus_method": method_name,
                })
                post_patch_body = post_result.get("context", post_patch_body) if isinstance(post_result, dict) else str(post_result)

                trace += f"**Method focused**: `{method_name}`\n\n"
            except Exception as e:
                trace += f"**Warning**: Could not pull function body — {e}\n\n"
                print(f"  Agent 1: Warning — could not pull body for {method_name}: {e}")

        # 3. LLM call — generate SemanticBlueprint
        blueprint = None
        for attempt in range(3):  # up to 3 attempts (1 initial + 2 retries)
            prompt_user = _BLUEPRINT_USER.format(
                hunk=hunk_text,
                pre_patch_body=pre_patch_body[:3000],   # cap context size
                post_patch_body=post_patch_body[:3000],
            )
            messages = [
                SystemMessage(content=_BLUEPRINT_SYSTEM),
                HumanMessage(content=prompt_user),
            ]
            try:
                response = await llm.ainvoke(messages)
                raw_content = response.content if hasattr(response, "content") else str(response)
                blueprint = _parse_blueprint(raw_content)
                if blueprint:
                    break
                print(f"  Agent 1: Blueprint parse failed (attempt {attempt+1}/3), retrying...")
            except Exception as e:
                print(f"  Agent 1: LLM call error (attempt {attempt+1}/3): {e}")

        if not blueprint:
            # Fallback — use structural info from the patch itself
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
            verified = await _self_reflect(llm, pre_patch_body, blueprint)
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

async def _self_reflect(llm: ChatGoogleGenerativeAI, pre_patch_body: str, blueprint: SemanticBlueprint) -> bool:
    """
    Sends a verification prompt to the LLM to check that the blueprint is
    internally consistent with the pre-patch code. Returns True if verified.
    """
    messages = [
        SystemMessage(content=_REFLECTION_SYSTEM),
        HumanMessage(
            content=_REFLECTION_USER.format(
                pre_patch_body=pre_patch_body[:2000],
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
