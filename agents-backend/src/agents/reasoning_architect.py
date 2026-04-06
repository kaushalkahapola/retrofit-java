"""
Reasoning Architect

Per-file diagnostic planning node that produces verified surgical operations
for deterministic application by Agent 3 (File Editor).
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from agents.failure_diagnosis import FailureDiagnosisEngine
from agents.hunk_generator_tools import HunkGeneratorToolkit
from state import AgentState, SurgicalOp
from utils.llm_provider import get_llm
from utils.token_counter import add_usage, aggregate_usage_from_messages


_REASONING_SYSTEM = """You are the H-MABS Reasoning Architect for complex backports.

Mission:
- Produce a deterministic, multi-file surgical plan that resolves compilation/API drift.
- You can inspect parent classes and connected classes when required.
- You cannot edit files directly.

Execution protocol (mandatory):
1) Call diagnose_api_drift first.
2) Inspect related files and method hints (list_related_files, list_method_hints).
3) For every proposed operation:
   - verify anchor in the target file (read_target_code_window and/or grep_in_target_file),
   - if needed, inspect other files using read_repo_code_window/grep_in_repo,
   - ensure operation is minimal and deterministic.
4) Submit a single final plan using submit_surgical_plan.

Strict rules:
- Prefer exact local replacements; do not invent broad rewrites.
- Include cross-file edits only when diagnostics/symbol drift justify them.
- Every operation must set anchor_verified=true.
- Use target_file per op when the fix belongs to parent/connected classes.

Current primary file: {current_file}

Known related files:
{related_files}

Method/symbol hints:
{method_hints}

Build diagnostics:
{build_diagnostics}

Patch intent:
{patch_intent}

Return only via submit_surgical_plan.
"""


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
    for m in re.findall(
        r"([a-zA-Z0-9_./-]+\.java):(?:\[(\d+),\d+\]|(\d+)):", build_raw
    ):
        p = _normalize_rel_path(str(m[0] or ""))
        if p:
            candidates.add(p)

    out = [p for p in sorted(candidates) if p and p != target]
    return out[:6]


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
            rejected.append(f"op_{idx}: anchor_not_in_file")
            continue

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
        return {
            "messages": [
                HumanMessage(
                    content="Reasoning Architect skipped: no valid retry file for surgical planning."
                )
            ]
        }

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
            prompt = _REASONING_SYSTEM.format(
                current_file=target_file,
                related_files="\n".join(f"- {p}" for p in related_files)
                if related_files
                else "- <none>",
                method_hints=", ".join(method_hints) if method_hints else "<none>",
                build_diagnostics=str(diagnostics),
                patch_intent=patch_intent or "<none>",
            )
            agent = create_react_agent(llm, tools=toolkit.get_tools(), prompt=prompt)
            result = await agent.ainvoke(
                {
                    "messages": [
                        HumanMessage(
                            content=(
                                "Diagnose this file and submit a fully verified surgical plan. "
                                "Inspect parent/connected files if needed. "
                                "Avoid malformed constructor/signature insertions. "
                                "Only propose operations that keep Java structure valid. "
                                f"Primary file: `{target_file}`."
                            )
                        )
                    ]
                },
                config={"recursion_limit": 20},
            )
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
            verified_plan = _fallback_surgical_from_existing_plan(state, target_file)

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
