"""
Agent 1: Deterministic Context Analyzer

Builds a SemanticBlueprint without LLM calls.
Primary output is a per-file hunk chain used by downstream phases.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from langchain_core.messages import HumanMessage

from state import AgentState, SemanticBlueprint
from utils.patch_analyzer import PatchAnalyzer


def _infer_role(raw_hunk: str) -> str:
    h = raw_hunk or ""
    lines = h.splitlines()
    added = [l[1:] for l in lines[1:] if l.startswith("+") and not l.startswith("+++")]
    removed = [
        l[1:] for l in lines[1:] if l.startswith("-") and not l.startswith("---")
    ]

    body = "\n".join(added)
    has_import = any(l.strip().startswith("import ") for l in added)
    has_decl = any(
        kw in body
        for kw in (
            " class ",
            " interface ",
            " enum ",
            " record ",
            "private static",
            "private final",
        )
    )
    has_guard = any(
        kw in body
        for kw in (
            "if (",
            "throw ",
            "assert ",
            "return",
        )
    )
    has_call_change = any("(" in x and ")" in x for x in added + removed)

    if has_import or has_decl:
        return "declaration"
    if has_guard:
        return "guard"
    if has_call_change:
        return "core_fix"
    return "propagation"


def _hunk_summary(raw_hunk: str) -> str:
    lines = (raw_hunk or "").splitlines()[1:]
    add_count = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    del_count = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
    if add_count and del_count:
        return f"Modifies logic (+{add_count}/-{del_count} lines)."
    if add_count:
        return f"Adds logic (+{add_count} lines)."
    if del_count:
        return f"Removes logic (-{del_count} lines)."
    return "Context-only alignment hunk."


def _looks_like_test(path: str) -> bool:
    p = (path or "").lower()
    return "test" in p or p.endswith("test.java")


def _is_java_code_file(path: str) -> bool:
    p = (path or "").lower()
    return p.endswith(".java") and not _looks_like_test(p)


async def context_analyzer_node(state: AgentState, config) -> dict:
    print("Agent 1 (Context Analyzer): Deterministic blueprint generation...")

    patch_diff = state.get("patch_diff", "")
    patch_analysis = state.get("patch_analysis", [])
    with_test_changes = state.get("with_test_changes", False)

    if not patch_diff:
        msg = "Agent 1 Error: No patch_diff in state."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    analyzer = PatchAnalyzer()
    raw_hunks_by_file = analyzer.extract_raw_hunks(
        patch_diff, with_test_changes=with_test_changes
    )

    file_hunks: dict[str, list[str]] = defaultdict(list)
    for file_path, hunks in (raw_hunks_by_file or {}).items():
        if not _is_java_code_file(file_path):
            continue
        if not with_test_changes and _looks_like_test(file_path):
            continue
        file_hunks[file_path].extend(hunks or [])

    hunk_chain: list[dict[str, Any]] = []
    global_idx = 1
    for file_path in sorted(file_hunks.keys()):
        hunks = file_hunks[file_path]
        for idx, raw_hunk in enumerate(hunks, start=1):
            role = _infer_role(raw_hunk)
            connects = (
                "Prepares next hunk in same file with related context."
                if idx < len(hunks)
                else ""
            )
            hunk_chain.append(
                {
                    "hunk_index": idx,
                    "file": file_path,
                    "summary": _hunk_summary(raw_hunk),
                    "role": role,
                    "connects_to_next": connects,
                    "global_index": global_idx,
                }
            )
            global_idx += 1

    dependent_apis: list[str] = []
    for fc in patch_analysis or []:
        for ln in getattr(fc, "added_lines", []) or []:
            s = (ln or "").strip()
            if "(" in s and ")" in s:
                token = s.split("(", 1)[0].split()[-1]
                if token.isidentifier() and token not in dependent_apis:
                    dependent_apis.append(token)
            if len(dependent_apis) >= 20:
                break

    consolidated: SemanticBlueprint = {
        "root_cause_hypothesis": "Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.",
        "fix_logic": "Apply each source hunk with target-verified context and symbol consistency while preserving behavior.",
        "dependent_apis": dependent_apis,
        "patch_intent_summary": "Backport patch behavior to target branch with minimal, context-correct edits.",
        "hunk_chain": hunk_chain,
    }

    print(
        f"Agent 1: Complete. Files={len(file_hunks)} hunks={len(hunk_chain)} (deterministic)."
    )

    return {
        "messages": [
            HumanMessage(
                content=(
                    f"Agent 1 complete (deterministic). "
                    f"Hunk chain entries: {len(hunk_chain)}"
                )
            )
        ],
        "semantic_blueprint": consolidated,
        "patch_diff": patch_diff,
        "token_usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated": False,
            "reason": "deterministic_no_llm",
        },
    }
