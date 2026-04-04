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
import os
import re
import subprocess
from collections import defaultdict
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
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
from agents.semantic_hunk_adapter import SemanticHunkAdapter


# ---------------------------------------------------------------------------
# Planner system prompt
# ---------------------------------------------------------------------------

_PLANNER_SYSTEM = """\
You are a Java backport planning agent.

You do NOT edit files. You only produce an execution plan for File Editor.

MANDATORY TODO WORKFLOW (do in order):
1) Check whether mainline location and detected target location are the same.
2) Compare PRE-PATCH surrounding context: mainline before-patch surroundings vs detected target surroundings.
3) If surrounding context is effectively same, prefer same mainline edit logic.
4) If blocked, identify blockers explicitly.
5) Determine whether blockers can be solved with namespace-only changes (variable/method/api/signature renames) based on context.
6) If namespace-only is insufficient, plan structural rewrite.

Adaptation type definitions:
- TYPE_I: same change, same location
- TYPE_II: same change, different location
- TYPE_III: same location + namespace changes needed
- TYPE_IV: different location + namespace changes needed
- TYPE_V: structural rewrite needed

Output JSON only with this schema:
{
  "hunk_index": int,
  "target_file": "path",
  "adaptation_type": "TYPE_I|TYPE_II|TYPE_III|TYPE_IV|TYPE_V",
  "location_match": true|false,
  "surrounding_match": true|false,
  "blockers": ["..."],
  "namespace_only_possible": true|false,
  "namespace_changes": [{"from":"...","to":"...","reason":"..."}],
  "edit_type": "replace|insert_after|insert_before|delete",
  "old_string": "exact text from target file",
  "new_string": "replacement text for target",
  "verified": true|false,
  "verification_result": "short status",
  "notes": "short reason",
  "surround_before_3": ["line1","line2","line3"],
  "surround_after_3": ["line1","line2","line3"]
}

Rules:
- Prefer deterministic, minimal changes.
- old_string must be directly applicable on target.
- No prose outside JSON.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _looks_like_test(path: str) -> bool:
    p = (path or "").lower()
    return "test" in p or p.endswith("test.java")


def _is_java_code_file(path: str) -> bool:
    p = (path or "").lower()
    return p.endswith(".java") and not _looks_like_test(p)


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


def _extract_json_payload(text: str) -> Any | None:
    """Parse JSON object or array from LLM output."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = "\n".join(
            line for line in t.splitlines() if not line.strip().startswith("```")
        ).strip()

    # Try object first
    start_obj = t.find("{")
    end_obj = t.rfind("}")
    if start_obj >= 0 and end_obj >= start_obj:
        try:
            return json.loads(t[start_obj : end_obj + 1])
        except Exception:
            pass

    # Then array
    start_arr = t.find("[")
    end_arr = t.rfind("]")
    if start_arr >= 0 and end_arr >= start_arr:
        try:
            return json.loads(t[start_arr : end_arr + 1])
        except Exception:
            pass
    return None


def _nearest_non_empty_before(lines: list[str], index: int) -> str:
    i = index - 1
    while i >= 0:
        line = lines[i]
        if line.strip():
            return line
        i -= 1
    return ""


def _nearest_non_empty_after(lines: list[str], index: int) -> str:
    i = index + 1
    while i < len(lines):
        line = lines[i]
        if line.strip():
            return line
        i += 1
    return ""


