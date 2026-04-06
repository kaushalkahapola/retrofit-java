"""
Agent 1: Deterministic Context Analyzer

Builds a SemanticBlueprint without LLM calls.
Primary output is a per-file hunk chain used by downstream phases.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
import os

from langchain_core.messages import HumanMessage, SystemMessage
from state import AgentState, SemanticBlueprint
from utils.patch_analyzer import PatchAnalyzer
from agents.hunk_variant_detector import HunkVariantDetector
from utils.llm_provider import get_llm
from utils.token_counter import count_messages_tokens, extract_usage_from_response, add_usage

_ANALYZER_SYSTEM = """You are an expert Java architect analyzing a security patch for backporting.
Your goal is to produce a Semantic Blueprint that explains the fix logic and identifies key dependencies.

Analyze the provided diff and output a JSON blueprint with:
1. root_cause_hypothesis: A technical explanation of the vulnerability being fixed.
2. fix_logic: The core algorithm or logic change introduced by the patch.
3. dependent_apis: A list of method names, class names, or constants that are critical to the fix.
4. patch_intent_summary: A one-sentence summary of the overall goal.
5. hunk_chain: An array of objects, one per hunk, describing its role:
   - hunk_index: 1-based index in the file
   - file: path
   - role: "core_fix" | "guard" | "propagation" | "declaration" | "cleanup" | "refactor"
   - summary: brief description of what this hunk does

Output ONLY the JSON object."""

_ANALYZER_USER = """## Patch Diff
```diff
{patch_diff}
```

## Commit Message
{commit_message}

Produce the Semantic Blueprint JSON now."""


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
    mainline_repo_path = state.get("mainline_repo_path", "")

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
    hunk_variants_map: dict[int, Any] = {}  # global_idx → variants
    global_idx = 1

    # Initialize variant detector if mainline repo available
    variant_detector = None
    if mainline_repo_path and os.path.isdir(mainline_repo_path):
        variant_detector = HunkVariantDetector(mainline_repo_path)

    for file_path in sorted(file_hunks.keys()):
        hunks = file_hunks[file_path]
        for idx, raw_hunk in enumerate(hunks, start=1):
            role = _infer_role(raw_hunk)
            connects = (
                "Prepares next hunk in same file with related context."
                if idx < len(hunks)
                else ""
            )
            hunk_entry = {
                "hunk_index": idx,
                "file": file_path,
                "summary": _hunk_summary(raw_hunk),
                "role": role,
                "connects_to_next": connects,
                "global_index": global_idx,
            }
            hunk_chain.append(hunk_entry)

            # Detect variants if available
            if variant_detector:
                try:
                    removed_lines = [
                        l[1:]
                        for l in raw_hunk.splitlines()[1:]
                        if l.startswith("-") and not l.startswith("---")
                    ]
                    added_lines = [
                        l[1:]
                        for l in raw_hunk.splitlines()[1:]
                        if l.startswith("+") and not l.startswith("+++")
                    ]
                    variants = variant_detector.detect_variants_for_hunk(
                        idx, file_path, raw_hunk, added_lines, removed_lines
                    )
                    if variants and variants.variants:
                        hunk_variants_map[global_idx] = {
                            "semantic_intent": variants.semantic_intent,
                            "variants": [
                                {
                                    "variant_id": v.variant_id,
                                    "pattern_type": v.pattern_type,
                                    "description": v.description,
                                    "old_string": v.old_string,
                                    "new_string": v.new_string,
                                    "found_in_mainline": v.found_in_mainline,
                                    "line_in_mainline": v.line_in_mainline,
                                    "confidence": v.confidence,
                                }
                                for v in variants.variants
                            ],
                        }
                except Exception as e:
                    # Silently skip variant detection on error
                    import traceback

                    print(f"Variant detection failed for hunk {global_idx}: {e}")

            global_idx += 1

    dependent_apis: list[str] = []
    for fc in patch_analysis or []:
        for ln in getattr(fc, "added_lines", []) or []:
            s = (ln or "").strip()
            if "(" in s and ")" in s:
                before_paren = s.split("(", 1)[0].strip().split()
                if before_paren:
                    token = before_paren[-1]
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

    # --- Option 1: LLM-based analysis for REWRITE patches ---
    complexity = str(state.get("patch_complexity") or "REWRITE").strip().upper()
    token_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated": False,
    }

    if complexity == "REWRITE":
        print("Agent 1: Patch complexity is REWRITE - running LLM-based semantic analysis...")
        llm = get_llm(temperature=0)
        messages = [
            SystemMessage(content=_ANALYZER_SYSTEM),
            HumanMessage(content=_ANALYZER_USER.format(
                patch_diff=patch_diff[:10000], # Cap to avoid context overflow
                commit_message=state.get("commit_message", "")
            ))
        ]
        
        try:
            response = await llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            
            # Extract JSON from response
            import json
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                llm_blueprint = json.loads(json_match.group(0))
                
                # Merge or replace deterministic consolidated with LLM output
                # We prioritize LLM for high-level logic but keep deterministic hunk list
                # for exact tracking if LLM returns a different structure.
                consolidated["root_cause_hypothesis"] = llm_blueprint.get("root_cause_hypothesis", consolidated["root_cause_hypothesis"])
                consolidated["fix_logic"] = llm_blueprint.get("fix_logic", consolidated["fix_logic"])
                consolidated["patch_intent_summary"] = llm_blueprint.get("patch_intent_summary", consolidated["patch_intent_summary"])
                
                llm_apis = llm_blueprint.get("dependent_apis", [])
                if isinstance(llm_apis, list):
                    consolidated["dependent_apis"] = sorted(list(set(consolidated["dependent_apis"] + llm_apis)))
                
                # Update hunk roles if provided
                llm_hunks = llm_blueprint.get("hunk_chain", [])
                if isinstance(llm_hunks, list) and len(llm_hunks) == len(consolidated["hunk_chain"]):
                    for i, h in enumerate(consolidated["hunk_chain"]):
                        if i < len(llm_hunks):
                            h["role"] = llm_hunks[i].get("role", h["role"])
                            h["summary"] = llm_hunks[i].get("summary", h["summary"])
                
                print(f"Agent 1: LLM analysis successful. Logic: {consolidated['fix_logic'][:100]}...")
            
            # Track usage
            usage = extract_usage_from_response(response)
            if usage:
                token_usage.update(usage)
            else:
                token_usage["input_tokens"] = count_messages_tokens(messages)
                token_usage["output_tokens"] = len(content) // 4
                token_usage["total_tokens"] = token_usage["input_tokens"] + token_usage["output_tokens"]
                token_usage["estimated"] = True
                
        except Exception as e:
            print(f"Agent 1: LLM analysis failed: {e} - falling back to deterministic.")
            token_usage["reason"] = f"llm_failed: {e}"

    print(
        f"Agent 1: Complete. Files={len(file_hunks)} hunks={len(hunk_chain)} (complexity={complexity})."
    )
    if hunk_variants_map:
        print(f"Agent 1: Detected {len(hunk_variants_map)} hunk(s) with variants.")

    result = {
        "messages": [
            HumanMessage(
                content=(
                    f"Agent 1 complete ({complexity}). "
                    f"Hunk chain entries: {len(hunk_chain)}"
                )
            )
        ],
        "semantic_blueprint": consolidated,
        "patch_diff": patch_diff,
        "token_usage": token_usage,
    }

    # Add variants to state if any were detected
    if hunk_variants_map:
        result["hunk_variants"] = hunk_variants_map

    return result
