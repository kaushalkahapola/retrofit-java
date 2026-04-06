"""
Reasoning Architect

Per-file diagnostic planning node that produces verified surgical operations
for deterministic application by Agent 3 (File Editor).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from agents.failure_diagnosis import FailureDiagnosisEngine, FailureKind
from agents.hunk_generator_tools import HunkGeneratorToolkit
from agents.type_v_rulebook import TypeVRulebook
from state import AgentState, SurgicalOp

from utils.llm_provider import get_llm
from utils.plan_validator import _resolve_old as _resolve_old_in_content
from utils.token_counter import add_usage, aggregate_usage_from_messages


_REASONING_SYSTEM = """You are ReasoningArchitect — a senior Java backporting specialist working inside the H-MABS system.

[ROLE & AUTONOMY]
You are meticulous and safety-first. Your only goal is to produce a verified, minimal, deterministic surgical plan that resolves compilation and API drift failures.
You never edit files directly. You only diagnose and plan.

[AUTONOMY BUDGET]
- You MUST start with diagnosis tools.
- You are authorized to inspect ANY file in the related_files list (including parents and callers/callees).
- You may propose edits to multiple files if needed to resolve cascading signature changes (e.g. fullDocSizeEstimate propagation).
- You are NOT allowed to make repetitive tool calls with identical arguments.

[EXECUTION PROTOCOL — follow strictly]
1. Always begin by calling diagnose_api_drift.
2. Use read_target_code_window / grep_in_target_file to verify anchors in the target file.
3. When signature or API drift is detected, use compare_mainline_target and read_repo_code_window on connected files.
4. Understand parent classes and callers/callees before proposing changes.
5. Propose only minimal changes that preserve original intent.
6. Every operation must have anchor_verified=true and be verifiable with exact string match (or resolved whitespace).

[OUTPUT CONTRACT — use exactly this structure]
<thinking>Brief internal reasoning (1-3 sentences). What is the root cause? What files are in scope?</thinking>
[DIAGNOSIS] Root cause + API drift summary + sphere of influence.
[PLAN]
```json
[
  {{
    "target_file": "...",
    "old_string": "...",
    "new_string": "...",
    "anchor_verified": true,
    "verification_method": "exact",
    "confidence": 0.85
  }}
]
```
[CONFIDENCE] high/medium/low + one-sentence justification

[STRICT RULES]
- Process ONE primary file at a time. Do not bleed context from previous files.
- Never repeat the same tool call with the same arguments twice.
- If anchor not found, shrink search window and re-read — do not guess large blocks.
- When proposing changes to parent/connected files, explain why in <thinking>.
- Final submission must go through submit_surgical_plan only.

Current primary file: {current_file}

Related files (sphere of influence):
{related_files}

Method/symbol hints:
{method_hints}

Build diagnostics:
{build_diagnostics}

Patch intent (high-level):
{patch_intent}