def _decompose_hunk_to_required_entries(
    *,
    hunk_idx: int,
    raw_hunk: str,
    target_file: str,
    consistency_map: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Deterministically decompose a unified hunk into required text-edit operations.

    This prevents a critical failure mode where a mixed hunk (replace + insertion)
    is collapsed into a single plan entry and the insertion block gets dropped.
    """
    body_lines = (raw_hunk or "").splitlines()[1:]
    entries: list[dict[str, Any]] = []

    i = 0
    op_index = 0
    while i < len(body_lines):
        line = body_lines[i]

        # Collect contiguous deletion block.
        if line.startswith("-") and not line.startswith("---"):
            dels: list[str] = []
            while i < len(body_lines):
                cur = body_lines[i]
                if cur.startswith("-") and not cur.startswith("---"):
                    dels.append(cur[1:])
                    i += 1
                    continue
                break

            # Optional contiguous add block immediately after deletions.
            adds: list[str] = []
            while i < len(body_lines):
                cur = body_lines[i]
                if cur.startswith("+") and not cur.startswith("+++"):
                    adds.append(cur[1:])
                    i += 1
                    continue
                break

            if adds:
                entries.append(
                    {
                        "hunk_index": hunk_idx,
                        "target_file": target_file,
                        "operation_index": op_index,
                        "edit_type": "replace",
                        "old_string": "\n".join(dels),
                        "new_string": _apply_consistency_map(
                            "\n".join(adds), consistency_map
                        ),
                        "verified": False,
                        "verification_result": "deterministic_required_replace",
                        "notes": "required_op_replace",
                    }
                )
            else:
                entries.append(
                    {
                        "hunk_index": hunk_idx,
                        "target_file": target_file,
                        "operation_index": op_index,
                        "edit_type": "delete",
                        "old_string": "\n".join(dels),
                        "new_string": "",
                        "verified": False,
                        "verification_result": "deterministic_required_delete",
                        "notes": "required_op_delete",
                    }
                )
            op_index += 1
            continue

        # Collect contiguous pure insertion block.
        if line.startswith("+") and not line.startswith("+++"):
            adds: list[str] = []
            block_start = i
            while i < len(body_lines):
                cur = body_lines[i]
                if cur.startswith("+") and not cur.startswith("+++"):
                    adds.append(cur[1:])
                    i += 1
                    continue
                break

            added_text = _apply_consistency_map("\n".join(adds), consistency_map)
            prev_anchor = _nearest_non_empty_before(body_lines, block_start)
            next_anchor = _nearest_non_empty_after(body_lines, i - 1)

            # Prefer insert_before(next_anchor) when available; this is more stable
            # for blocks inserted before an existing method/class member.
            if next_anchor:
                entries.append(
                    {
                        "hunk_index": hunk_idx,
                        "target_file": target_file,
                        "operation_index": op_index,
                        "edit_type": "insert_before",
                        "old_string": next_anchor,
                        "new_string": f"{added_text}\n{next_anchor}",
                        "verified": False,
                        "verification_result": "deterministic_required_insert_before",
                        "notes": "required_op_insert_before",
                    }
                )
            elif prev_anchor:
                entries.append(
                    {
                        "hunk_index": hunk_idx,
                        "target_file": target_file,
                        "operation_index": op_index,
                        "edit_type": "insert_after",
                        "old_string": prev_anchor,
                        "new_string": f"{prev_anchor}\n{added_text}",
                        "verified": False,
                        "verification_result": "deterministic_required_insert_after",
                        "notes": "required_op_insert_after",
                    }
                )
            else:
                # Fallback: no stable anchor found; keep a direct replace-style op.
                entries.append(
                    {
                        "hunk_index": hunk_idx,
                        "target_file": target_file,
                        "operation_index": op_index,
                        "edit_type": "replace",
                        "old_string": "",
                        "new_string": added_text,
                        "verified": False,
                        "verification_result": "deterministic_required_insert_unanchored",
                        "notes": "required_op_insert_unanchored",
                    }
                )
            op_index += 1
            continue

        # Context line; move ahead.
        i += 1

    if entries:
        return entries

    # Final fallback for unusual hunks.
    return [_build_default_plan_entry(hunk_idx, raw_hunk, target_file, consistency_map)]


def _entry_operation_marker(entry: dict[str, Any]) -> str:
    """Extract a semantic marker from a plan entry for coverage matching."""
    edit_type = str(entry.get("edit_type") or "").strip().lower()
    old_s = str(entry.get("old_string") or "")
    new_s = str(entry.get("new_string") or "")

    if edit_type.startswith("insert"):
        # Marker from inserted part (new without old anchor when possible)
        if old_s and new_s.startswith(old_s + "\n"):
            inserted = new_s[len(old_s) + 1 :]
            for line in inserted.splitlines():
                if line.strip():
                    return line.strip()
        for line in new_s.splitlines():
            if line.strip() and line.strip() != old_s.strip():
                return line.strip()
    else:
        for line in new_s.splitlines():
            if line.strip() and line.strip() not in old_s:
                return line.strip()
    return ""


def _ensure_required_coverage(
    planned_entries: list[dict[str, Any]],
    required_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Ensure all deterministic required operations are represented in the final plan.
    Missing required operations are appended as backfill entries.
    """
    out = list(planned_entries)
    for req in required_entries:
        req_marker = _entry_operation_marker(req)
        req_type = str(req.get("edit_type") or "").strip().lower()
        req_idx = req.get("operation_index")
        req_old = str(req.get("old_string") or "")
        req_new = str(req.get("new_string") or "")
        matched = False
        for got in out:
            # First, check if there's a directed match on operation_index
            if req_idx is not None and got.get("operation_index") == req_idx:
                matched = True
                break

            got_type = str(got.get("edit_type") or "").strip().lower()
            if got_type != req_type:
                continue
            got_old = str(got.get("old_string") or "")
            got_new = str(got.get("new_string") or "")
            if req_old and got_old == req_old:
                if (
                    req_type.startswith("insert")
                    and req_marker
                    and req_marker not in got_new
                ):
                    continue
                matched = True
                break
            if req_marker:
                if req_marker in got_new:
                    matched = True
                    break
            else:
                if got_old == req_old and got_new == req_new:
                    matched = True
                    break
        if not matched:
            req_backfill = dict(req)
            req_backfill["verified"] = False
            req_backfill["verification_result"] = "coverage_backfill"
            req_backfill["notes"] = (
                str(req_backfill.get("notes") or "") + "|coverage_backfill"
            ).strip("|")
            out.append(req_backfill)
    return out


def _normalize_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/").lstrip("/")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p


def _read_target_file(target_repo_path: str, rel_path: str) -> str:
    try:
        p = _normalize_path(rel_path)
        full = os.path.normpath(os.path.join(target_repo_path, p))
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def _read_mainline_prepatch_file(
    mainline_repo_path: str,
    original_commit: str,
    rel_path: str,
) -> str:
    """Read mainline file content from pre-patch commit (original_commit^)."""
    if not mainline_repo_path or not rel_path:
        return ""

    path = _normalize_path(rel_path)
    commit = (original_commit or "HEAD").strip()
    candidates = [f"{commit}^:{path}", f"{commit}:{path}", f"HEAD:{path}"]

    for spec in candidates:
        try:
            result = subprocess.run(
                ["git", "show", spec],
                cwd=mainline_repo_path,
                capture_output=True,
                text=True,
                timeout=20,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception:
            continue

    return ""


def _parse_hunk_header(hunk_text: str) -> tuple[int, int, int, int]:
    lines = (hunk_text or "").splitlines()
    if not lines:
        return 1, 1, 1, 1
    header = lines[0]
    m = re.search(
        r"@@\s*-([0-9]+)(?:,([0-9]+))?\s+\+([0-9]+)(?:,([0-9]+))?\s*@@", header
    )
    if not m:
        return 1, 1, 1, 1
    old_start = int(m.group(1))
    old_count = int(m.group(2) or "1")
    new_start = int(m.group(3))
    new_count = int(m.group(4) or "1")
    return old_start, old_count, new_start, new_count


def _extract_surrounding_lines(
    content: str,
    start_line: int,
    end_line: int,
    window: int = 3,
) -> tuple[list[str], list[str]]:
    lines = (content or "").splitlines()
    if not lines:
        return [], []

    s = max(1, int(start_line or 1))
    e = max(s, int(end_line or s))
    s_idx = s - 1
    e_idx = min(len(lines) - 1, e - 1)

    before_start = max(0, s_idx - window)
    before = lines[before_start:s_idx]
    after_end = min(len(lines), e_idx + 1 + window)
    after = lines[e_idx + 1 : after_end]
    return before, after


def _normalize_line(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _surrounding_match(
    main_before: list[str],
    main_after: list[str],
    target_before: list[str],
    target_after: list[str],
) -> bool:
    main_seq = [
        _normalize_line(x) for x in (main_before + main_after) if _normalize_line(x)
    ]
    target_seq = [
        _normalize_line(x) for x in (target_before + target_after) if _normalize_line(x)
    ]
    if not main_seq or not target_seq:
        return False

    overlap = sum(1 for x in main_seq if x in target_seq)
    denom = max(1, min(len(main_seq), len(target_seq)))
    return (overlap / denom) >= 0.5


def _location_match(
    mainline_file: str, target_file: str, mainline_start: int, target_start: int
) -> bool:
    if _normalize_path(mainline_file) != _normalize_path(target_file):
        return False
    return abs(int(mainline_start or 1) - int(target_start or 1)) <= 5


def _build_hunk_planner_prompt(
    *,
    mainline_file: str,
    target_file: str,
    hunk_index: int,
    raw_hunk: str,
    mainline_old_start: int,
    target_start_line: int,
    mainline_pre_before: list[str],
    mainline_pre_after: list[str],
    target_before: list[str],
    target_after: list[str],
    consistency_map: dict[str, str],
    deterministic_entries: list[dict[str, Any]],
    retry_failure_context: str,
) -> str:
    return f"""Plan this backport hunk.

Mainline file: {mainline_file}
Target file: {target_file}
Hunk index: {hunk_index}
Mainline old-start line (pre-patch): {mainline_old_start}
Detected target start line: {target_start_line}

Mainline diff hunk:
```diff
{raw_hunk}
```

Mainline PRE-PATCH surrounding (3 before / 3 after):
before={json.dumps(mainline_pre_before, ensure_ascii=False)}
after={json.dumps(mainline_pre_after, ensure_ascii=False)}

Detected target surrounding (3 before / 3 after):
before={json.dumps(target_before, ensure_ascii=False)}
after={json.dumps(target_after, ensure_ascii=False)}

Consistency map:
{json.dumps(consistency_map or {{}}, indent=2, ensure_ascii=False)}

Deterministic candidate operations:
{json.dumps(deterministic_entries, indent=2, ensure_ascii=False)}

Retry/failure context:
{retry_failure_context or "<none>"}

Follow this exact TODO:
1. Check if mainline location and detected target location are same.
2. Compare PRE-PATCH surrounding context (mainline before patch) with detected target surroundings.
3. If both surroundings are same, use same edit logic as mainline.
4. If blocked, list blockers.
5. Check whether blockers can be solved with namespace-only changes based on context (do not assume; justify).
6. If namespace-only is insufficient, do structural rewrite.

Return JSON ONLY in this shape:
{{
  "adaptation_type": "TYPE_I|TYPE_II|TYPE_III|TYPE_IV|TYPE_V",
  "location_match": true,
  "surrounding_match": true,
  "blockers": [],
  "namespace_only_possible": true,
  "namespace_changes": [{{"from":"","to":"","reason":""}}],
  "operations": [
    {{
      "operation_index": 0,
      "edit_type": "replace|insert_before|insert_after|delete",
      "old_string": "",
      "new_string": "",
      "verified": true,
      "verification_result": "",
      "notes": "",
      "surround_before_3": ["","",""],
      "surround_after_3": ["","",""]
    }}
  ]
}}"""


def _normalize_planner_response_entries(
    payload: dict[str, Any],
    fallback_entries: list[dict[str, Any]],
    target_file: str,
    hunk_index: int,
) -> list[dict[str, Any]]:
    operations = payload.get("operations") if isinstance(payload, dict) else None
    if not isinstance(operations, list) or not operations:
        return []

    out: list[dict[str, Any]] = []
    for idx, op in enumerate(operations):
        if not isinstance(op, dict):
            continue
        fallback = fallback_entries[idx] if idx < len(fallback_entries) else {}
        out.append(
            {
                "hunk_index": hunk_index,
                "target_file": target_file,
                "operation_index": op.get(
                    "operation_index", fallback.get("operation_index", idx)
                ),
                "edit_type": str(
                    op.get("edit_type") or fallback.get("edit_type") or "replace"
                ),
                "old_string": str(
                    op.get("old_string") or fallback.get("old_string") or ""
                ),
                "new_string": str(
                    op.get("new_string") or fallback.get("new_string") or ""
                ),
                "verified": bool(op.get("verified", fallback.get("verified", False))),
                "verification_result": str(
                    op.get("verification_result")
                    or fallback.get("verification_result")
                    or "llm_planned"
                ),
                "notes": str(op.get("notes") or fallback.get("notes") or "llm_planned"),
                "surround_before_3": op.get("surround_before_3")
                or fallback.get("surround_before_3")
                or [],
                "surround_after_3": op.get("surround_after_3")
                or fallback.get("surround_after_3")
                or [],
            }
        )
    return out


def _infer_adaptation_type(
    *,
    location_match: bool,
    blockers: list[str],
    namespace_only_possible: bool,
    explicit: str = "",
) -> str:
    exp = str(explicit or "").strip().upper()
    if exp in {"TYPE_I", "TYPE_II", "TYPE_III", "TYPE_IV", "TYPE_V"}:
        return exp
    has_blocker = bool(blockers)
    if not has_blocker:
        return "TYPE_I" if location_match else "TYPE_II"
    if namespace_only_possible:
        return "TYPE_III" if location_match else "TYPE_IV"
    return "TYPE_V"


def _attach_entry_surround_context(
    entry: dict[str, Any], target_content: str
) -> dict[str, Any]:
    out = dict(entry)
    old_s = str(out.get("old_string") or "")
    if not old_s or not target_content:
        out.setdefault("surround_before_3", [])
        out.setdefault("surround_after_3", [])
        return out

    idx = target_content.find(old_s)
    if idx < 0:
        out.setdefault("surround_before_3", [])
        out.setdefault("surround_after_3", [])
        return out

    start_line = target_content[:idx].count("\n") + 1
    line_span = max(1, old_s.count("\n") + 1)
    end_line = start_line + line_span - 1
    before, after = _extract_surrounding_lines(
        target_content, start_line, end_line, window=3
    )
    out["surround_before_3"] = before[-3:]
    out["surround_after_3"] = after[:3]
    return out


def _resolve_old_in_content(content: str, old_string: str) -> tuple[str, str]:
    """Resolve old_string to exact on-disk text when possible."""
    if not content or not old_string:
        return "", "empty"
    if old_string in content:
        return old_string, "exact"

    if "\n" not in old_string:
        stripped = old_string.strip()
        if stripped:
            lines = [l for l in content.splitlines() if l.strip() == stripped]
            if len(lines) == 1:
                return lines[0], "line_trimmed_unique"
        if old_string.lstrip() != old_string and old_string.lstrip() in content:
            return old_string.lstrip(), "lstrip_exact"
        return "", "not_found_single"

    cand = old_string.splitlines()
    file_lines = content.splitlines()
    n = len(cand)
    matches: list[str] = []
    for i in range(0, len(file_lines) - n + 1):
        ok = True
        for j in range(n):
            if file_lines[i + j].strip() != cand[j].strip():
                ok = False
                break
        if ok:
            matches.append("\n".join(file_lines[i : i + n]))
    if len(matches) == 1:
        return matches[0], "multiline_trimmed_unique"

    # Secondary fallback: anchor-line reconstruction for diverged multiline blocks.
    # Find the strongest unique anchor line from candidate, then reconstruct a window.
    anchor_idx = -1
    anchor_line = ""
    best_len = -1
    for i, line in enumerate(cand):
        s = line.strip()
        if not s:
            continue
        if len(s) > best_len:
            best_len = len(s)
            anchor_idx = i
            anchor_line = s

    if anchor_idx >= 0 and anchor_line:
        anchor_hits = [
            idx
            for idx, fl in enumerate(file_lines)
            if fl.strip() == anchor_line or anchor_line in fl.strip()
        ]
        if len(anchor_hits) == 1:
            hit = anchor_hits[0]
            start = hit - anchor_idx
            if start < 0:
                start = 0
            if start + n <= len(file_lines):
                window = file_lines[start : start + n]
                matched = 0
                for j in range(n):
                    if window[j].strip() == cand[j].strip():
                        matched += 1
                # Require at least 50% line-level match to avoid false anchors.
                if n > 0 and matched * 2 >= n:
                    return "\n".join(window), "multiline_anchor_reconstructed"

    return "", "not_found_multiline"


def _sanitize_entry_against_target(
    entry: dict[str, Any],
    content: str,
) -> dict[str, Any]:
    """
    Normalize planner entry against real file content.
    Ensures old_string exists verbatim when possible and recomposes insertion new_string.
    """
    out = dict(entry)
    edit_type = str(out.get("edit_type") or "").strip().lower()
    old_s = str(out.get("old_string") or "")
    new_s = str(out.get("new_string") or "")

    resolved_old, reason = _resolve_old_in_content(content, old_s)
    if not resolved_old:
        out["verified"] = False
        out["verification_result"] = f"sanitize_old_not_found:{reason}"
        out["notes"] = (
            str(out.get("notes") or "") + f"|sanitize_old_not_found:{reason}"
        ).strip("|")
        return out

    out["old_string"] = resolved_old
    out["verified"] = True
    out["verification_result"] = f"sanitize_resolved:{reason}"

    if edit_type in {"insert_before", "insert_after"}:
        payload = None
        # Try matching original old_s first, then resolved_old to extract payload
        for anchor_candidate in [old_s, resolved_old]:
            if not anchor_candidate:
                continue
            if edit_type == "insert_before":
                idx = new_s.rfind(anchor_candidate)
                if idx >= 0:
                    payload = new_s[:idx]
                    break
            else:
                idx = new_s.find(anchor_candidate)
                if idx >= 0:
                    payload = new_s[idx + len(anchor_candidate) :]
                    break

        # Fallback: derive payload by suffix/prefix trimmed-line matching.
        if payload is None:
            new_lines = new_s.splitlines()
            old_lines = old_s.splitlines()
            if old_lines and len(new_lines) >= len(old_lines):
                if edit_type == "insert_before":
                    tail = new_lines[-len(old_lines) :]
                    if all(
                        tail[i].strip() == old_lines[i].strip()
                        for i in range(len(old_lines))
                    ):
                        payload = "\n".join(new_lines[: -len(old_lines)])
                        if new_s.endswith("\n"):
                            payload += "\n"
                else:
                    head = new_lines[: len(old_lines)]
                    if all(
                        head[i].strip() == old_lines[i].strip()
                        for i in range(len(old_lines))
                    ):
                        payload = "\n".join(new_lines[len(old_lines) :])
                        if payload and not payload.startswith("\n") and "\n" in new_s:
                            payload = "\n" + payload
        if payload is None:
            out["verified"] = False
            out["verification_result"] = "sanitize_payload_missing"
            out["notes"] = (
                str(out.get("notes") or "") + "|sanitize_payload_missing"
            ).strip("|")
            return out
        if edit_type == "insert_before" and payload and not payload.endswith("\n"):
            payload += "\n"
        if edit_type == "insert_after" and payload and not payload.startswith("\n"):
            payload = "\n" + payload
        out["new_string"] = (
            payload + resolved_old
            if edit_type == "insert_before"
            else resolved_old + payload
        )

    return out


def _attempt_semantic_adapt_entry(
    entry: dict[str, Any],
    target_content: str,
    target_file: str,
) -> dict[str, Any]:
    """
    Attempt semantic adaptation for a planning entry that failed verification.

    Args:
        entry: Planning entry that may have failed verification
        target_content: Full content of target file
        target_file: Path to target file (for logging)

    Returns:
        Modified entry with potentially adapted old_string/new_string
    """
    # Only attempt adaptation if verification failed
    if entry.get("verified", False):
        return entry

    # Only attempt for entries with resolvable content
    old_string = entry.get("old_string", "").strip()
    new_string = entry.get("new_string", "").strip()

    if not old_string or not new_string:
        return entry

    # Check if failure is due to anchor not found
    verification_result = entry.get("verification_result", "")
    if (
        "old_not_found" not in verification_result
        and "not_found" not in verification_result
    ):
        return entry

    # Attempt semantic adaptation
    success, adapted_old, adapted_new = _attempt_semantic_adaptation(
        hunk_old_string=old_string,
        hunk_new_string=new_string,
        target_file_path=target_file,
        target_file_content=target_content,
    )

    if success and adapted_old and adapted_new:
        # Verify adapted strings exist in target
        if adapted_old in target_content:
            entry["old_string"] = adapted_old
            entry["new_string"] = adapted_new
            entry["verified"] = True
            entry["verification_result"] = f"semantic_adapted:{verification_result}"
            entry["notes"] = (str(entry.get("notes", "")) + "|semantic_adapted").strip(
                "|"
            )
            print(
                f"    Semantic adaptation succeeded for {target_file}: "
                f"adapted hunk for {verification_result}"
            )
        else:
            entry["notes"] = (
                str(entry.get("notes", "")) + "|semantic_adapted_but_anchor_not_found"
            ).strip("|")

    return entry


def _attempt_semantic_adaptation(
    hunk_old_string: str,
    hunk_new_string: str,
    target_file_path: str,
    target_file_content: str,
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Attempt semantic hunk adaptation for hunks that failed anchor resolution.

    Args:
        hunk_old_string: Old string from planning entry
        hunk_new_string: New string from planning entry
        target_file_path: Path to target file
        target_file_content: Full content of target file

    Returns:
        (success: bool, adapted_old_string: str or None, adapted_new_string: str or None)
    """
    try:
        adapter = SemanticHunkAdapter()
        result = adapter.analyze_and_adapt(
            hunk_old_string=hunk_old_string,
            hunk_new_string=hunk_new_string,
            target_file_content=target_file_content,
            target_file_path=target_file_path,
        )

        # Only accept adaptations with high confidence
        if result.success and result.confidence >= 0.6:
            return (
                True,
                result.adapted_old_string,
                result.adapted_new_string,
            )

        # Log adaptation attempts even if they failed
        if result.confidence >= 0.4:
            print(
                f"  Semantic adaptation for {target_file_path}: "
                f"confidence={result.confidence:.2f}, strategy={result.strategy.value}"
            )

    except Exception as e:
        # Log but don't fail - adaptation is best-effort
        print(f"  Semantic adaptation error for {target_file_path}: {e}")

    return False, None, None


# ---------------------------------------------------------------------------
# LLM Fallback for Unverified Hunks (Option 2 Implementation)
# ---------------------------------------------------------------------------


def _build_llm_adaptation_prompt(
    entry: dict[str, Any],
    target_file_path: str,
    target_content: str,
    mainline_file: str,
    raw_hunk: str,
    consistency_map: dict | None = None,
) -> str:
    """Build a prompt for LLM to adapt an unverified hunk"""

    old_string = entry.get("old_string", "").strip()
    new_string = entry.get("new_string", "").strip()
    verification_result = entry.get("verification_result", "")
    hunk_index = entry.get("hunk_index", 0)

    # Get surrounding context from target file
    target_lines = target_content.splitlines()
    insertion_line = min(entry.get("insertion_line", 100), len(target_lines) - 1)

    context_start = max(0, insertion_line - 15)
    context_end = min(len(target_lines), insertion_line + 15)
    context_lines = target_lines[context_start:context_end]
    context = "\n".join(context_lines)

    cm_section = ""
    if consistency_map:
        cm_str = "\n".join(f"  {k} -> {v}" for k, v in consistency_map.items())
        cm_section = f"\nConsistency Map (apply these renames):\n{cm_str}\n"

    prompt = f"""Your task is to review a mainline patch hunk, find the equivalent code in the target file, and adapt the specific operation that failed.

Here is the original mainline hunk making changes to {mainline_file} (hunk #{hunk_index}):
```diff
{raw_hunk}
```
{cm_section}
The specific operation that failed to apply is extracting this code:
OLD: {old_string}
NEW: {new_string}

However, the exact old_string does NOT exist in the target file {target_file_path}.
This likely means the target uses a different code pattern or API.

Here is the target file code around line {insertion_line} where this change should apply:

```java
{context}
```

Your task:
1. Understand what the mainline patch is trying to achieve semantically
2. Find the equivalent code pattern in the target file above
3. Apply the symbol renames from the consistency map if applicable
4. Provide the adapted old_string and new_string that would apply the same semantic fix to target's code

CRITICAL: Do not invent completely new variables or methods. Use the exact variables present in the target code or the consistency map.

Respond ONLY with valid JSON in this exact format, no other text:
{{
  "semantic_intent": "description of what the patch is trying to fix",
  "found_equivalent": true/false,
  "equivalent_old_string": "EXACT on-disk text from the target file that needs to be removed/replaced",
  "equivalent_new_string": "what to change it to, applying the same semantic fix",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

If you cannot find an equivalent pattern, set found_equivalent to false and return empty strings."""

    return prompt


async def _adapt_unverified_hunks_with_llm(
    plan: dict[str, list[dict[str, Any]]],
    target_repo_path: str,
    mainline_file: str,
    token_usage: dict,
    raw_hunks: list[str] = None,
    consistency_map: dict | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    For any hunk that failed verification, use LLM to find and adapt it to target code.
    This implements Option 2: LLM-Based Adaptation Fallback.
    """

    llm = get_llm(temperature=0)
    adapted_plan = defaultdict(list)

    for file_path, entries in plan.items():
        adapted_plan[file_path] = []
        target_content = _read_target_file(target_repo_path, file_path)

        seen_operations = set()

        for entry in entries:
            # Only try to adapt if verification failed
            if entry.get("verified", False):
                adapted_plan[file_path].append(entry)
                continue

            # Deduplicate by hunk_index and operation_index
            hidx = entry.get("hunk_index")
            oidx = entry.get("operation_index")
            op_key = (hidx, oidx)
            if op_key in seen_operations and hidx is not None:
                adapted_plan[file_path].append(entry)
                continue
            seen_operations.add(op_key)

            old_string = (entry.get("old_string") or "").strip()
            if not old_string:
                # Can't adapt empty old_string
                adapted_plan[file_path].append(entry)
                continue

            if not target_content:
                # Can't adapt without target content
                adapted_plan[file_path].append(entry)
                continue

            try:
                # Identify the raw hunk for this entry
                raw_hunk = ""
                if raw_hunks and entry.get("hunk_index") is not None:
                    hidx = entry.get("hunk_index")
                    if 0 <= hidx < len(raw_hunks):
                        raw_hunk = raw_hunks[hidx]

                # Build LLM prompt
                prompt = _build_llm_adaptation_prompt(
                    entry,
                    file_path,
                    target_content,
                    mainline_file,
                    raw_hunk,
                    consistency_map,
                )

                # Call LLM
                print(
                    f"    Planning Agent: Using LLM to adapt hunk {entry.get('hunk_index')} in {file_path}"
                )
                response = llm.invoke([HumanMessage(content=prompt)])
                response_text = response.content.strip()

                # Parse JSON response
                import json

                # Try to find JSON in response (it might have extra text)
                json_match = response_text
                if "{" in response_text and "}" in response_text:
                    json_match = response_text[
                        response_text.index("{") : response_text.rindex("}") + 1
                    ]

                adaptation = json.loads(json_match)

                # Check if adaptation was successful
                if (
                    adaptation.get("found_equivalent", False)
                    and adaptation.get("confidence", 0) >= 0.6
                ):
                    adapted_old = (
                        adaptation.get("equivalent_old_string") or ""
                    ).strip()
                    adapted_new = (
                        adaptation.get("equivalent_new_string") or ""
                    ).strip()

                    if adapted_old and adapted_new:
                        # Use adapted strings
                        entry["old_string"] = adapted_old
                        entry["new_string"] = adapted_new
                        entry["verified"] = True
                        entry["verification_result"] = (
                            f"llm_adapted:{adaptation.get('confidence', 0.0):.2f}"
                        )
                        entry["notes"] = (
                            (entry.get("notes") or "")
                            + f"|llm_intent:{adaptation.get('semantic_intent', '')}"
                        ).strip("|")

                        print(
                            f"    Planning Agent: LLM adapted {file_path}[{entry.get('hunk_index')}] "
                            f"with confidence {adaptation.get('confidence', 0.0):.2f}"
                        )

                adapted_plan[file_path].append(entry)

            except json.JSONDecodeError as e:
                print(
                    f"    Planning Agent: Could not parse LLM response for {file_path}[{entry.get('hunk_index')}]: {e}"
                )
                adapted_plan[file_path].append(entry)
            except Exception as e:
                print(
                    f"    Planning Agent: LLM adaptation failed for {file_path}[{entry.get('hunk_index')}]: {e}"
                )
                adapted_plan[file_path].append(entry)

    return dict(adapted_plan)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


async def planning_agent_node(state: AgentState, config) -> dict:
    print("Planning Agent: Building per-hunk str_replace edit plans...")

    patch_diff = state.get("patch_diff") or ""
    mapped_target_context = state.get("mapped_target_context") or {}
    target_repo_path = state.get("target_repo_path") or ""
    mainline_repo_path = state.get("mainline_repo_path") or ""
    original_commit = state.get("original_commit") or "HEAD"
    with_test_changes = state.get("with_test_changes", False)
    validation_attempts = int(state.get("validation_attempts") or 0)
    retry_files_raw = state.get("validation_retry_files") or []
    retry_hunks_raw = state.get("validation_retry_hunks") or []
    validation_error_context = str(state.get("validation_error_context") or "")
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

    plan: dict[str, list[dict[str, Any]]] = defaultdict(list)
    token_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated": False,
        "sources": [],
    }
    model_name = resolve_model_name()
    mainline_pre_cache: dict[str, str] = {}

    truncated_failure_context = validation_error_context
    if len(truncated_failure_context) > 2000:
        truncated_failure_context = (
            truncated_failure_context[:1200]
            + "\n... [TRUNCATED] ...\n"
            + truncated_failure_context[-700:]
        )

    for mainline_file, raw_hunks in (raw_hunks_by_file or {}).items():
        normalized_mainline = str(mainline_file).replace("\\", "/").strip().lstrip("/")
        if not _is_java_code_file(normalized_mainline):
            continue
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

            required_entries = _decompose_hunk_to_required_entries(
                hunk_idx=hidx,
                raw_hunk=raw_hunk,
                target_file=target_file,
                consistency_map=consistency_map,
            )

            target_content = _read_target_file(target_repo_path, target_file)
            sanitized_entries = list(required_entries)
            if target_content:
                sanitized_entries = [
                    _sanitize_entry_against_target(e, target_content)
                    for e in required_entries
                ]

            old_start, old_count, _new_start, _new_count = _parse_hunk_header(raw_hunk)
            target_start = int(ctx.get("start_line") or old_start or 1)

            if mainline_file not in mainline_pre_cache:
                mainline_pre_cache[mainline_file] = _read_mainline_prepatch_file(
                    mainline_repo_path,
                    original_commit,
                    mainline_file,
                )
            mainline_pre = mainline_pre_cache.get(mainline_file) or ""

            main_before, main_after = _extract_surrounding_lines(
                mainline_pre,
                old_start,
                old_start + max(1, old_count) - 1,
                window=3,
            )
            target_before, target_after = _extract_surrounding_lines(
                target_content,
                target_start,
                target_start + max(1, old_count) - 1,
                window=3,
            )

            loc_match = _location_match(
                mainline_file,
                target_file,
                old_start,
                target_start,
            )
            surr_match = _surrounding_match(
                main_before,
                main_after,
                target_before,
                target_after,
            )

            planner_prompt = _build_hunk_planner_prompt(
                mainline_file=mainline_file,
                target_file=target_file,
                hunk_index=hidx,
                raw_hunk=raw_hunk,
                mainline_old_start=old_start,
                target_start_line=target_start,
                mainline_pre_before=main_before,
                mainline_pre_after=main_after,
                target_before=target_before,
                target_after=target_after,
                consistency_map=consistency_map,
                deterministic_entries=sanitized_entries,
                retry_failure_context=truncated_failure_context,
            )

            planner_messages = [
                SystemMessage(content=_PLANNER_SYSTEM),
                HumanMessage(content=planner_prompt),
            ]

            payload = None
            try:
                response = await llm.ainvoke(planner_messages)
                usage = extract_usage_from_response(response)
                if usage and (usage["input_tokens"] or usage["output_tokens"]):
                    add_usage(
                        token_usage,
                        usage["input_tokens"],
                        usage["output_tokens"],
                        "planning_agent.provider_usage",
                    )
                else:
                    approx_in = count_text_tokens(
                        _PLANNER_SYSTEM + "\n" + planner_prompt,
                        model_name,
                    )
                    response_text = (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    )
                    add_usage(
                        token_usage,
                        approx_in,
                        count_text_tokens(str(response_text), model_name),
                        "planning_agent.tiktoken",
                    )
                    token_usage["estimated"] = True

                response_text = (
                    response.content if hasattr(response, "content") else str(response)
                )
                payload = _extract_json_payload(str(response_text))
            except Exception as e:
                print(
                    f"    Planning Agent: LLM planning failed for {target_file}[{hidx}]: {e}"
                )

            llm_entries = _normalize_planner_response_entries(
                payload if isinstance(payload, dict) else {},
                sanitized_entries,
                target_file,
                hidx,
            )
            if not llm_entries:
                llm_entries = list(sanitized_entries)

            entries = _ensure_required_coverage(llm_entries, required_entries)

            blockers = []
            namespace_only_possible = False
            namespace_changes = []
            explicit_type = ""
            if isinstance(payload, dict):
                blockers = payload.get("blockers") or []
                if not isinstance(blockers, list):
                    blockers = [str(blockers)]
                namespace_only_possible = bool(
                    payload.get("namespace_only_possible", False)
                )
                namespace_changes = payload.get("namespace_changes") or []
                if not isinstance(namespace_changes, list):
                    namespace_changes = []
                explicit_type = str(payload.get("adaptation_type") or "")

            adaptation_type = _infer_adaptation_type(
                location_match=loc_match,
                blockers=[str(x) for x in blockers],
                namespace_only_possible=namespace_only_possible,
                explicit=explicit_type,
            )
            if adaptation_type == "TYPE_I" and not loc_match:
                adaptation_type = "TYPE_II"

            normalized_entries: list[dict[str, Any]] = []
            for entry in entries:
                entry = (
                    _sanitize_entry_against_target(entry, target_content)
                    if target_content
                    else dict(entry)
                )
                entry = _attach_entry_surround_context(entry, target_content)
                entry["adaptation_type"] = adaptation_type
                entry["location_match"] = loc_match
                entry["surrounding_match"] = surr_match
                entry["blockers"] = [str(x) for x in blockers]
                entry["namespace_only_possible"] = namespace_only_possible
                entry["namespace_changes"] = namespace_changes
                normalized_entries.append(entry)

            plan[mainline_file].extend(normalized_entries)

    total_entries = sum(len(v) for v in plan.values())
    print(f"Planning Agent: Complete. Planned {total_entries} adapted edit(s).")

    # Generate plan signature for retry loop dedup
    import hashlib

    plan_json = json.dumps(dict(plan), sort_keys=True)
    plan_sig = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()

    return {
        "messages": [
            HumanMessage(
                content=f"Planning Agent complete. Planned {total_entries} str_replace edit(s)."
            )
        ],
        "hunk_generation_plan": dict(plan),
        "last_plan_signature": plan_sig,
        "token_usage": token_usage,
    }
