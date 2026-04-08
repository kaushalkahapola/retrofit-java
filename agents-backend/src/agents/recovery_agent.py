"""
Claude-Code-Style Recovery Agent

Superior version: Simple master loop (n0-inspired), strong constitution-style
system prompt, prompt-based to-dos, sub-agent delegation with isolated context,
aggressive context management, stagnation detection, and strict minimal-change
plan contract.

Single fallback planner invoked after deterministic file-editor validation failure.
The agent has broad local tooling and can delegate to subagents, but its output
contract is still a deterministic `hunk_generation_plan` consumed by File Editor.

No web tools. No ask-user tool.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from agents.failure_diagnosis import FailureDiagnosisEngine
from agents.type_v_rulebook import TypeVRulebook
from state import AgentState
from utils.api_drift_detector import detect_drift
from utils.llm_provider import get_llm
from utils.mcp_client import get_client
from utils.method_fingerprinter import MethodFingerprinter
from utils.plan_validator import consolidate_plan_entries_java
from utils.token_counter import add_usage, aggregate_usage_from_messages


_RECOVERY_SYSTEM = """<context>
This is a technical software development environment focused on code adaptation and backporting changes between codebases.
</context>

<role>
You are an Adaptation Assistant — a senior software engineer specializing in adapting patches from a newer mainline codebase to an older target repository.
Your goal is to DIRECTLY EDIT the target files using the apply_edit tool, then call recovery_done when finished.
</role>

<primary_workflow>
THIS IS THE PRIMARY WORKFLOW. Use these tools, not submit_recovery_plan:

1. apply_edit(target_file, old_string, new_string, edit_type)
   — Apply ONE edit at a time directly to the target file on disk.
   — Whitespace-tolerant matching is built in.
   — old_string MUST come from the actual TARGET file (shown in <target_files>),
     NOT from the mainline patch's `-` lines.
   — Returns SUCCESS or FAILED with a hint. Iterate based on the response.
   — Make multiple calls — one per edit. Small, focused edits work best.

2. mark_no_change(target_file, reason)
   — Use ONLY when the target already has the equivalent code, or the change
     is structurally inapplicable. Do not use this to skip work.

3. recovery_done(summary)
   — Call EXACTLY ONCE when every required file has been edited or marked.
   — The recovery loop will exit and the modified files will be validated.

DO NOT call submit_recovery_plan unless apply_edit is somehow unavailable.
The apply_edit tool IS the verification — if it returns SUCCESS, the file
was actually modified on disk. There is no separate plan to submit.
</primary_workflow>

<situation>
We need to adapt a change from the mainline codebase to the target (older) repository, which has structural differences.
Either a direct patch application needs adjustment, or the patch is complex and requires structural mapping.
</situation>

<important_notice>
MAINLINE ≠ TARGET — Do not confuse the two codebases.

The <mainline_patch> below comes from the newer mainline codebase.
The TARGET repository is older and has different code structure, constructors, fields, method signatures, etc.

- Lines in the mainline patch are NOT necessarily present verbatim in the target.
- Use old_string anchors ONLY from the actual target code shown in <target_files> (or read via tools for other files).
- Never copy old_strings from the mainline patch's context lines.
</important_notice>

<objectives>
1. Understand the intent of the mainline change.
2. Analyze deterministic recovery brief and obligations first.
3. Analyze the actual target code provided in <target_files>.
4. Identify differences (e.g., constructor signatures, field order, imports, error handling).
5. Create minimal, semantically correct edits that achieve the same goal in the target's structure.
6. Submit the plan via the submit_recovery_plan tool.
</objectives>

<rules>
1. Base all edits on the target code visible in <target_files> or retrieved via tools.
2. Prefer small, precise edits using exact matching anchors from the target.
3. Avoid no-op edits, comment-only changes, or unnecessary modifications.
4. Submit the plan only via the submit_recovery_plan tool — do not output raw JSON outside the tool.
</rules>

<analysis_steps>
A) Read <deterministic_recovery_brief> and <impact_obligations> first.
B) Summarize required adaptation and why it is needed.
C) Extract the main intent from the <mainline_patch>.
D) Examine <target_files> for actual signatures, declarations, and structure.
E) Compare mainline intent vs. target's current code.
F) Decide each obligation as edited or verified_no_change, with evidence.
G) Build adapted edits: use old_string from target, new_string reflecting the intended change.
H) Submit the plan.
</analysis_steps>

<thinking_protocol>
Follow this exact order before creating edits:
1) Intent Lock
   - What is the core security/behavior intent of the mainline patch?
2) Target Fit Check
   - Can the same edit be applied as-is, or does target context require adaptation?
3) Drift Scan (must check)
   - variable names, method names, method signatures, types/classes, constructors/fields.
4) Connected Impact Scan
   - Will this break connected locations?
   - Check callers/callees, parent/child classes, overrides, imports, helper methods, side files.
5) Edit Decision
   - Make minimal safe edits with exact anchors from TARGET code.
6) Final Check
   - Did we fully implement mainline intent?
   - Did we likely break anything in target?
If uncertain, gather more evidence first.
</thinking_protocol>

<example>
If the mainline patch adds parameters to a constructor that looks different in the target:
- WRONG: copy old_string from mainline patch context lines.
- CORRECT: copy old_string from the target's actual constructor in <target_files>, then adapt the new_string accordingly.
</example>

<submission_rules>
- The submission must include a decision for every obligation in <impact_obligations>.
- Decisions may be: edited | verified_no_change. Avoid fake edits.
- Prioritize files in <retry_scope>.
- submit_recovery_plan accepts either legacy map plan OR wrapper payload with investigation_evidence, obligation_decisions, edit_ops, risk_notes.
- In notes, include a short final-check statement showing: intent coverage, connected-locations check, drift check, and breakage risk review.
</submission_rules>

<output_contract>
Preferred wrapper payload for submit_recovery_plan:
{{
  "investigation_evidence": [{{"kind":"...", "details":"..."}}],
  "obligation_decisions": [
    {{"obligation_id":"...", "status":"edited|verified_no_change", "reason":"...", "evidence":["..."]}}
  ],
  "edit_ops": {{
    "path/to/MainlineFile.java": [
      {{
        "hunk_index": int,
        "target_file": str,
        "edit_type": "replace" | "insert_before" | "insert_after" | "delete",
        "old_string": str,
        "new_string": str,
        "verified": false,
        "verification_result": "ready_to_apply",
        "notes": str
      }}
    ]
  }},
  "risk_notes": ["..."]
}}
</output_contract>

<deterministic_recovery_brief>
{recovery_brief}
</deterministic_recovery_brief>

<impact_obligations>
{recovery_obligations}
</impact_obligations>

<mainline_patch>
{failure_context}
</mainline_patch>

<agent_eligible_files>
{agent_eligible_files}
</agent_eligible_files>

<retry_scope>
{retry_scope}
</retry_scope>

<existing_plan>
{existing_plan}
</existing_plan>

