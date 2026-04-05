"""
Pre-flight validation for planning-agent str_replace edit plans (Agent 3).

Blocks the class of bugs where a micro-edit inserts constructor / instance
initialization statements immediately before a method signature, producing
orphaned statements at class scope and useless ReAct burn.

Defense layers:
  1) Static heuristics (fast, no I/O)
  2) In-memory dry apply (same resolution rules as file_editor)
  3) Tree-sitter Java parse — ERROR nodes indicate broken structure
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Tree-sitter (optional — same stack as method_fingerprinter)
# ---------------------------------------------------------------------------

_ts_parser = None


def _get_java_parser():
    global _ts_parser
    if _ts_parser is not None:
        return _ts_parser
    try:
        from tree_sitter import Language, Parser
        import tree_sitter_java

        lang = Language(tree_sitter_java.language())
        p = Parser(lang)
        _ts_parser = p
        return p
    except Exception:
        return None


def java_source_has_tree_sitter_errors(source: str) -> bool:
    """
    Return True if the Java source likely has structural issues (unbalanced blocks, etc.).
    Falls open (False) if tree-sitter is unavailable.
    """
    parser = _get_java_parser()
    if not parser or not (source or "").strip():
        return False
    try:
        tree = parser.parse(bytes(source, "utf8"))
        err = getattr(tree, "root_node", None)
        if err is None:
            return False

        def walk_has_error(node) -> bool:
            if node.type == "ERROR" or node.is_missing:
                return True
            for i in range(node.child_count):
                if walk_has_error(node.child(i)):
                    return True
            return False

        return walk_has_error(tree.root_node)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Static rules
# ---------------------------------------------------------------------------

_METHOD_DECL_LINE = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*"
    r"(?:public|protected|private)\s+"
    r"(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:native\s+)?(?:abstract\s+)?(?:strictfp\s+)?"
    r"(?:<[^>]+>\s+)?[\w.<>,\[\]\s]+\s+\w+\s*\(",
    re.MULTILINE,
)

_THIS_ASSIGN = re.compile(
    r"^\s*this\.\s*\w+\s*=",
    re.MULTILINE,
)

_OUTSIDE_BLOCK_MARKERS = (
    "illegal start of type",
    "class, interface, or enum expected",
    "')' expected",
    "not a statement",
)


def classify_syntax_failure_message(msg: str) -> str:
    """
    Bucket javac / checker output for escalation policy.
    """
    m = (msg or "").lower()
    for marker in _OUTSIDE_BLOCK_MARKERS:
        if marker in m:
            return "statement_outside_block"
    if "illegal start of type" in m:
        return "statement_outside_block"
    return "other_syntax"


def _extract_insert_payload(
    edit_type: str, old_string: str, new_string: str
) -> str | None:
    et = (edit_type or "replace").lower()
    old_string = (old_string or "").replace("\r\n", "\n").replace("\r", "\n")
    new_string = (new_string or "").replace("\r\n", "\n").replace("\r", "\n")
    if et == "replace":
        return None
    if et == "insert_before":
        for anchor in [old_string]:
            if not anchor:
                continue
            idx = new_string.rfind(anchor)
            if idx >= 0:
                return new_string[:idx]
        new_lines = new_string.splitlines()
        old_lines = old_string.splitlines()
        if old_lines and len(new_lines) >= len(old_lines):
            tail = new_lines[-len(old_lines) :]
            if all(
                tail[i].strip() == old_lines[i].strip() for i in range(len(old_lines))
            ):
                payload = "\n".join(new_lines[: -len(old_lines)])
                if new_string.endswith("\n"):
                    payload += "\n"
                return payload
        return None
    if et == "insert_after":
        for anchor in [old_string]:
            if not anchor:
                continue
            idx = new_string.find(anchor)
            if idx >= 0:
                return new_string[idx + len(anchor) :]
        new_lines = new_string.splitlines()
        old_lines = old_string.splitlines()
        if old_lines and len(new_lines) >= len(old_lines):
            head = new_lines[: len(old_lines)]
            if all(
                head[i].strip() == old_lines[i].strip() for i in range(len(old_lines))
            ):
                payload = "\n".join(new_lines[len(old_lines) :])
                if payload and not payload.startswith("\n") and "\n" in new_string:
                    payload = "\n" + payload
                return payload
        return None
    return None


def static_validate_plan_entry(entry: dict[str, Any]) -> tuple[bool, str]:
    """
    Reject obviously invalid micro-ops before any file I/O.
    """
    edit_type = str((entry or {}).get("edit_type") or "replace").lower()
    old_string = str((entry or {}).get("old_string") or "")
    new_string = str((entry or {}).get("new_string") or "")

    if edit_type in {"insert_before", "insert_after"}:
        payload = _extract_insert_payload(edit_type, old_string, new_string)
        if payload is None:
            payload = new_string
        plines = [ln for ln in payload.splitlines() if ln.strip()]
        if not plines:
            return True, "ok"

        anchor_lines = [
            ln for ln in old_string.strip().splitlines() if ln.strip()
        ]
        looks_like_method = any(
            bool(_METHOD_DECL_LINE.search(ln)) for ln in anchor_lines[:5]
        )

        if looks_like_method and _THIS_ASSIGN.search(payload):
            return (
                False,
                "static_reject:this_assignment_before_method_signature",
            )

        for ln in plines[:5]:
            if _THIS_ASSIGN.match(ln) and looks_like_method:
                return (
                    False,
                    "static_reject:this_assignment_with_method_anchor",
                )

    return True, "ok"


# ---------------------------------------------------------------------------
# In-memory apply (mirrors agents/file_editor._apply_edit_deterministically)
# ---------------------------------------------------------------------------


def _resolve_old(content_text: str, candidate: str) -> tuple[str, str]:
    content_text = (content_text or "").replace("\r\n", "\n").replace("\r", "\n")
    candidate = (candidate or "").replace("\r\n", "\n").replace("\r", "\n")

    if candidate in content_text:
        return candidate, "exact"

    cand_lines_raw = candidate.splitlines()
    file_lines_raw = content_text.splitlines()
    if cand_lines_raw:
        n = len(cand_lines_raw)
        for i in range(len(file_lines_raw) - n + 1):
            match = True
            for j in range(n):
                if file_lines_raw[i + j].rstrip() != cand_lines_raw[j].rstrip():
                    match = False
                    break
            if match:
                return (
                    "\n".join(file_lines_raw[i : i + n]),
                    "line_trailing_whitespace_agnostic",
                )

    if "\n" not in candidate:
        stripped = candidate.strip()
        if not stripped:
            return "", "empty_candidate"
        line_matches = [
            line for line in content_text.splitlines() if line.strip() == stripped
        ]
        if len(line_matches) == 1:
            return line_matches[0], "line_trimmed_unique"
        if candidate.lstrip() != candidate and candidate.lstrip() in content_text:
            return candidate.lstrip(), "lstrip_exact"
        return "", "not_found_single"

    cand_lines = candidate.splitlines()
    file_lines = content_text.splitlines()
    if not cand_lines:
        return "", "empty_multiline"
    n = len(cand_lines)
    hits: list[str] = []
    for i in range(0, len(file_lines) - n + 1):
        ok = True
        for j in range(n):
            if file_lines[i + j].strip() != cand_lines[j].strip():
                ok = False
                break
        if ok:
            hits.append("\n".join(file_lines[i : i + n]))
    if len(hits) == 1:
        return hits[0], "multiline_trimmed_unique"

    anchor_idx = -1
    anchor_line = ""
    best_len = -1
    for i, line in enumerate(cand_lines):
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
                    if window[j].strip() == cand_lines[j].strip():
                        matched += 1
                if n > 0 and matched * 2 >= n:
                    return (
                        "\n".join(window),
                        "multiline_anchor_reconstructed",
                    )
    return "", "not_found_multiline"


def apply_single_plan_entry_to_content(
    content: str, plan_entry: dict[str, Any]
) -> tuple[bool, str, str]:
    """
    Apply one plan entry to a string buffer. Does not touch disk.
    Returns (ok, message, new_content).
    """
    edit_type = str(plan_entry.get("edit_type") or "replace").lower()
    old_string = str(plan_entry.get("old_string") or "")
    new_string = str(plan_entry.get("new_string") or "")

    if not old_string:
        return False, "empty_old_string", content

    resolved_old, reason = _resolve_old(content, old_string)
    if not resolved_old:
        return False, f"old_resolution_failed:{reason}", content

    resolved_new = new_string
    if edit_type in {"insert_before", "insert_after"}:
        payload = None
        for anchor in [old_string, resolved_old]:
            if not anchor:
                continue
            if edit_type == "insert_before":
                idx = new_string.rfind(anchor)
                if idx >= 0:
                    payload = new_string[:idx]
                    break
            else:
                idx = new_string.find(anchor)
                if idx >= 0:
                    payload = new_string[idx + len(anchor) :]
                    break

        if payload is None:
            new_lines = new_string.splitlines()
            old_lines = old_string.splitlines()
            if old_lines and len(new_lines) >= len(old_lines):
                if edit_type == "insert_before":
                    tail = new_lines[-len(old_lines) :]
                    if all(
                        tail[i].strip() == old_lines[i].strip()
                        for i in range(len(old_lines))
                    ):
                        payload = "\n".join(new_lines[: -len(old_lines)])
                        if new_string.endswith("\n"):
                            payload += "\n"
                else:
                    head = new_lines[: len(old_lines)]
                    if all(
                        head[i].strip() == old_lines[i].strip()
                        for i in range(len(old_lines))
                    ):
                        payload = "\n".join(new_lines[len(old_lines) :])
                        if (
                            payload
                            and not payload.startswith("\n")
                            and "\n" in new_string
                        ):
                            payload = "\n" + payload

        if payload is None:
            return False, "insert_payload_derivation_failed", content

        if edit_type == "insert_before" and payload and not payload.endswith("\n"):
            payload += "\n"
        if edit_type == "insert_after" and payload and not payload.startswith("\n"):
            payload = "\n" + payload

        resolved_new = (
            payload + resolved_old
            if edit_type == "insert_before"
            else resolved_old + payload
        )

    if resolved_old not in content:
        return False, "resolved_old_not_in_content", content
    count = content.count(resolved_old)
    if count > 1:
        return False, "ambiguous_old_string", content
    new_content = content.replace(resolved_old, resolved_new, 1)
    return True, f"applied:{reason}", new_content


def dry_apply_plan_entries(content: str, entries: list[dict[str, Any]]) -> tuple[bool, str, str]:
    """
    Apply all entries sequentially in memory.
    Returns (ok, reason, final_content).
    """
    work = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    for i, entry in enumerate(entries or []):
        ok, msg, work = apply_single_plan_entry_to_content(work, entry)
        if not ok:
            return False, f"dry_apply_failed[{i}]:{msg}", work
    return True, "dry_apply_ok", work


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class PlanPreflightResult:
    ok: bool
    reason: str
    static_warnings: list[str]
    dry_run_ok: bool
    tree_sitter_ok: bool


def validate_plan_before_apply(
    *,
    plan_entries: list[dict[str, Any]],
    file_content: str,
    target_file: str,
) -> PlanPreflightResult:
    """
    Run static checks, then dry apply + tree-sitter validation.
    """
    warnings: list[str] = []
    entries = list(plan_entries or [])

    for i, entry in enumerate(entries):
        ok, reason = static_validate_plan_entry(entry)
        if not ok:
            return PlanPreflightResult(
                ok=False,
                reason=f"PLAN_STATIC_REJECT:{reason}[entry={i}]",
                static_warnings=warnings,
                dry_run_ok=False,
                tree_sitter_ok=False,
            )

    dry_ok, dry_msg, merged = dry_apply_plan_entries(file_content, entries)
    if not dry_ok:
        return PlanPreflightResult(
            ok=False,
            reason=f"PLAN_DRY_APPLY_FAILED:{dry_msg}",
            static_warnings=warnings,
            dry_run_ok=False,
            tree_sitter_ok=False,
        )

    skip_ts = (os.getenv("PLAN_VALIDATOR_SKIP_TREE_SITTER", "") or "").strip() in (
        "1",
        "true",
        "yes",
    )
    ts_bad = (not skip_ts) and target_file.lower().endswith(
        ".java"
    ) and java_source_has_tree_sitter_errors(merged)
    if ts_bad:
        return PlanPreflightResult(
            ok=False,
            reason="PLAN_TREE_SITTER_REJECT:parse_has_error_nodes",
            static_warnings=warnings,
            dry_run_ok=True,
            tree_sitter_ok=False,
        )

    return PlanPreflightResult(
        ok=True,
        reason="preflight_ok",
        static_warnings=warnings,
        dry_run_ok=True,
        tree_sitter_ok=True,
    )


def _normalize_for_substring_compare(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip())


def consolidate_plan_entries_java(
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge planner fragmentation: drop insert_before/insert_after hunks whose only job is
    a `this.field = ...` assignment already present in a replace new_string.
    """
    if not entries:
        return entries
    merged_replace = "\n".join(
        str(e.get("new_string") or "")
        for e in entries
        if str(e.get("edit_type") or "").lower() == "replace"
    )
    nr = _normalize_for_substring_compare(merged_replace)
    out: list[dict[str, Any]] = []
    for e in entries:
        et = str(e.get("edit_type") or "").lower()
        if et not in ("insert_before", "insert_after"):
            out.append(e)
            continue
        payload = _extract_insert_payload(
            et,
            str(e.get("old_string") or ""),
            str(e.get("new_string") or ""),
        )
        if payload is None:
            payload = str(e.get("new_string") or "")
        drop = False
        for line in payload.splitlines():
            s = line.strip()
            if not s:
                continue
            if _THIS_ASSIGN.match(s):
                key = _normalize_for_substring_compare(s.rstrip(";"))
                if len(key) >= 8 and key in nr:
                    drop = True
                    break
        if not drop:
            out.append(e)
    return out
