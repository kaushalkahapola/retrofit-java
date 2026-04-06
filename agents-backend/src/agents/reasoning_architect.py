"""
Reasoning Architect

Per-file diagnostic planning node that produces verified surgical operations
for deterministic application by Agent 3 (File Editor).
"""

from __future__ import annotations

import os
import re
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from agents.failure_diagnosis import FailureDiagnosisEngine
from agents.hunk_generator_tools import HunkGeneratorToolkit
from state import AgentState, SurgicalOp
from utils.llm_provider import get_llm
from utils.token_counter import add_usage, aggregate_usage_from_messages


_REASONING_SYSTEM = """You are the H-MABS Reasoning Architect.

You operate on exactly one target file and cannot edit files.
Your only output is a verified surgical plan for deterministic execution.

Hard constraints:
- Call diagnose_api_drift first.
- Verify every old_string anchor using read_target_code_window and/or grep_in_target_file.
- Submit only operations where anchor_verified=true.
- Keep the plan minimal and deterministic.

Current file: {current_file}

Build diagnostics:
{build_diagnostics}

Patch intent:
{patch_intent}

When ready, call submit_surgical_plan with the complete operation list.
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
        mainline_repo_path: str,
        build_diagnostics: dict[str, Any],
        validation_error_context: str,
    ):
        self.repo = target_repo_path
        self.locked_file = _normalize_rel_path(target_file)
        self.mainline = mainline_repo_path
        self.diagnostics = build_diagnostics or {}
        self.validation_error_context = str(validation_error_context or "")
        self._hg = HunkGeneratorToolkit(target_repo_path)
        self._submitted_plan: list[SurgicalOp] = []

    def read_target_code_window(self, center_line: int, radius: int = 20) -> str:
        return self._hg.read_file_window(
            self.locked_file, int(center_line), int(radius)
        )

    def grep_in_target_file(
        self,
        search_text: str,
        is_regex: bool = False,
        max_results: int = 20,
    ) -> str:
        return self._hg.grep_in_file(
            file_path=self.locked_file,
            search_text=str(search_text or ""),
            is_regex=bool(is_regex),
            max_results=max(1, min(int(max_results or 20), 100)),
        )

    def diagnose_api_drift(self) -> dict[str, Any]:
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
        cleaned: list[SurgicalOp] = []
        for op in operations or []:
            if not isinstance(op, dict):
                continue
            old_s = str(op.get("old_string") or "")
            new_s = str(op.get("new_string") or "")
            if not old_s:
                continue
            cleaned.append(
                {
                    "target_file": self.locked_file,
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
        return list(self._submitted_plan or [])

    def get_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool.from_function(
                self.diagnose_api_drift, name="diagnose_api_drift"
            ),
            StructuredTool.from_function(
                self.read_target_code_window,
                name="read_target_code_window",
            ),
            StructuredTool.from_function(
                self.grep_in_target_file,
                name="grep_in_target_file",
            ),
            StructuredTool.from_function(
                self.get_method_signature,
                name="get_method_signature",
            ),
            StructuredTool.from_function(
                self.compare_mainline_target,
                name="compare_mainline_target",
            ),
            StructuredTool.from_function(
                self.submit_surgical_plan,
                name="submit_surgical_plan",
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
        patch_intent = str(
            (state.get("semantic_blueprint") or {}).get("fix_logic") or ""
        )
        toolkit = FileIsolatedToolkit(
            target_repo_path=target_repo_path,
            target_file=target_file,
            mainline_repo_path=mainline_repo_path,
            build_diagnostics=diagnostics,
            validation_error_context=str(state.get("validation_error_context") or ""),
        )

        plan: list[SurgicalOp] = []
        try:
            prompt = _REASONING_SYSTEM.format(
                current_file=target_file,
                build_diagnostics=str(diagnostics),
                patch_intent=patch_intent or "<none>",
            )
            agent = create_react_agent(llm, tools=toolkit.get_tools(), prompt=prompt)
            result = await agent.ainvoke(
                {
                    "messages": [
                        HumanMessage(
                            content=(
                                "Diagnose this file and submit a fully verified surgical plan "
                                f"for `{target_file}`."
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

        if verified_plan:
            merged[target_file] = verified_plan
            planned_count += 1

        failed_symbol = _extract_primary_symbol_from_context(
            diagnostics,
            str(state.get("validation_error_context") or ""),
        )
        last_context = {
            "current_file": target_file,
            "failure_kind": "anchor_not_found"
            if not verified_plan
            else "signature_drift",
            "build_diagnostics": diagnostics,
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
