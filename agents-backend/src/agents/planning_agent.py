"""
Planning Agent (Phase 2.5)

Creates per-hunk generation plans from raw hunks + mapped target context.
Uses a ReAct loop with file-reading tools to verify anchors/context.
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


_PLANNER_SYSTEM = """You are a Java backport planning agent.

Goal: produce a precise per-hunk execution plan for the hunk generator.

Rules:
1) Verify target context using tools before planning anchors.
2) Prefer exact line matches and structural anchors over comments.
3) Output ONLY JSON with this schema:
{
  "anchor_line": <int>,
  "anchor_before": "<line text>",
  "anchor_after": "<line text or empty>",
  "generation_mode": "import|pure_insertion|rewrite",
  "notes": "<short reason>"
}
"""


def _extract_json_obj(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = "\n".join(
            l for l in t.splitlines() if not l.strip().startswith("```")
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


def _extract_added_text(hunk_text: str) -> str:
    out = []
    for l in (hunk_text or "").splitlines()[1:]:
        if l.startswith("+") and not l.startswith("+++"):
            out.append(l[1:])
    return "\n".join(out)


async def planning_agent_node(state: AgentState, config) -> dict:
    print("Planning Agent: Building per-hunk generation plan...")

    patch_diff = state.get("patch_diff") or ""
    mapped_target_context = state.get("mapped_target_context") or {}
    target_repo_path = state.get("target_repo_path") or ""
    with_test_changes = state.get("with_test_changes", False)

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
        mapped = mapped_target_context.get(mainline_file, [])
        for hidx, raw_hunk in enumerate(raw_hunks):
            ctx = mapped[min(hidx, len(mapped) - 1)] if mapped else {}
            target_file = (ctx.get("target_file") or mainline_file).replace("\\", "/")
            insertion_line = int(ctx.get("start_line") or 1)

            mode = "rewrite"
            if _is_import_hunk(raw_hunk):
                mode = "import"
            elif _is_pure_insertion(raw_hunk):
                mode = "pure_insertion"

            entry = {
                "hunk_index": hidx,
                "target_file": target_file,
                "insertion_line": insertion_line,
                "generation_mode": mode,
                "anchor_line": insertion_line,
                "anchor_before": "",
                "anchor_after": "",
                "notes": "deterministic_default",
                "raw_added_preview": _extract_added_text(raw_hunk)[:500],
            }

            if react and toolkit:
                prompt = (
                    f"Target file: {target_file}\n"
                    f"Mapped insertion line: {insertion_line}\n"
                    f"Generation mode hint: {mode}\n"
                    f"Hunk:\n```diff\n{raw_hunk}\n```\n"
                    "Use tools to verify exact anchors and return JSON."
                )
                try:
                    prompt_input_tokens = count_text_tokens(
                        _PLANNER_SYSTEM + "\n" + prompt, model_name
                    )
                    res = await react.ainvoke(
                        {"messages": [("user", prompt)]},
                        config={"recursion_limit": 20},
                    )
                    msgs = res.get("messages", [])
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
                        output_tokens = count_text_tokens(
                            str(final_content), model_name
                        )
                        add_usage(
                            token_usage,
                            prompt_input_tokens,
                            output_tokens,
                            "planner.tiktoken",
                        )
                        token_usage["estimated"] = True

                    final = msgs[-1].content if msgs else ""
                    parsed = _extract_json_obj(final)
                    if parsed:
                        for k in (
                            "anchor_line",
                            "anchor_before",
                            "anchor_after",
                            "generation_mode",
                            "notes",
                        ):
                            if k in parsed:
                                entry[k] = parsed[k]
                except Exception as e:
                    entry["notes"] = f"planner_tool_error:{e}"

            # Safe fallback anchor extraction from snippet
            if not entry.get("anchor_before"):
                snippet = str(ctx.get("code_snippet") or "")
                snippet_lines = [l for l in snippet.splitlines() if l.strip()]
                if snippet_lines:
                    # Prefer structural line
                    for l in snippet_lines:
                        s = l.strip()
                        if any(x in s for x in ("class ", "private ", "public ", "(")):
                            entry["anchor_before"] = l
                            break
                    if not entry["anchor_before"]:
                        entry["anchor_before"] = snippet_lines[0]
                    if len(snippet_lines) > 1:
                        entry["anchor_after"] = snippet_lines[1]

            # Normalize types
            try:
                entry["anchor_line"] = int(entry.get("anchor_line") or insertion_line)
            except Exception:
                entry["anchor_line"] = insertion_line

            mode_val = str(entry.get("generation_mode") or mode).strip().lower()
            if mode_val not in {"import", "pure_insertion", "rewrite"}:
                mode_val = mode
            entry["generation_mode"] = mode_val

            plan[mainline_file].append(entry)

    total_entries = sum(len(v) for v in plan.values())
    print(f"Planning Agent: Complete. Planned {total_entries} hunk(s).")

    return {
        "messages": [
            HumanMessage(
                content=f"Planning Agent complete. Planned {total_entries} hunk(s)."
            )
        ],
        "hunk_generation_plan": dict(plan),
        "token_usage": token_usage,
    }
