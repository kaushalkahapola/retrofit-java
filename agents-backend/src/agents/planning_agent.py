"""
Planning Agent (Phase 2.5) - str_replace Edition

Creates per-hunk str_replace edit plans from raw hunks + mapped target context.
Uses a ReAct loop with file-reading tools to verify exact old_string values
in the real target file before committing to the plan.

Output schema per hunk entry:
{
  "hunk_index":          int,
  "target_file":         str,
  "edit_type":           "replace" | "insert_before" | "insert_after" | "delete",
  "old_string":          str,   # exact text verified to exist in target file
  "new_string":          str,   # replacement text (includes old_string for insertions)
  "verified":            bool,  # True if old_string confirmed in real file
  "verification_result": str,   # e.g. "EXACT_MATCH at line 59"
  "notes":               str
}
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from state import AgentState
from utils.llm_provider import get_llm
from utils.patch_analyzer import PatchAnalyzer
from utils.token_counter import (
    add_usage,
    count_text_tokens,
    extract_usage_from_response,
    resolve_model_name,
)
from agents.hunk_generator_tools import HunkGeneratorToolkit


# ---------------------------------------------------------------------------
# Planner system prompt
# ---------------------------------------------------------------------------

_PLANNER_SYSTEM = """\
You are a Java backport planning agent.

Your goal: for each mainline diff hunk, produce a precise str_replace edit plan
that can be applied directly to the target file WITHOUT generating unified diff syntax.

MANDATORY WORKFLOW for each hunk:

STEP 1 - CLASSIFY the hunk type:
  - "replace"        : hunk removes one or more lines and adds replacement lines
  - "insert_after"   : hunk only adds lines (pure insertion, no removals)
  - "insert_before"  : hunk adds lines before a known anchor (uncommon)
  - "delete"         : hunk only removes lines

STEP 2 - GATHER the exact target text using tools:
  For REPLACE hunks:
    a. Extract the lines being REMOVED (-) from the mainline diff as the candidate old_string.
    b. Use verify_context_at_line or grep_in_file to check if that exact text exists in
       the target file. The target may have diverged from mainline (symbol renames, etc.).
    c. If NOT_FOUND: use grep_in_file with key identifiers, then read_file_window to see
       the real surrounding content. Adjust old_string to match the target exactly.
    d. Build new_string by taking old_string and applying the intended semantic change
       (the + lines from the mainline hunk, adapted if needed).

  For INSERT_AFTER hunks:
    a. Find the anchor line in the target file - the line AFTER which the new code goes.
       Use grep_in_file to locate the nearest structural anchor (method signature, field,
       closing brace, etc.) that appears in the mainline hunk as a context line.
    b. Use get_exact_lines or read_file_window to get that anchor line verbatim.
    c. Set old_string = anchor_line_exact_text
       Set new_string = anchor_line_exact_text + "\\n" + <all new lines to insert>
       (i.e. old_string is included at the start of new_string - it is not deleted)

  For IMPORT hunks:
    a. Extract the new import(s) to add.
    b. Use grep_in_file to find an alphabetically adjacent existing import in the target.
    c. old_string = that adjacent import line (exact text)
       new_string = adjacent import line + "\\n" + new import (or new import + "\\n" + adjacent)

STEP 3 - VERIFY the plan:
    Call verify_context_at_line or grep_in_file to confirm old_string exists verbatim
    in the target file. Set "verified": true only if you get EXACT_MATCH or TRIMMED_MATCH.

STEP 4 - OUTPUT only JSON with this exact schema:
{
  "hunk_index":          <int>,
  "target_file":         "<path>",
  "edit_type":           "replace" | "insert_after" | "insert_before" | "delete",
  "old_string":          "<exact text from target file>",
  "new_string":          "<replacement text>",
  "verified":            true | false,
  "verification_result": "<tool output>",
  "notes":               "<short reason>"
}

RULES:
- old_string must match character-for-character with the real target file content.
- For multi-line old_string, preserve exact indentation and line endings.
- Never invent text that is not in the real target file.
- new_string for INSERT hunks MUST include the anchor line (old_string) at the start
  so the anchor line is preserved, not deleted.
- Apply any symbol renames from the ConsistencyMap to new_string's added content.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_json_obj(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = "\n".join(
            line for line in t.splitlines() if not line.strip().startswith("```")
        ).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(t[start : end + 1])
    except Exception:
        return None


def _is_import_hunk(hunk_text: str) -> bool:
    lines = (hunk_text or "").splitlines()[1:]
    for line in lines:
        if not line:
            continue
        if line[0] not in {"+", "-", " "}:
            continue
        content = line[1:].strip()
        if not content:
            continue
        if not content.startswith("import "):
            return False
    return True