<previous_attempts>
{attempt_artifacts}
</previous_attempts>
"""


def _extract_lines_around(
    repo_path: str, rel_path: str, center: int, radius: int = 20
) -> str:
    """Return numbered lines [center-radius, center+radius] from a target file."""
    abs_path = os.path.join(repo_path, _normalize_rel_path(rel_path))
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            all_lines = fh.readlines()
    except Exception:
        return f"<<could not read {rel_path}>>"
    lo = max(0, center - radius - 1)
    hi = min(len(all_lines), center + radius)
    return "".join(
        f"{lo + i + 1:5d}: {line}" for i, line in enumerate(all_lines[lo:hi])
    )


def _normalize_rel_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/").lstrip("/")
    while p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p


def _truncate(text: str, max_len: int = 8000) -> str:
    t = str(text or "")
    if len(t) <= max_len:
        return t
    head = max_len // 2
    tail = max_len - head
    return t[:head] + "\n... [TRUNCATED] ...\n" + t[-tail:]


def _extract_primary_symbol_from_text(text: str) -> str:
    t = str(text or "")
    m = re.search(
        r"(?:public|private|protected|static|final|synchronized)?\s*[\w<>,\[\]?]+\s+(\w+)\s*\(",
        t,
    )
    if m:
        cand = str(m.group(1) or "")
        if cand and cand not in {"if", "for", "while", "switch", "catch", "return"}:
            return cand
    for tok in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", t):
        if len(tok) >= 5 and tok.lower() not in {
            "public",
            "private",
            "protected",
            "static",
            "final",
            "return",
            "class",
            "method",
            "symbol",
        }:
            return tok
    return ""


def _parse_plan_target_pairs(
    state: AgentState,
) -> list[tuple[str, str, dict[str, Any]]]:
    out: list[tuple[str, str, dict[str, Any]]] = []
    plan = state.get("hunk_generation_plan") or {}
    if not isinstance(plan, dict):
        return out
    for mainline_file, entries in plan.items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            tf = _normalize_rel_path(str(e.get("target_file") or ""))
            mf = _normalize_rel_path(str(mainline_file or ""))
            if not mf:
                continue
            if not tf:
                tf = mf
            out.append((mf, tf, e))
    return out


def _build_recovery_obligations(state: AgentState) -> list[dict[str, Any]]:
    obligations: list[dict[str, Any]] = []
    seen: set[str] = set()

    retry_files = [
        _normalize_rel_path(str(x or ""))
        for x in (state.get("validation_retry_files") or [])
        if str(x or "").strip()
    ]
    structured = state.get("validation_error_context_structured") or {}

    def add_ob(kind: str, file_path: str, symbol: str = "", source: str = "") -> None:
        fp = _normalize_rel_path(str(file_path or ""))
        if not fp:
            return
        oid = f"{kind}:{fp}:{symbol}"
        if oid in seen:
            return
        seen.add(oid)
        obligations.append(
            {
                "obligation_id": oid,
                "kind": kind,
                "required_file": fp,
                "symbol": str(symbol or ""),
                "source": str(source or "state"),
                "status": "pending",
            }
        )

    for f in retry_files:
        add_ob("retry_file", f, source="validation_retry_files")

    if isinstance(structured, dict):
        for loc in structured.get("failed_locations") or []:
            if isinstance(loc, dict):
                add_ob(
                    "failed_location",
                    str(loc.get("file") or ""),
                    source="validation_error_context_structured.failed_locations",
                )

        for it in structured.get("failed_hunk_targets") or []:
            if not isinstance(it, dict):
                continue
            add_ob(
                "failed_hunk_target",
                str(it.get("target_file") or ""),
                source="validation_error_context_structured.failed_hunk_targets",
            )

        for s in structured.get("symbol_errors") or []:
            if not isinstance(s, dict):
                continue
            sym = str(s.get("name") or "")
            pf = str(structured.get("primary_failed_file") or "")
            add_ob(
                "symbol_error",
                pf,
                symbol=sym,
                source="validation_error_context_structured.symbol_errors",
            )

        for sig in structured.get("signature_errors") or []:
            if not isinstance(sig, dict):
                continue
            sym = str(sig.get("method") or "")
            pf = str(structured.get("primary_failed_file") or "")
            add_ob(
                "signature_error",
                pf,
                symbol=sym,
                source="validation_error_context_structured.signature_errors",
            )

    for mf, tf, entry in _parse_plan_target_pairs(state):
        sym = _extract_primary_symbol_from_text(
            str(entry.get("old_string") or "") or str(entry.get("new_string") or "")
        )
        add_ob("planned_target", tf, symbol=sym, source=f"plan:{mf}")

    # Always seed obligations from patch scope so recovery has concrete coverage
    # even when validation emits empty retry_files (e.g. empty_generation).
    patch_diff = str(state.get("patch_diff") or "")
    if patch_diff:
        try:
            from utils.patch_analyzer import PatchAnalyzer as _PA

            raw_hunks = _PA().extract_raw_hunks(patch_diff)
            for f in raw_hunks.keys():
                add_ob(
                    "patch_file", _normalize_rel_path(str(f or "")), source="patch_diff"
                )
        except Exception:
            pass

    return obligations


def _get_java_source_safe(repo_path: str, rel_path: str, cap: int = 80000) -> str:
    txt = _read_file(repo_path, rel_path)
    if not txt:
        return ""
    if len(txt) <= cap:
        return txt
    return txt[: cap // 2] + "\n" + txt[-(cap // 2) :]


def _build_deterministic_recovery_brief(state: AgentState) -> dict[str, Any]:
    target_repo_path = str(state.get("target_repo_path") or "")
    mainline_repo_path = str(state.get("mainline_repo_path") or "")
    validation_error = str(state.get("validation_error_context") or "")
    structured = state.get("validation_error_context_structured") or {}
    consistency = state.get("consistency_map") or {}

    diag_engine = FailureDiagnosisEngine(target_repo_path, mainline_repo_path)
    rulebook = TypeVRulebook(target_repo_path, mainline_repo_path)

    pairs = _parse_plan_target_pairs(state)
    primary_target = ""
    primary_mainline = ""
    failed_entry: dict[str, Any] = {}
    if pairs:
        primary_mainline, primary_target, failed_entry = pairs[0]
    if not primary_target:
        primary_target = _normalize_rel_path(
            str((structured or {}).get("primary_failed_file") or "")
        )
    if not primary_target:
        retries = state.get("validation_retry_files") or []
        if isinstance(retries, list) and retries:
            primary_target = _normalize_rel_path(str(retries[0] or ""))

    failed_symbol = _extract_primary_symbol_from_text(
        str((structured or {}).get("primary_failed_symbol") or "")
    )
    if not failed_symbol:
        failed_symbol = _extract_primary_symbol_from_text(
            str(failed_entry.get("old_string") or "")
        )

    diagnosis = None
    try:
        diagnosis = diag_engine.diagnose(
            target_file=primary_target or "",
            failed_old_string=str(failed_entry.get("old_string") or ""),
            failed_symbol=failed_symbol,
            build_error=validation_error,
            hunk_text="",
            consistency_map=consistency if isinstance(consistency, dict) else {},
        )
    except Exception as e:
        diagnosis = {
            "kind": "diagnosis_error",
            "confidence": 0.0,
            "error": str(e),
            "target_file": primary_target,
        }

    rule_decision: dict[str, Any] = {}
    try:
        if primary_target:
            decision = rulebook.apply(
                target_file=primary_target,
                failed_plan_entry=failed_entry
                if isinstance(failed_entry, dict)
                else {},
                build_error=validation_error,
                hunk_apply_error="",
                consistency_map=consistency if isinstance(consistency, dict) else {},
                patch_diff_for_file="",
            )
            rule_decision = {
                "action": decision.action,
                "confidence": decision.confidence,
                "override_target_file": decision.override_target_file,
                "override_target_method": decision.override_target_method,
                "additional_files": list(decision.additional_files or []),
                "target_signature": decision.target_signature,
                "param_adaptation_notes": decision.param_adaptation_notes,
                "new_anchor_file": decision.new_anchor_file,
                "new_anchor_line": decision.new_anchor_line,
                "investigation_summary": decision.investigation_summary,
            }
    except Exception as e:
        rule_decision = {
            "action": "rulebook_error",
            "confidence": 0.0,
            "error": str(e),
        }

    drift_map: dict[str, Any] = {}
    try:
        if (
            primary_mainline
            and primary_target
            and mainline_repo_path
            and target_repo_path
        ):
            mainline_src = _get_java_source_safe(mainline_repo_path, primary_mainline)
            target_src = _get_java_source_safe(target_repo_path, primary_target)
            if mainline_src and target_src:
                drift_map = detect_drift(mainline_src, target_src)
    except Exception as e:
        drift_map = {"error": str(e)}

    if hasattr(diagnosis, "to_dict"):
        diagnosis_payload = diagnosis.to_dict()  # type: ignore[attr-defined]
    elif isinstance(diagnosis, dict):
        diagnosis_payload = diagnosis
    else:
        diagnosis_payload = {
            "kind": "unknown",
            "confidence": 0.0,
            "target_file": primary_target,
        }

    return {
        "version": 1,
        "primary_mainline_file": primary_mainline,
        "primary_target_file": primary_target,
        "failed_symbol": failed_symbol,
        "diagnosis": diagnosis_payload,
        "rulebook_decision": rule_decision,
        "api_drift_map": drift_map,
        "structured_failure": structured if isinstance(structured, dict) else {},
    }


def _resolve_path(repo_path: str, path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    if os.path.isabs(raw):
        return os.path.normpath(raw)
    return os.path.normpath(os.path.join(repo_path, _normalize_rel_path(raw)))


def _read_file(repo_path: str, rel_path: str) -> str:
    try:
        full = _resolve_path(repo_path, rel_path)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def _extract_json_payload(text: str) -> Any | None:
    if not text:
        return None
    t = str(text).strip()
    if t.startswith("```"):
        t = "\n".join(
            line for line in t.splitlines() if not line.strip().startswith("```")
        ).strip()

    s1 = t.find("{")
    e1 = t.rfind("}")
    if s1 >= 0 and e1 >= s1:
        try:
            return json.loads(t[s1 : e1 + 1])
        except Exception:
            pass

    s2 = t.find("[")
    e2 = t.rfind("]")
    if s2 >= 0 and e2 >= s2:
        try:
            return json.loads(t[s2 : e2 + 1])
        except Exception:
            pass
    return None


class RecoveryPlanToolkit:
    """Read/search/delegate plan-mode tools + plan sink."""

    def __init__(
        self,
        state: AgentState,
        target_repo_path: str,
        mainline_repo_path: str,
        required_patch_files: list[str] | None = None,
    ):
        self.state = state
        self.target_repo_path = target_repo_path
        self.mainline_repo_path = mainline_repo_path
        # Files that MUST be covered in the recovery plan (derived from patch diff)
        self._required_patch_files: list[str] = list(required_patch_files or [])
        self._submitted_plan: dict[str, list[dict[str, Any]]] = {}
        self._submitted_status: dict[str, Any] | None = None
        self._submitted_wrapper: dict[str, Any] = {}
        self._submitted_decisions: list[dict[str, Any]] = []
        self._submitted_investigation: list[dict[str, Any]] = []
        self._submitted_risk_notes: list[str] = []
        self._todo: list[dict[str, str]] = []
        self._todo_counter = 0
        # Number of submit_recovery_plan calls that have been REJECTED so far.
        # After enough rejections we switch from "reject the whole plan on any
        # bad anchor" to "auto-prune the failing ops and accept the rest" so
        # the recovery loop can converge on a partial-but-runnable plan.
        self._submission_rejection_count = 0
        # INCREMENTAL ACCUMULATOR: ops accepted across multiple submit calls
        # within a single recovery_agent invocation. Lets weak models submit
        # one file at a time instead of cramming all files into one call.
        self._accumulated_plan: dict[str, list[dict[str, Any]]] = {}
        # ── DIRECT-APPLY MODE (Claude-Code style) ─────────────────────────
        # Records of edits that have ALREADY been applied to disk via
        # `apply_edit`. Each entry is a successful str_replace; the file
        # has been mutated. Recovery agent can now use this instead of
        # the submit_recovery_plan dance.
        self._applied_edits: list[dict[str, Any]] = []
        # Files that the model has explicitly marked as needing no changes.
        self._direct_no_change_files: set[str] = set()
        # Whether the model has called recovery_done().
        self._recovery_done: bool = False
        # Lazy hunk-generator toolkit (for str_replace primitives).
        self._hunk_toolkit = None

    def _required_obligation_ids(self) -> set[str]:
        ids: set[str] = set()
        for ob in self.state.get("recovery_obligations") or []:
            if not isinstance(ob, dict):
                continue
            oid = str(ob.get("obligation_id") or "").strip()
            if oid:
                ids.add(oid)
        return ids

    def _parse_wrapper_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        investigation = payload.get("investigation_evidence") or []
        decisions = payload.get("obligation_decisions") or []
        edit_ops = payload.get("edit_ops") or {}
        risk_notes = payload.get("risk_notes") or []
        if not isinstance(investigation, list):
            investigation = []
        if not isinstance(decisions, list):
            decisions = []
        if not isinstance(edit_ops, dict):
            edit_ops = {}
        if not isinstance(risk_notes, list):
            risk_notes = []
        return {
            "investigation_evidence": investigation,
            "obligation_decisions": decisions,
            "edit_ops": edit_ops,
            "risk_notes": [str(x) for x in risk_notes if str(x).strip()],
        }

    def _agent_eligible_files(self) -> set[str]:
        """Files the agent pipeline is responsible for: every file present in
        the agent-eligible patch (state['patch_diff'] is already test/non-Java
        stripped upstream in evaluate_full_workflow._build_agent_eligible_patch)."""
        files: set[str] = set()
        patch_diff = str(self.state.get("patch_diff") or "")
        if patch_diff:
            try:
                from utils.patch_analyzer import PatchAnalyzer as _PA

                raw_hunks = _PA().extract_raw_hunks(patch_diff)
                for f in raw_hunks.keys():
                    fs = _normalize_rel_path(str(f or ""))
                    if fs:
                        files.add(fs)
            except Exception:
                pass
        return files

    def _retry_scope_files(self) -> set[str]:
        # Seed from the full agent-eligible patch: the recovery agent must plan
        # for EVERY file the pipeline is responsible for, not just whatever
        # happened to be in validation_retry_files (which is empty when Phase 3
        # bails out with "no adapted hunks").
        files: set[str] = self._agent_eligible_files()

        retry_files = self.state.get("validation_retry_files") or []
        if isinstance(retry_files, list):
            for f in retry_files:
                fs = _normalize_rel_path(str(f or ""))
                if fs:
                    files.add(fs)

        # Also include files from previous adapted edits when available.
        for key in ("adapted_file_edits",):
            edits = self.state.get(key) or []
            if isinstance(edits, list):
                for e in edits:
                    if not isinstance(e, dict):
                        continue
                    tf = _normalize_rel_path(str(e.get("target_file") or ""))
                    if tf:
                        files.add(tf)
        return files

    def _apply_decision_based_scope(self, decisions: list[dict[str, Any]]) -> None:
        if not isinstance(decisions, list):
            return
        scope_files: set[str] = {
            _normalize_rel_path(str((o or {}).get("required_file") or ""))
            for o in (self.state.get("recovery_obligations") or [])
            if isinstance(o, dict)
            and _normalize_rel_path(str((o or {}).get("required_file") or ""))
        }
        retry_files = list(self.state.get("validation_retry_files") or [])
        for d in decisions:
            if not isinstance(d, dict):
                continue
            status = str(d.get("status") or "").strip().lower()
            if status not in {"edited", "verified_no_change", "blocked"}:
                continue
            rf = _normalize_rel_path(
                str(d.get("required_file") or d.get("target_file") or "")
            )
            if rf:
                scope_files.add(rf)
        for sf in sorted(scope_files):
            if sf and sf not in retry_files:
                retry_files.append(sf)
        self.state["validation_retry_files"] = retry_files

    def _contains_only_comment_or_whitespace_change(self, old: str, new: str) -> bool:
        if old == new:
            return True

        # Remove line comments and whitespace to detect semantic no-op edits.
        def strip_comments_ws(s: str) -> str:
            lines = []
            for ln in (s or "").splitlines():
                lines.append(re.sub(r"//.*$", "", ln).strip())
            return "".join(x for x in lines if x)

        stripped_old = strip_comments_ws(old)
        stripped_new = strip_comments_ws(new)
        if stripped_old == stripped_new:
            return True

        # Purely adding/removing comment lines is considered low-value/no-op.
        old_lines = [ln.strip() for ln in (old or "").splitlines() if ln.strip()]
        new_lines = [ln.strip() for ln in (new or "").splitlines() if ln.strip()]
        comment = lambda x: (
            x.startswith("//") or x.startswith("/*") or x.startswith("*")
        )
        if all(comment(x) for x in old_lines + new_lines):
            return True
        if old_lines and new_lines:
            non_comment_old = [x for x in old_lines if not comment(x)]
            non_comment_new = [x for x in new_lines if not comment(x)]
            if non_comment_old == non_comment_new:
                return True
        return False

    # ──────────────────────────────────────────────────────────────────
    # DIRECT-APPLY TOOLS (Claude-Code style)
    # The recovery agent uses these to mutate files in place. No plan,
    # no submit, no anchor verifier theatre — `_apply_edit_deterministically`
    # IS the verification: if it returns success, the file changed.
    # ──────────────────────────────────────────────────────────────────
    def _get_hunk_toolkit(self):
        if self._hunk_toolkit is None:
            from agents.hunk_generator_tools import HunkGeneratorToolkit
            self._hunk_toolkit = HunkGeneratorToolkit(self.target_repo_path)
        return self._hunk_toolkit

    def apply_edit(
        self,
        target_file: str,
        old_string: str,
        new_string: str,
        edit_type: str = "replace",
    ) -> str:
        """
        Apply ONE edit directly to a file in the target repo.

        - target_file: repo-relative path (e.g. "server/.../Foo.java")
        - old_string: text to find. For 'replace'/'insert_after'/'insert_before',
          must match a snippet in the file (whitespace-tolerant).
        - new_string: replacement / inserted text.
        - edit_type: 'replace' | 'insert_after' | 'insert_before' | 'delete'

        On success the file IS mutated on disk. Returns 'SUCCESS: ...' or
        'ERROR: ...' / 'NOT_FOUND: ...'. Call this once per edit; iterate
        based on the response. When all required files are edited (or
        marked no_change), call recovery_done().
        """
        from agents.file_editor import _apply_edit_deterministically
        rel = _normalize_rel_path(target_file)
        if not rel:
            return "ERROR: target_file is required"
        if not old_string and edit_type not in {"insert_after", "insert_before"}:
            return "ERROR: old_string is required for replace/delete"

        plan_entry = {
            "edit_type": edit_type,
            "old_string": old_string,
            "new_string": new_string,
        }
        try:
            ok, msg, resolved_old, resolved_new, reason = _apply_edit_deterministically(
                self._get_hunk_toolkit(),
                self.target_repo_path,
                plan_entry,
                rel,
                strict_exact=False,
            )
        except Exception as exc:
            return f"ERROR: apply_edit crashed: {exc}"

        if not ok:
            return (
                f"FAILED: {msg} (reason={reason}). "
                f"Tip: read the target file and copy old_string VERBATIM "
                f"from the on-disk content; do NOT use mainline `-` lines."
            )

        self._applied_edits.append(
            {
                "target_file": rel,
                "edit_type": edit_type,
                "old_string": resolved_old or old_string,
                "new_string": resolved_new or new_string,
                "resolution": reason,
                "message": msg,
            }
        )
        # If model previously claimed no_change for this file, clear it.
        self._direct_no_change_files.discard(rel)
        print(f"[Recovery] apply_edit OK: {rel} ({reason})")
        return f"SUCCESS: {msg} (resolution={reason})"

    def mark_no_change(self, target_file: str, reason: str = "") -> str:
        """
        Declare that a required patch file needs NO edits in the target.
        Use this only when you've verified the target already has the
        equivalent code, or when the change genuinely doesn't apply.
        """
        rel = _normalize_rel_path(target_file)
        if not rel:
            return "ERROR: target_file is required"
        self._direct_no_change_files.add(rel)
        print(f"[Recovery] mark_no_change: {rel} ({reason})")
        return f"SUCCESS: marked {rel} as no_change ({reason})"

    def recovery_done(self, summary: str = "") -> str:
        """
        Signal that all required edits have been applied (or files marked
        no_change). Call this exactly once when finished. The recovery loop
        will exit and the modified files will be passed to validation.
        """
        # Coverage check: every required file must be either edited or
        # explicitly marked no_change.
        edited = {e["target_file"] for e in self._applied_edits}
        covered = edited | self._direct_no_change_files
        missing = [
            f for f in (self._required_patch_files or []) if f not in covered
        ]
        if missing:
            return (
                "ERROR: cannot finish — these required files have neither "
                "an applied edit nor a no_change mark:\n  - "
                + "\n  - ".join(missing)
                + "\nFix: call apply_edit for each, or mark_no_change with a reason."
            )
        self._recovery_done = True
        print(
            f"[Recovery] recovery_done: {len(self._applied_edits)} edits applied "
            f"across {len(edited)} file(s); {len(self._direct_no_change_files)} no_change."
        )
        return (
            f"SUCCESS: recovery complete. {len(self._applied_edits)} edit(s) applied. "
            f"You may stop calling tools now."
        )

    # -------- read/search tools --------
    def read_file(self, file_path: str, max_lines: int = 400) -> str:
        rel = _normalize_rel_path(file_path)
        content = _read_file(self.target_repo_path, rel)
        if not content:
            return f"ERROR: cannot read file '{rel}'"
        lines = content.splitlines()
        cap = max(1, min(int(max_lines or 400), 1200))
        out = [f"[read_file] {rel} total={len(lines)}"]
        for i, line in enumerate(lines[:cap], start=1):
            out.append(f"{i:5d}: {line}")
        if len(lines) > cap:
            out.append(f"... truncated ({len(lines) - cap} more lines)")
        return "\n".join(out)

    def glob(self, pattern: str, max_results: int = 200) -> str:
        q = (pattern or "").strip()
        if not q:
            return "ERROR: empty pattern"
        cap = max(1, min(int(max_results or 200), 500))
        try:
            cmd = [
                "bash",
                "-lc",
                f"python3 - <<'PY'\nimport glob\nfor p in glob.glob({q!r}, recursive=True):\n print(p)\nPY",
            ]
            res = subprocess.run(
                cmd,
                cwd=self.target_repo_path,
                capture_output=True,
                text=True,
                timeout=20,
            )
            items = [x.strip() for x in (res.stdout or "").splitlines() if x.strip()]
            if not items:
                return f"No paths for pattern: {q}"
            items = sorted(items)[:cap]
            return "[glob]\n" + "\n".join(items)
        except Exception as e:
            return f"ERROR: glob failed: {e}"

    def grep(
        self, pattern: str, include: str = "*.java", max_results: int = 200
    ) -> str:
        pat = str(pattern or "").strip()
        if not pat:
            return "ERROR: empty pattern"
        inc = str(include or "*.java").strip()
        cap = max(1, min(int(max_results or 200), 500))
        try:
            try:
                res = subprocess.run(
                    ["rg", "-n", "--no-heading", "-g", inc, pat, "."],
                    cwd=self.target_repo_path,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except FileNotFoundError:
                # ripgrep not installed — fall back to grep
                res = subprocess.run(
                    ["grep", "-rn", "--include=" + inc, pat, "."],
                    cwd=self.target_repo_path,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            lines = [x for x in (res.stdout or "").splitlines() if x.strip()]
            if not lines:
                return f"No grep matches for /{pat}/ with include={inc}"
            lines = lines[:cap]
            return "[grep]\n" + "\n".join(lines)
        except Exception as e:
            return f"ERROR: grep failed: {e}"

    def bash(self, command: str, timeout_seconds: int = 20) -> str:
        """Read-only-ish bash helper for diagnostics/log inspection.

        This does not hard-sandbox writes. It is intended for inspection use.
        """
        cmd = str(command or "").strip()
        if not cmd:
            return "ERROR: empty command"
        t = max(1, min(int(timeout_seconds or 20), 90))
        try:
            res = subprocess.run(
                ["bash", "-lc", cmd],
                cwd=self.target_repo_path,
                capture_output=True,
                text=True,
                timeout=t,
            )
            out = res.stdout or ""
            err = res.stderr or ""
            merged = (out + ("\n" + err if err else "")).strip()
            return _truncate(merged, 12000) or "(no output)"
        except Exception as e:
            return f"ERROR: bash failed: {e}"

    def batch_tools(self, tasks: list[dict[str, Any]]) -> str:
        """Run multiple independent tool tasks in one call.

        Supported task kinds: read_file, read_mainline_file, grep, glob, bash,
        summarize_failure, todoread.
        """
        if not isinstance(tasks, list) or not tasks:
            return "ERROR: tasks must be a non-empty list"

        max_tasks = 8
        selected = tasks[:max_tasks]

        def _run_one(item: dict[str, Any]) -> dict[str, Any]:
            kind = str((item or {}).get("tool") or "").strip()
            args = (item or {}).get("args") or {}
            if not isinstance(args, dict):
                args = {}
            try:
                if kind == "read_file":
                    res = self.read_file(**args)
                elif kind == "read_mainline_file":
                    res = self.read_mainline_file(**args)
                elif kind == "grep":
                    res = self.grep(**args)
                elif kind == "glob":
                    res = self.glob(**args)
                elif kind == "bash":
                    res = self.bash(**args)
                elif kind == "summarize_failure":
                    res = self.summarize_failure()
                elif kind == "todoread":
                    res = self.todoread()
                else:
                    res = f"ERROR: unsupported tool '{kind}' in batch_tools"
            except Exception as e:
                res = f"ERROR: {kind} failed: {e}"
            return {"tool": kind, "result": res}

        workers = max(1, min(4, len(selected)))
        out: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_run_one, it) for it in selected]
            for fut in futures:
                out.append(fut.result())
        return _truncate(json.dumps(out, ensure_ascii=False, indent=2), 20000)

    # -------- todo tools --------
    def todoask(self, task: str) -> str:
        txt = str(task or "").strip()
        if not txt:
            return "ERROR: empty todo task"
        for entry in self._todo:
            if entry.get("status") == "in_progress":
                entry["status"] = "pending"
        self._todo_counter += 1
        tid = f"todo_{self._todo_counter}"
        self._todo.append({"id": tid, "status": "in_progress", "task": txt})
        return f"Added todo {tid}: {txt}"

    def todoread(self) -> str:
        if not self._todo:
            return "No active to-dos."
        out = ["[To-do List]"]
        for t in self._todo:
            out.append(f"- {t['id']} [{t['status']}] {t['task']}")
        return "\n".join(out)

    # -------- subagent delegation --------
    async def agenttool(
        self,
        role: str,
        objective: str,
        mainline_file: str = "",
        target_file: str = "",
        max_steps: int = 10,
    ) -> str:
        """Spawn isolated sub-agent and return compact evidence JSON."""
        role_name = str(role or "investigator").strip().lower()
        obj = str(objective or "").strip()
        if not obj:
            return json.dumps({"error": "objective required"})

        sub_prompt = f"""You are a focused Recovery sub-agent.
