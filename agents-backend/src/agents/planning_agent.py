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
  Preferred tool order for anchor discovery:
    1. find_method_definitions (locate method/class declaration lines)
    2. ripgrep_in_file(pattern, offset, limit) for paginated regex search
    3. find_symbol_references(symbol, offset, limit) for call-site anchors
    4. read_file_window / get_exact_lines for exact nearby text
    5. verify_context_at_line for final confirmation

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
        req_old = str(req.get("old_string") or "")
        req_new = str(req.get("new_string") or "")
        matched = False
        for got in out:
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


def _parse_grep_hits(grep_output: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for line in (grep_output or "").splitlines():
        m = re.search(r"Line\s+(\d+):\s?(.*)$", line)
        if not m:
            continue
        try:
            hits.append((int(m.group(1)), m.group(2)))
        except ValueError:
            continue
    return hits


def _candidate_probe_terms(raw_hunk: str) -> list[str]:
    """Build ordered, de-duplicated probe terms for low-confidence anchor recovery."""
    terms: list[str] = []

    def _add_lines(block: str) -> None:
        for line in (block or "").splitlines():
            s = line.strip()
            if (
                not s
                or len(s) < 8
                or s in {"{", "}", "(", ")", ";"}
                or s.startswith("//")
                or s.startswith("*")
            ):
                continue
            terms.append(s)

    _add_lines(_extract_removed_text(raw_hunk))
    _add_lines("\n".join(_extract_context_lines(raw_hunk)))
    _add_lines(_extract_added_text(raw_hunk))

    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


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
            insertion_line = int(ctx.get("start_line") or 1)
            code_snippet = ctx.get("code_snippet") or ""
            anchor_confidence = str(ctx.get("anchor_confidence") or "").strip().lower()
            anchor_reason = str(ctx.get("anchor_reason") or "")

            low_confidence_mode = anchor_confidence == "low"
            low_confidence_reason = f"mapping_low_confidence:{anchor_reason}"
            if low_confidence_mode and toolkit:
                # Do not fail-closed on low confidence. Try direct in-file anchor recovery.
                for probe in _candidate_probe_terms(raw_hunk)[:8]:
                    grep_out = toolkit.grep_in_file(
                        target_file,
                        probe,
                        is_regex=False,
                        max_results=5,
                    )
                    hits = _parse_grep_hits(grep_out)
                    if not hits:
                        continue
                    insertion_line = hits[0][0]
                    low_confidence_reason += f"|probe_anchor:{probe}"
                    break

            required_entries = _decompose_hunk_to_required_entries(
                hunk_idx=hidx,
                raw_hunk=raw_hunk,
                target_file=target_file,
                consistency_map=consistency_map,
            )

            if low_confidence_mode:
                for req in required_entries:
                    req["notes"] = (
                        str(req.get("notes") or "") + f"|{low_confidence_reason}"
                    ).strip("|")
                    req["verification_result"] = (
                        str(req.get("verification_result") or "")
                        + "|mapping_low_confidence_recovery"
                    ).strip("|")

            planned_entries: list[dict[str, Any]] = []

            if react and toolkit:
                for req in required_entries:
                    edit_type_hint = str(
                        req.get("edit_type") or _classify_edit_type(raw_hunk)
                    )
                    prompt = (
                        f"Target file: {target_file}\n"
                        f"Mapped insertion line (approximate): {insertion_line}\n"
                        f"Hunk index: {hidx}\n"
                        f"Operation index: {req.get('operation_index', 0)}\n"
                        f"Required edit_type: {edit_type_hint}\n"
                        f"Required old_string (candidate):\n```text\n{req.get('old_string', '')}\n```\n"
                        f"Required new_string (candidate):\n```text\n{req.get('new_string', '')}\n```\n\n"
                        f"Mainline hunk to adapt:\n```diff\n{raw_hunk}\n```\n\n"
                        f"Context snippet from Agent 2 (may be from mainline, verify in target):\n"
                        f"```java\n{code_snippet[:600]}\n```\n\n"
                        f"ConsistencyMap (apply these renames to new_string added content):\n"
                        + (
                            "\n".join(
                                f"  {k} -> {v}" for k, v in consistency_map.items()
                            )
                            if consistency_map
                            else "  (none)"
                        )
                        + "\n\n"
                        "Use tools to verify old_string in the real target file and output ONE JSON object. "
                        "Do not drop this required operation."
                    )

                    entry = dict(req)
                    try:
                        prompt_tokens = count_text_tokens(
                            _PLANNER_SYSTEM + "\n" + prompt, model_name
                        )
                        res = await react.ainvoke(
                            {"messages": [("user", prompt)]},
                            config={"recursion_limit": 25},
                        )
                        msgs = res.get("messages", [])

                        exact_any = False
                        for m in msgs:
                            if getattr(m, "type", "") != "ai":
                                continue
                            usage = extract_usage_from_response(m)
                            if usage and (
                                usage["input_tokens"] or usage["output_tokens"]
                            ):
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
                        payload = _extract_json_payload(final)
                        parsed_obj = None
                        if isinstance(payload, dict):
                            parsed_obj = payload
                        elif isinstance(payload, list) and payload:
                            # If model returns a list unexpectedly, pick first dict.
                            for x in payload:
                                if isinstance(x, dict):
                                    parsed_obj = x
                                    break

                        if parsed_obj:
                            for k in (
                                "edit_type",
                                "old_string",
                                "new_string",
                                "verified",
                                "verification_result",
                                "notes",
                            ):
                                if k in parsed_obj:
                                    entry[k] = parsed_obj[k]
                        else:
                            entry["notes"] = (
                                str(entry.get("notes") or "")
                                + "|planner_parse_fallback"
                            ).strip("|")
                            print(
                                f"    Planning Agent: Could not parse JSON for "
                                f"{target_file}[{hidx}] op={req.get('operation_index', 0)} - using required fallback."
                            )
                    except Exception as e:
                        entry["notes"] = (
                            str(entry.get("notes") or "") + f"|planner_tool_error:{e}"
                        ).strip("|")
                        print(
                            f"    Planning Agent: Error on {target_file}[{hidx}] op={req.get('operation_index', 0)}: {e} "
                            "- using required fallback."
                        )

                    planned_entries.append(entry)
            else:
                planned_entries = list(required_entries)

            # Hard coverage guarantee: never drop deterministic required operations.
            planned_entries = _ensure_required_coverage(
                planned_entries, required_entries
            )

            target_content = _read_target_file(target_repo_path, target_file)
            if target_content:
                planned_entries = [
                    _sanitize_entry_against_target(e, target_content)
                    for e in planned_entries
                ]

            # Sanitize + append all operations for this source hunk.
            for entry in planned_entries:
                default_type = _classify_edit_type(raw_hunk)
                entry["hunk_index"] = hidx
                entry["target_file"] = target_file
                entry["edit_type"] = (
                    str(entry.get("edit_type") or default_type).strip().lower()
                )
                if entry["edit_type"] not in {
                    "replace",
                    "insert_after",
                    "insert_before",
                    "delete",
                }:
                    entry["edit_type"] = default_type
                entry["verified"] = bool(entry.get("verified", False))
                entry.setdefault("old_string", "")
                entry.setdefault("new_string", "")
                entry.setdefault("verification_result", "")
                entry.setdefault("notes", "")
                entry.pop("operation_index", None)
                plan[mainline_file].append(entry)

    total_entries = sum(len(v) for v in plan.values())
    print(f"Planning Agent: Complete. Planned {total_entries} edit(s).")

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