def _is_pure_insertion(hunk_text: str) -> bool:
    lines = (hunk_text or "").splitlines()[1:]
    has_add = any(l.startswith("+") and not l.startswith("+++") for l in lines)
    has_del = any(l.startswith("-") and not l.startswith("---") for l in lines)
    return has_add and not has_del


def _classify_edit_type(hunk_text: str) -> str:
    if _is_import_hunk(hunk_text):
        return (
            "insert_after"  # imports are always insertions adjacent to existing imports
        )
    if _is_pure_insertion(hunk_text):
        return "insert_after"
    lines = (hunk_text or "").splitlines()[1:]
    has_del = any(l.startswith("-") and not l.startswith("---") for l in lines)
    has_add = any(l.startswith("+") and not l.startswith("+++") for l in lines)
    if has_del and not has_add:
        return "delete"
    return "replace"


def _extract_removed_text(hunk_text: str) -> str:
    """Return the removed lines as a single string (candidate old_string for replace hunks)."""
    out = []
    for line in (hunk_text or "").splitlines()[1:]:
        if line.startswith("-") and not line.startswith("---"):
            out.append(line[1:])
    return "\n".join(out)


def _extract_added_text(hunk_text: str) -> str:
    out = []
    for line in (hunk_text or "").splitlines()[1:]:
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line[1:])
    return "\n".join(out)


def _extract_context_lines(hunk_text: str) -> list[str]:
    """Return context lines (space-prefixed) from a hunk."""
    out = []
    for line in (hunk_text or "").splitlines()[1:]:
        if line.startswith(" "):
            out.append(line[1:])
    return out


def _apply_consistency_map(text: str, consistency_map: dict[str, str]) -> str:
    """Apply whole-word symbol renames to a block of text."""
    if not consistency_map or not text:
        return text
    for old, new in consistency_map.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    return text


def _build_default_plan_entry(
    hunk_idx: int,
    raw_hunk: str,
    target_file: str,
    consistency_map: dict[str, str],
) -> dict[str, Any]:
    """
    Deterministic fallback plan when the LLM/ReAct loop is unavailable or fails.
    Extracts old_string from removed lines, new_string from added lines.
    """
    edit_type = _classify_edit_type(raw_hunk)
    removed = _extract_removed_text(raw_hunk)
    added = _apply_consistency_map(_extract_added_text(raw_hunk), consistency_map)
    context = _extract_context_lines(raw_hunk)

    if edit_type == "replace":
        old_string = removed
        new_string = added
    elif edit_type in ("insert_after", "insert_before"):
        # Use first context line as anchor
        anchor = context[0] if context else ""
        old_string = anchor
        new_string = (anchor + "\n" + added) if anchor else added
    elif edit_type == "delete":
        old_string = removed
        new_string = ""
    else:
        old_string = removed
        new_string = added

    return {
        "hunk_index": hunk_idx,
        "target_file": target_file,
        "edit_type": edit_type,
        "old_string": old_string,
        "new_string": new_string,
        "verified": False,
        "verification_result": "deterministic_fallback",
        "notes": "fallback_no_llm",
    }


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