Session modified files so far:
{session_modified_files}
"""


def _render_msg_content(content: Any) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text is not None:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join([p for p in parts if p]).strip()
    return str(content or "").strip()


def _truncate_for_log(text: str, max_chars: int = 5000) -> str:
    t = str(text or "")
    if len(t) <= max_chars:
        return t
    head = max_chars // 2
    tail = max_chars - head
    return t[:head] + "\n... [TRUNCATED] ...\n" + t[-tail:]


def _log_reasoning_trace(response: dict[str, Any], target_file: str) -> None:
    try:
        messages = (response or {}).get("messages", []) or []
        if not messages:
            print(f"Reasoning Architect: no trace messages for {target_file}")
            return
        print(
            "Reasoning Architect: ReAct trace for "
            f"{target_file} [BEGIN] (messages={len(messages)})"
        )
        for idx, msg in enumerate(messages, start=1):
            role = str(getattr(msg, "type", "") or "unknown").strip().lower()
            print(f"Reasoning Architect: [message {idx}] role={role}")

            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                for tc_i, tc in enumerate(tool_calls, start=1):
                    tc_name = str((tc or {}).get("name") or "")
                    tc_args = (tc or {}).get("args", {})
                    try:
                        args_text = json.dumps(tc_args, ensure_ascii=False, default=str)
                    except Exception:
                        args_text = str(tc_args)
                    print(
                        "Reasoning Architect:   tool_call["
                        f"{tc_i}] name={tc_name} args={_truncate_for_log(args_text, 2000)}"
                    )

            rendered = _render_msg_content(getattr(msg, "content", ""))
            if rendered:
                print(_truncate_for_log(rendered, 6000))

            if role == "tool":
                tool_name = str(getattr(msg, "name", "") or "")
                tool_call_id = str(getattr(msg, "tool_call_id", "") or "")
                if tool_name or tool_call_id:
                    print(
                        "Reasoning Architect:   tool_result "
                        f"name={tool_name} call_id={tool_call_id}"
                    )
        print(f"Reasoning Architect: ReAct trace for {target_file} [END]")
    except Exception as e:
        print(f"Reasoning Architect: trace logging failed for {target_file}: {e}")


def _normalize_rel_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/").lstrip("/")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p


def _load_file_text(repo_path: str, rel_path: str) -> str:
    try:
        full_path = os.path.normpath(
            os.path.join(repo_path, _normalize_rel_path(rel_path))
        )
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def _is_readable_repo_file(repo_path: str, rel_path: str) -> bool:
    p = _normalize_rel_path(rel_path)
    if not p:
        return False
    full = os.path.normpath(os.path.join(repo_path, p))
    return os.path.isfile(full)


def _extract_primary_symbol_from_context(
    structured: dict[str, Any],
    diagnostics_text: str,
) -> str:
    if isinstance(structured, dict):
        sym = str(structured.get("primary_failed_symbol") or "").strip()
        if sym:
            return sym
        for item in structured.get("symbol_errors") or []:
            name = str((item or {}).get("name") or "").strip()
            if name:
                return name
    text = str(diagnostics_text or "")
    m = re.search(r"symbol:\s+(?:variable|method|class)\s+(\w+)", text)
    if m:
        return str(m.group(1) or "").strip()
    m = re.search(r"method\s+(\w+)\([^)]*\)\s+in\s+class", text)
    if m:
        return str(m.group(1) or "").strip()
    return ""


def _extract_file_diagnostics(
    state: AgentState,
    target_file: str,
) -> dict[str, Any]:
    target = _normalize_rel_path(target_file)
    vr = state.get("validation_results") or {}
    build_diag = (
        ((vr.get("build") or {}).get("diagnostics") or {})
        if isinstance(vr, dict)
        else {}
    )
    structured = state.get("validation_error_context_structured") or {}

    filtered_issues = []
    for issue in build_diag.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        issue_file = _normalize_rel_path(str(issue.get("file") or ""))
        if issue_file and target and issue_file != target:
            continue
        filtered_issues.append(issue)

    failed_locations = []
    for loc in structured.get("failed_locations") or []:
        if not isinstance(loc, dict):
            continue
        loc_file = _normalize_rel_path(str(loc.get("file") or ""))
        if loc_file and target and loc_file != target:
            continue
        failed_locations.append(loc)

    out = {
        "target_file": target,
        "issues": filtered_issues,
        "failed_locations": failed_locations,
        "symbol_errors": structured.get("symbol_errors") or [],
        "signature_errors": structured.get("signature_errors") or [],
        "primary_failed_symbol": str(structured.get("primary_failed_symbol") or ""),
        "raw_error_preview": str(state.get("validation_error_context") or "")[:1500],
    }
    return out


def _extract_side_files_from_state(state: AgentState, target_file: str) -> list[str]:
    """
    Derive side files from validation/build diagnostics to loosen retry scope
    for API/signature drift fixes that require multi-file adaptation.
    """
    target = _normalize_rel_path(target_file)
    candidates: set[str] = set()

    vr = state.get("validation_results") or {}
    build = (vr.get("build") or {}) if isinstance(vr, dict) else {}
    diagnostics = (build.get("diagnostics") or {}) if isinstance(build, dict) else {}
    structured = state.get("validation_error_context_structured") or {}

    for issue in diagnostics.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        p = _normalize_rel_path(str(issue.get("file") or ""))
        if p:
            candidates.add(p)

    for p in diagnostics.get("retry_files") or []:
        pp = _normalize_rel_path(str(p or ""))
        if pp:
            candidates.add(pp)

    for loc in structured.get("failed_locations") or []:
        if not isinstance(loc, dict):
            continue
        p = _normalize_rel_path(str(loc.get("file") or ""))
        if p:
            candidates.add(p)

    build_raw = str(build.get("raw") or "")
    # Robust regex for both Maven/Gradle and containerized paths
    for m in re.findall(
        r"((?:/repo/)?[a-zA-Z0-9_./-]+\.java):(?:\[(\d+),\d+\]|(\d+)):", build_raw
    ):
        path_match = str(m[0] or "")
        if path_match.startswith("/repo/"):
            path_match = path_match[len("/repo/") :]
        p = _normalize_rel_path(path_match)
        if p:
            candidates.add(p)

    out = [p for p in sorted(candidates) if p and p != target]
    return out[:10]  # Slightly increase limit for more context


def _extract_related_files_and_method_hints(
    state: AgentState,
    target_file: str,
    target_repo_path: str,
) -> tuple[list[str], list[str]]:
    target = _normalize_rel_path(target_file)
    related: set[str] = set()
    hints: set[str] = set()

    for p in state.get("validation_retry_files") or []:
        pp = _normalize_rel_path(str(p or ""))
        if pp:
            related.add(pp)

    for p in state.get("force_type_v_retry_files") or []:
        pp = _normalize_rel_path(str(p or ""))
        if pp:
            related.add(pp)

    for p in _extract_side_files_from_state(state, target):
        if p:
            related.add(p)

    mapped_ctx = state.get("mapped_target_context") or {}
    if isinstance(mapped_ctx, dict):
        for _, entries in mapped_ctx.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                tf = _normalize_rel_path(str(entry.get("target_file") or ""))
                if tf:
                    related.add(tf)
                for key in ("target_method", "mainline_method"):
                    hv = str(entry.get(key) or "").strip()
                    if hv:
                        hints.add(hv)

    hgp = state.get("hunk_generation_plan") or {}
    if isinstance(hgp, dict):
        for _, entries in hgp.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                tf = _normalize_rel_path(str(entry.get("target_file") or ""))
                if tf:
                    related.add(tf)
                for k in (
                    "required_symbols",
                    "must_preserve_symbols",
                    "protected_symbols",
                ):
                    for sym in entry.get(k) or []:
                        sv = str(sym or "").strip()
                        if sv:
                            hints.add(sv)

    structured = state.get("validation_error_context_structured") or {}
    if isinstance(structured, dict):
        pf = _normalize_rel_path(str(structured.get("primary_failed_file") or ""))
        if pf:
            related.add(pf)

        ps = str(structured.get("primary_failed_symbol") or "").strip()
        if ps:
            hints.add(ps)

        for item in structured.get("symbol_errors") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                hints.add(name)

        for item in structured.get("signature_errors") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("method") or "").strip()
            if name:
                hints.add(name)

        for loc in structured.get("failed_locations") or []:
            if not isinstance(loc, dict):
                continue
            f = _normalize_rel_path(str(loc.get("file") or ""))
            if f:
                related.add(f)

    # Parent-class hint from current file (if any)
    current_text = _load_file_text(target_repo_path, target)
    m = re.search(r"class\s+\w+\s+extends\s+(\w+)", current_text)
    if m:
        parent_name = str(m.group(1) or "").strip()
        if parent_name:
            hints.add(parent_name)
            try:
                rg = subprocess.run(
                    [
                        "git",
                        "grep",
                        "-n",
                        "--full-name",
                        "-E",
                        rf"class\s+{re.escape(parent_name)}\b",
                        "HEAD",
                        "--",
                        "*.java",
                    ],
                    cwd=target_repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for ln in (rg.stdout or "").splitlines()[:10]:
                    parts = ln.split(":", 3)
                    if len(parts) < 4:
                        continue
                    pf = _normalize_rel_path(str(parts[1] or ""))
                    if pf:
                        related.add(pf)
            except Exception:
                pass

    rel_out = []
    for p in sorted(related):
        if not p:
            continue
        full = os.path.join(target_repo_path, p)
        if os.path.isfile(full):
            rel_out.append(p)
    if target and target not in rel_out:
        rel_out.insert(0, target)

    hint_out = sorted(hints)
    return rel_out[:40], hint_out[:40]


def _derive_retry_files_from_generation_checklist(state: AgentState) -> list[str]:
    out: set[str] = set()
    for item in state.get("generation_checklist") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status and status != "failed":
            continue
        for key in ("target_file", "mainline_file"):
            p = _normalize_rel_path(str(item.get(key) or ""))
            if not p or p == "<all>":
                continue
            if p.lower().endswith(".java"):
                out.add(p)
    return sorted(out)


def _sanitize_surgical_ops(
    *,
    repo_path: str,
    default_target_file: str,
    ops: list[SurgicalOp],
) -> tuple[list[SurgicalOp], list[str]]:
    """Reject unsafe/malformed operations before deterministic execution."""
    safe: list[SurgicalOp] = []
    rejected: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    default_target = _normalize_rel_path(default_target_file)

    for idx, op in enumerate(ops or []):
        if not isinstance(op, dict):
            rejected.append(f"op_{idx}: not_a_dict")
            continue

        old_s = str(op.get("old_string") or "")
        new_s = str(op.get("new_string") or "")
        op_target = _normalize_rel_path(str(op.get("target_file") or default_target))
        if not op_target:
            rejected.append(f"op_{idx}: empty_target_file")
            continue
        op_full = os.path.join(repo_path, op_target)
        if not os.path.isfile(op_full):
            rejected.append(f"op_{idx}: missing_target_file:{op_target}")
            continue

        if not bool(op.get("anchor_verified", False)):
            rejected.append(f"op_{idx}: unverified_anchor")
            continue
        if not old_s:
            rejected.append(f"op_{idx}: empty_old_string")
            continue
        if old_s == new_s:
            rejected.append(f"op_{idx}: no_op")
            continue
        if old_s.strip() in {"{", "}", ";", "(", ")"}:
            rejected.append(f"op_{idx}: weak_anchor")
            continue
        if len(old_s.strip()) < 4:
            rejected.append(f"op_{idx}: tiny_anchor")
            continue
        if "\x00" in old_s or "\x00" in new_s:
            rejected.append(f"op_{idx}: nul_bytes")
            continue
        content = _load_file_text(repo_path, op_target)
        if content and old_s not in content:
            # Before hard-rejecting, attempt whitespace-normalised resolution so
            # that LLM-guessed indentation variants don't silently drop valid ops.
            resolved_s, _resolve_reason = _resolve_old_in_content(content, old_s)
            if not resolved_s:
                rejected.append(f"op_{idx}: anchor_not_in_file")
                continue
            # Adopt the resolved anchor so the deterministic apply will succeed.
            op = dict(op)
            op["old_string"] = resolved_s
            old_s = resolved_s

        key = (op_target, old_s, new_s)
        if key in seen:
            continue
        seen.add(key)
        safe.append(
            {
                "target_file": op_target,
                "old_string": old_s,
                "new_string": new_s,
                "anchor_verified": True,
                "verification_method": str(op.get("verification_method") or "exact"),
                "confidence": float(op.get("confidence", 0.0) or 0.0),
            }
        )

    return safe, rejected


def _fallback_surgical_from_existing_plan(
    state: AgentState,
    target_file: str,
) -> list[SurgicalOp]:
    target = _normalize_rel_path(target_file)
    out: list[SurgicalOp] = []
    seen: set[tuple[str, str]] = set()
    hgp = state.get("hunk_generation_plan") or {}
    if not isinstance(hgp, dict):
        return out
    for entries in hgp.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_target = _normalize_rel_path(str(entry.get("target_file") or ""))
            if entry_target != target:
                continue
            if not bool(entry.get("verified", False)):
                continue
            old_s = str(entry.get("old_string") or "")
            if not old_s:
                continue
            new_s = str(entry.get("new_string") or "")
            key = (old_s, new_s)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "target_file": target,
                    "old_string": old_s,
                    "new_string": new_s,
                    "anchor_verified": True,
                    "verification_method": "exact",
                    "confidence": 0.75,
                }
            )
    return out


class FileIsolatedToolkit:
    """Toolkit that is physically scoped to one file."""

    def __init__(
        self,
        *,
        target_repo_path: str,
        target_file: str,
        allowed_files: list[str],
        method_hints: list[str],
        mainline_repo_path: str,
        build_diagnostics: dict[str, Any],
        validation_error_context: str,
    ):
        self.repo = target_repo_path
        self.locked_file = _normalize_rel_path(target_file)
        self.allowed_files = [
            _normalize_rel_path(p)
            for p in (allowed_files or [])
            if _normalize_rel_path(p)
        ]
        if self.locked_file and self.locked_file not in self.allowed_files:
            self.allowed_files.insert(0, self.locked_file)
        self.method_hints = [
            str(m).strip() for m in (method_hints or []) if str(m).strip()
        ]
        self.mainline = mainline_repo_path
        self.diagnostics = build_diagnostics or {}
        self.validation_error_context = str(validation_error_context or "")
        self._hg = HunkGeneratorToolkit(target_repo_path)
        self._submitted_plan: list[SurgicalOp] = []

    def read_target_code_window(self, center_line: int, radius: int = 20) -> str:
        """Read code window around a line in the primary file."""
        return self._hg.read_file_window(
            self.locked_file, int(center_line), int(radius)
        )

    def grep_in_target_file(
        self,
        search_text: str,
        is_regex: bool = False,
        max_results: int = 20,
    ) -> str:
        """Search text in the primary file and return line hits."""
        return self._hg.grep_in_file(
            file_path=self.locked_file,
            search_text=str(search_text or ""),
            is_regex=bool(is_regex),
            max_results=max(1, min(int(max_results or 20), 100)),
        )

    def list_related_files(self) -> dict[str, Any]:
        """Return suggested related files for this reasoning pass."""
        return {
            "current_file": self.locked_file,
            "allowed_files": self.allowed_files,
            "count": len(self.allowed_files),
        }

    def list_method_hints(self) -> dict[str, Any]:
        """Return method/symbol hints collected from failure context."""
        return {
            "current_file": self.locked_file,
            "method_hints": self.method_hints,
            "count": len(self.method_hints),
        }

    def read_repo_code_window(
        self,
        file_path: str,
        center_line: int,
        radius: int = 20,
    ) -> str:
        """Read code window from any repository file by path."""
        p = _normalize_rel_path(str(file_path or ""))
        if not _is_readable_repo_file(self.repo, p):
            return f"ERROR: file_not_found:{p}"
        return self._hg.read_file_window(p, int(center_line), int(radius))

    def grep_in_repo(
        self,
        file_path: str,
        search_text: str,
        is_regex: bool = False,
        max_results: int = 20,
    ) -> str:
        """Search text in any repository file by path."""
        p = _normalize_rel_path(str(file_path or ""))
        if not _is_readable_repo_file(self.repo, p):
            return f"ERROR: file_not_found:{p}"
        return self._hg.grep_in_file(
            file_path=p,
            search_text=str(search_text or ""),
            is_regex=bool(is_regex),
            max_results=max(1, min(int(max_results or 20), 100)),
        )

    def search_repo_symbol(
        self,
        search_text: str,
        is_regex: bool = False,
        max_results: int = 50,
    ) -> str:
        """Search symbol/text across repo Java files and return file:line hits."""
        text = str(search_text or "").strip()
        if not text:
            return "ERROR: empty_search_text"
        cap = max(1, min(int(max_results or 50), 200))
        cmd = ["git", "grep", "-n", "--full-name"]
        if not is_regex:
            cmd.append("-F")
        cmd.extend([text, "HEAD", "--", "*.java"])
        try:
            res = subprocess.run(
                cmd,
                cwd=self.repo,
                capture_output=True,
                text=True,
                timeout=15,
            )
            lines = (res.stdout or "").splitlines()
            if not lines:
                return f"No matches for '{text}'"
            out = [f"[search_repo_symbol] '{text}' matches={min(len(lines), cap)}"]
            for ln in lines[:cap]:
                parts = ln.split(":", 3)
                if len(parts) < 4:
                    continue
                file_path = _normalize_rel_path(str(parts[1] or ""))
                line_no = str(parts[2] or "").strip()
                code = str(parts[3] or "")
                out.append(f"{file_path}:{line_no}: {code}")
            return "\n".join(out)
        except Exception as e:
            return f"ERROR: search_repo_symbol_failed:{e}"

    def diagnose_api_drift(self) -> dict[str, Any]:
        """Run deterministic failure diagnosis for current file."""
        engine = FailureDiagnosisEngine(self.repo, self.mainline)
        failed_symbol = _extract_primary_symbol_from_context(
            self.diagnostics,
            self.validation_error_context,
        )
        diag = engine.diagnose(
            target_file=self.locked_file,
            failed_old_string="",
            failed_symbol=failed_symbol,
            build_error=self.validation_error_context,
        )
        payload = diag.to_dict()
        payload["failed_symbol"] = failed_symbol
        return payload

    def get_method_signature(self, method_name: str) -> str:
        """Get candidate method signatures for a method in current file."""
        content = _load_file_text(self.repo, self.locked_file)
        if not content:
            return f"Method {method_name} not found in {self.locked_file}"

        pattern = re.compile(
            rf"(?:public|protected|private)[^{{;]*\b{re.escape(str(method_name or ''))}\s*\([^{{;]*\)",
            re.MULTILINE,
        )
        matches = list(pattern.finditer(content))
        if not matches:
            return f"Method {method_name} not found in {self.locked_file}"
        results = []
        for m in matches[:3]:
            line_no = content[: m.start()].count("\n") + 1
            results.append(f"Line {line_no}: {m.group(0).strip()}")
        return "\n".join(results)

    def compare_mainline_target(self, method_name: str) -> str:
        """Compare method signature between target and mainline for current file."""
        target_sig = self.get_method_signature(method_name)
        mainline_content = _load_file_text(self.mainline, self.locked_file)
        if not mainline_content:
            return f"Target:\n{target_sig}\n\nMainline: method unavailable for {self.locked_file}"
        pattern = re.compile(
            rf"(?:public|protected|private)[^{{;]*\b{re.escape(str(method_name or ''))}\s*\([^{{;]*\)",
            re.MULTILINE,
        )
        mm = list(pattern.finditer(mainline_content))
        if not mm:
            mainline_sig = "method not found"
        else:
            line_no = mainline_content[: mm[0].start()].count("\n") + 1
            mainline_sig = f"Line {line_no}: {mm[0].group(0).strip()}"
        return f"Target:\n{target_sig}\n\nMainline:\n{mainline_sig}"

    def submit_surgical_plan(self, operations: list[dict[str, Any]]) -> str:
        """Submit final multi-file surgical operations for deterministic execution."""
        cleaned: list[SurgicalOp] = []
        for op in operations or []:
            if not isinstance(op, dict):
                continue
            target_file = _normalize_rel_path(
                str(op.get("target_file") or self.locked_file)
            )
            if not _is_readable_repo_file(self.repo, target_file):
                continue
            old_s = str(op.get("old_string") or "")
            new_s = str(op.get("new_string") or "")
            if not old_s:
                continue
            cleaned.append(
                {
                    "target_file": target_file,
                    "old_string": old_s,
                    "new_string": new_s,
                    "anchor_verified": bool(op.get("anchor_verified", False)),
                    "verification_method": str(
                        op.get("verification_method") or "exact"
                    ),
                    "confidence": float(op.get("confidence", 0.0) or 0.0),
                }
            )
        self._submitted_plan = cleaned

        verified = sum(1 for op in cleaned if op.get("anchor_verified"))
        unverified = len(cleaned) - verified
        if unverified > 0:
            return (
                f"WARNING: {unverified}/{len(cleaned)} operations are unverified. "
                "Verify anchors with grep_in_target_file before submitting."
            )
        return (
            f"Plan submitted: {len(cleaned)} verified operations for {self.locked_file}"
        )

    def get_submitted_plan(self) -> list[SurgicalOp]:
        """Return last submitted surgical plan."""
        return list(self._submitted_plan or [])

    def get_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool.from_function(
                self.diagnose_api_drift,
                name="diagnose_api_drift",
                description="Run deterministic diagnosis for current file",
            ),
            StructuredTool.from_function(
                self.read_target_code_window,
                name="read_target_code_window",
                description="Read code window in current file",
            ),
            StructuredTool.from_function(
                self.grep_in_target_file,
                name="grep_in_target_file",
                description="Search text in current file",
            ),
            StructuredTool.from_function(
                self.list_related_files,
                name="list_related_files",
                description="List suggested related files",
            ),
            StructuredTool.from_function(
                self.list_method_hints,
                name="list_method_hints",
                description="List method and symbol hints",
            ),
            StructuredTool.from_function(
                self.read_repo_code_window,
                name="read_repo_code_window",
                description="Read code window in any repo file",
            ),
            StructuredTool.from_function(
                self.grep_in_repo,
                name="grep_in_repo",
                description="Search text in a specific repo file",
            ),
            StructuredTool.from_function(
                self.search_repo_symbol,
                name="search_repo_symbol",
                description="Search symbol across repo Java files",
            ),
            StructuredTool.from_function(
                self.get_method_signature,
                name="get_method_signature",
                description="Get method signatures in current file",
            ),
            StructuredTool.from_function(
                self.compare_mainline_target,
                name="compare_mainline_target",
                description="Compare method signature target vs mainline",
            ),
            StructuredTool.from_function(
                self.submit_surgical_plan,
                name="submit_surgical_plan",
                description="Submit final verified surgical operations",
            ),
        ]


async def reasoning_architect_node(state: AgentState, config) -> dict:
    """Build per-file surgical plans for retry-heavy failures."""
    print("Reasoning Architect: Starting per-file diagnostic planning...")
    retry_files = list(state.get("validation_retry_files") or [])
    print(f"Reasoning Architect: input validation_retry_files={retry_files}")
    structured = state.get("validation_error_context_structured") or {}
    if not retry_files and isinstance(structured, dict):
        primary = str(structured.get("primary_failed_file") or "").strip()
        if primary:
            retry_files = [primary]

    target_repo_path = str(state.get("target_repo_path") or "")
    mainline_repo_path = str(state.get("mainline_repo_path") or "")
    if not target_repo_path:
        return {
            "messages": [
                HumanMessage(
                    content="Reasoning Architect skipped: missing target repo path."
                )
            ]
        }

    normalized_files: list[str] = []
    seen: set[str] = set()
    for f in retry_files:
        p = _normalize_rel_path(str(f or ""))
        if not p or p in seen:
            continue
        full = os.path.join(target_repo_path, p)
        if not os.path.isfile(full):
            continue
        seen.add(p)
        normalized_files.append(p)

    if not normalized_files:
        derived = _derive_retry_files_from_generation_checklist(state)
        if derived:
            print(
                "Reasoning Architect: fallback retry scope from generation_checklist="
                + ", ".join(derived)
            )
            for p in derived:
                if p in seen:
                    continue
                full = os.path.join(target_repo_path, p)
                if not os.path.isfile(full):
                    continue
                seen.add(p)
                normalized_files.append(p)

    expanded_retry_files: list[str] = []
    for p in list(normalized_files):
        expanded_retry_files.extend(_extract_side_files_from_state(state, p))
    for p in expanded_retry_files:
        if not p or p in seen:
            continue
        full = os.path.join(target_repo_path, p)
        if not os.path.isfile(full):
            continue
        seen.add(p)
        normalized_files.append(p)

    if not normalized_files:
        print(
            "Reasoning Architect: no concrete retry files found; returning no-op "
            "(check validation_retry_files and generation_checklist extraction)."
        )
        return {
            "messages": [
                HumanMessage(
                    content="Reasoning Architect skipped: no valid retry file for surgical planning."
                )
            ]
        }

    print("Reasoning Architect: retry scope files=" + ", ".join(normalized_files))

    # --- Parent-class scope expansion ---
    # For each retry file, inspect its failed plan entries and run the
    # FailureDiagnosisEngine to detect PARENT_CLASS_CHANGE.  When the
    # anchor text that the planner tried to match lives in a parent class
    # rather than the child file, that parent file needs its own reasoning
    # pass so the file editor can apply the correct edit there instead.
    try:
        _diag_engine = FailureDiagnosisEngine(target_repo_path, mainline_repo_path)
        _hgp = state.get("hunk_generation_plan") or {}
        _build_error = str(state.get("validation_error_context") or "")
        _parent_additions: list[str] = []
        for _tf in list(normalized_files):
            # Collect old_strings from plan entries that target this file.
            _failed_old_strings: list[str] = []
            for _entries in _hgp.values() if isinstance(_hgp, dict) else []:
                for _e in _entries or []:
                    if not isinstance(_e, dict):
                        continue
                    _e_target = _normalize_rel_path(str(_e.get("target_file") or ""))
                    if _e_target != _tf:
                        continue
                    _os = str(_e.get("old_string") or "")
                    if _os and len(_os.strip()) > 10:
                        _failed_old_strings.append(_os)
            for _os in _failed_old_strings[:3]:
                _diag = _diag_engine.diagnose(
                    target_file=_tf,
                    failed_old_string=_os,
                    failed_symbol="",
                    build_error=_build_error,
                )
                if _diag.kind == FailureKind.PARENT_CLASS_CHANGE and _diag.parent_file:
                    _pf = _normalize_rel_path(_diag.parent_file)
                    if _pf and _pf not in seen:
                        _full_pf = os.path.join(target_repo_path, _pf)
                        if os.path.isfile(_full_pf):
                            _parent_additions.append(_pf)
                            seen.add(_pf)
                            print(
                                f"Reasoning Architect: PARENT_CLASS_CHANGE detected — "
                                f"adding parent file {_pf} (child={_tf})"
                            )
                    break  # one confirmed diagnosis per file is sufficient
        normalized_files.extend(_parent_additions)
        if _parent_additions:
            print(
                "Reasoning Architect: expanded retry scope with parent file(s): "
                + ", ".join(_parent_additions)
            )
    except Exception as _parent_exc:
        print(f"Reasoning Architect: parent-class detection skipped: {_parent_exc}")

    llm = get_llm(temperature=0)
    token_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated": False,
        "sources": [],
    }

    existing = state.get("surgical_plans") or {}
    merged: dict[str, list[SurgicalOp]] = {}
    if isinstance(existing, dict):
        for key, ops in existing.items():
            if isinstance(ops, list):
                merged[_normalize_rel_path(str(key or ""))] = [
                    op for op in ops if isinstance(op, dict)
                ]

    last_context: dict[str, Any] | None = None
    planned_count = 0

    for target_file in normalized_files:
        diagnostics = _extract_file_diagnostics(state, target_file)
        related_files, method_hints = _extract_related_files_and_method_hints(
            state,
            target_file,
            target_repo_path,
        )
        print(
            "Reasoning Architect: file="
            f"{target_file} related_files={len(related_files)} method_hints={len(method_hints)}"
        )
        patch_intent = str(
            (state.get("semantic_blueprint") or {}).get("fix_logic") or ""
        )
        toolkit = FileIsolatedToolkit(
            target_repo_path=target_repo_path,
            target_file=target_file,
            allowed_files=related_files,
            method_hints=method_hints,
            mainline_repo_path=mainline_repo_path,
            build_diagnostics=diagnostics,
            validation_error_context=str(state.get("validation_error_context") or ""),
        )

        plan: list[SurgicalOp] = []
        try:
            # 1. Run Structured Rulebook Diagnosis
            rulebook = TypeVRulebook(target_repo_path, mainline_repo_path)

            # Find the failed hunk entry if any
            failed_hunk = {}
            validation_error_context = state.get("validation_error_context") or ""

            # Safely extract hunk information
            validation_retry_hunks = state.get("validation_retry_hunks")
            failed_hunk_indices = []
            if isinstance(validation_retry_hunks, dict):
                failed_hunk_indices = validation_retry_hunks.get(target_file, [])
            elif isinstance(validation_retry_hunks, list):
                # If it's a list, it might be a broadcasted retry or special signal
                failed_hunk_indices = []  # Default to empty for list types

            extracted_hunks_val = state.get("extracted_hunks")
            all_hunks = []
            if isinstance(extracted_hunks_val, dict):
                all_hunks = extracted_hunks_val.get(target_file, [])

            current_failed_entry = {}
            if failed_hunk_indices and all_hunks:
                # Take the first failed one for the rulebook focus
                idx = failed_hunk_indices[0]
                if 0 <= idx < len(all_hunks):
                    current_failed_entry = all_hunks[idx]

            rule_decision = rulebook.apply(
                target_file=target_file,
                failed_plan_entry=current_failed_entry,
                build_error=str(validation_error_context),
            )

            rulebook_hint = rule_decision.to_prompt_context()

            # 2. Enhanced Prompt Construction
            prompt = _REASONING_SYSTEM.format(
                current_file=target_file,
                related_files="\n".join(f"- {p}" for p in related_files[:30])
                or "- <none>",
                method_hints=", ".join(method_hints[:30]) or "<none>",
                build_diagnostics=_truncate_for_log(str(diagnostics), 4000),
                patch_intent=_truncate_for_log(patch_intent or "<none>", 1000),
                session_modified_files="\n".join(
                    f"- {f}"
                    for f in sorted(
                        list(
                            set(
                                op.get("target_file", "")
                                for op in state.get("surgical_history", [])
                                if op.get("target_file")
                            )
                        )
                    )
                )
                or "- <none>",
            )

            # 3. Initial Code Context
            initial_code = ""
            if diagnostics.get("failed_locations"):
                loc = diagnostics["failed_locations"][0]
                line = int(loc.get("line") or 0)
                if line > 0:
                    win = toolkit.read_target_code_window(center_line=line, radius=12)
                    initial_code = f"\n\nCurrent code window around failure (line {line}):\n{win}\n"

            # Strong initial message that forces diagnostic-first behavior
            initial_message = HumanMessage(
                content=(
                    "Diagnose the failure completely and submit a clean surgical plan. "
                    "Start with diagnose_api_drift. Verify every anchor. "
                    "Handle cascading changes across related files if needed. "
                    f"Primary file: {target_file}\n\n"
                    f"{rulebook_hint}\n"
                    f"{initial_code}"
                )
            )

            agent = create_react_agent(llm, tools=toolkit.get_tools(), prompt=prompt)
            result = await agent.ainvoke(
                {"messages": [initial_message]},
                config={
                    "recursion_limit": 60,
                    "configurable": {"thread_id": f"reasoning-{target_file}"},
                },
            )
            _log_reasoning_trace(result or {}, target_file)
            agg = aggregate_usage_from_messages((result or {}).get("messages") or [])
            if agg.get("input_tokens") or agg.get("output_tokens"):
                add_usage(
                    token_usage,
                    int(agg.get("input_tokens", 0) or 0),
                    int(agg.get("output_tokens", 0) or 0),
                    "reasoning_architect.react.aggregate_usage",
                )
            plan = toolkit.get_submitted_plan()
        except Exception as e:
            print(f"Reasoning Architect: planning failed for {target_file}: {e}")

        verified_plan = [
            op for op in (plan or []) if bool(op.get("anchor_verified", False))
        ]
        if not verified_plan:
            # Do not blindly replay stale planner ops when reasoning produced
            # no valid plan; this often injects malformed code and burns retries.
            verified_plan = []
            if verified_plan:
                print(
                    "Reasoning Architect: using fallback existing-plan ops for "
                    f"{target_file} count={len(verified_plan)}"
                )

        verified_plan, rejected = _sanitize_surgical_ops(
            repo_path=target_repo_path,
            default_target_file=target_file,
            ops=verified_plan,
        )
        if rejected:
            print(
                f"Reasoning Architect: rejected {len(rejected)} unsafe op(s) for {target_file}: "
                + ", ".join(rejected[:5])
            )

        if verified_plan:
            print(
                "Reasoning Architect: accepted ops for "
                f"{target_file} count={len(verified_plan)}"
            )
            for i, op in enumerate(verified_plan, start=1):
                old_preview = str(op.get("old_string") or "").replace("\n", "\\n")[:120]
                new_preview = str(op.get("new_string") or "").replace("\n", "\\n")[:120]
                print(
                    "Reasoning Architect:   op["
                    f"{i}] target={op.get('target_file')} old='{old_preview}' new='{new_preview}'"
                )

        if verified_plan:
            grouped: dict[str, list[SurgicalOp]] = {}
            for op in verified_plan:
                tf = _normalize_rel_path(str(op.get("target_file") or target_file))
                if not tf:
                    continue
                grouped.setdefault(tf, []).append(op)
            for tf, ops in grouped.items():
                merged[tf] = ops
            planned_count += 1

        failed_symbol = _extract_primary_symbol_from_context(
            diagnostics,
            str(state.get("validation_error_context") or ""),
        )
        side_files = _extract_side_files_from_state(state, target_file)
        last_context = {
            "current_file": target_file,
            "failure_kind": "anchor_not_found"
            if not verified_plan
            else "signature_drift",
            "build_diagnostics": diagnostics,
            "side_files": side_files,
            "iteration": int(state.get("reasoning_iterations") or 0) + 1,
            "surgical_ops": verified_plan,
        }

    return {
        "messages": [
            HumanMessage(
                content=(
                    "Reasoning Architect complete. "
                    f"Built surgical plans for {planned_count}/{len(normalized_files)} file(s)."
                )
            )
        ],
        "surgical_plans": merged,
        "reasoning_context": last_context,
        "reasoning_iterations": int(state.get("reasoning_iterations") or 0) + 1,
        "token_usage": token_usage,
    }