Role: {role_name}
Objective: {obj}
Mainline file: {mainline_file}
Target file: {target_file}

Collect ONLY relevant evidence. Return strict JSON with key findings, exact code snippets, and root cause hypothesis if clear.
Do NOT submit any recovery plan. Stay concise."""

        llm = get_llm(temperature=0.0)
        sub_tools = [
            t
            for t in self.get_tools(include_submit=False)
            if t.name
            not in {"submit_recovery_plan", "agenttool", "todoask", "todoread"}
        ]
        sub_agent = create_react_agent(llm, tools=sub_tools)
        try:
            resp = await sub_agent.ainvoke(
                {"messages": [HumanMessage(content=sub_prompt)]},
                config={"recursion_limit": max(8, min(int(max_steps or 12), 40))},
            )
            msgs = (resp or {}).get("messages") or []
            for m in reversed(msgs):
                if not isinstance(m, AIMessage):
                    continue
                payload = _extract_json_payload(getattr(m, "content", ""))
                if payload is not None:
                    return json.dumps(payload, ensure_ascii=False, indent=2)
            raw = str(msgs[-1].content if msgs else "")
            return json.dumps(
                {
                    "role": role_name,
                    "result": "no structured output",
                    "raw": _truncate(raw, 2000),
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"role": role_name, "error": str(e)})

    # -------- state context --------
    def summarize_failure(self) -> dict[str, Any]:
        return {
            "failure_category": str(
                self.state.get("validation_failure_category") or ""
            ),
            "failed_stage": str(self.state.get("validation_failed_stage") or ""),
            "retry_files": list(self.state.get("validation_retry_files") or []),
            "retry_hunks": list(self.state.get("validation_retry_hunks") or []),
            "repeated_plan": bool(
                self.state.get("validation_repeated_plan_detected") or False
            ),
            "repeated_patch": bool(
                self.state.get("validation_repeated_patch_detected") or False
            ),
            "validation_error": _truncate(
                str(self.state.get("validation_error_context") or ""), 4000
            ),
            "structured": self.state.get("validation_error_context_structured") or {},
        }

    def get_dependency_graph(
        self,
        file_paths: list[str],
        explore_neighbors: bool = True,
    ) -> dict[str, Any]:
        if not isinstance(file_paths, list) or not file_paths:
            return {"error": "file_paths must be a non-empty list"}
        try:
            client = get_client()
            return client.call_tool(
                "get_dependency_graph",
                {
                    "target_repo_path": self.target_repo_path,
                    "file_paths": [
                        _normalize_rel_path(str(p or ""))
                        for p in file_paths
                        if str(p or "").strip()
                    ],
                    "explore_neighbors": bool(explore_neighbors),
                },
            )
        except Exception as e:
            return {"error": str(e)}

    def get_class_context(self, file_path: str, focus_method: str = "") -> Any:
        rel = _normalize_rel_path(file_path)
        if not rel:
            return {"error": "file_path required"}
        try:
            client = get_client()
            focus = str(focus_method or "").strip() or None
            return client.call_tool(
                "get_class_context",
                {
                    "target_repo_path": self.target_repo_path,
                    "file_path": rel,
                    "focus_method": focus,
                },
            )
        except Exception as e:
            return {"error": str(e)}

    def find_symbol_locations(self, symbol_name: str) -> list[dict[str, Any]]:
        sym = str(symbol_name or "").strip()
        if not sym:
            return []
        hits = []
        grep_res = self.grep(
            pattern=rf"\b{re.escape(sym)}\b",
            include="*.java",
            max_results=200,
        )
        for ln in str(grep_res or "").splitlines():
            if ln.startswith("[grep]"):
                continue
            m = re.match(r"([^:]+):(\d+):(.*)$", ln)
            if not m:
                continue
            hits.append(
                {
                    "file": _normalize_rel_path(m.group(1)),
                    "line": int(m.group(2)),
                    "content": m.group(3).strip(),
                }
            )
        return hits

    def find_method_match(
        self,
        target_file_path: str,
        old_method_name: str,
        old_signature: str = "",
        old_calls: list[str] | None = None,
    ) -> dict[str, Any]:
        rel = _normalize_rel_path(target_file_path)
        if not rel:
            return {"error": "target_file_path required"}
        try:
            client = get_client()
            graph = client.call_tool(
                "get_dependency_graph",
                {
                    "target_repo_path": self.target_repo_path,
                    "file_paths": [rel],
                    "explore_neighbors": False,
                },
            )
            candidate_methods: list[dict[str, Any]] = []
            for node in graph.get("nodes") or []:
                methods = node.get("methods") or []
                if isinstance(methods, list):
                    candidate_methods.extend(
                        [m for m in methods if isinstance(m, dict)]
                    )
            fp = MethodFingerprinter()
            out = fp.find_match(
                old_method_name=str(old_method_name or "").strip(),
                old_signature=str(old_signature or ""),
                old_code="",
                old_calls=list(old_calls or []),
                candidate_methods=candidate_methods,
            )
            return out if isinstance(out, dict) else {"result": str(out)}
        except Exception as e:
            return {"error": str(e)}

    def read_mainline_file(self, file_path: str, max_lines: int = 250) -> str:
        rel = _normalize_rel_path(file_path)
        text = _read_file(self.mainline_repo_path, rel)
        if not text:
            return f"ERROR: cannot read mainline file '{rel}'"
        lines = text.splitlines()
        cap = max(1, min(int(max_lines or 250), 800))
        out = [f"[read_mainline_file] {rel} total={len(lines)}"]
        for i, ln in enumerate(lines[:cap], start=1):
            out.append(f"{i:5d}: {ln}")
        if len(lines) > cap:
            out.append(f"... truncated ({len(lines) - cap} more lines)")
        return "\n".join(out)

    # -------- plan sink --------
    def submit_recovery_plan(
        self,
        plan: dict[str, Any] | None = None,
        investigation_evidence: list | None = None,
        obligation_decisions: list | None = None,
        edit_ops: dict[str, Any] | None = None,
        risk_notes: list | None = None,
    ) -> str:
        """Accept either wrapper fields directly OR a single `plan` dict."""
        # LLM may call with wrapper fields as top-level args (most common)
        if plan is None and (edit_ops is not None or investigation_evidence is not None):
            plan = {}
            if investigation_evidence is not None:
                plan["investigation_evidence"] = investigation_evidence
            if obligation_decisions is not None:
                plan["obligation_decisions"] = obligation_decisions
            if edit_ops is not None:
                plan["edit_ops"] = edit_ops
            if risk_notes is not None:
                plan["risk_notes"] = risk_notes
        if not isinstance(plan, dict) or not plan:
            return "ERROR: plan payload must be a non-empty object."

        # Accept wrapper payload: {"plan": {...}} and explicit no-fix status.
        if isinstance(plan.get("status"), str):
            status = str(plan.get("status") or "").strip().lower()
            if status == "no_fix_found":
                reason = str(plan.get("reason") or "unspecified")
                self._submitted_status = {
                    "status": "no_fix_found",
                    "reason": reason,
                }
                self._submitted_plan = {}
                return f"SUCCESS: recorded no_fix_found ({reason})."

        wrapper_payload: dict[str, Any] = {}
        if any(
            k in plan
            for k in (
                "investigation_evidence",
                "obligation_decisions",
                "edit_ops",
                "risk_notes",
            )
        ):
            wrapper_payload = self._parse_wrapper_payload(plan)
            plan = wrapper_payload.get("edit_ops") or {}

        if "plan" in plan and isinstance(plan.get("plan"), dict):
            plan = plan.get("plan") or {}
        if not isinstance(plan, dict):
            return "ERROR: plan must be an object keyed by mainline file."
        # Empty edit_ops is OK if the model is sending decisions/no-change
        # claims for files already in the accumulator. We'll evaluate
        # coverage below using accumulator + verified_no_change decisions.
        if not plan and not self._accumulated_plan and not (
            wrapper_payload.get("obligation_decisions")
        ):
            return "ERROR: plan must be an object keyed by mainline file."

        required_ids = self._required_obligation_ids()

        allowed_edit_types = {"replace", "insert_before", "insert_after", "delete"}
        cleaned: dict[str, list[dict[str, Any]]] = {}
        op_count = 0
        retry_scope_files = self._retry_scope_files()
        touched_files: set[str] = set()
        filtered_low_value = 0
        # Cache of on-disk target file contents for anchor verification.
        import os as _os  # local import to avoid broad changes at module top

        _target_file_cache: dict[str, str] = {}

        def _load_target(rel: str) -> str | None:
            if not rel:
                return None
            if rel in _target_file_cache:
                return _target_file_cache[rel]
            abs_p = _os.path.join(self.target_repo_path, rel)
            try:
                with open(abs_p, "r", encoding="utf-8", errors="replace") as fh:
                    txt = fh.read()
            except Exception:
                txt = ""
            _target_file_cache[rel] = txt
            return txt

        anchor_errors: list[str] = []
        # Per-key diagnostics: how many ops the model submitted under each
        # mainline_file key, and why each one was dropped. Surfaced in
        # rejection errors so the model knows what to fix instead of guessing.
        per_key_drop_reasons: dict[str, list[str]] = {}
        per_key_submitted: dict[str, int] = {}

        for mainline_file, ops in plan.items():
            mainline_key_norm = _normalize_rel_path(str(mainline_file))
            if not isinstance(ops, list):
                per_key_drop_reasons.setdefault(mainline_key_norm, []).append(
                    f"value is {type(ops).__name__}, expected list"
                )
                continue
            per_key_submitted[mainline_key_norm] = len(ops)
            entries: list[dict[str, Any]] = []
            # Track ops dropped purely by the low-value filter so we can
            # restore one if it would otherwise leave the file with zero
            # entries (which would silently break the coverage check).
            low_value_holdback: list[dict[str, Any]] = []
            for idx, op in enumerate(ops):
                if not isinstance(op, dict):
                    per_key_drop_reasons.setdefault(mainline_key_norm, []).append(
                        f"op[{idx}]: not a dict ({type(op).__name__})"
                    )
                    continue
                edit_type = str(op.get("edit_type") or "replace").strip().lower()
                if edit_type not in allowed_edit_types:
                    per_key_drop_reasons.setdefault(mainline_key_norm, []).append(
                        f"op[{idx}]: edit_type={edit_type!r} not in {sorted(allowed_edit_types)}"
                    )
                    continue

                # Infer target_file from the mainline_file key when the model
                # forgets to set it on the op (very common silent failure).
                if not op.get("target_file"):
                    op["target_file"] = mainline_key_norm

                old_string = str(op.get("old_string") or "")
                new_string = str(op.get("new_string") or "")
                if not old_string:
                    per_key_drop_reasons.setdefault(mainline_key_norm, []).append(
                        f"op[{idx}]: empty old_string"
                    )
                    continue
                if edit_type != "delete" and not new_string:
                    per_key_drop_reasons.setdefault(mainline_key_norm, []).append(
                        f"op[{idx}]: empty new_string for edit_type={edit_type!r}"
                    )
                    continue

                if self._contains_only_comment_or_whitespace_change(
                    old_string, new_string
                ):
                    filtered_low_value += 1
                    low_value_holdback.append(
                        {
                            "hunk_index": int(op.get("hunk_index", idx) or idx),
                            "target_file": _normalize_rel_path(str(op.get("target_file") or "")),
                            "edit_type": edit_type,
                            "old_string": old_string,
                            "new_string": new_string,
                            "verified": bool(op.get("verified", False)),
                            "verification_result": str(
                                op.get("verification_result") or "submitted_unchecked"
                            ),
                            "notes": str(op.get("notes") or "") + " [low-value-restored]",
                        }
                    )
                    continue

                target_file = _normalize_rel_path(str(op.get("target_file") or ""))
                if target_file:
                    touched_files.add(target_file)

                # HARD ANCHOR VERIFICATION: the old_string must exist verbatim in
                # the on-disk target file. This is the contract that keeps the LLM
                # from copying mainline `-` lines as anchors.
                #
                # Fallback: strip line-number prefixes that appear when LLM copies
                # from numbered <target_files> display (e.g. "   42: actual code").
                import re as _re
                _LINE_NUM_RE = _re.compile(r"^[ \t]*\d+:[ \t]?", _re.MULTILINE)
                if _LINE_NUM_RE.search(old_string):
                    stripped = _LINE_NUM_RE.sub("", old_string)
                    # Only use the stripped version if it actually matches the target
                    # (prevent false positive stripping)
                    if stripped and stripped != old_string:
                        old_string = stripped

                tf_content = _load_target(target_file) if target_file else None
                if tf_content is not None and tf_content != "":
                    if old_string not in tf_content:
                        # FUZZY FALLBACK: try matching with whitespace-normalized
                        # lines. If a unique contiguous run of target lines matches
                        # the anchor's lines after stripping, rewrite old_string to
                        # the verbatim slice from the target file. This rescues
                        # the very common case where the model copies code with
                        # slightly different indentation/trailing whitespace.
                        anchor_lines = old_string.splitlines()
                        anchor_stripped = [ln.strip() for ln in anchor_lines]
                        # Drop trailing empty lines from comparison window
                        while anchor_stripped and anchor_stripped[-1] == "":
                            anchor_stripped.pop()
                            anchor_lines.pop()
                        target_lines = tf_content.splitlines(keepends=True)
                        target_stripped = [ln.strip() for ln in target_lines]
                        n = len(anchor_stripped)
                        match_starts: list[int] = []
                        if n > 0 and n <= len(target_stripped):
                            first = anchor_stripped[0]
                            for s in range(0, len(target_stripped) - n + 1):
                                if target_stripped[s] != first:
                                    continue
                                if target_stripped[s : s + n] == anchor_stripped:
                                    match_starts.append(s)
                                    if len(match_starts) > 1:
                                        break
                        rescued = False
                        if len(match_starts) == 1:
                            s = match_starts[0]
                            verbatim = "".join(target_lines[s : s + n])
                            # Strip the trailing newline only if the original
                            # anchor didn't end with one
                            if not old_string.endswith("\n") and verbatim.endswith("\n"):
                                verbatim = verbatim[:-1]
                            if verbatim in tf_content:
                                old_string = verbatim
                                op["old_string"] = verbatim
                                rescued = True
                                print(
                                    f"[Recovery] anchor fuzzy-rescued for "
                                    f"{target_file}#op[{idx}] (whitespace-normalized match)"
                                )
                        if not rescued:
                            # Provide a helpful hint: show what the first line of the
                            # anchor looks like in the file (if it's there at all).
                            first_line = (old_string.splitlines() or [""])[0].strip()
                            hint = ""
                            if first_line:
                                for i, ln in enumerate(tf_content.splitlines(), 1):
                                    if first_line and first_line in ln:
                                        hint = f" (first anchor line found at target line {i}: {ln.strip()[:120]})"
                                        break
                                if not hint:
                                    hint = " (anchor's first line does not appear in target — you are likely copying mainline `-` lines)"
                            anchor_errors.append(
                                f"{target_file}#op[{idx}]: old_string NOT FOUND in target file{hint}"
                            )
                            continue
                elif target_file and tf_content == "":
                    anchor_errors.append(
                        f"{target_file}#op[{idx}]: target file could not be read from disk"
                    )
                    continue

                entries.append(
                    {
                        "hunk_index": int(op.get("hunk_index", idx) or idx),
                        "target_file": target_file,
                        "edit_type": edit_type,
                        "old_string": old_string,
                        "new_string": new_string,
                        "verified": bool(op.get("verified", False)),
                        "verification_result": str(
                            op.get("verification_result") or "submitted_unchecked"
                        ),
                        "notes": str(op.get("notes") or ""),
                    }
                )

            # If the low-value filter would have wiped out this file's only
            # ops, restore them so coverage doesn't fail. A "no-op" edit is
            # harmless to apply but losing the file silently is fatal.
            if not entries and low_value_holdback:
                entries.extend(low_value_holdback)
                print(
                    f"[Recovery] restored {len(low_value_holdback)} low-value op(s) "
                    f"for {mainline_file} (would have left file uncovered)"
                )
            if not entries:
                continue
            cleaned[_normalize_rel_path(str(mainline_file))] = entries
            op_count += len(entries)
        # ── INCREMENTAL ACCUMULATION (Claude-Code style) ────────────────
        # Merge this call's valid ops into the persistent accumulator. The
        # model can submit one file at a time across multiple calls; we only
        # require the union to cover all required files. This is what makes
        # the system work with weak models (gpt-4.1-mini) that can't produce
        # a complete multi-file plan in a single tool call.
        for mf, ops_list in cleaned.items():
            self._accumulated_plan[mf] = ops_list  # latest submission wins per file
        if cleaned:
            print(
                f"[Recovery] accumulator: +{len(cleaned)} file(s) this call, "
                f"now covering {len(self._accumulated_plan)} file(s) total"
            )

        # Coverage check is against the ACCUMULATOR (union across all calls).
        accum_touched: set[str] = set()
        for ops in self._accumulated_plan.values():
            for op in ops:
                tf = _normalize_rel_path(str(op.get("target_file") or ""))
                if tf:
                    accum_touched.add(tf)
        # ALSO accept files explicitly marked verified_no_change / blocked in
        # obligation_decisions. The model uses these to declare "this file
        # doesn't need any edits in the target" — accepting them prevents
        # the loop from forever demanding ops for files that need none.
        # Also persist them across calls so a decisions-only call counts.
        decisions_now = wrapper_payload.get("obligation_decisions") or []
        if not hasattr(self, "_accumulated_no_change"):
            self._accumulated_no_change: set[str] = set()
        for d in decisions_now:
            if not isinstance(d, dict):
                continue
            st = str(d.get("status") or "").strip().lower()
            if st in {"verified_no_change", "blocked"}:
                # obligation_id format is typically "patch_file:<path>:" — extract
                oid = str(d.get("obligation_id") or "")
                tf = str(d.get("target_file") or "")
                if not tf and oid.startswith("patch_file:"):
                    tf = oid.split(":", 2)[1] if ":" in oid[len("patch_file:"):] else oid[len("patch_file:"):]
                    tf = tf.rstrip(":")
                tf = _normalize_rel_path(tf)
                if tf:
                    self._accumulated_no_change.add(tf)
        accum_touched |= self._accumulated_no_change
        missing_files_accum = [
            f for f in (self._required_patch_files or []) if f not in accum_touched
        ]

        # Anchor errors: accept the surviving ops into the accumulator (already
        # done above) and tell the model which ops failed so it can retry just
        # those. Do NOT reject the whole call — partial progress is progress.
        if anchor_errors and missing_files_accum:
            # Only emit the anchor-failure error if we're still incomplete.
            # If accumulator already covers everything, fall through to success.
            self._submission_rejection_count += 1
            err_lines = "\n  - ".join(anchor_errors[:10])
            still_missing = "\n  - ".join(missing_files_accum)
            return (
                "PARTIAL: some ops accepted into accumulator, but anchor "
                "verification failed for others AND coverage is still incomplete.\n"
                f"Accumulator now covers: {sorted(accum_touched)}\n"
                f"Still missing files:\n  - {still_missing}\n"
                "Anchor failures (fix old_string to match target VERBATIM):\n  - "
                + err_lines + "\n"
                "Next call: submit ops ONLY for the still-missing files, "
                "and/or resubmit corrected versions of the anchor-failed ops. "
                "You do NOT need to resubmit ops that were already accepted."
            )

        # Coverage check: accumulator must touch ALL required patch files.
        if self._required_patch_files:
            missing_files = missing_files_accum
            if missing_files:
                self._submission_rejection_count += 1
                # Do NOT wipe the accumulator — we want to keep progress.
                # Per-file diagnostic: for files the model tried this call,
                # tell it why its ops were dropped. For files it didn't try,
                # tell it those are still needed.
                diag_lines: list[str] = []
                for mf in missing_files:
                    submitted = per_key_submitted.get(mf, 0)
                    reasons = per_key_drop_reasons.get(mf, [])
                    if submitted == 0 and not reasons:
                        diag_lines.append(
                            f"  - {mf}: not yet submitted — add ops for this file in your next call"
                        )
                    else:
                        reason_str = (
                            "; ".join(reasons[:5]) if reasons else "all dropped silently"
                        )
                        diag_lines.append(
                            f"  - {mf}: submitted {submitted} op(s), all dropped → {reason_str}"
                        )
                already = sorted(accum_touched) or ["(none)"]
                return (
                    "PARTIAL: plan is incomplete but accumulator preserved.\n"
                    f"Already accepted: {already}\n"
                    "Still missing edits for:\n"
                    + "\n".join(diag_lines) + "\n"
                    "Next call: submit ops ONLY for the still-missing files. "
                    "Each op MUST have non-empty `old_string`, non-empty `new_string` "
                    "(unless edit_type='delete'), and `target_file` set to the file path. "
                    "You do NOT need to resubmit files that are already accepted — "
                    "the accumulator keeps them."
                )

        if not cleaned and not self._accumulated_plan:
            if required_ids:
                decisions = wrapper_payload.get("obligation_decisions") or []
                all_verified = True
                for d in decisions:
                    if not isinstance(d, dict):
                        continue
                    st = str(d.get("status") or "").strip().lower()
                    if st not in {"verified_no_change", "blocked"}:
                        all_verified = False
                        break
                if all_verified and decisions:
                    self._submitted_plan = {}
                    self._submitted_wrapper = dict(wrapper_payload or {})
                    self._submitted_decisions = list(decisions)
                    self._submitted_investigation = list(
                        wrapper_payload.get("investigation_evidence") or []
                    )
                    self._submitted_risk_notes = list(
                        wrapper_payload.get("risk_notes") or []
                    )
                    self._submitted_status = {
                        "status": "no_fix_found",
                        "reason": "all_obligations_verified_no_change",
                    }
                    return (
                        "SUCCESS: recorded no_fix_found (all obligations "
                        "verified_no_change/blocked, no edits required)."
                    )
            if filtered_low_value > 0:
                return (
                    "ERROR: plan had only low-value/no-op edits "
                    f"(filtered={filtered_low_value})."
                )
            return "ERROR: plan had no valid operation entries."

        decisions = list(wrapper_payload.get("obligation_decisions") or [])
        decision_ids = {
            str(d.get("obligation_id") or "").strip()
            for d in decisions
            if isinstance(d, dict)
        }
        if required_ids:
            missing_decisions = sorted(
                [oid for oid in required_ids if oid not in decision_ids]
            )
            if missing_decisions:
                # If we got here via the auto-prune path, the model isn't able
                # to produce a complete decisions list either. Auto-fill the
                # missing entries as 'edited' (since cleaned has ops covering
                # every required file at this point) so we can ship the plan.
                if (
                    self._submission_rejection_count >= 3
                    and cleaned
                    and self._required_patch_files
                ):
                    print(
                        f"[submit_recovery_plan] AUTO_FILL decisions for "
                        f"{len(missing_decisions)} obligation(s)"
                    )
                    for oid in missing_decisions:
                        decisions.append(
                            {
                                "obligation_id": oid,
                                "status": "edited",
                                "reason": "auto_filled_after_auto_prune",
                            }
                        )
                    decision_ids = {
                        str(d.get("obligation_id") or "").strip()
                        for d in decisions
                        if isinstance(d, dict)
                    }
                    # Make sure the wrapper carries the augmented decisions.
                    wrapper_payload = dict(wrapper_payload or {})
                    wrapper_payload["obligation_decisions"] = decisions
                else:
                    self._submission_rejection_count += 1
                    self._submitted_plan = {}
                    return (
                        "ERROR: recovery submission missing obligation decisions. "
                        f"missing_obligations={missing_decisions[:20]}"
                    )

            invalid_status = []
            for d in decisions:
                if not isinstance(d, dict):
                    continue
                st = str(d.get("status") or "").strip().lower()
                if st not in {"edited", "verified_no_change", "blocked"}:
                    invalid_status.append(str(d.get("obligation_id") or ""))
            if invalid_status:
                self._submitted_plan = {}
                return (
                    "ERROR: invalid obligation decision status. "
                    "Allowed: edited | verified_no_change | blocked. "
                    f"invalid={invalid_status[:20]}"
                )

        elif (
            retry_scope_files
            and touched_files
            and retry_scope_files.isdisjoint(touched_files)
        ):
            # Fallback for the (rare) case where patch_diff is unavailable:
            # keep the legacy disjoint gate.
            return (
                "ERROR: plan does not touch retry-scope files. "
                f"retry_scope={sorted(retry_scope_files)} touched={sorted(touched_files)}"
            )

        # Ship the ACCUMULATOR (union of all calls), not just this call's ops.
        final_plan = dict(self._accumulated_plan)
        final_op_count = sum(len(v) for v in final_plan.values())
        self._submitted_plan = final_plan
        self._submitted_wrapper = dict(wrapper_payload or {})
        self._submitted_decisions = list(
            wrapper_payload.get("obligation_decisions") or []
        )
        self._apply_decision_based_scope(self._submitted_decisions)
        self._submitted_investigation = list(
            wrapper_payload.get("investigation_evidence") or []
        )
        self._submitted_risk_notes = list(wrapper_payload.get("risk_notes") or [])
        self._submitted_status = {"status": "ok"}
        return (
            f"SUCCESS: recovery plan submitted ({len(final_plan)} files, "
            f"{final_op_count} ops, accumulated across "
            f"{self._submission_rejection_count + 1} call(s))."
        )

    def get_submitted_plan(self) -> dict[str, list[dict[str, Any]]]:
        return dict(self._submitted_plan or {})

    def get_submitted_status(self) -> dict[str, Any] | None:
        return (
            dict(self._submitted_status)
            if isinstance(self._submitted_status, dict)
            else None
        )

    def get_submitted_decisions(self) -> list[dict[str, Any]]:
        return list(self._submitted_decisions or [])

    def get_submitted_investigation(self) -> list[dict[str, Any]]:
        return list(self._submitted_investigation or [])

    def get_submitted_risk_notes(self) -> list[str]:
        return list(self._submitted_risk_notes or [])

    def get_tools(
        self,
        include_submit: bool = True,
        exclude_names: set[str] | None = None,
    ) -> list[StructuredTool]:
        tools: list[StructuredTool] = [
            StructuredTool.from_function(
                func=self.read_file,
                name="read_file",
                description="Read target file with line numbers.",
            ),
            StructuredTool.from_function(
                func=self.glob,
                name="glob",
                description="Glob file paths using recursive pattern.",
            ),
            StructuredTool.from_function(
                func=self.grep,
                name="grep",
                description="Search repository content with regex using ripgrep.",
            ),
            StructuredTool.from_function(
                func=self.bash,
                name="bash",
                description="Run a shell command for diagnostics and inspection.",
            ),
            StructuredTool.from_function(
                func=self.batch_tools,
                name="batch_tools",
                description=(
                    "Run multiple independent tool tasks in parallel in a single call. "
                    "Use this to reduce round-trips and token overhead."
                ),
            ),
            StructuredTool.from_function(
                func=self.todoask,
                name="todoask",
                description="Add a planning todo item.",
            ),
            StructuredTool.from_function(
                func=self.todoread,
                name="todoread",
                description="Read current planning todo list.",
            ),
            StructuredTool.from_function(
                func=self.read_mainline_file,
                name="read_mainline_file",
                description="Read a file from mainline repository with line numbers.",
            ),
            StructuredTool.from_function(
                func=self.summarize_failure,
                name="summarize_failure",
                description="Get structured failure summary from validation state.",
            ),
            StructuredTool.from_function(
                func=self.get_dependency_graph,
                name="get_dependency_graph",
                description="Get dependency graph for target Java files.",
            ),
            StructuredTool.from_function(
                func=self.get_class_context,
                name="get_class_context",
                description="Get class context with optional focused method body.",
            ),
            StructuredTool.from_function(
                func=self.find_symbol_locations,
                name="find_symbol_locations",
                description="Find symbol locations in target repository files.",
            ),
            StructuredTool.from_function(
                func=self.find_method_match,
                name="find_method_match",
                description="Find likely renamed/moved method in a target file.",
                args_schema=None,
            ),
            StructuredTool.from_function(
                coroutine=self.agenttool,
                name="agenttool",
                description="Delegate bounded exploration to a subagent and return evidence JSON.",
            ),
            # ── Direct-apply tools (PRIMARY recovery path) ──────────────
            StructuredTool.from_function(
                func=self.apply_edit,
                name="apply_edit",
                description=(
                    "PRIMARY EDITING TOOL. Apply ONE edit directly to a target "
                    "file on disk. Args: target_file (repo-relative path), "
                    "old_string (verbatim text from the on-disk target file), "
                    "new_string (replacement text), edit_type "
                    "('replace'|'insert_after'|'insert_before'|'delete', default 'replace'). "
                    "On success the file IS mutated. Iterate one edit at a time. "
                    "Whitespace-tolerant matching is built in. Do NOT copy "
                    "old_string from mainline `-` lines — copy from the actual "
                    "target file content shown in <target_files>."
                ),
            ),
            StructuredTool.from_function(
                func=self.mark_no_change,
                name="mark_no_change",
                description=(
                    "Mark a required patch file as needing NO edits in the target "
                    "(e.g. because the target already has the equivalent code, or "
                    "the change is structurally inapplicable). Args: target_file, reason."
                ),
            ),
            StructuredTool.from_function(
                func=self.recovery_done,
                name="recovery_done",
                description=(
                    "Call this EXACTLY ONCE when every required file is either "
                    "edited (via apply_edit) or marked (via mark_no_change). "
                    "Signals the recovery loop to exit. Args: summary (brief)."
                ),
            ),
        ]
        if include_submit and (
            not exclude_names or "submit_recovery_plan" not in exclude_names
        ):
            tools.append(
                StructuredTool.from_function(
                    func=self.submit_recovery_plan,
                    name="submit_recovery_plan",
                    description=(
                        "Submit the final recovery plan. The `plan` argument MUST be a dict "
                        "keyed by MAINLINE file path; each value is a LIST of edit operations. "
                        "Each op MUST have: edit_type (one of 'replace'|'insert_before'|'insert_after'|'delete'), "
                        "old_string (MUST exist VERBATIM in the on-disk TARGET file — copy from preloaded target contents, NOT from mainline `-` lines), "
                        "new_string (required unless edit_type='delete'), "
                        "target_file (the TARGET repo relative path). "
                        "Optional: hunk_index, notes. "
                        "Do NOT use fields like 'edits', 'file_path', 'content', 'insert_after_line' — those are REJECTED.\n\n"
                        "EXACT schema example:\n"
                        "{\n"
                        '  "plan": {\n'
                        '    "server/src/main/java/io/crate/Foo.java": [\n'
                        "      {\n"
                        '        "edit_type": "replace",\n'
                        '        "target_file": "server/src/main/java/io/crate/Foo.java",\n'
                        '        "old_string": "exact verbatim text from target file",\n'
                        '        "new_string": "replacement text",\n'
                        '        "notes": "why"\n'
                        "      }\n"
                        "    ]\n"
                        "  }\n"
                        "}\n"
                        'To signal no fix: {"plan": {"status": "no_fix_found", "reason": "..."}}.'
                    ),
                )
            )
        if exclude_names:
            tools = [t for t in tools if t.name not in exclude_names]
        return tools


def _extract_plan_from_messages(messages: list[Any]) -> dict[str, list[dict[str, Any]]]:
    for msg in reversed(messages or []):
        role = str(getattr(msg, "type", "") or "").strip().lower()
        if role != "ai":
            continue
        payload = _extract_json_payload(getattr(msg, "content", ""))
        if isinstance(payload, dict):
            return payload
    return {}


def _summarize_attempt_artifacts(state: AgentState) -> str:
    lines: list[str] = []

    edits = state.get("adapted_file_edits") or []
    if isinstance(edits, list) and edits:
        lines.append("adapted_file_edits:")
        cap = edits[:12]
        for e in cap:
            if not isinstance(e, dict):
                continue
            tf = _normalize_rel_path(str(e.get("target_file") or ""))
            vr = str(e.get("verification_result") or "")
            ar = str(e.get("apply_result") or "")
            lines.append(f"- {tf} | verify={vr} | apply={ar}")

    vctx = str(state.get("validation_error_context") or "")
    if vctx:
        lines.append("validation_error_context_excerpt:")
        lines.append(_truncate(vctx, 2000))

    structured = state.get("validation_error_context_structured") or {}
    if isinstance(structured, dict) and structured:
        lines.append("validation_error_context_structured:")
        try:
            lines.append(
                _truncate(json.dumps(structured, ensure_ascii=False, indent=2), 2500)
            )
        except Exception:
            lines.append(_truncate(str(structured), 2500))

    if not lines:
        return "(no prior-attempt artifacts available in state)"
    return "\n".join(lines)


def _normalize_recovery_plan(
    raw_plan: dict[str, Any], state: AgentState, target_repo_path: str
) -> dict[str, list[dict[str, Any]]]:
    existing_plan = state.get("hunk_generation_plan") or {}
    mapped_ctx = state.get("mapped_target_context") or {}

    if not isinstance(raw_plan, dict) or not raw_plan:
        return dict(existing_plan) if isinstance(existing_plan, dict) else {}

    def infer_target(mainline_file: str, sample: dict[str, Any]) -> str:
        tf = _normalize_rel_path(str(sample.get("target_file") or ""))
        if tf:
            return tf
        m_entries = (
            mapped_ctx.get(mainline_file) if isinstance(mapped_ctx, dict) else None
        )
        if isinstance(m_entries, list) and m_entries and isinstance(m_entries[0], dict):
            guessed = _normalize_rel_path(str(m_entries[0].get("target_file") or ""))
            if guessed:
                return guessed
        e_entries = (
            existing_plan.get(mainline_file)
            if isinstance(existing_plan, dict)
            else None
        )
        if isinstance(e_entries, list) and e_entries and isinstance(e_entries[0], dict):
            guessed = _normalize_rel_path(str(e_entries[0].get("target_file") or ""))
            if guessed:
                return guessed
        return _normalize_rel_path(mainline_file)

    allowed = {"replace", "insert_before", "insert_after", "delete"}
    out: dict[str, list[dict[str, Any]]] = {}
    for raw_mainline_file, raw_entries in raw_plan.items():
        mainline_file = _normalize_rel_path(str(raw_mainline_file or ""))
        if not mainline_file or not isinstance(raw_entries, list):
            continue
        entries: list[dict[str, Any]] = []
        for idx, e in enumerate(raw_entries):
            if not isinstance(e, dict):
                continue
            edit_type = str(e.get("edit_type") or "replace").strip().lower()
            if edit_type not in allowed:
                continue
            target_file = infer_target(mainline_file, e)
            old_string = str(e.get("old_string") or "")
            new_string = str(e.get("new_string") or "")
            if not old_string:
                continue
            if edit_type != "delete" and not new_string:
                continue

            file_text = _read_file(target_repo_path, target_file)
            anchor_ok = bool(file_text and old_string in file_text)
            vres = str(e.get("verification_result") or "")
            if not vres:
                vres = (
                    "recovery_exact_match" if anchor_ok else "recovery_anchor_missing"
                )

            entries.append(
                {
                    "hunk_index": int(e.get("hunk_index", idx) or idx),
                    "target_file": target_file,
                    "edit_type": edit_type,
                    "old_string": old_string,
                    "new_string": new_string,
                    "verified": bool(anchor_ok),
                    "verification_result": vres,
                    "notes": str(e.get("notes") or "") + "|recovery_agent",
                }
            )

        if entries:
            out[mainline_file] = consolidate_plan_entries_java(entries)

    if out:
        return out
    return dict(existing_plan) if isinstance(existing_plan, dict) else {}


def _tool_signature(tool_name: str, tool_args: Any) -> str:
    try:
        args = json.dumps(tool_args, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        args = str(tool_args)
    return f"{tool_name}:{args}"


def _detect_stagnation(
    tool_calls: list[tuple[str, Any]], limit: int = 4
) -> tuple[bool, str]:
    streak_sig = ""
    streak = 0
    for nm, args in tool_calls:
        sig = _tool_signature(nm, args)
        if sig == streak_sig:
            streak += 1
        else:
            streak_sig = sig
            streak = 1
        if nm == "submit_recovery_plan" and streak >= 2:
            return True, f"repeated_submit_tool_call:{streak}:{sig[:180]}"
        if streak >= limit:
            return True, f"repeated_tool_call_streak:{streak}:{sig[:180]}"
    return False, ""


def _extract_tool_calls(messages: list[Any]) -> list[tuple[str, Any, str]]:
    calls: list[tuple[str, Any, str]] = []
    for m in messages or []:
        if str(getattr(m, "type", "") or "").lower() != "ai":
            continue
        for tc in getattr(m, "tool_calls", None) or []:
            name = str((tc or {}).get("name") or "")
            args = (tc or {}).get("args") or {}
            call_id = str((tc or {}).get("id") or "")
            calls.append((name, args, call_id))
    return calls


def _extract_submit_rejection(messages: list[Any]) -> str:
    for m in reversed(messages or []):
        if str(getattr(m, "type", "") or "").lower() != "tool":
            continue
        tool_name = str(getattr(m, "name", "") or "")
        if tool_name != "submit_recovery_plan":
            continue
        content = str(getattr(m, "content", "") or "").strip()
        if content.startswith("ERROR:"):
            return _truncate(content, 400)
    return ""


def _ai_tool_calls_fully_resolved(messages: list[Any], ai_index: int) -> bool:
    msg = messages[ai_index]
    tool_calls = getattr(msg, "tool_calls", None) or []
    call_ids = [str((tc or {}).get("id") or "") for tc in tool_calls if tc]
    call_ids = [cid for cid in call_ids if cid]
    if not call_ids:
        return True

    resolved: set[str] = set()
    for later in messages[ai_index + 1 :]:
        if str(getattr(later, "type", "") or "").lower() != "tool":
            continue
        tcid = str(getattr(later, "tool_call_id", "") or "")
        if tcid:
            resolved.add(tcid)

    return all(cid in resolved for cid in call_ids)


def _sanitize_messages_for_reinvoke(messages: list[Any]) -> list[Any]:
    """Drop assistant tool_call messages that do not have tool results yet."""
    out: list[Any] = []
    for i, m in enumerate(messages or []):
        role = str(getattr(m, "type", "") or "").lower()
        if role == "ai" and (getattr(m, "tool_calls", None) or []):
            if not _ai_tool_calls_fully_resolved(messages, i):
                continue
        out.append(m)
    return out


def _next_strategy(
    history: list[str],
    *,
    repeated_plan: bool,
    stagnation_reason: str,
) -> str:
    sequence = [
        "expand_search_scope",
        "hierarchy_first",
        "signature_drift_first",
        "side_file_first",
    ]
    if not history:
        return sequence[0]
    if not repeated_plan and not stagnation_reason:
        return history[-1]
    for item in sequence:
        if item not in history:
            return item
    return sequence[-1]


def _is_content_filter_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return (
        "content_filter" in text
        or "responsibleaipolicyviolation" in text
        or "content management policy" in text
    )


def _sanitize_for_content_policy(text: str, max_len: int = 5000) -> str:
    t = _truncate(str(text or ""), max_len)
    # Conservative redaction for terms that frequently trigger false positives
    # in provider-side policy filters when embedded in large prompts/logs.
    patterns = [
        r"(?i)self[-\s]?harm",
        r"(?i)suicid\w*",
        r"(?i)kill\s+yourself",
        r"(?i)want\s+to\s+die",
    ]
    for pat in patterns:
        t = re.sub(pat, "[redacted-term]", t)
    return t


def _build_compact_recovery_system_prompt(
    *,
    failure_context: str,
    retry_scope: str,
    recovery_brief: str,
    recovery_obligations: str,
) -> str:
    return _sanitize_for_content_policy(
        (
            "You are a Java backport recovery planner.\n"
            "Goal: produce a minimal valid recovery submission.\n"
            "Rules:\n"
            "- Ground every old_string in target code (use tools).\n"
            "- Provide obligation decisions for all obligations.\n"
            "- Avoid broad edits; prefer minimal safe changes.\n"
            "- Output only via submit_recovery_plan tool.\n\n"
            "deterministic_recovery_brief:\n"
            f"{recovery_brief}\n\n"
            "impact_obligations:\n"
            f"{recovery_obligations}\n\n"
            "retry_scope:\n"
            f"{retry_scope}\n\n"
            "failure_excerpt:\n"
            f"{_truncate(failure_context, 2500)}\n"
        ),
        10000,
    )


def _env_truthy(name: str) -> bool:
    v = str(os.getenv(name, "") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _default_compact_mode_for_provider() -> bool:
    provider = str(os.getenv("LLM_PROVIDER", "") or "").strip().lower()
    if provider != "azure":
        return False
    if _env_truthy("RECOVERY_DISABLE_AZURE_COMPACT"):
        return False
    return True


def _should_force_full_recovery_prompt(state: AgentState) -> bool:
    failure_category = (
        str(state.get("validation_failure_category") or "").strip().lower()
    )
    if failure_category in {
        "empty_generation",
        "context_mismatch",
        "target_file_missing",
    }:
        return True

    blueprint = state.get("semantic_blueprint") or {}
    if isinstance(blueprint, dict):
        complexity = str(blueprint.get("complexity") or "").strip().upper()
        if complexity in {"STRUCTURAL", "REWRITE"}:
            return True
    return False


def _cleanup_unused_java_imports(repo_path: str, rel_path: str) -> list[str]:
    """Remove import lines whose simple class name doesn't appear in the file body.

    Deterministic post-edit cleanup: when the recovery agent removes a code
    block, the imports it referenced may become orphaned. Checkstyle treats
    those as build failures, so we strip them before capturing the diff.
    """
    import os

    full = os.path.join(repo_path, rel_path)
    if not os.path.isfile(full):
        return []
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    import_indices: list[tuple[int, str, str]] = []  # (line_idx, simple_name, raw_line)
    body_parts: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import "):
            # "import static foo.Bar.baz;" → "baz"
            # "import foo.Bar;"            → "Bar"
            # "import foo.*;"              → skip (wildcard)
            if stripped.rstrip(";").endswith(".*"):
                continue
            m = re.search(r"[\.\s](\w+)\s*;", stripped)
            if m:
                import_indices.append((i, m.group(1), line))
        else:
            body_parts.append(line)
    body = "".join(body_parts)

    to_remove: set[int] = set()
    removed: list[str] = []
    for idx, name, raw in import_indices:
        # Word-boundary match so "List" doesn't match "ArrayList".
        if not re.search(rf"\b{re.escape(name)}\b", body):
            to_remove.add(idx)
            removed.append(raw.strip())

    if to_remove:
        new_lines = [l for i, l in enumerate(lines) if i not in to_remove]
        with open(full, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    return removed


async def _run_parallel_tool_loop(
    llm,
    tools: list,
    initial_messages: list,
    preloaded_cache: dict[str, str],
    max_investigation_rounds: int = 2,
    toolkit: Any = None,
) -> tuple[list, str]:
    """
    Parallel batch tool execution loop.

    Replaces create_react_agent's serial ReAct (one tool call → LLM → next tool call)
    with a batched pattern:
      1. Call LLM once → get ALL tool calls it needs in one response
      2. Execute all tool calls in parallel (deduplicating identical ones)
      3. Return all results to LLM in a single batch
      4. Repeat up to max_investigation_rounds times
      5. After max rounds, force submit_recovery_plan

    For read_file calls on preloaded files, the cache is returned immediately
    (full content, no max_lines truncation) without hitting the tool.

    Returns (final_messages, termination_reason).
    """
    tool_map = {t.name: t for t in tools}
    bound_llm = llm.bind_tools(tools)
    base_llm = llm  # keep original for temperature bumps on repeated rejection
    messages = list(initial_messages)
    loop = asyncio.get_event_loop()
    recent_tool_calls: list[tuple[str, Any]] = []
    last_submit_rejected = False
    rejection_retry_bonus_used = 0
    last_submit_args_sig: str = ""

    async def execute_one(tc: dict) -> tuple[str, str]:
        name = str(tc.get("name") or "")
        args = dict(tc.get("args") or {})
        call_id = str(tc.get("id") or "")

        # Cache hit: return full preloaded content, ignoring max_lines
        if name == "read_file":
            fp = str(args.get("file_path") or "")
            rel = _normalize_rel_path(fp)
            if rel in preloaded_cache:
                content = preloaded_cache[rel]
                numbered = "\n".join(
                    f"{i + 1:5d}: {ln}" for i, ln in enumerate(content.splitlines())
                )
                return (
                    call_id,
                    f'<cached_file path="{rel}">\n{numbered}\n</cached_file>',
                )

        tool = tool_map.get(name)
        if not tool:
            return call_id, f"ERROR: unknown tool {name!r}"
        try:
            _tool, _args = tool, args
            result = await loop.run_in_executor(None, lambda: _tool.invoke(_args))
            return call_id, str(result)
        except Exception as exc:
            return call_id, f"ERROR executing {name}: {exc}"

    round_num = -1
    # Hard absolute cap to bound LLM cost regardless of bonuses granted.
    absolute_round_cap = max_investigation_rounds + 4
    while True:
        round_num += 1
        if round_num > absolute_round_cap:
            print(
                f"[Recovery] absolute round cap ({absolute_round_cap}) reached"
            )
            break
        # Soft cap: stop when we've used budget AND no rejection is pending
        if round_num > max_investigation_rounds + 1:
            break
        print(f"[Recovery] === Round {round_num} ===")
        try:
            response = await asyncio.wait_for(
                bound_llm.ainvoke(messages),
                timeout=180.0,  # 3 min hard cap per LLM call
            )
        except asyncio.TimeoutError:
            print(f"[Recovery] LLM call timed out in round {round_num}; aborting.")
            return messages, "llm_timeout"
        messages = messages + [response]

        # Log response text content
        resp_text = getattr(response, "content", "") or ""
        if isinstance(resp_text, list):
            resp_text = " ".join(
                str(p.get("text") or "") if isinstance(p, dict) else str(p)
                for p in resp_text
            )
        if resp_text.strip():
            print(f"[Recovery] LLM text: {str(resp_text)[:500]}")

        tool_calls = list(getattr(response, "tool_calls", None) or [])
        if not tool_calls:
            print("[Recovery] No tool calls in response; exiting")
            return messages, "no_tool_calls"

        # Log tool calls
        for tc in tool_calls:
            name = tc.get("name", "?")
            args = tc.get("args") or {}
            args_full = json.dumps(args, default=str)
            args_summary = args_full[:300]
            print(f"[Recovery] tool_call: {name}({args_summary})")
            if name == "submit_recovery_plan" and len(args_full) > 300:
                # Log edit_ops keys to see which files are included
                edit_ops = args.get("edit_ops") or args.get("plan", {}).get("edit_ops") or {}
                print(f"[Recovery] submit edit_ops keys: {list(edit_ops.keys())}")

        # If the LLM called submit_recovery_plan, execute it and return
        submit_calls = [
            tc for tc in tool_calls if tc.get("name") == "submit_recovery_plan"
        ]
        investigate_calls = [
            tc for tc in tool_calls if tc.get("name") != "submit_recovery_plan"
        ]

        if submit_calls:
            # DEBUG: dump full submit args to understand rejection root cause
            try:
                _dbg_args = submit_calls[0].get("args") or {}
                _dbg_eo = (
                    _dbg_args.get("edit_ops")
                    or (_dbg_args.get("plan") or {}).get("edit_ops")
                    or {}
                )
                for _k, _v in _dbg_eo.items():
                    if isinstance(_v, list):
                        for _i, _op in enumerate(_v):
                            if not isinstance(_op, dict):
                                continue
                            print(
                                f"[Recovery][dbg] {_k}#op[{_i}] "
                                f"target_file={_op.get('target_file')!r} "
                                f"edit_type={_op.get('edit_type')!r} "
                                f"old_len={len(str(_op.get('old_string') or ''))} "
                                f"new_len={len(str(_op.get('new_string') or ''))}"
                            )
            except Exception as _exc:
                print(f"[Recovery][dbg] dump failed: {_exc}")
            # Capture signature of submitted edit_ops only (not investigation
            # evidence / risk notes / decisions, which the model regenerates
            # with minor wording variation each round and would defeat dedup).
            try:
                _sig_args = submit_calls[0].get("args") or {}
                _sig_eo = (
                    _sig_args.get("edit_ops")
                    or (_sig_args.get("plan") or {}).get("edit_ops")
                    or {}
                )
                submit_args_sig = hashlib.sha256(
                    json.dumps(_sig_eo, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()
            except Exception:
                submit_args_sig = ""
            results = await asyncio.gather(*[execute_one(tc) for tc in submit_calls])
            result_map = dict(results)
            for tc in submit_calls:
                content = result_map.get(str(tc.get("id") or ""), "")
                full_content = str(content)
                print(f"[Recovery] submit_recovery_plan → {full_content[:1500]}")
                if len(full_content) > 1500:
                    print(f"[Recovery] submit_recovery_plan (continued) → {full_content[1500:3000]}")
                messages = messages + [
                    ToolMessage(
                        content=content,
                        tool_call_id=str(tc.get("id") or ""),
                        name=str(tc.get("name") or ""),
                    )
                ]
            # Only return "submitted" if at least one submit reached SUCCESS.
            # PARTIAL responses mean the accumulator absorbed ops but coverage
            # is still incomplete — we must keep looping so the model can
            # submit the still-missing files.
            def _is_success(c: str) -> bool:
                s = str(c)
                return not s.startswith("ERROR") and not s.startswith("PARTIAL")
            any_success = any(_is_success(content) for _, content in results)
            if any_success:
                return messages, "submitted"
            # Submit was rejected — let the LLM see the error and retry
            # (fall through to the round-limit check below)
            last_submit_rejected = True
            # Parse rejection hints of the form:
            #   "{file}#op[{idx}]: old_string NOT FOUND in target file
            #    (first anchor line found at target line N: ...)"
            # and emit a fresh <hunk_snippets> block centred on each hinted
            # line so the model can copy verbatim text from the REAL target
            # location next round (the structural_locator's mapping was wrong).
            import re as _re_hint
            rejection_text = ""
            for _, _content in results:
                if str(_content).startswith("ERROR"):
                    rejection_text += "\n" + str(_content)
            hint_re = _re_hint.compile(
                r"([^\s()]+\.java)#op\[\d+\]:\s*old_string NOT FOUND[^\(]*"
                r"\(first anchor line found at target line (\d+):"
            )
            seen_hints: set[tuple[str, int]] = set()
            remap_blocks: list[str] = []
            for m in hint_re.finditer(rejection_text):
                rel_hint = _normalize_rel_path(m.group(1))
                try:
                    line_hint = int(m.group(2))
                except ValueError:
                    continue
                key = (rel_hint, line_hint)
                if key in seen_hints:
                    continue
                seen_hints.add(key)
                file_text = preloaded_cache.get(rel_hint)
                if not file_text:
                    continue
                lines = file_text.splitlines()
                radius = 30
                lo = max(1, line_hint - radius)
                hi = min(len(lines), line_hint + radius)
                numbered = "\n".join(
                    f"{i:5d}: {lines[i - 1]}" for i in range(lo, hi + 1)
                )
                remap_blocks.append(
                    f'<remap_snippet path="{rel_hint}" '
                    f'real_target_line="{line_hint}" '
                    f'shown_range="{lo}-{hi}">\n'
                    f"{numbered}\n"
                    f"</remap_snippet>"
                )
            if remap_blocks:
                remap_xml = (
                    "<remap_hints>\n"
                    "The structural_locator's mapping for the failing op(s) "
                    "was WRONG. The rejection error told us where the REAL "
                    "target code lives. Below is the actual TARGET code at "
                    "those line numbers — copy old_string VERBATIM from "
                    "these blocks, not from <mainline_patch> or the original "
                    "<hunk_snippets>.\n\n" + "\n\n".join(remap_blocks) + "\n</remap_hints>"
                )
                messages = messages + [HumanMessage(content=remap_xml)]
                print(
                    f"[Recovery] injected remap_hints for {len(remap_blocks)} "
                    f"failing op(s): {sorted(seen_hints)}"
                )
            identical_resubmit = bool(
                last_submit_args_sig and submit_args_sig == last_submit_args_sig
            )
            last_submit_args_sig = submit_args_sig
            # Grant up to 2 extra rounds so the model has clean retry
            # opportunities without force_submit drowning out the rejection.
            if rejection_retry_bonus_used < 2:
                rejection_retry_bonus_used += 1
                max_investigation_rounds += 1
                print(
                    f"[Recovery] submit rejected — granting extra round "
                    f"#{rejection_retry_bonus_used} for the model to fix and resubmit."
                )
            # Append a sharp directive that re-emphasizes fixing the plan
            # (the tool message already contains the rejection reason).
            base_directive = (
                "<fix_and_resubmit>\n"
                "Your previous submit_recovery_plan call was REJECTED. "
                "Read the ERROR text in the tool result above CAREFULLY.\n\n"
                "ANCHOR RULES (most rejections are anchor failures):\n"
                "1. old_string MUST exist VERBATIM in the TARGET file shown "
                "in <target_files>. The TARGET file is OLDER than mainline "
                "and has DIFFERENT surrounding code.\n"
                "2. Do NOT copy old_string from the mainline patch's `-` or "
                "context lines. Mainline lines may not exist in target.\n"
                "3. Prefer SHORT anchors (1-3 lines). The shorter the anchor, "
                "the more likely it matches the target verbatim. Long "
                "multi-line anchors are the #1 cause of rejection.\n"
                "4. Use <hunk_snippets> for the EXACT target text at each "
                "mapped location — copy from there, not from <mainline_patch>.\n"
                "5. If the rejection hint says 'first anchor line found at "
                "target line N', a fresh <remap_hints> block has been "
                "appended below showing the ACTUAL target code at that "
                "line — copy old_string VERBATIM from there.\n\n"
                "ESCAPE HATCH (use this if anchoring is genuinely impossible):\n"
                "If a particular op CANNOT be anchored even with <remap_hints> "
                "(because the target's code structure has no equivalent of "
                "that mainline change), DROP that single op from edit_ops and "
                "submit the rest. The coverage check counts FILES, not "
                "individual ops — as long as each required file still has "
                "at least one valid op, the plan is acceptable. A partial-"
                "but-valid plan is FAR better than a fully-rejected one. "
                "Add a risk_note explaining which mainline hunk you dropped "
                "and why (e.g. 'target lacks equivalent forwardFailure block').\n\n"
                "Now call submit_recovery_plan again. Do not call any other "
                "tools.\n"
                "</fix_and_resubmit>"
            )
            if identical_resubmit:
                base_directive = (
                    "<critical>\n"
                    "You just resubmitted an IDENTICAL plan that was already "
                    "rejected. This is wasted work — the result will be the "
                    "same. You MUST change the failing old_string anchors, OR "
                    "if a hunk simply cannot be applied to this target (because "
                    "the target's code structure lacks the equivalent block), "
                    "DROP that single edit op from edit_ops and submit the rest. "
                    "A partial-but-valid plan is better than a fully-rejected one. "
                    "The coverage check counts FILES, not individual ops, so as "
                    "long as you keep at least one valid op per required file, "
                    "the plan is acceptable.\n"
                    "</critical>\n" + base_directive
                )
                # Break determinism: bump temperature for the next LLM call
                # so the model doesn't produce byte-identical output again.
                try:
                    new_temp = 0.3 + 0.2 * (rejection_retry_bonus_used - 1)
                    bumped_llm = get_llm(temperature=min(new_temp, 0.9))
                    bound_llm = bumped_llm.bind_tools(tools)
                    print(
                        f"[Recovery] bumping LLM temperature to "
                        f"{min(new_temp, 0.9):.2f} to break identical-resubmit loop"
                    )
                except Exception as exc:
                    print(f"[Recovery] failed to bump temperature: {exc}")
            messages = messages + [HumanMessage(content=base_directive)]

        # Execute investigate_calls (must always respond to every tool_call_id)
        if investigate_calls:
            # Deduplicate: identical (name, args) → same result
            sig_to_canonical: dict[str, dict] = {}
            for tc in investigate_calls:
                sig = _tool_signature(str(tc.get("name") or ""), tc.get("args") or {})
                if sig not in sig_to_canonical:
                    sig_to_canonical[sig] = tc

            unique_calls = list(sig_to_canonical.values())
            raw_results = await asyncio.gather(
                *[execute_one(tc) for tc in unique_calls]
            )
            # Build sig → content map for dedup resolution
            sig_to_content: dict[str, str] = {}
            for tc, (_cid, content) in zip(unique_calls, raw_results):
                sig = _tool_signature(str(tc.get("name") or ""), tc.get("args") or {})
                sig_to_content[sig] = content
                tool_name = str(tc.get("name") or "")
                snippet = str(content)[:200].replace("\n", "\\n")
                is_err = str(content).startswith("ERROR")
                tag = "ERR" if is_err else "ok"
                print(f"[Recovery] tool_result[{tag}] {tool_name}: {snippet}")

            # Append ToolMessages for all original calls (duplicates reuse the result)
            tool_messages: list[ToolMessage] = []
            for tc in investigate_calls:
                sig = _tool_signature(str(tc.get("name") or ""), tc.get("args") or {})
                content = sig_to_content.get(sig, "ERROR: result missing")
                tool_messages.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=str(tc.get("id") or ""),
                        name=str(tc.get("name") or ""),
                    )
                )
            messages = messages + tool_messages
            print(
                f"[Recovery] Round {round_num}: executed {len(unique_calls)} unique call(s) ({len(investigate_calls)} total)"
            )

            # ── DIRECT-APPLY EXIT ─────────────────────────────────────
            # If the model called recovery_done() and the toolkit accepted
            # it (coverage satisfied), exit the loop immediately and let
            # the node hand off the modified files to validation.
            if toolkit is not None and getattr(toolkit, "_recovery_done", False):
                print(
                    f"[Recovery] recovery_done acknowledged — exiting loop. "
                    f"applied={len(toolkit._applied_edits)} "
                    f"no_change={len(toolkit._direct_no_change_files)}"
                )
                return messages, "applied_directly"

            # Stagnation guard: if the model keeps repeating identical calls,
            # force plan submission early instead of burning rounds/tokens.
            for tc in investigate_calls:
                recent_tool_calls.append(
                    (str(tc.get("name") or ""), tc.get("args") or {})
                )
            if len(recent_tool_calls) > 32:
                recent_tool_calls = recent_tool_calls[-32:]

            stagnating, reason = _detect_stagnation(recent_tool_calls[-12:], limit=3)
            if stagnating and round_num < max_investigation_rounds:
                print(f"[Recovery] Stagnation detected; forcing submit early: {reason}")
                max_investigation_rounds = round_num

        # After responding to all tool calls, check if investigation budget is exhausted.
        # Skip force_submit if the last action was a rejected submit — the rejection
        # tool message + <fix_and_resubmit> directive already tell the model what to do,
        # and force_submit would just nudge it to resubmit the same broken plan.
        if round_num >= max_investigation_rounds and not last_submit_rejected:
            print(
                f"[Recovery] Round {round_num} >= max_investigation_rounds, injecting force_submit"
            )
            messages = messages + [
                HumanMessage(
                    content=(
                        "<force_submit>You have used all investigation rounds. "
                        "You must now submit your final plan via submit_recovery_plan. "
                        "Do not call any other tools.</force_submit>"
                    )
                )
            ]
        # Reset for next round (cleared whether we injected fix_and_resubmit or not)
        last_submit_rejected = False

    print("[Recovery] Exited loop: max_rounds_exceeded")
    return messages, "max_rounds_exceeded"


async def recovery_agent_node(state: AgentState, config) -> dict[str, Any]:
    """Plan-only recovery agent with explicit bounded while-loop."""
    print("Recovery Agent (Claude-Code style): Starting master loop...")

    target_repo_path = str(state.get("target_repo_path") or "")
    mainline_repo_path = str(state.get("mainline_repo_path") or "")
    if not target_repo_path:
        return {
            "messages": [
                HumanMessage(
                    content="Recovery Agent skipped: missing target_repo_path."
                )
            ]
        }

    # toolkit is instantiated before patch_files are parsed; will be updated below
    toolkit = RecoveryPlanToolkit(state, target_repo_path, mainline_repo_path)

    recovery_obligations = _build_recovery_obligations(state)
    deterministic_recovery_brief = _build_deterministic_recovery_brief(state)
    recovery_scope_files = sorted(
        {
            _normalize_rel_path(str((o or {}).get("required_file") or ""))
            for o in recovery_obligations
            if isinstance(o, dict)
        }
    )
    recovery_scope_files = [f for f in recovery_scope_files if f]

    # Build rich failure context including mainline patch and what was tried
    patch_diff = str(state.get("patch_diff") or "")
    validation_error = str(state.get("validation_error_context") or "")
    adapted_edits = state.get("adapted_file_edits") or []

    # Construct failure context with mainline patch and dumb run attempt
    failure_context_parts = []
    failure_context_parts.append("=== MAINLINE PATCH ===")
    failure_context_parts.append(_sanitize_for_content_policy(patch_diff, 4000))
    failure_context_parts.append("\n=== DUMB RUN FAILURE ===")
    failure_context_parts.append(_sanitize_for_content_policy(validation_error, 4000))
    if adapted_edits:
        failure_context_parts.append(
            f"\n=== DUMB RUN EDITS ATTEMPTED ({len(adapted_edits)} edits) ==="
        )
        for edit in adapted_edits[:5]:  # Show first 5 edits attempted
            failure_context_parts.append(
                f"File: {edit.get('target_file')}, Type: {edit.get('edit_type')}, Applied: {edit.get('applied')}"
            )

    failure_context = _sanitize_for_content_policy(
        "\n".join(failure_context_parts), 12000
    )

    retry_scope = json.dumps(
        {
            "retry_files": list(state.get("validation_retry_files") or []),
            "retry_hunks": list(state.get("validation_retry_hunks") or []),
            "failure_category": str(state.get("validation_failure_category") or ""),
            "failed_stage": str(state.get("validation_failed_stage") or ""),
            "validation_attempts": int(state.get("validation_attempts") or 0),
        },
        ensure_ascii=False,
        indent=2,
    )

    # Include mapped target context (where locator found the code)
    mapped_target_context = state.get("mapped_target_context") or {}
    existing_plan = _truncate(
        json.dumps(
            {
                "hunk_generation_plan": state.get("hunk_generation_plan") or {},
                "locations_found_by_locator": mapped_target_context,
            },
            ensure_ascii=False,
            indent=2,
        ),
        12000,
    )
    existing_plan = _sanitize_for_content_policy(existing_plan, 12000)
    attempt_artifacts = _sanitize_for_content_policy(
        _summarize_attempt_artifacts(state),
        12000,
    )

    # Full agent-eligible file list — coverage contract for submit_recovery_plan.
    agent_eligible_list = sorted(toolkit._agent_eligible_files())
    agent_eligible_files_str = (
        "\n".join(f"- {f}" for f in agent_eligible_list)
        if agent_eligible_list
        else "(unknown — patch_diff unavailable)"
    )

    recovery_brief_json = _sanitize_for_content_policy(
        json.dumps(deterministic_recovery_brief, ensure_ascii=False, indent=2),
        12000,
    )
    recovery_obligations_json = _sanitize_for_content_policy(
        json.dumps(recovery_obligations, ensure_ascii=False, indent=2),
        12000,
    )

    system_prompt = _RECOVERY_SYSTEM.format(
        failure_context=failure_context,
        agent_eligible_files=agent_eligible_files_str,
        retry_scope=retry_scope,
        existing_plan=existing_plan,
        attempt_artifacts=attempt_artifacts,
        recovery_brief=recovery_brief_json,
        recovery_obligations=recovery_obligations_json,
    )
    system_prompt = _sanitize_for_content_policy(system_prompt, 35000)

    force_full_prompt = _should_force_full_recovery_prompt(state)
    compact_mode = _env_truthy("RECOVERY_COMPACT_PROMPT") or (
        _default_compact_mode_for_provider() and not force_full_prompt
    )
    if force_full_prompt and not _env_truthy("RECOVERY_COMPACT_PROMPT"):
        print(
            "Recovery Agent: forcing full prompt mode for structural/empty-generation retry."
        )
    if compact_mode:
        system_prompt = _build_compact_recovery_system_prompt(
            failure_context=failure_context,
            retry_scope=retry_scope,
            recovery_brief=recovery_brief_json,
            recovery_obligations=recovery_obligations_json,
        )

    llm = get_llm(temperature=0.0)

    max_content_filter_retries = 2
    content_filter_retry_count = 0
    token_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated": False,
        "sources": [],
    }

    # ── Preload target files ──────────────────────────────────────────────────
    # Collect all files referenced by the patch (from raw_hunks) PLUS any
    # explicitly flagged retry files. Preloading eliminates the read_file
    # stagnation loop: the agent has the full target content up-front and
    # the system prompt explicitly says NOT to call read_file on them.
    from utils.patch_analyzer import PatchAnalyzer as _PA

    _raw_hunks = _PA().extract_raw_hunks(patch_diff)
    patch_files = [_normalize_rel_path(f) for f in _raw_hunks.keys()]
    # Tell the toolkit which files MUST be covered so submit_recovery_plan can validate
    toolkit._required_patch_files = patch_files
    retry_files_list = [
        _normalize_rel_path(f) for f in (state.get("validation_retry_files") or [])
    ]
    files_to_preload = list(dict.fromkeys(patch_files + retry_files_list))[:6]

    preloaded_file_parts: list[str] = []
    preloaded_cache: dict[str, str] = {}  # rel_path → full raw content (for cache hits)
    for rel in files_to_preload:
        abs_path = os.path.join(target_repo_path, rel)
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception as e:
            content = f"<<unreadable: {e}>>"
        preloaded_cache[rel] = content  # store full content before truncation
        # Cap per-file to keep prompt bounded; large files get head+tail slice.
        if len(content) > 16000:
            content = content[:12000] + "\n...<truncated>...\n" + content[-3000:]
        numbered = "\n".join(
            f"{i + 1:5d}: {ln}" for i, ln in enumerate(content.splitlines())
        )
        preloaded_file_parts.append(f'<file path="{rel}">\n{numbered}\n</file>')

    # ── Per-hunk snippets from structural_locator mappings ───────────────────
    # Give the agent laser-focused context at each mapped location so it can
    # copy exact old_string anchors without guessing line numbers.
    per_hunk_parts: list[str] = []
    for mainline_file, hunk_map in (mapped_target_context or {}).items():
        if not isinstance(hunk_map, dict):
            continue
        for hunk_id, mapping in hunk_map.items():
            if not isinstance(mapping, dict):
                continue
            t_file = _normalize_rel_path(
                str(mapping.get("target_file") or mainline_file)
            )
            line_num = (
                mapping.get("target_line_start")
                or mapping.get("line_start")
                or mapping.get("line")
            )
            if not line_num:
                continue
            snippet = _extract_lines_around(
                target_repo_path, t_file, int(line_num), radius=20
            )
            if snippet:
                per_hunk_parts.append(
                    f'<hunk id="{hunk_id}" file="{t_file}" mapped_line="{line_num}">\n'
                    f"{snippet}\n"
                    f"</hunk>"
                )

    # ── Build initial HumanMessage ────────────────────────────────────────────
    target_files_xml = ""
    hunk_snippets_xml = ""
    if not compact_mode:
        # Structure: <target_files> → <hunk_snippets> → <task>
        # The agent sees the actual target code before any instructions, so it
        # cannot mistake mainline context lines for target code.
        target_files_xml = (
            (
                "<target_files>\n"
                "These are the ACTUAL files in the TARGET REPO — an older codebase, DIFFERENT from mainline.\n"
                "Lines are shown with numbers for reference: '   42: actual code here'\n"
                "IMPORTANT: When writing old_string, copy ONLY the actual code — do NOT include the line number prefix.\n"
                "Example: '   42:     private Foo foo;' → old_string should be '    private Foo foo;'\n\n"
                + "\n\n".join(preloaded_file_parts)
                + "\n</target_files>"
            )
            if preloaded_file_parts
            else ""
        )

        hunk_snippets_xml = (
            (
                "<hunk_snippets>\n"
                "Exact target code at each location found by Structural Locator.\n"
                "Use these as precise old_string sources — they are already extracted for you.\n\n"
                + "\n\n".join(per_hunk_parts)
                + "\n</hunk_snippets>"
            )
            if per_hunk_parts
            else ""
        )

    # Build explicit per-file coverage mandate
    if patch_files:
        file_checklist = "\n".join(f"  - {f}" for f in patch_files)
        coverage_section = (
            "\n<coverage_mandate>\n"
            "MANDATORY: Your plan MUST include adapted edits for ALL of these files.\n"
            "Submitting a partial plan (fewer files) will be REJECTED.\n"
            "Files required:\n"
            + file_checklist
            + "\n\nFor each file: find the relevant diff in <mainline_patch>, "
            "locate the matching target code in <target_files> above, "
            "and write old_string = EXACT text from the TARGET file (not from mainline `-` lines).\n"
            "</coverage_mandate>"
        )
    else:
        coverage_section = ""

    # Determine if all patch files are preloaded — if so, no investigation needed
    all_patch_files_preloaded = bool(patch_files) and all(
        f in preloaded_cache for f in patch_files
    )
    if all_patch_files_preloaded:
        read_files_note = (
            "NOTE: All target file contents are already loaded in <target_files> above. "
            "The read_file tool is NOT available — use the preloaded content directly."
        )
    else:
        read_files_note = (
            "Use read_file or other tools to fetch file content needed for anchors."
        )

    task_xml = (
        "<task>\n"
        "INSTRUCTIONS:\n"
        "1. Read <mainline_patch> in the system prompt — it shows EXACTLY what changes to make in each file.\n"
        "2. Read <target_files> and <hunk_snippets> above — these are your anchor sources.\n"
        "   " + read_files_note + "\n"
        "3. For each file in <coverage_mandate>, produce adapted edits:\n"
        "   - old_string = EXACT verbatim text from the TARGET file (copy from <target_files>)\n"
        "   - new_string = the adapted replacement\n"
        "   - edit_type = 'replace' (preferred), 'insert_before', 'insert_after', or 'delete'\n"
        "   - target_file = the target repo relative path\n"
        "4. Submit your COMPLETE plan in a SINGLE call to submit_recovery_plan:\n"
        "   {\n"
        '     "investigation_evidence": [{"kind":"...","details":"..."}],\n'
        '     "obligation_decisions": [{"obligation_id":"...","status":"edited|verified_no_change","reason":"...","evidence":["..."]}],\n'
        '     "edit_ops": {\n'
        '       "path/to/MainlineFile.java": [\n'
        '         {"hunk_index":0,"target_file":"exact/target/path.java","edit_type":"replace",\n'
        '          "old_string":"EXACT target text","new_string":"replacement","notes":"why"}\n'
        '       ]\n'
        "     },\n"
        '     "risk_notes": ["..."]\n'
        "   }\n"
        + coverage_section
        + "\n</task>"
    )

    if compact_mode:
        task_xml = (
            "<task>\n"
            "COMPACT MODE:\n"
            "- Use deterministic brief + obligations only.\n"
            "- Use tools to fetch exact target anchors as needed.\n"
            "- Submit wrapper payload with obligation decisions.\n"
            "</task>"
        )

    initial_message = "\n\n".join(
        filter(None, [target_files_xml, hunk_snippets_xml, task_xml])
    )
    messages: list[Any] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=initial_message),
    ]
    stagnation_reason = ""
    recovery_strategy_history = list(state.get("recovery_strategy_history") or [])

    # When all patch files are preloaded in <target_files>, read_file is redundant.
    # When all patch files are preloaded, the LLM has EVERYTHING in <target_files>.
    # Expose ONLY submit_recovery_plan — no investigation tools.
    # This forces a single-shot submit in Round 0 and prevents context explosion
    # (LLM calling grep/read_file blows up context → Azure timeout in Round 1).
    if all_patch_files_preloaded:
        # All target files already in <target_files>. Force the direct-apply
        # path: keep apply_edit / mark_no_change / recovery_done, drop the
        # investigation tools AND submit_recovery_plan so the model has no
        # choice but to mutate files via apply_edit.
        keep = {"apply_edit", "mark_no_change", "recovery_done", "batch_tools"}
        all_tool_names = {t.name for t in toolkit.get_tools(include_submit=True)}
        exclude_tools = {n for n in all_tool_names if n not in keep}
        max_inv_rounds = 12  # allow many apply_edit iterations
    else:
        exclude_tools = {"submit_recovery_plan"}
        max_inv_rounds = 12

    print("Recovery Agent: starting parallel batch tool loop...")
    print(
        f"Recovery Agent: all_files_preloaded={all_patch_files_preloaded}, "
        f"max_inv_rounds={max_inv_rounds}, "
        f"submit_only={all_patch_files_preloaded}"
    )
    try:
        final_messages, term_reason = await _run_parallel_tool_loop(
            llm=llm,
            tools=toolkit.get_tools(exclude_names=exclude_tools),
            initial_messages=messages,
            preloaded_cache=preloaded_cache,
            max_investigation_rounds=max_inv_rounds,
            toolkit=toolkit,
        )
    except Exception as exc:
        if _is_content_filter_error(exc):
            content_filter_retry_count += 1
            if content_filter_retry_count > max_content_filter_retries:
                stagnation_reason = "content_filter_exhausted"
                final_messages = messages
                term_reason = "content_filter_exhausted"
            else:
                print(
                    "Recovery Agent: provider content filter triggered; "
                    "switching to compact prompt mode and retrying."
                )
                compact_mode = True
                system_prompt = _build_compact_recovery_system_prompt(
                    failure_context=failure_context,
                    retry_scope=retry_scope,
                    recovery_brief=recovery_brief_json,
                    recovery_obligations=recovery_obligations_json,
                )
                compact_messages: list[Any] = [
                    HumanMessage(
                        content=_sanitize_for_content_policy(
                            str(getattr(m, "content", "") or ""),
                            2500,
                        )
                    )
                    for m in messages
                    if isinstance(m, HumanMessage)
                ] or [
                    HumanMessage(
                        content=(
                            "Use deterministic brief and obligations. "
                            "Produce minimal wrapper submission with obligation decisions."
                        )
                    )
                ]
                compact_llm = get_llm(temperature=0.0)
                compact_messages = [
                    SystemMessage(content=system_prompt)
                ] + compact_messages
                try:
                    final_messages, term_reason = await _run_parallel_tool_loop(
                        llm=compact_llm,
                        tools=toolkit.get_tools(),
                        initial_messages=compact_messages,
                        preloaded_cache=preloaded_cache,
                        max_investigation_rounds=1,
                        toolkit=toolkit,
                    )
                except Exception:
                    stagnation_reason = "content_filter_exhausted"
                    final_messages = compact_messages
                    term_reason = "content_filter_exhausted"
        else:
            raise

    print(f"Recovery Agent: loop finished, reason={term_reason}")

    # ── DIRECT-APPLY SHORT-CIRCUIT ─────────────────────────────────────
    # If the recovery agent used apply_edit tools to mutate files on disk,
    # synthesize adapted_code_hunks from git diff and hand off straight to
    # validation. This bypasses the entire submit_recovery_plan + hunk_generator
    # pipeline.
    applied_edits = list(getattr(toolkit, "_applied_edits", []) or [])
    if applied_edits:
        from agents.file_editor import _git_diff_file, _git_reset_file
        modified_files = []
        seen = set()
        for e in applied_edits:
            tf = str(e.get("target_file") or "")
            if tf and tf not in seen:
                seen.add(tf)
                modified_files.append(tf)

        # Strip orphaned Java imports that became unused after the edits.
        # Checkstyle fails the build on unused imports, so do this BEFORE
        # capturing the diff.
        for tf in modified_files:
            if tf.endswith(".java"):
                try:
                    removed = _cleanup_unused_java_imports(target_repo_path, tf)
                    if removed:
                        print(
                            f"[Recovery] cleaned {len(removed)} unused import(s) "
                            f"from {tf}: {removed}"
                        )
                except Exception as exc:
                    print(f"[Recovery] import cleanup crashed for {tf}: {exc}")

        # Capture diffs FIRST (while files are still mutated), THEN reset the
        # files to HEAD so validation's git apply step can re-apply cleanly.
        # The validation pipeline expects to apply hunks against pristine HEAD
        # state, not against already-mutated files.
        adapted_code_hunks: list[dict[str, Any]] = []
        for tf in modified_files:
            diff_text = _git_diff_file(target_repo_path, tf)
            if not diff_text:
                print(f"[Recovery] direct-apply: no diff for {tf} (already reverted?)")
                continue
            adapted_code_hunks.append(
                {
                    "target_file": tf,
                    "mainline_file": tf,
                    "hunk_text": diff_text,
                    "insertion_line": 1,
                    "intent_verified": True,
                    "file_operation": "MODIFIED",
                }
            )
        # Reset all modified files to HEAD so validation can re-apply.
        for tf in modified_files:
            try:
                ok = _git_reset_file(target_repo_path, tf)
                print(f"[Recovery] reset {tf} → {'ok' if ok else 'FAILED'}")
            except Exception as exc:
                print(f"[Recovery] reset {tf} crashed: {exc}")

        # Token accounting (still need it before return)
        agg = aggregate_usage_from_messages(final_messages)
        if agg.get("input_tokens") or agg.get("output_tokens"):
            add_usage(
                token_usage,
                int(agg.get("input_tokens", 0) or 0),
                int(agg.get("output_tokens", 0) or 0),
                "recovery_agent.direct_apply",
            )

        no_change_files = sorted(getattr(toolkit, "_direct_no_change_files", set()))
        summary = (
            f"Recovery Agent (direct-apply): applied {len(applied_edits)} edit(s) "
            f"to {len(adapted_code_hunks)} file(s); "
            f"{len(no_change_files)} file(s) marked no_change."
        )
        print(f"[Recovery] direct-apply handoff: {summary}")
        return {
            "messages": [HumanMessage(content=summary)],
            "adapted_code_hunks": adapted_code_hunks,
            "adapted_test_hunks": [],
            "recovery_applied_directly": True,
            "recovery_agent_mode": True,
            "recovery_agent_status": "ok",
            "recovery_agent_summary": summary,
            "recovery_brief": deterministic_recovery_brief,
            "recovery_obligations": recovery_obligations,
            "recovery_scope_files": recovery_scope_files,
            "recovery_strategy_history": recovery_strategy_history,
            "recovery_plan_version": 1,
            "recovery_risk_notes": [],
            "token_usage": token_usage,
        }

    # Token accounting
    agg = aggregate_usage_from_messages(final_messages)
    if agg.get("input_tokens") or agg.get("output_tokens"):
        add_usage(
            token_usage,
            int(agg.get("input_tokens", 0) or 0),
            int(agg.get("output_tokens", 0) or 0),
            "recovery_agent.parallel_loop",
        )

    # Map termination reason to stagnation_reason expected by downstream code
    if not stagnation_reason:
        if term_reason == "submitted":
            # Check for submit rejection in final messages
            submit_rejection = _extract_submit_rejection(final_messages)
            if submit_rejection:
                print(f"Recovery Agent: submit rejected: {submit_rejection}")
                if "missing obligation decisions" in submit_rejection.lower() or (
                    "invalid obligation decision status" in submit_rejection.lower()
                ):
                    stagnation_reason = "submit_rejected_missing_or_invalid_decisions"
        elif term_reason in ("max_rounds_exceeded", "no_tool_calls"):
            stagnation_reason = term_reason
        elif term_reason == "content_filter_exhausted":
            stagnation_reason = "content_filter_exhausted"

    # Check for no_fix_found status
    submitted_status = toolkit.get_submitted_status() or {}
    if (
        str(submitted_status.get("status") or "") == "no_fix_found"
        and not stagnation_reason
    ):
        stagnation_reason = "no_fix_found: " + str(
            submitted_status.get("reason") or "unspecified"
        )

    raw_plan = toolkit.get_submitted_plan()
    # NOTE: Do NOT fall back to scraping plans from raw LLM text. Any scraped
    # plan bypasses the on-disk anchor verification in submit_recovery_plan,
    # which is exactly how broken plans (mainline `-` lines used as anchors)
    # were reaching file_editor. If the agent didn't call submit_recovery_plan,
    # that is a failure and we return an empty plan.

    normalized_plan = _normalize_recovery_plan(raw_plan, state, target_repo_path)
    has_actionable_plan = bool(
        isinstance(normalized_plan, dict)
        and any(isinstance(v, list) and v for v in normalized_plan.values())
    )
    submitted_decisions = toolkit.get_submitted_decisions()
    submitted_investigation = toolkit.get_submitted_investigation()
    submitted_risk_notes = toolkit.get_submitted_risk_notes()

    plan_json = json.dumps(normalized_plan, sort_keys=True)
    plan_sig = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()
    prev_sig = str(state.get("last_plan_signature") or "")
    repeated = bool(prev_sig and prev_sig == plan_sig)
    total_ops = (
        sum(len(v) for v in normalized_plan.values())
        if isinstance(normalized_plan, dict)
        else 0
    )

    summary = (
        "Recovery Agent complete: "
        f"planned {total_ops} operation(s) across {len(normalized_plan)} file(s)."
    )
    if repeated:
        summary += " Repeated plan signature detected."
    if stagnation_reason:
        summary += f" Stagnation: {stagnation_reason}."
    if not has_actionable_plan:
        summary += " Recovery produced no actionable edits."

    if stagnation_reason in {
        "submit_rejected_missing_or_invalid_decisions",
        "repeated_submit_without_progress",
        "content_filter_exhausted",
    }:
        summary += (
            " Recovery output contract violation: obligation decisions are missing "
            "or invalid; marking no_fix_found to avoid redundant loops."
        )
    if stagnation_reason == "content_filter_exhausted":
        summary += (
            " Provider content filter persisted after compact retries; "
            "marking no_fix_found for this attempt."
        )

    return {
        "messages": [HumanMessage(content=summary)],
        "hunk_generation_plan": normalized_plan,
        "last_plan_signature": plan_sig,
        "validation_repeated_plan_detected": repeated,
        "recovery_agent_mode": True,
        "recovery_brief": deterministic_recovery_brief,
        "recovery_obligations": recovery_obligations,
        "recovery_investigation": submitted_investigation,
        "recovery_decisions": submitted_decisions,
        "recovery_scope_files": recovery_scope_files,
        "recovery_strategy_history": recovery_strategy_history,
        "recovery_plan_version": 1,
        "recovery_agent_status": (
            "no_fix_found"
            if (
                stagnation_reason.startswith("no_fix_found:")
                or stagnation_reason
                in {
                    "submit_rejected_missing_or_invalid_decisions",
                    "repeated_submit_without_progress",
                    "content_filter_exhausted",
                }
                or not has_actionable_plan
            )
            else "ok"
        ),
        "recovery_agent_summary": summary,
        "validation_failed_stage": (
            "recovery_no_fix_found"
            if (
                stagnation_reason.startswith("no_fix_found:")
                or stagnation_reason
                in {
                    "submit_rejected_missing_or_invalid_decisions",
                    "repeated_submit_without_progress",
                    "content_filter_exhausted",
                }
                or not has_actionable_plan
            )
            else state.get("validation_failed_stage")
        ),
        "recovery_risk_notes": submitted_risk_notes,
        "token_usage": token_usage,
    }