async def planning_agent_node(state: AgentState, config) -> dict:
    print("Planning Agent: Building per-hunk str_replace edit plans...")

    patch_diff = state.get("patch_diff") or ""
    mapped_target_context = state.get("mapped_target_context") or {}
    target_repo_path = state.get("target_repo_path") or ""
    with_test_changes = state.get("with_test_changes", False)
    validation_attempts = int(state.get("validation_attempts") or 0)
    retry_files_raw = state.get("validation_retry_files") or []
    retry_hunks_raw = state.get("validation_retry_hunks") or []
    consistency_map: dict[str, str] = state.get("consistency_map") or {}

    retry_files = {
        str(p).replace("\\", "/").strip().lstrip("/")
        for p in retry_files_raw
        if str(p).strip()
    }
    retry_hunks = {int(h) for h in retry_hunks_raw if isinstance(h, int)}

    if not patch_diff:
        msg = "Planning Agent Error: missing patch_diff"
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    analyzer = PatchAnalyzer()
    raw_hunks_by_file = analyzer.extract_raw_hunks(
        patch_diff, with_test_changes=with_test_changes
    )

    llm = get_llm(temperature=0)
    toolkit = HunkGeneratorToolkit(target_repo_path) if target_repo_path else None
    react = (
        create_react_agent(llm, tools=toolkit.get_tools(), prompt=_PLANNER_SYSTEM)
        if toolkit
        else None
    )

    plan: dict[str, list[dict[str, Any]]] = defaultdict(list)
    token_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated": False,
        "sources": [],
    }
    model_name = resolve_model_name()

    for mainline_file, raw_hunks in (raw_hunks_by_file or {}).items():
        normalized_mainline = str(mainline_file).replace("\\", "/").strip().lstrip("/")
        if (
            validation_attempts > 0
            and retry_files
            and normalized_mainline not in retry_files
        ):
            continue

        mapped = mapped_target_context.get(mainline_file, [])
        for hidx, raw_hunk in enumerate(raw_hunks):
            if validation_attempts > 0 and retry_hunks and hidx not in retry_hunks:
                continue

            ctx = mapped[min(hidx, len(mapped) - 1)] if mapped else {}
            target_file = (ctx.get("target_file") or mainline_file).replace("\\", "/")
            insertion_line = int(ctx.get("start_line") or 1)
            code_snippet = ctx.get("code_snippet") or ""

            edit_type = _classify_edit_type(raw_hunk)
            removed_text = _extract_removed_text(raw_hunk)
            added_text = _apply_consistency_map(
                _extract_added_text(raw_hunk), consistency_map
            )
            context_lines = _extract_context_lines(raw_hunk)

            # Default entry - will be overwritten by LLM if available
            entry = _build_default_plan_entry(
                hidx, raw_hunk, target_file, consistency_map
            )

            if react and toolkit:
                # Build a focused prompt for the planner ReAct agent
                prompt = (
                    f"Target file: {target_file}\n"
                    f"Mapped insertion line (approximate): {insertion_line}\n"
                    f"Edit type hint: {edit_type}\n\n"
                    f"Mainline hunk to adapt:\n```diff\n{raw_hunk}\n```\n\n"
                    f"Context snippet from Agent 2 (may be from mainline, verify in target):\n"
                    f"```java\n{code_snippet[:600]}\n```\n\n"
                    f"ConsistencyMap (apply these renames to new_string added content):\n"
                    + (
                        "\n".join(f"  {k} -> {v}" for k, v in consistency_map.items())
                        if consistency_map
                        else "  (none)"
                    )
                    + "\n\n"
                    "Use tools to verify old_string in the real target file, then "
                    "output the JSON plan."
                )

                try:
                    prompt_tokens = count_text_tokens(
                        _PLANNER_SYSTEM + "\n" + prompt, model_name
                    )
                    res = await react.ainvoke(
                        {"messages": [("user", prompt)]},
                        config={"recursion_limit": 25},
                    )
                    msgs = res.get("messages", [])

                    # Collect token usage
                    exact_any = False
                    for m in msgs:
                        if getattr(m, "type", "") != "ai":
                            continue
                        usage = extract_usage_from_response(m)
                        if usage and (usage["input_tokens"] or usage["output_tokens"]):
                            add_usage(
                                token_usage,
                                usage["input_tokens"],
                                usage["output_tokens"],
                                "planner.provider_usage",
                            )
                            exact_any = True

                    if not exact_any:
                        final_content = msgs[-1].content if msgs else ""
                        add_usage(
                            token_usage,
                            prompt_tokens,
                            count_text_tokens(str(final_content), model_name),
                            "planner.tiktoken",
                        )
                        token_usage["estimated"] = True

                    final = msgs[-1].content if msgs else ""
                    parsed = _extract_json_obj(final)
                    if parsed:
                        # Merge verified fields from LLM into entry
                        for k in (
                            "edit_type",
                            "old_string",
                            "new_string",
                            "verified",
                            "verification_result",
                            "notes",
                        ):
                            if k in parsed:
                                entry[k] = parsed[k]
                        # Always preserve hunk_index and target_file from our side
                        entry["hunk_index"] = hidx
                        entry["target_file"] = target_file
                    else:
                        print(
                            f"    Planning Agent: Could not parse JSON for "
                            f"{target_file}[{hidx}] - using deterministic fallback."
                        )
                except Exception as e:
                    entry["notes"] = f"planner_tool_error:{e}"
                    print(
                        f"    Planning Agent: Error on {target_file}[{hidx}]: {e} "
                        "- using deterministic fallback."
                    )

            # Sanity-clamp types
            entry["hunk_index"] = hidx
            entry["target_file"] = target_file
            entry["edit_type"] = (
                str(entry.get("edit_type") or edit_type).strip().lower()
            )
            if entry["edit_type"] not in {
                "replace",
                "insert_after",
                "insert_before",
                "delete",
            }:
                entry["edit_type"] = edit_type
            entry["verified"] = bool(entry.get("verified", False))
            entry.setdefault("old_string", "")
            entry.setdefault("new_string", "")
            entry.setdefault("verification_result", "")
            entry.setdefault("notes", "")

            plan[mainline_file].append(entry)

    total_entries = sum(len(v) for v in plan.values())
    print(f"Planning Agent: Complete. Planned {total_entries} edit(s).")

    return {
        "messages": [
            HumanMessage(
                content=f"Planning Agent complete. Planned {total_entries} str_replace edit(s)."
            )
        ],
        "hunk_generation_plan": dict(plan),
        "token_usage": token_usage,
    }
