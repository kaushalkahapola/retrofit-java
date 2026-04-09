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
2. Analyze deterministic recovery brief and obligations — check if remapped files are indicated.
3. Verify the obligation files actually contain the symbols being patched. If a file is a thin
   stub (few lines) or the methods are absent, use grep/get_class_context to find where they
   live in the target repo (e.g. they may have moved to a superclass).
4. Analyze the actual target code via <target_files> and tools.
5. Identify differences (constructor signatures, field order, imports, error handling, hierarchy).
6. Apply minimal, semantically correct edits via apply_edit, then call recovery_done.
</objectives>

<rules>
1. Base all edits on the target code visible in <target_files> or retrieved via tools.
2. Prefer small, precise edits using exact matching anchors from the target (max ~50 lines per edit).
3. Avoid no-op edits, comment-only changes, or unnecessary modifications.
4. Never use placeholder text like "// ... omitted for brevity" in new_string — write real code.
5. After calling recovery_done the first time you will be asked to self-review. Use grep or
   get_class_context to verify intent coverage, then call recovery_done again to finalize.
6. Use apply_edit and recovery_done — do NOT call submit_recovery_plan.
7. Use `grep` intelligently with regex patterns (e.g. `countdown.*MaybeContinue`) instead of long exact strings. Minor formatting differences will cause exact matches to fail.
8. When examining large files, use `read_file` with `start_line` and `max_lines` based on grep line numbers, instead of always reading from the beginning.
9. You have full access to the `bash` tool. Use it for advanced exploration, checking files, or finding context (e.g. using `sed -n '100,150p' File.java`, `find`, `rg`, `ls`).
</rules>

<analysis_steps>
A) Read <deterministic_recovery_brief> and <impact_obligations> first.
B) Summarize required adaptation and why it is needed.
C) Extract the main intent from the <mainline_patch>.
D) Examine <target_files> for actual signatures, declarations, and structure.
   For anything not in <target_files>, use grep (find a method/symbol) or
   get_class_context (get class skeleton). Avoid read_file on files already shown.
E) Compare mainline intent vs. target's current code.
F) Decide each obligation as edited or verified_no_change, with evidence.
G) Build adapted edits: use old_string from target, new_string reflecting the intended change.
H) Apply edits and call recovery_done.
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

<completion_rules>
- Apply every required change via apply_edit (one focused edit per call).
- Explicitly handle all obligations: either edit the file or call mark_no_change with a reason.
- Prioritize files in <retry_scope>.
- After completing all edits, call recovery_done once. You will receive a self-review prompt.
  Verify edits (use grep or get_class_context — NOT read_file on files already in context),
  fix any issues, then call recovery_done again to finalize.
</completion_rules>

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

    # Also include test files from the full mainline patch when the validation
    # failed before compilation (empty_generation). Test files need to be updated
    # when the patch changes a public constructor or method signature — otherwise
    # the build fails because tests still use the old signature.
    # We read patch_path (the raw full patch file) since patch_diff may be
    # stripped of test changes by the evaluation harness.
    failure_category = (
        str(state.get("validation_failure_category") or "").strip().lower()
    )
    if failure_category in {"empty_generation", "context_mismatch"}:
        patch_path = str(state.get("patch_path") or "")
        if patch_path and os.path.isfile(patch_path):
            try:
                with open(patch_path, "r", encoding="utf-8", errors="replace") as _fh:
                    full_patch = _fh.read()
                from utils.patch_analyzer import PatchAnalyzer as _PA2

                full_hunks = _PA2().extract_raw_hunks(full_patch)
                for f in full_hunks.keys():
                    nf = _normalize_rel_path(str(f or ""))
                    if nf and ("Test" in nf or "/test/" in nf or "test/" in nf.lower()):
                        add_ob("test_file", nf, source="patch_path_full")
            except Exception:
                pass

    return obligations


def _extract_modified_methods_from_patch(patch_diff: str, rel_path: str) -> list[str]:
    """Return method names that the patch modifies in a given file.

    Handles multi-modifier signatures, e.g.:
      public synchronized Breakdown getProfileBreakdown(Query q)
      private static void broadcastKill(...)
    """
    methods: list[str] = []
    in_file = False
    _SKIP = {"if", "for", "while", "switch", "catch", "return", "new"}
    # Allow one or more modifier keywords before the return type, then method name.
    _METHOD_RE = re.compile(
        r"(?:(?:public|private|protected|static|final|synchronized|abstract|default|native)\s+)+"
        r"[\w<>\[\],\s]+?\s+(\w+)\s*\("
    )
    for line in patch_diff.splitlines():
        if line.startswith("diff --git"):
            in_file = rel_path in line or rel_path.rsplit("/", 1)[-1] in line
            continue
        if not in_file:
            continue
        # @@ -N,M +N,M @@ methodName(...) — trailing text is often the enclosing method
        if line.startswith("@@"):
            m = re.search(r"@@[^@]+@@\s*(.*)", line)
            if m:
                ctx = str(m.group(1) or "").strip()
                mm = _METHOD_RE.search(ctx)
                if mm:
                    name = str(mm.group(1) or "")
                    if name and name not in _SKIP and name not in methods:
                        methods.append(name)
            continue
        # Scan both + and - lines for method declarations being added/modified
        if (line.startswith("+") and not line.startswith("+++")) or (
            line.startswith("-") and not line.startswith("---")
        ):
            mm = _METHOD_RE.search(line)
            if mm:
                name = str(mm.group(1) or "")
                if name and name not in _SKIP and name not in methods:
                    methods.append(name)
    return methods


def _extract_added_methods_from_patch(patch_diff: str, rel_path: str) -> list[str]:
    """Return method names that the patch *adds* (appear only on '+' lines, not '-' lines).

    A method is considered newly introduced if its declaration appears in '+' lines
    but NOT in any '-' line in the same file section of the diff.
    """
    _SKIP = {"if", "for", "while", "switch", "catch", "return", "new"}
    _METHOD_RE = re.compile(
        r"(?:(?:public|private|protected|static|final|synchronized|abstract|default|native)\s+)+"
        r"[\w<>\[\],\s]+?\s+(\w+)\s*\("
    )
    added: set[str] = set()
    removed: set[str] = set()
    in_file = False
    for line in patch_diff.splitlines():
        if line.startswith("diff --git"):
            in_file = rel_path in line or rel_path.rsplit("/", 1)[-1] in line
            continue
        if not in_file:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            mm = _METHOD_RE.search(line)
            if mm:
                name = str(mm.group(1) or "")
                if name and name not in _SKIP:
                    added.add(name)
        elif line.startswith("-") and not line.startswith("---"):
            mm = _METHOD_RE.search(line)
            if mm:
                name = str(mm.group(1) or "")
                if name and name not in _SKIP:
                    removed.add(name)
    # Truly new = appears in added lines but never in removed lines
    return [m for m in added if m not in removed]


def _find_callsite_obligations(
    patch_diff: str,
    symbol: str,
    defining_file: str,
    target_repo_path: str,
    seen: set[str],
) -> list[dict[str, Any]]:
    """Return new obligations for files that CALL `symbol` in the patch's + lines.

    When a method like `broadcastKill` is newly introduced in `defining_file`,
    the patch may also add CALL SITES of that method in other files.  Those
    files need to be edited too — but a plain per-file obligation won't tell
    the agent *what* to add.  This function creates a `callsite` obligation
    for each such file so the recovery agent knows to look there.
    """
    result: list[dict[str, Any]] = []
    if not patch_diff or not symbol:
        return result

    # Parse + lines per file from the diff
    current: str = ""
    files_calling: set[str] = set()
    for raw_line in patch_diff.splitlines():
        if raw_line.startswith("diff --git "):
            parts = raw_line.split(" b/", 1)
            current = _normalize_rel_path(parts[1].strip()) if len(parts) > 1 else ""
            continue
        if raw_line.startswith("+++ ") or raw_line.startswith("--- "):
            continue
        if current and current != defining_file and raw_line.startswith("+"):
            # Check if the added line calls the symbol
            added_content = raw_line[1:]
            if f"{symbol}(" in added_content or f"{symbol} " in added_content:
                files_calling.add(current)

    for calling_file in sorted(files_calling):
        oid = f"callsite:{calling_file}:{symbol}"
        if oid in seen:
            continue
        # Also check: is the call site already in the target?
        target_content = _read_file(target_repo_path, calling_file) or ""
        already_present = (
            f"{symbol}(" in target_content or f"{symbol} " in target_content
        )
        result.append(
            {
                "obligation_id": oid,
                "kind": "callsite",
                "required_file": calling_file,
                "symbol": symbol,
                "source": f"callsite_of:{defining_file}",
                "status": "pending",
                "_verification": "callsite_already_present"
                if already_present
                else "callsite_must_add",
            }
        )
        if not already_present:
            print(
                f"[Recovery] callsite obligation: {calling_file} must call {symbol}() "
                f"(introduced by patch in {defining_file})"
            )
    return result


def _verify_and_remap_obligations(
    state: AgentState,
    obligations: list[dict[str, Any]],
    target_repo_path: str,
) -> list[dict[str, Any]]:
    """For each obligation, verify the symbols exist in the target file.

    If the obligation file is very small (few lines) compared to the expected
    changes, or if the key methods from the mainline patch are absent, grep
    the target repo for where those methods actually live. If they're found
    in a different file (e.g. a superclass), remap the obligation.

    This catches the "logic moved to superclass" pattern (case: crate_10643658).
    """
    patch_diff = str(state.get("patch_diff") or "")
    if not patch_diff or not target_repo_path:
        return obligations

    remapped: list[dict[str, Any]] = []
    # Track callsite obligation IDs already added to avoid duplicates
    callsite_seen: set[str] = set()
    for ob in obligations:
        if not isinstance(ob, dict):
            remapped.append(ob)
            continue
        kind = str(ob.get("kind") or "")
        rel = str(ob.get("required_file") or "")
        if not rel or not rel.endswith(".java"):
            remapped.append(ob)
            continue

        abs_path = os.path.join(target_repo_path, rel)

        # Read target file
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                target_content = fh.read()
            target_lines = len(target_content.splitlines())
        except Exception:
            # File doesn't exist in target at all
            ob2 = dict(ob)
            ob2["_verification"] = "file_missing"
            remapped.append(ob2)
            continue

        # Extract method names the patch modifies in this file
        methods_in_patch = _extract_modified_methods_from_patch(patch_diff, rel)
        if not methods_in_patch:
            remapped.append(ob)
            continue

        # Check which methods are absent from the target file
        absent_methods = [
            m
            for m in methods_in_patch
            if not re.search(rf"\b{re.escape(m)}\b", target_content)
        ]
        if not absent_methods:
            # All methods found — obligation is correct
            ob2 = dict(ob)
            ob2["_verification"] = "symbols_confirmed"
            remapped.append(ob2)
            continue

        # Some/all methods absent — target file may be a stub; try to find them
        print(
            f"[Recovery] obligation verify: {len(absent_methods)}/{len(methods_in_patch)} "
            f"method(s) absent from {rel}: {absent_methods}. "
            f"Target has {target_lines} lines. Searching for where they live..."
        )
        # Grep the repo for the first absent method
        search_method = absent_methods[0]
        try:
            grep_res = subprocess.run(
                [
                    "rg",
                    "-n",
                    "--no-heading",
                    "-g",
                    "*.java",
                    rf"(?:public|private|protected)\s+\S+\s+{re.escape(search_method)}\s*\(",
                    ".",
                ],
                cwd=target_repo_path,
                capture_output=True,
                text=True,
                timeout=15,
            )
            matches = [ln.strip() for ln in grep_res.stdout.splitlines() if ln.strip()]
        except Exception:
            matches = []

        if not matches:
            # Distinguish: is the symbol genuinely absent from the target, or is it
            # being *introduced* by this patch (i.e. it appears only on '+' lines in the diff)?
            patch_added_methods = _extract_added_methods_from_patch(patch_diff, rel)
            must_insert = [m for m in absent_methods if m in patch_added_methods]
            if must_insert:
                # Symbol is introduced by the patch — obligation is to INSERT it, not remap.
                ob2 = dict(ob)
                ob2["_verification"] = f"must_insert:{must_insert}"
                remapped.append(ob2)
                print(
                    f"[Recovery] {must_insert} introduced by patch (absent from target as expected) "
                    f"— obligation tagged must_insert"
                )
                # Propagate: for every file in the patch that calls these new
                # methods (appears in + lines), add a callsite obligation so the
                # recovery agent knows it must also update those files.
                for new_sym in must_insert:
                    callsite_obs = _find_callsite_obligations(
                        patch_diff, new_sym, rel, target_repo_path, callsite_seen
                    )
                    for cs_ob in callsite_obs:
                        cs_oid = str(cs_ob.get("obligation_id") or "")
                        if cs_oid and cs_oid not in callsite_seen:
                            callsite_seen.add(cs_oid)
                            remapped.append(cs_ob)
            else:
                # Method not found anywhere — keep obligation as-is but flag it
                ob2 = dict(ob)
                ob2["_verification"] = (
                    f"absent_methods_not_found_in_repo:{absent_methods}"
                )
                remapped.append(ob2)
                print(
                    f"[Recovery] {search_method} not found anywhere in target repo — keeping obligation as-is"
                )
            continue

        # Find the best candidate: prefer files in the same package directory
        rel_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
        best_match = None
        for m_line in matches:
            file_part = m_line.split(":")[0].lstrip("./")
            if file_part == rel:
                continue  # that's the original file — method truly absent
            if rel_dir and file_part.startswith(rel_dir):
                best_match = file_part
                break
        if best_match is None and matches:
            # Take the first hit that isn't the original file
            for m_line in matches:
                fp = m_line.split(":")[0].lstrip("./")
                if fp != rel:
                    best_match = fp
                    break

        if best_match:
            ob2 = dict(ob)
            ob2["required_file"] = _normalize_rel_path(best_match)
            ob2["_verification"] = (
                f"remapped_from:{rel}:absent_methods:{absent_methods}"
            )
            ob2["_original_required_file"] = rel
            print(
                f"[Recovery] REMAP obligation {rel} → {ob2['required_file']} "
                f"(methods {absent_methods} found there)"
            )
            remapped.append(ob2)
        else:
            ob2 = dict(ob)
            ob2["_verification"] = f"absent_methods_only_in_original:{absent_methods}"
            remapped.append(ob2)

    return remapped


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
        # Incremental decision accumulator keyed by obligation_id (or fallback key).
        # This prevents later submit calls from losing earlier verified_no_change/
        # blocked decisions, which are needed for hunk-level waiver coverage.
        self._accumulated_decisions: dict[str, dict[str, Any]] = {}
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
        # Whether the self-review phase has been entered (first recovery_done call).
        self._self_review_phase: bool = False
        # Failure tracking: rel_path → list of failed old_string snippets (≤120 chars each).
        # Used to trigger automatic "here is the actual file content" injections.
        self._failed_edit_tracker: dict[str, list[str]] = {}
        # Files for which we have already injected ACTUAL_FILE_CONTENT context so we
        # don't flood the model with repeated injections for the same file.
        self._context_injected_files: set[str] = set()
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

    def _candidate_hunk_indices(self, value: Any) -> set[int]:
        """Return compatible hunk indices (supports 0/1-based drift)."""
        out: set[int] = set()
        try:
            idx = int(value)
        except Exception:
            return out
        if idx <= 0:
            out.add(1)
            return out
        out.add(idx)
        out.add(idx + 1)
        return out

    def _mapped_line_for(self, target_file: str, hunk_index: Any) -> int | None:
        """Find mapped start line for (target_file, hunk_index), if available."""
        tf = _normalize_rel_path(target_file)
        if not tf:
            return None
        idx_candidates = self._candidate_hunk_indices(hunk_index)
        if not idx_candidates:
            return None

        mapped_ctx = self.state.get("mapped_target_context") or {}
        if not isinstance(mapped_ctx, dict):
            return None

        for entries in mapped_ctx.values():
            if not isinstance(entries, list):
                continue
            for m in entries:
                if not isinstance(m, dict):
                    continue
                mtf = _normalize_rel_path(str(m.get("target_file") or ""))
                if mtf != tf:
                    continue
                try:
                    midx = int(m.get("hunk_index"))
                except Exception:
                    continue
                if midx not in idx_candidates:
                    continue
                try:
                    line = int(m.get("start_line") or m.get("target_line_start") or 0)
                except Exception:
                    line = 0
                if line > 0:
                    return line
        return None

    def _anchor_match_lines(self, file_text: str, anchor: str) -> list[int]:
        """Return 1-based line numbers where anchor starts in file_text."""
        txt = str(file_text or "")
        anc = str(anchor or "")
        if not txt or not anc:
            return []
        hits: list[int] = []
        start = 0
        while True:
            idx = txt.find(anc, start)
            if idx < 0:
                break
            hits.append(txt.count("\n", 0, idx) + 1)
            start = idx + 1
        return hits

    def _required_hunk_targets(self) -> list[dict[str, Any]]:
        """Build required hunk targets from patch diff + locator mappings."""
        patch_diff = str(self.state.get("patch_diff") or "")
        if not patch_diff:
            return []
        try:
            from utils.patch_analyzer import PatchAnalyzer as _PA

            raw_hunks = _PA().extract_raw_hunks(patch_diff)
        except Exception:
            return []

        mapped_ctx = self.state.get("mapped_target_context") or {}
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()

        for mainline_file, hunks in raw_hunks.items():
            mf = _normalize_rel_path(str(mainline_file or ""))
            if not mf or not isinstance(hunks, list):
                continue
            entries = mapped_ctx.get(mf) if isinstance(mapped_ctx, dict) else []
            mapped_by_idx: dict[int, dict[str, Any]] = {}
            if isinstance(entries, list):
                for m in entries:
                    if not isinstance(m, dict):
                        continue
                    try:
                        midx = int(m.get("hunk_index"))
                    except Exception:
                        continue
                    mapped_by_idx[midx] = m

            for pos, _ in enumerate(hunks, start=1):
                m = mapped_by_idx.get(pos) or mapped_by_idx.get(pos - 1)
                tf = _normalize_rel_path(str((m or {}).get("target_file") or mf))
                if not tf:
                    continue
                key = (tf, pos)
                if key in seen:
                    continue
                seen.add(key)
                line = 0
                try:
                    line = int(
                        (m or {}).get("start_line")
                        or (m or {}).get("target_line_start")
                        or 0
                    )
                except Exception:
                    line = 0
                out.append(
                    {
                        "mainline_file": mf,
                        "target_file": tf,
                        "hunk_index": pos,
                        "mapped_line": line if line > 0 else None,
                    }
                )
        return out

    def _decision_file_and_hunk(
        self, decision: dict[str, Any]
    ) -> tuple[str, int | None]:
        tf = _normalize_rel_path(
            str(decision.get("required_file") or decision.get("target_file") or "")
        )
        hidx: int | None = None
        try:
            if decision.get("hunk_index") is not None:
                hidx = int(decision.get("hunk_index"))
                if hidx <= 0:
                    hidx = 1
        except Exception:
            hidx = None

        oid = str(decision.get("obligation_id") or "")
        if not tf and oid.startswith("patch_file:"):
            body = oid[len("patch_file:") :]
            tf = _normalize_rel_path(body.split(":", 1)[0])
        return tf, hidx

    def _hunks_waived_by_decisions(
        self, decisions: list[dict[str, Any]]
    ) -> set[tuple[str, int]]:
        """Return waived (target_file, hunk_index) pairs from no-change decisions."""
        waived: set[tuple[str, int]] = set()
        required = self._required_hunk_targets()
        if not required:
            return waived
        req_by_file: dict[str, list[int]] = {}
        for r in required:
            tf = _normalize_rel_path(str(r.get("target_file") or ""))
            try:
                hi = int(r.get("hunk_index") or 0)
            except Exception:
                hi = 0
            if tf and hi > 0:
                req_by_file.setdefault(tf, []).append(hi)

        for d in decisions or []:
            if not isinstance(d, dict):
                continue
            st = str(d.get("status") or "").strip().lower()
            if st not in {"verified_no_change", "blocked"}:
                continue
            if not str(d.get("reason") or "").strip():
                continue
            tf, hidx = self._decision_file_and_hunk(d)
            if not tf:
                continue
            if hidx is None:
                for hi in req_by_file.get(tf, []):
                    waived.add((tf, hi))
                continue
            for cand in self._candidate_hunk_indices(hidx):
                waived.add((tf, cand))
        return waived

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
        if not old_string and edit_type in {"insert_after", "insert_before"}:
            return (
                f"ERROR: old_string is required for {edit_type} — provide the exact "
                "verbatim line(s) from the target file to use as the insertion anchor. "
                "Read the file first and copy a unique nearby line into old_string."
            )

        # Guard: normalize literal escape sequences that the LLM sometimes
        # double-encodes (writes \\n in JSON output → Python receives the
        # 2-char sequence backslash + n).  Only normalize when the string
        # has NO actual newline characters — that unambiguously signals the
        # model intended multi-line code but accidentally double-escaped.
        # Strings that already contain real newlines are left unchanged to
        # avoid corrupting Java string literals (\n inside "...") that
        # legitimately contain backslash-n sequences.
        def _decode_llm_escapes(s: str) -> str:
            if not s:
                return s
            if "\n" not in s and "\\n" in s:
                s = s.replace("\\n", "\n")
            if "\t" not in s and "\\t" in s:
                s = s.replace("\\t", "\t")
            # Unescape HTML entities the LLM sometimes emits (e.g. &lt; for <)
            import html as _html

            if "&" in s:
                s = _html.unescape(s)
            return s

        old_string = _decode_llm_escapes(old_string)
        old_string = _strip_diff_markers_from_lines(old_string)
        new_string = _decode_llm_escapes(new_string)
        new_string = _strip_diff_markers_from_lines(new_string)

        # Guard: reject LLM placeholder bodies that would corrupt the file.
        _PLACEHOLDER_PATTERNS = [
            "omitted for brevity",
            "... existing code ...",
            "// rest of",
            "// ... rest",
            "// remaining",
            "// ... method body",
            "// TODO: implement",
            "/* unchanged */",
            "/* same as",
            "// same as above",
        ]
        new_lower = new_string.lower()
        for _pat in _PLACEHOLDER_PATTERNS:
            if _pat.lower() in new_lower:
                return (
                    f"ERROR: new_string contains placeholder text ({_pat!r}). "
                    "Write the actual complete replacement code — do not use "
                    "placeholder comments or 'omitted' stubs."
                )

        # Guard: reject oversized edits that risk destroying surrounding code.
        # A large old_string almost certainly grabs too much context and will
        # wipe out code that should be preserved. Decompose into smaller edits.
        # Cap is 80 lines — enough for a multi-arg constructor signature; well
        # below the 200+ line mass-replace that destroys surrounding code.
        _MAX_EDIT_LINES = 80
        old_line_count = len((old_string or "").splitlines())
        new_line_count = len((new_string or "").splitlines())
        if old_line_count > _MAX_EDIT_LINES:
            return (
                f"ERROR: old_string is {old_line_count} lines — too broad. "
                f"Maximum is {_MAX_EDIT_LINES} lines. "
                "Decompose into multiple focused apply_edit calls, each targeting "
                "a single method, field block, or import group. "
                "Tip: split at a method boundary (e.g. right before `public`/`private`) "
                "or isolate just the signature/body that changes."
            )
        if new_line_count > _MAX_EDIT_LINES * 2:
            return (
                f"ERROR: new_string is {new_line_count} lines — too large. "
                "Break this into multiple smaller apply_edit calls."
            )

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
            # Wrong-file detection: when the anchor text isn't in target_file,
            # check whether it actually lives in a DIFFERENT file we know about
            # (preloaded cache + required patch files). This catches the common
            # LLM confusion where it uses an anchor from mainline_patch for
            # fileA but sets target_file to fileB. Without this nudge, the
            # agent loops on `not_found_multiline` until round budget exhausts.
            suggestion = ""
            try:
                anchor = (old_string or "").strip()
                # Use the first distinctive non-empty line as the search key;
                # fall back to the first ~200 chars if the first line is too
                # generic (e.g. a lone brace).
                first_line = ""
                for ln in anchor.splitlines():
                    s = ln.strip()
                    if len(s) >= 15 and not s.startswith(("//", "/*", "*")):
                        first_line = s
                        break
                key = first_line or anchor[:200]
                if key and len(key) >= 10:
                    candidates: list[str] = []
                    # Search preloaded cache first (cheap, in-memory)
                    cache = getattr(self, "_preloaded_cache", None) or {}
                    for other_rel, other_content in cache.items():
                        if other_rel == rel:
                            continue
                        if key in other_content:
                            candidates.append(other_rel)
                    # If cache miss, search other required_patch_files on disk
                    if not candidates:
                        required = getattr(self, "_required_patch_files", None) or []
                        for other_rel in required:
                            if other_rel == rel or other_rel in cache:
                                continue
                            try:
                                abs_other = os.path.join(
                                    self.target_repo_path, other_rel
                                )
                                with open(
                                    abs_other, "r", encoding="utf-8", errors="replace"
                                ) as _fh:
                                    if key in _fh.read():
                                        candidates.append(other_rel)
                            except Exception:
                                pass
                    if len(candidates) == 1:
                        suggestion = (
                            f" WRONG FILE: the anchor text was NOT found in "
                            f"'{rel}', but it IS present in '{candidates[0]}'. "
                            f"Retry apply_edit with target_file='{candidates[0]}'."
                        )
                    elif len(candidates) > 1:
                        suggestion = (
                            f" WRONG FILE: anchor not in '{rel}' but found in: "
                            f"{candidates}. Pick the correct one and retry."
                        )
            except Exception:
                pass  # best-effort hint; never block the error path

            if msg and msg.startswith("AMBIGUOUS:"):
                count = 0
                import re as _re_amb

                m = _re_amb.search(r"AMBIGUOUS:\s+(\d+)", msg)
                if m:
                    count = int(m.group(1))

                occurrences = []
                try:
                    full_path = os.path.join(self.target_repo_path, rel)
                    with open(
                        full_path, "r", encoding="utf-8", errors="replace"
                    ) as _af:
                        _content = _af.read()
                    _search_start = 0
                    while True:
                        _idx = _content.find(resolved_old or old_string, _search_start)
                        if _idx < 0:
                            break
                        _ln = _content.count("\n", 0, _idx) + 1
                        occurrences.append((_ln, _idx))
                        _search_start = _idx + 1
                except Exception:
                    pass

                disambiguated = False
                if occurrences and rel:
                    mapped_ln = None
                    _mc = (getattr(self, "state", {}) or {}).get(
                        "mapped_target_context"
                    )
                    if isinstance(_mc, dict):
                        for _mf_entries in _mc.values():
                            if not isinstance(_mf_entries, dict):
                                continue
                            for _hid, _hmap in _mf_entries.items():
                                if not isinstance(_hmap, dict):
                                    continue
                                if (
                                    _normalize_rel_path(
                                        str(_hmap.get("target_file") or "")
                                    )
                                    == rel
                                ):
                                    _ln = int(
                                        _hmap.get("target_line_start")
                                        or _hmap.get("line")
                                        or 0
                                    )
                                    if _ln > 0:
                                        mapped_ln = _ln
                                        break
                            if mapped_ln:
                                break

                    if mapped_ln:
                        best_line = min(
                            occurrences, key=lambda p: abs(p[0] - mapped_ln)
                        )
                        best_offset = best_line[1]
                        try:
                            _updated = (
                                _content[:best_offset]
                                + (resolved_new or new_string)
                                + _content[
                                    best_offset + len(resolved_old or old_string) :
                                ]
                            )
                            with open(full_path, "w", encoding="utf-8") as _af:
                                _af.write(_updated)
                            approx_line = best_line[0]
                            self._applied_edits.append(
                                {
                                    "target_file": rel,
                                    "edit_type": edit_type,
                                    "old_string": (resolved_old or old_string),
                                    "new_string": (resolved_new or new_string),
                                    "resolution": "auto_disambiguated",
                                    "message": f"SUCCESS: auto-disambiguated to line ~{approx_line}",
                                }
                            )
                            if (
                                hasattr(self, "_preloaded_cache")
                                and self._preloaded_cache
                                and rel in self._preloaded_cache
                            ):
                                self._preloaded_cache[rel] = _updated
                            print(
                                f"[Recovery] apply_edit AUTO-DISAMBIGUATED: {rel} (line ~{approx_line}, mapped_ln={mapped_ln})"
                            )
                            return f"SUCCESS: auto-disambiguated to line ~{approx_line} (closest to structural mapping {mapped_ln}). (resolution=auto_disambiguated)"
                        except Exception as _de:
                            print(
                                f"[Recovery] auto-disambiguate failed for {rel}: {_de}"
                            )

                msg_amb = (
                    f"FAILED: AMBIGUOUS: {count} occurrences of old_string found in '{rel}'. "
                    "Extend old_string with more surrounding context lines to make it unique. "
                    "Include at least 3 lines before and after the target section."
                )
                print(f"[Recovery] apply_edit AMBIGUOUS: {rel} ({count} occurrences)")
                self._failed_edit_tracker.setdefault(rel, []).append(
                    f"AMBIGUOUS:{(old_string or '')[:80]}"
                )
                return msg_amb

            if reason and reason.startswith("not_found"):
                self._failed_edit_tracker.setdefault(rel, []).append(
                    (old_string or "")[:120]
                )

            return (
                f"FAILED: {msg} (reason={reason})."
                + suggestion
                + " Tip: read the target file and copy old_string VERBATIM "
                "from the on-disk content; do NOT use mainline `-` lines."
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
        # Fix: refresh preloaded_cache so subsequent read_file calls in the same
        # loop see the post-edit content rather than the stale pre-edit snapshot.
        if (
            hasattr(self, "_preloaded_cache")
            and self._preloaded_cache is not None
            and rel in self._preloaded_cache
        ):
            abs_path = os.path.join(self.target_repo_path, rel)
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as _fh:
                    self._preloaded_cache[rel] = _fh.read()
            except Exception:
                pass  # non-fatal; stale cache is better than a crash
        print(f"[Recovery] apply_edit OK: {rel} ({reason})")
        return f"SUCCESS: {msg} (resolution={reason})"

    def edit_by_lines(
        self,
        target_file: str,
        start_line: int,
        end_line: int,
        new_string: str,
    ) -> str:
        """
        Replace lines `start_line` through `end_line` (1-indexed, inclusive) with `new_string`.
        This avoids whitespace/formatting mismatch failures in apply_edit.
        To INSERT without deleting, use start_line = end_line = line_number_to_insert_after, and
        start your new_string with the original line content.
        """
        rel = _normalize_rel_path(target_file)
        if not rel:
            return "ERROR: target_file is required"
        try:
            start = int(start_line)
            end = int(end_line)
        except ValueError:
            return "ERROR: start_line and end_line must be integers"

        if start < 1 or end < 1 or start > end:
            return "ERROR: invalid start_line / end_line. Must be 1-indexed and start_line <= end_line."

        # Read file
        content = _read_file(self.target_repo_path, rel)
        if not content:
            return f"ERROR: File {rel} not found or empty."

        lines = content.splitlines(keepends=True)
        if start > len(lines):
            return f"ERROR: start_line {start} is beyond EOF ({len(lines)} lines)"

        # Replace
        before = "".join(lines[: start - 1])
        after = "".join(lines[end:])

        # Ensure new_string ends with newline if original had it, and file doesn't collapse
        new_s = str(new_string or "")
        if new_s and not new_s.endswith("\n"):
            new_s += "\n"

        new_content = before + new_s + after

        # Write back
        full_path = _resolve_path(self.target_repo_path, rel)
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            return f"ERROR writing file: {e}"

        # Record edit for deduplication / tracking
        self._applied_edits.append(
            {
                "target_file": rel,
                "start_line": start,
                "end_line": end,
                "new_string": new_s,
                "tool": "edit_by_lines",
            }
        )

        self._direct_no_change_files.discard(rel)
        if (
            hasattr(self, "_preloaded_cache")
            and self._preloaded_cache is not None
            and rel in self._preloaded_cache
        ):
            self._preloaded_cache[rel] = new_content

        print(f"[Recovery] edit_by_lines OK: {rel} ({start}-{end})")
        return f"SUCCESS: replaced lines {start}-{end} in {rel}."

    def append_method(
        self,
        target_file: str,
        new_code: str,
    ) -> str:
        """
        Append new methods or fields to the END of a class body (just before the final '}').
        This is much safer than `apply_edit` for large insertions where anchor matching might fail.
        """
        rel = _normalize_rel_path(target_file)
        if not rel:
            return "ERROR: target_file is required"
        if not new_code or not new_code.strip():
            return "ERROR: new_code is required"

        content = _read_file(self.target_repo_path, rel)
        if not content:
            return f"ERROR: File {rel} not found or empty."

        # Find the last closing brace
        last_brace_idx = content.rfind("}")
        if last_brace_idx == -1:
            return "ERROR: Could not find closing brace '}' in file."

        new_s = str(new_code)
        if not new_s.endswith("\n"):
            new_s += "\n"
        if not new_s.startswith("\n"):
            new_s = "\n" + new_s

        new_content = content[:last_brace_idx] + new_s + content[last_brace_idx:]

        full_path = _resolve_path(self.target_repo_path, rel)
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            return f"ERROR writing file: {e}"

        # Record edit
        self._applied_edits.append(
            {"target_file": rel, "new_string": new_code, "tool": "append_method"}
        )

        self._direct_no_change_files.discard(rel)
        if (
            hasattr(self, "_preloaded_cache")
            and self._preloaded_cache is not None
            and rel in self._preloaded_cache
        ):
            self._preloaded_cache[rel] = new_content

        print(f"[Recovery] append_method OK: {rel}")
        return f"SUCCESS: appended code before final closing brace in {rel}."

    def mark_no_change(self, target_file: str, reason: str = "") -> str:
        """
        Declare that a required patch file needs NO edits in the target.
        Use this only when you've verified the target already has the
        equivalent code, or when the change genuinely doesn't apply.
        """
        rel = _normalize_rel_path(target_file)
        if not rel:
            return "ERROR: target_file is required"

        # Guard: if the mainline patch substantially adds new code to this file,
        # mark_no_change is almost certainly wrong. Force the model to verify
        # by reading the file before it can override.
        try:
            patch_diff = (
                str((self.state or {}).get("patch_diff") or "")
                if hasattr(self, "state")
                else ""
            )
        except Exception:
            patch_diff = ""
        if patch_diff:
            added_lines = 0
            in_file = False
            basename = rel.rsplit("/", 1)[-1]
            for line in patch_diff.splitlines():
                if (
                    line.startswith("diff --git")
                    or line.startswith("+++ ")
                    or line.startswith("--- ")
                ):
                    in_file = (rel in line) or (basename in line)
                    continue
                if in_file and line.startswith("+") and not line.startswith("+++"):
                    added_lines += 1
            override = "verified:" in (reason or "").lower()
            if added_lines > 5 and not override:
                return (
                    f"WARNING: mark_no_change rejected for '{rel}' — the mainline "
                    f"patch adds {added_lines} line(s) to this file. mark_no_change "
                    f"is only valid if the target ALREADY contains the equivalent of "
                    f"every addition. Use grep or get_class_context to verify the target "
                    f"already contains the equivalent code, then either:\n"
                    f"  (a) call apply_edit for the missing pieces, OR\n"
                    f"  (b) call mark_no_change again with reason starting "
                    f'"verified: <evidence>" to override this guard.'
                )

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
        truly_missing: list[str] = []
        auto_covered: list[str] = []
        for f in self._required_patch_files or []:
            if f in covered:
                continue
            # Auto-check: if _compute_missing_patch_additions shows no missing
            # lines for this file, all required changes are present — treat as
            # implicitly covered (no edit needed).
            _auto_report = self._compute_missing_patch_additions({f})
            if not _auto_report.get(f):
                # No missing additions → file is already correct
                auto_covered.append(f)
                self._direct_no_change_files.add(f)
                print(
                    f"[Recovery] auto-covered {f}: all required additions already present"
                )
            else:
                truly_missing.append(f)

        if truly_missing:
            return (
                "ERROR: cannot finish — these required files have neither "
                "an applied edit nor a no_change mark:\n  - "
                + "\n  - ".join(truly_missing)
                + "\nFix: call apply_edit for each, or mark_no_change with a reason."
            )

        def _build_missing_block_error(missing_report: dict, *, final: bool) -> str:
            """Return an ERROR string describing what is still absent and providing
            the actual current content of the first affected file so the LLM can
            copy a correct old_string without a read_file call."""
            missing_lines: list[str] = []
            for mf, items in sorted(missing_report.items()):
                missing_lines.append(f"\n  [{mf}]")
                for item in items[:8]:
                    missing_lines.append(f"    MISSING: {item}")

            # Provide live content of the first affected file as an anchor aid.
            context_hint = ""
            for mf in list(missing_report.keys())[:1]:
                full_path = os.path.join(self.target_repo_path, mf)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as _f:
                        _lines = _f.readlines()
                    shown = "".join(
                        f"{i + 1}: {ln}" for i, ln in enumerate(_lines[:250])
                    )
                    context_hint = (
                        f"\n\nCurrent on-disk content of {mf} "
                        f"(lines 1-{min(250, len(_lines))}):\n"
                        f"```java\n{shown}\n```\n"
                        "old_string MUST be copied VERBATIM from the lines above — "
                        "NOT from the mainline patch context lines."
                    )
                except Exception:
                    pass

            prefix = (
                "ERROR: recovery_done BLOCKED (final check) — "
                if final
                else "ERROR: recovery_done BLOCKED — "
            )
            return (
                prefix
                + "the following required additions are still absent:\n"
                + "".join(missing_lines)
                + context_hint
                + "\n\nApply the missing code with apply_edit, then call recovery_done again."
            )

        if not self._self_review_phase:
            self._self_review_phase = True
            # Deterministic verification BEFORE allowing exit.
            missing_report = self._compute_missing_patch_additions(edited)
            if missing_report:
                print(
                    f"[Recovery] recovery_done BLOCKED (missing additions): "
                    f"{len(missing_report)} file(s) with absent lines."
                )
                return _build_missing_block_error(missing_report, final=False)
            # Nothing missing — proceed to second (final) call.
            print(
                f"[Recovery] recovery_done (first check passed): {len(self._applied_edits)} "
                f"edit(s) applied. All additions present — ready to finalise."
            )
            return (
                f"VERIFIED: {len(self._applied_edits)} edit(s) applied to "
                f"{sorted(edited)} file(s). All required additions confirmed present.\n"
                "Call recovery_done once more to commit and exit."
            )

        # Second call: final verification then exit.
        missing_report = self._compute_missing_patch_additions(edited)
        if missing_report:
            print(
                f"[Recovery] recovery_done BLOCKED (final check): still missing additions."
            )
            return _build_missing_block_error(missing_report, final=True)

        self._recovery_done = True
        print(
            f"[Recovery] recovery_done: {len(self._applied_edits)} edits applied "
            f"across {len(edited)} file(s); {len(self._direct_no_change_files)} no_change."
        )
        return (
            f"SUCCESS: recovery complete. {len(self._applied_edits)} edit(s) applied. "
            f"You may stop calling tools now."
        )

    def _compute_missing_patch_additions(
        self, edited_files: set[str]
    ) -> dict[str, list[str]]:
        """Check which meaningful mainline patch additions are still absent from
        the target files after all edits have been applied.

        Returns a dict mapping rel_path → list of missing line snippets.
        Only reports lines that are substantive (methods, fields, imports,
        call sites) — skips blank lines, comments, and trivial tokens.
        """
        patch_diff = str(self.state.get("patch_diff") or "")
        if not patch_diff:
            return {}

        # Parse + lines per file from the patch diff
        added_by_file: dict[str, list[str]] = {}
        current_file: str = ""
        for raw_line in patch_diff.splitlines():
            if raw_line.startswith("diff --git "):
                # Extract b-side file path: "diff --git a/... b/..."
                parts = raw_line.split(" b/", 1)
                current_file = (
                    _normalize_rel_path(parts[1].strip()) if len(parts) > 1 else ""
                )
                continue
            if raw_line.startswith("+++ ") or raw_line.startswith("--- "):
                continue
            if current_file and raw_line.startswith("+"):
                content = raw_line[1:]  # strip leading +
                stripped = content.strip()
                # Only keep substantive lines (skip blanks, pure-comment lines,
                # and very short tokens like lone braces)
                if len(stripped) < 10:
                    continue
                if (
                    stripped.startswith("//")
                    or stripped.startswith("*")
                    or stripped.startswith("/*")
                ):
                    continue
                added_by_file.setdefault(current_file, []).append(stripped)

        missing: dict[str, list[str]] = {}
        for rel, added_lines in added_by_file.items():
            if rel not in edited_files:
                # File wasn't edited — skip (may be intentional no_change)
                continue
            target_content = _read_file(self.target_repo_path, rel) or ""
            absent = []
            for line in added_lines:
                # Use a substring of the line as the needle (strip leading
                # whitespace already done above; use first 60 chars to avoid
                # false negatives from line-wrapping differences)
                needle = line[:80]
                if needle not in target_content:
                    absent.append(line)
            if absent:
                missing[rel] = absent
        return missing

    # -------- read/search tools --------
    def read_file(
        self, file_path: str, start_line: int = 1, max_lines: int = 400
    ) -> str:
        rel = _normalize_rel_path(file_path)
        content = _read_file(self.target_repo_path, rel)
        if not content:
            return f"ERROR: cannot read file '{rel}'"
        lines = content.splitlines()
        start = max(1, start_line)
        cap = max(1, min(int(max_lines or 400), 1200))
        out = [f"[read_file] {rel} total={len(lines)}"]
        end_idx = min(start - 1 + cap, len(lines))
        for i in range(start - 1, end_idx):
            out.append(f"{i + 1:5d}: {lines[i]}")
        if len(lines) > end_idx:
            out.append(f"... truncated ({len(lines) - end_idx} more lines)")
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
                # Standard grep --include only matches basenames, so if 'inc' is a full path, just search that path directly
                search_path = "."
                grep_args = ["grep", "-rn"]
                if "/" in inc and not any(c in inc for c in "*?[]"):
                    search_path = inc
                else:
                    grep_args.append("--include=" + os.path.basename(inc))

                grep_args.extend([pat, search_path])

                res = subprocess.run(
                    grep_args,
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
        get_class_context, summarize_failure, todoread.

        Each task can be in either of two formats:
          {"tool": "read_file", "args": {"file_path": "..."}}   ← preferred
          {"read_file": {"file_path": "..."}}                   ← shorthand also accepted
        """
        if not isinstance(tasks, list) or not tasks:
            return "ERROR: tasks must be a non-empty list"

        _KNOWN_TOOLS = {
            "read_file",
            "read_mainline_file",
            "grep",
            "glob",
            "bash",
            "get_class_context",
            "summarize_failure",
            "todoread",
        }

        max_tasks = 8
        selected = tasks[:max_tasks]

        def _run_one(item: dict[str, Any]) -> dict[str, Any]:
            item = item or {}
            kind = str(item.get("tool") or "").strip()
            args = item.get("args") or {}

            # Accept shorthand format: {"get_class_context": {"file_path": "..."}}
            # where the tool name is used as the dict key instead of "tool".
            if not kind:
                for k, v in item.items():
                    if k in _KNOWN_TOOLS:
                        kind = k
                        if isinstance(v, dict):
                            args = v
                        break

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
                elif kind == "get_class_context":
                    res = self.get_class_context(**args)
                elif kind == "summarize_failure":
                    res = self.summarize_failure()
                elif kind == "todoread":
                    res = self.todoread()
                else:
                    res = (
                        f"ERROR: unsupported tool '{kind}' in batch_tools. "
                        f"Supported: {sorted(_KNOWN_TOOLS)}"
                    )
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

    def read_mainline_file(
        self, file_path: str, start_line: int = 1, max_lines: int = 250
    ) -> str:
        rel = _normalize_rel_path(file_path)
        text = _read_file(self.mainline_repo_path, rel)
        if not text:
            return f"ERROR: cannot read mainline file '{rel}'"
        lines = text.splitlines()
        start = max(1, start_line)
        cap = max(1, min(int(max_lines or 250), 800))
        out = [f"[read_mainline_file] {rel} total={len(lines)}"]
        end_idx = min(start - 1 + cap, len(lines))
        for i in range(start - 1, end_idx):
            out.append(f"{i + 1:5d}: {lines[i]}")
        if len(lines) > end_idx:
            out.append(f"... truncated ({len(lines) - end_idx} more lines)")
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
        if plan is None and (
            edit_ops is not None or investigation_evidence is not None
        ):
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
        if (
            not plan
            and not self._accumulated_plan
            and not (wrapper_payload.get("obligation_decisions"))
        ):
            return "ERROR: plan must be an object keyed by mainline file."

        required_ids = self._required_obligation_ids()
        required_hunk_targets = self._required_hunk_targets()

        allowed_edit_types = {"replace", "insert_before", "insert_after", "delete"}
        cleaned: dict[str, list[dict[str, Any]]] = {}
        op_count = 0
        retry_scope_files = self._retry_scope_files()
        touched_files: set[str] = set()
        filtered_low_value = 0
        # Cache of on-disk target file contents for anchor verification.
        import os as _os  # local import to avoid broad changes at module top

        _target_file_cache: dict[str, str] = {}
        _TARGET_HUNK_LINE_WINDOW = 80

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

        # Merge decision payload incrementally across submit calls so coverage,
        # obligation checks, and hunk waivers remain stable in accumulator mode.
        decisions_now = list(wrapper_payload.get("obligation_decisions") or [])

        def _decision_key(d: dict[str, Any]) -> str:
            oid = str(d.get("obligation_id") or "").strip()
            if oid:
                return f"oid:{oid}"
            tf, hi = self._decision_file_and_hunk(d)
            if tf and hi is not None:
                return f"tfh:{tf}:{hi}"
            if tf:
                return f"tf:{tf}"
            return f"anon:{hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode('utf-8')).hexdigest()[:16]}"

        for d in decisions_now:
            if not isinstance(d, dict):
                continue
            self._accumulated_decisions[_decision_key(d)] = d
        decisions_all = list(self._accumulated_decisions.values())
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
                            "target_file": _normalize_rel_path(
                                str(op.get("target_file") or "")
                            ),
                            "edit_type": edit_type,
                            "old_string": old_string,
                            "new_string": new_string,
                            "verified": bool(op.get("verified", False)),
                            "verification_result": str(
                                op.get("verification_result") or "submitted_unchecked"
                            ),
                            "notes": str(op.get("notes") or "")
                            + " [low-value-restored]",
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
                            if not old_string.endswith("\n") and verbatim.endswith(
                                "\n"
                            ):
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

                # Hunk-line proximity gate (when locator mapping exists):
                # Require anchors for a specific hunk to match close to the mapped
                # target line, otherwise this is likely the wrong block in same file.
                mapped_line = None
                try:
                    mapped_line = self._mapped_line_for(
                        target_file, op.get("hunk_index")
                    )
                except Exception:
                    mapped_line = None
                if (
                    target_file
                    and tf_content
                    and mapped_line
                    and int(mapped_line) > 0
                    and op.get("hunk_index") is not None
                ):
                    op_old = str(op.get("old_string") or "")
                    is_import_anchor = (
                        all(
                            (ln.strip().startswith("import ") or not ln.strip())
                            for ln in op_old.splitlines()
                        )
                        if op_old.strip()
                        else False
                    )
                    if not is_import_anchor:
                        starts = self._anchor_match_lines(tf_content, old_string)
                        if starts:
                            nearest = min(
                                starts, key=lambda ln: abs(int(ln) - int(mapped_line))
                            )
                            # Only reject if there are multiple matches and ALL are out of window
                            # If there's exactly 1 match, it's unambiguous regardless of distance.
                            if (
                                len(starts) > 1
                                and abs(int(nearest) - int(mapped_line))
                                > _TARGET_HUNK_LINE_WINDOW
                            ):
                                anchor_errors.append(
                                    f"{target_file}#op[{idx}]: anchor matches {len(starts)} times, "
                                    f"nearest is line {nearest}, too far from mapped hunk line {mapped_line} "
                                    f"(window=±{_TARGET_HUNK_LINE_WINDOW})"
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
        if not hasattr(self, "_accumulated_no_change"):
            self._accumulated_no_change: set[str] = set()
        for d in decisions_all:
            if not isinstance(d, dict):
                continue
            st = str(d.get("status") or "").strip().lower()
            if st in {"verified_no_change", "blocked"}:
                # obligation_id format is typically "patch_file:<path>:" — extract
                oid = str(d.get("obligation_id") or "")
                tf = str(d.get("target_file") or "")
                if not tf and oid.startswith("patch_file:"):
                    tf = (
                        oid.split(":", 2)[1]
                        if ":" in oid[len("patch_file:") :]
                        else oid[len("patch_file:") :]
                    )
                    tf = tf.rstrip(":")
                tf = _normalize_rel_path(tf)
                if tf:
                    self._accumulated_no_change.add(tf)
        accum_touched |= self._accumulated_no_change
        missing_files_accum = [
            f for f in (self._required_patch_files or []) if f not in accum_touched
        ]

        # HUNK-LEVEL COVERAGE: touching file is not enough; each required hunk
        # must be represented by accepted ops or explicit waived decisions.
        accum_hunks_covered: set[tuple[str, int]] = set()
        for ops in self._accumulated_plan.values():
            for op in ops:
                tf = _normalize_rel_path(str(op.get("target_file") or ""))
                if not tf:
                    continue
                try:
                    hi = int(op.get("hunk_index") or 0)
                except Exception:
                    hi = 0
                if hi <= 0:
                    continue
                for cand in self._candidate_hunk_indices(hi):
                    accum_hunks_covered.add((tf, cand))

        waived_hunks = self._hunks_waived_by_decisions(decisions_all)
        missing_hunks_accum: list[tuple[str, int]] = []
        for req in required_hunk_targets:
            tf = _normalize_rel_path(str(req.get("target_file") or ""))
            try:
                hi = int(req.get("hunk_index") or 0)
            except Exception:
                hi = 0
            if not tf or hi <= 0:
                continue
            key = (tf, hi)
            if key in accum_hunks_covered or key in waived_hunks:
                continue
            missing_hunks_accum.append(key)

        # Anchor errors: accept the surviving ops into the accumulator (already
        # done above) and tell the model which ops failed so it can retry just
        # those. Do NOT reject the whole call — partial progress is progress.
        if anchor_errors and (missing_files_accum or missing_hunks_accum):
            # Only emit the anchor-failure error if we're still incomplete.
            # If accumulator already covers everything, fall through to success.
            self._submission_rejection_count += 1
            err_lines = "\n  - ".join(anchor_errors[:10])
            still_missing = "\n  - ".join(missing_files_accum)
            still_missing_hunks = ", ".join(
                [f"{f}#h{h}" for f, h in missing_hunks_accum[:12]]
            )
            return (
                "PARTIAL: some ops accepted into accumulator, but anchor "
                "verification failed for others AND coverage is still incomplete.\n"
                f"Accumulator now covers: {sorted(accum_touched)}\n"
                f"Still missing files:\n  - {still_missing}\n"
                f"Still missing hunks: {still_missing_hunks}\n"
                "Anchor failures (fix old_string to match target VERBATIM):\n  - "
                + err_lines
                + "\n"
                "Next call: submit ops ONLY for the still-missing files, "
                "and/or resubmit corrected versions of the anchor-failed ops. "
                "You do NOT need to resubmit ops that were already accepted."
            )

        # Coverage check: accumulator must touch ALL required patch files.
        if self._required_patch_files:
            missing_files = missing_files_accum
            if missing_files or missing_hunks_accum:
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
                            "; ".join(reasons[:5])
                            if reasons
                            else "all dropped silently"
                        )
                        diag_lines.append(
                            f"  - {mf}: submitted {submitted} op(s), all dropped → {reason_str}"
                        )
                already = sorted(accum_touched) or ["(none)"]
                hunk_diag = ""
                if missing_hunks_accum:
                    preview = ", ".join(
                        [f"{f}#h{h}" for f, h in missing_hunks_accum[:12]]
                    )
                    hunk_diag = (
                        "\nMissing required hunk coverage (file-level touch is insufficient):\n"
                        f"  - {preview}"
                    )
                return (
                    "PARTIAL: plan is incomplete but accumulator preserved.\n"
                    f"Already accepted: {already}\n"
                    "Still missing edits for:\n"
                    + "\n".join(diag_lines)
                    + hunk_diag
                    + "\n"
                    "Next call: submit ops ONLY for the still-missing files. "
                    "Each op MUST have non-empty `old_string`, non-empty `new_string` "
                    "(unless edit_type='delete'), and `target_file` set to the file path. "
                    "You do NOT need to resubmit files that are already accepted — "
                    "the accumulator keeps them."
                )

        if not cleaned and not self._accumulated_plan:
            if required_ids:
                decisions = list(self._accumulated_decisions.values())
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

        decisions = list(decisions_all)
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
                    # Keep accumulator coherent with any auto-filled decisions.
                    for d in decisions:
                        if isinstance(d, dict):
                            self._accumulated_decisions[_decision_key(d)] = d
                    decisions_all = list(self._accumulated_decisions.values())
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
        self._submitted_decisions = list(self._accumulated_decisions.values())
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
                    "Use this to reduce round-trips and token overhead. "
                    "Supported tools: read_file, read_mainline_file, grep, glob, bash, get_class_context, summarize_failure, todoread. "
                    'Each task must be {"tool": "<name>", "args": {...}} '
                    'OR shorthand {"<tool_name>": {<args>}}.'
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
                func=self.edit_by_lines,
                name="edit_by_lines",
                description=(
                    "USE THIS IF apply_edit FAILS OR FOR LARGE EDITS. "
                    "Replace lines `start_line` through `end_line` (1-indexed, inclusive) with `new_string`. "
                    "This avoids whitespace/formatting mismatch failures entirely. "
                    "To INSERT without deleting, use start_line = end_line = line_number_to_insert_after, "
                    "and start your new_string with the original line content."
                ),
            ),
            StructuredTool.from_function(
                func=self.append_method,
                name="append_method",
                description=(
                    "USE THIS FOR ADDING NEW METHODS/FIELDS. "
                    "Append new code to the very end of a class body (just before the final '}'). "
                    "This is much safer than `apply_edit` for large insertions."
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


def _extract_partial_feedback(submit_result: str) -> dict[str, list[str]]:
    """Parse structured hints from PARTIAL submit_recovery_plan output."""
    text = str(submit_result or "")
    missing_files: list[str] = []
    missing_hunks: list[str] = []
    anchor_failures: list[str] = []

    # Still missing files:
    #   - path
    m_files = re.search(
        r"Still missing files:\n(.*?)(?:\n[A-Z][^\n]*:|\Z)", text, re.DOTALL
    )
    if m_files:
        for ln in m_files.group(1).splitlines():
            s = ln.strip()
            if s.startswith("-"):
                val = s[1:].strip()
                if val:
                    missing_files.append(val)

    # Still missing hunks: file#h1, file#h2
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("Still missing hunks:"):
            tail = s.split(":", 1)[1].strip()
            if tail:
                parts = [p.strip() for p in tail.split(",") if p.strip()]
                missing_hunks.extend(parts)

    # Missing required hunk coverage (alternate PARTIAL format)
    m_hunks_alt = re.search(
        r"Missing required hunk coverage \(file-level touch is insufficient\):\n(.*?)(?:\n[A-Z][^\n]*:|\Z)",
        text,
        re.DOTALL,
    )
    if m_hunks_alt:
        for ln in m_hunks_alt.group(1).splitlines():
            s = ln.strip()
            if s.startswith("-"):
                val = s[1:].strip()
                if val:
                    for part in [p.strip() for p in val.split(",") if p.strip()]:
                        missing_hunks.append(part)

    # Anchor failures (fix old_string to match target VERBATIM):
    #   - ...
    m_anchor = re.search(
        r"Anchor failures .*?:\n(.*?)(?:\nNext call:|\Z)", text, re.DOTALL
    )
    if m_anchor:
        for ln in m_anchor.group(1).splitlines():
            s = ln.strip()
            if s.startswith("-"):
                val = s[1:].strip()
                if val:
                    anchor_failures.append(val)

    def _dedupe_keep_order(items: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for it in items:
            if it not in seen:
                seen.add(it)
                out.append(it)
        return out

    return {
        "missing_files": _dedupe_keep_order(missing_files),
        "missing_hunks": _dedupe_keep_order(missing_hunks),
        "anchor_failures": _dedupe_keep_order(anchor_failures),
    }


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


def _strip_diff_markers_from_lines(s: str) -> str:
    """Strip leading '+' / '-' diff markers from lines in old_string / new_string.

    LLMs frequently copy-paste diff context verbatim, including the +/- prefix
    characters.  This causes every multi-line match to fail because the literal
    dash or plus is not present in the actual file.

    We only strip when the marker is followed by a space (canonical diff format)
    to avoid false-positives on legitimate Java code starting with unary operators.
    """
    if not s:
        return s
    # Fast exit: if neither pattern is present, don't bother splitting
    if (
        "\n- " not in s
        and "\n+ " not in s
        and not s.startswith("- ")
        and not s.startswith("+ ")
    ):
        return s
    lines = s.split("\n")
    out = []
    for line in lines:
        if len(line) >= 2 and line[0] in ("+", "-") and line[1] == " ":
            out.append(line[1:])  # strip only the single marker char
        else:
            out.append(line)
    return "\n".join(out)


def _build_compact_recovery_system_prompt(
    *,
    failure_context: str,
    retry_scope: str,
    recovery_brief: str,
    recovery_obligations: str,
) -> str:
    """Compact system prompt (≤8k chars) used by default to keep per-round context bounded.

    Describes the direct-apply workflow (apply_edit + recovery_done), which is the primary
    path. submit_recovery_plan is excluded from tools when this prompt is active.
    """
    return _sanitize_for_content_policy(
        (
            "You are a Java backport recovery agent.\n"
            "Goal: directly apply all required edits to the target files, then call recovery_done.\n\n"
            "PRIMARY WORKFLOW (use these tools in order):\n"
            "1. apply_edit(target_file, old_string, new_string, edit_type)\n"
            "   — Applies ONE edit at a time. old_string MUST come from the actual TARGET file.\n"
            "   — Returns SUCCESS or FAILED with a hint. Iterate based on the response.\n"
            "   — Use grep or get_class_context to locate exact text if unsure.\n"
            "2. mark_no_change(target_file, reason)\n"
            "   — Only when target already has the equivalent code or change is inapplicable.\n"
            "3. recovery_done(summary)\n"
            "   — Call EXACTLY ONCE when every required file has been edited or marked.\n\n"
            "RULES:\n"
            "- MAINLINE ≠ TARGET. old_string must come from target code, not mainline patch lines.\n"
            "- Prefer short anchors (1-3 lines) — long anchors are the #1 cause of failure.\n"
            "- Make minimal, semantically correct edits only.\n"
            "- Prefer agenttool(role, objective, target_file) for heavy investigation — "
            "it runs in an isolated context and returns compact JSON evidence.\n\n"
            "deterministic_recovery_brief:\n"
            f"{recovery_brief}\n\n"
            "impact_obligations:\n"
            f"{recovery_obligations}\n\n"
            "retry_scope:\n"
            f"{retry_scope}\n\n"
            "failure_excerpt:\n"
            f"{_truncate(failure_context, 2000)}\n"
        ),
        8000,
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


def _cleanup_unused_java_imports(
    repo_path: str,
    rel_path: str,
    restrict_to: set[str] | None = None,
) -> list[str]:
    """Remove import lines whose simple class name doesn't appear in the file body.

    Deterministic post-edit cleanup: when the recovery agent removes a code
    block, the imports it referenced may become orphaned. Checkstyle treats
    those as build failures, so we strip them before capturing the diff.

    restrict_to: if provided, only consider removing imports whose simple class
    name is in this set (i.e. imports the mainline patch explicitly removed).
    This prevents accidentally dropping imports the developer kept.
    """
    import os

    full = os.path.join(repo_path, rel_path)
    if not os.path.isfile(full):
        return []
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    import_indices: list[tuple[int, str, str]] = []  # (line_idx, simple_name, raw_line)
    non_import_lines: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import "):
            if stripped.rstrip(";").endswith(".*"):
                continue  # keep wildcards
            m = re.search(r"[\.\s](\w+)\s*;", stripped)
            if m:
                import_indices.append((i, m.group(1), line))
        else:
            non_import_lines.append(line)

    # Strip block + line comments so commented-out references don't block removal.
    body_raw = "".join(non_import_lines)
    body_no_block = re.sub(r"/\*.*?\*/", " ", body_raw, flags=re.DOTALL)
    body_no_comments = re.sub(r"//[^\n]*", " ", body_no_block)

    to_remove: set[int] = set()
    removed: list[str] = []
    for idx, name, raw in import_indices:
        # If restrict_to is set, only consider removing imports explicitly
        # deleted by the mainline patch — don't touch imports the developer kept.
        if restrict_to is not None and name not in restrict_to:
            continue
        if not re.search(rf"\b{re.escape(name)}\b", body_no_comments):
            to_remove.add(idx)
            removed.append(raw.strip())

    if to_remove:
        new_lines = [l for i, l in enumerate(lines) if i not in to_remove]
        with open(full, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    return removed


def _build_progress_ledger(
    round_summaries: list[str],
    applied_edit_sigs: dict[str, int],
) -> HumanMessage | None:
    """Build a compact progress ledger HumanMessage from round summaries.

    Purely deterministic — no LLM calls. Returns None if nothing to summarize.
    """
    if not round_summaries and not applied_edit_sigs:
        return None
    lines = ["<progress_ledger>"]
    lines.extend(round_summaries)
    if applied_edit_sigs:
        files_edited = sorted({sig.split("|")[0] for sig in applied_edit_sigs})
        lines.append(f"Applied edits so far in: {', '.join(files_edited)}")
    lines.append("</progress_ledger>")
    return HumanMessage(content="\n".join(lines))


async def _run_parallel_tool_loop(
    llm,
    tools: list,
    initial_messages: list,
    preloaded_cache: dict[str, str],
    max_investigation_rounds: int = 2,
    toolkit: Any = None,
) -> tuple[list, str]:
    """
    Parallel batch tool execution loop with rolling context window.

    Key design principles to prevent LLM timeouts:
    1. ROLLING WINDOW: only the last 2 AI+Tool round pairs enter each LLM call.
       Older rounds are summarized in a compact progress ledger (pure Python, no LLM).
    2. TOOL RESULT PRUNING: results >4k chars are truncated before entering history.
    3. EDIT DEDUP: identical apply_edit calls are short-circuited without hitting disk.
    4. TIMEOUT RETRY: on timeout, shrink the window further and retry once.
    5. Parallel tool execution within each round (batch pattern).

    Returns (final_messages, termination_reason).
    """
    tool_map = {t.name: t for t in tools}
    bound_llm = llm.bind_tools(tools)
    base_llm = llm  # keep original for temperature bumps on repeated rejection
    loop = asyncio.get_event_loop()
    recent_tool_calls: list[tuple[str, Any]] = []
    last_submit_rejected = False
    rejection_retry_bonus_used = 0
    last_submit_args_sig: str = ""
    consecutive_read_calls: int = 0

    # Rolling context window state
    # initial_messages = [SystemMessage, HumanMessage(task)] — never mutated
    # recent_rounds: list of (AIMessage, [ToolMessage...]) pairs, capped at 2
    # ledger_summaries: plain text lines summarizing evicted rounds
    # applied_edit_sigs: hash → round_num for dedup of apply_edit calls
    recent_rounds: list[tuple[Any, list[Any]]] = []
    ledger_summaries: list[str] = []
    applied_edit_sigs: dict[str, int] = {}  # sig -> round_num first applied
    # Extra messages appended AFTER recent_rounds (remap hints, directives)
    # These are per-round ephemeral injections cleared each round
    round_tail_messages: list[Any] = []

    _TOOL_RESULT_MAX_CHARS = 4000  # truncate tool results before storing in history

    def _current_messages() -> list[Any]:
        """Reconstruct the live message list from rolling window state."""
        msgs = list(initial_messages)
        ledger = _build_progress_ledger(ledger_summaries, applied_edit_sigs)
        if ledger:
            msgs.append(ledger)
        for ai_msg, tool_msgs in recent_rounds:
            msgs.append(ai_msg)
            msgs.extend(tool_msgs)
        msgs.extend(round_tail_messages)
        return msgs

    def _summarize_tool_call(
        name: str, args: dict, content: str, round_num: int
    ) -> str:
        """Build a one-line ledger entry for an evicted tool call."""
        if name == "apply_edit":
            tf = str(args.get("target_file") or "")
            status = (
                "SUCCESS"
                if "SUCCESS" in content
                else ("SKIPPED" if "skipped" in content.lower() else "FAILED")
            )
            return f"R{round_num}: apply_edit({tf}) → {status}"
        if name in {"read_file", "get_class_context"}:
            fp = str(args.get("file_path") or args.get("class_name") or "")
            nlines = content.count("\n")
            return f"R{round_num}: {name}({fp}) → {nlines} lines"
        if name == "recovery_done":
            return f"R{round_num}: recovery_done → accepted"
        if name == "mark_no_change":
            tf = str(args.get("target_file") or "")
            return f"R{round_num}: mark_no_change({tf})"
        # generic
        snippet = content[:80].replace("\n", " ")
        return f"R{round_num}: {name}(...) → {snippet}"

    def _evict_oldest_round() -> None:
        """Move the oldest round from recent_rounds into ledger_summaries."""
        if not recent_rounds:
            return
        ai_msg, tool_msgs = recent_rounds.pop(0)
        tool_calls = list(getattr(ai_msg, "tool_calls", None) or [])
        # Pair each tool call with its result message
        tc_by_id = {str(tc.get("id") or ""): tc for tc in tool_calls}
        for tm in tool_msgs:
            tc_id = str(getattr(tm, "tool_call_id", "") or "")
            tc = tc_by_id.get(tc_id, {})
            name = str(tc.get("name") or getattr(tm, "name", "") or "")
            args = dict((tc.get("args") or {}))
            content = str(getattr(tm, "content", "") or "")
            # Use the already-parsed round from the ai_msg metadata if available
            rnum = getattr(ai_msg, "_round_num", "?")
            ledger_summaries.append(_summarize_tool_call(name, args, content, rnum))

    def _append_round(ai_msg: Any, tool_msgs: list[Any], round_num: int) -> None:
        """Add a completed round to the window, evicting oldest if at capacity."""
        ai_msg._round_num = round_num  # tag for ledger
        # Truncate tool message content before storing
        truncated_tool_msgs = []
        for tm in tool_msgs:
            content = str(getattr(tm, "content", "") or "")
            if len(content) > _TOOL_RESULT_MAX_CHARS:
                content = (
                    content[:_TOOL_RESULT_MAX_CHARS]
                    + f"\n…[truncated at {_TOOL_RESULT_MAX_CHARS} chars; use grep/read_file for more]"
                )
                tm = ToolMessage(
                    content=content,
                    tool_call_id=str(getattr(tm, "tool_call_id", "") or ""),
                    name=str(getattr(tm, "name", "") or ""),
                )
            truncated_tool_msgs.append(tm)
        recent_rounds.append((ai_msg, truncated_tool_msgs))
        # Keep at most 2 recent rounds
        while len(recent_rounds) > 2:
            _evict_oldest_round()

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

        # Dedup apply_edit: skip if identical (file, old_string, new_string) already applied
        if name == "apply_edit":
            tf = str(args.get("target_file") or "")
            old_s = str(args.get("old_string") or "")
            new_s = str(args.get("new_string") or "")
            sig = hashlib.sha256(f"{tf}|{old_s}|{new_s}".encode("utf-8")).hexdigest()[
                :16
            ]
            full_sig = f"{tf}|{sig}"
            if full_sig in applied_edit_sigs:
                prev_round = applied_edit_sigs[full_sig]
                return (
                    call_id,
                    f'{{"status":"skipped","reason":"identical edit already applied in round {prev_round} — move on to the next required file"}}',
                )

        tool = tool_map.get(name)
        if not tool:
            return call_id, f"ERROR: unknown tool {name!r}"
        try:
            _tool, _args = tool, args
            result = await loop.run_in_executor(None, lambda: _tool.invoke(_args))
            result_str = str(result)
            # Register successful apply_edit for dedup
            if name == "apply_edit" and "SUCCESS" in result_str:
                tf = str(args.get("target_file") or "")
                old_s = str(args.get("old_string") or "")
                new_s = str(args.get("new_string") or "")
                sig = hashlib.sha256(
                    f"{tf}|{old_s}|{new_s}".encode("utf-8")
                ).hexdigest()[:16]
                applied_edit_sigs[f"{tf}|{sig}"] = round_num
                # Invalidate preloaded_cache so subsequent read_file calls
                # return the updated on-disk content, not the stale cached version.
                rel_tf = _normalize_rel_path(tf)
                if rel_tf in preloaded_cache:
                    del preloaded_cache[rel_tf]
            return call_id, result_str
        except Exception as exc:
            return call_id, f"ERROR executing {name}: {exc}"

    round_num = -1
    # Hard absolute cap to bound LLM cost regardless of bonuses granted.
    absolute_round_cap = max_investigation_rounds + 4
    while True:
        round_num += 1
        if round_num > absolute_round_cap:
            print(f"[Recovery] absolute round cap ({absolute_round_cap}) reached")
            break
        # Soft cap: stop when we've used budget AND no rejection is pending
        if round_num > max_investigation_rounds + 1:
            break
        print(f"[Recovery] === Round {round_num} ===")

        async def _invoke_with_retry(shrink: bool = False) -> Any:
            """Invoke LLM with 180s timeout; on failure retry once with shrunk window."""
            _msgs = _current_messages()
            if shrink and len(recent_rounds) > 1:
                # Drop oldest recent round to further reduce context
                _evict_oldest_round()
                _msgs = _current_messages()
            return await asyncio.wait_for(
                bound_llm.ainvoke(_msgs),
                timeout=300.0,  # 3 min per call — healthy Gemma response is <60s
            )

        try:
            response = await _invoke_with_retry(shrink=False)
        except asyncio.TimeoutError:
            print(
                f"[Recovery] LLM call timed out in round {round_num}; retrying once with shrunk context…"
            )
            try:
                response = await _invoke_with_retry(shrink=True)
            except asyncio.TimeoutError:
                print(
                    f"[Recovery] LLM retry also timed out in round {round_num}; aborting."
                )
                return _current_messages(), "llm_timeout"

        # LLM has seen the tail messages from the previous round — clear them now
        # so they don't accumulate across rounds (they will be ledger-summarized instead).
        round_tail_messages.clear()

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
            return _current_messages(), "no_tool_calls"

        # Log tool calls
        for tc in tool_calls:
            name = tc.get("name", "?")
            args = tc.get("args") or {}
            args_full = json.dumps(args, default=str)
            args_summary = args_full[:300]
            print(f"[Recovery] tool_call: {name}({args_summary})")
            if name == "submit_recovery_plan" and len(args_full) > 300:
                # Log edit_ops keys to see which files are included
                edit_ops = (
                    args.get("edit_ops") or args.get("plan", {}).get("edit_ops") or {}
                )
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
            submit_tool_msgs: list[ToolMessage] = []
            for tc in submit_calls:
                content = result_map.get(str(tc.get("id") or ""), "")
                full_content = str(content)
                print(f"[Recovery] submit_recovery_plan → {full_content[:1500]}")
                if len(full_content) > 1500:
                    print(
                        f"[Recovery] submit_recovery_plan (continued) → {full_content[1500:3000]}"
                    )
                submit_tool_msgs.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=str(tc.get("id") or ""),
                        name=str(tc.get("name") or ""),
                    )
                )
            _append_round(response, submit_tool_msgs, round_num)

            # Only return "submitted" if at least one submit reached SUCCESS.
            # PARTIAL responses mean the accumulator absorbed ops but coverage
            # is still incomplete — we must keep looping so the model can
            # submit the still-missing files.
            def _is_success(c: str) -> bool:
                s = str(c)
                return not s.startswith("ERROR") and not s.startswith("PARTIAL")

            any_success = any(_is_success(content) for _, content in results)
            if any_success:
                return _current_messages(), "submitted"
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
                    "<hunk_snippets>.\n\n"
                    + "\n\n".join(remap_blocks)
                    + "\n</remap_hints>"
                )
                round_tail_messages.append(HumanMessage(content=remap_xml))
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
            round_tail_messages.append(HumanMessage(content=base_directive))

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

            # Collect ToolMessages for all original calls (duplicates reuse the result)
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
            # Commit this round into the rolling window (truncates results, evicts old)
            _append_round(response, tool_messages, round_num)
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
                return _current_messages(), "applied_directly"

            # Track consecutive read/grep calls (analysis paralysis)
            all_read = bool(investigate_calls)
            for tc in investigate_calls:
                name = str(tc.get("name") or "")
                if name not in (
                    "read_file",
                    "grep",
                    "get_class_context",
                    "glob",
                    "bash",
                    "batch_tools",
                ):
                    all_read = False
                    break

            if all_read and not submit_calls:
                consecutive_read_calls += 1
            else:
                consecutive_read_calls = 0

            if consecutive_read_calls >= 3 and round_num < max_investigation_rounds:
                stagnation_hint = (
                    "<stagnation_warning>\n"
                    "You have spent several rounds only reading files without making any edits. "
                    "If you are struggling to format a large `apply_edit` block with exact whitespace, "
                    "USE the `edit_by_lines` tool to replace the exact line numbers instead, or "
                    "`append_method` if you are adding new methods to the end of a class.\n"
                    "Stop reading and start editing!\n"
                    "</stagnation_warning>"
                )
                round_tail_messages.append(HumanMessage(content=stagnation_hint))
                print(
                    f"[Recovery] Injected analysis paralysis warning at round {round_num}"
                )
                consecutive_read_calls = 0  # reset to avoid spamming every round

            # Stagnation guard: if the model keeps repeating identical calls,
            # force plan submission early instead of burning rounds/tokens.
            for tc in investigate_calls:
                recent_tool_calls.append(
                    (str(tc.get("name") or ""), tc.get("args") or {})
                )
            if len(recent_tool_calls) > 32:
                recent_tool_calls = recent_tool_calls[-32:]

            stagnating, reason = _detect_stagnation(recent_tool_calls[-12:], limit=5)
            if stagnating and round_num < max_investigation_rounds:
                print(f"[Recovery] Stagnation detected; injecting nudge: {reason}")
                round_tail_messages.append(
                    HumanMessage(
                        content=(
                            "<stagnation_warning>You have called the same tool with the "
                            "same arguments multiple times without progress. Try a "
                            "different approach: use grep to locate the exact text in the "
                            "file, pick a different (shorter, more unique) old_string anchor, "
                            "or target a different location. "
                            "Do NOT repeat the failing call.</stagnation_warning>"
                        )
                    )
                )

            # Special case: if the last tool result was a size-cap rejection
            # and the model is repeating the same call, inject a concrete
            # decomposition hint rather than the generic force_submit message.
            if tool_messages:
                last_result = str(getattr(tool_messages[-1], "content", "") or "")
                if "too broad" in last_result or "too large" in last_result:
                    # Check if the same apply_edit was already rejected last round
                    last_calls = recent_tool_calls[-6:]
                    _ae_sigs = [
                        json.dumps(args, sort_keys=True)
                        for name, args in last_calls
                        if name == "apply_edit"
                    ]
                    if len(_ae_sigs) >= 2 and len(set(_ae_sigs)) == 1:
                        # Same exact oversized call repeated — give targeted guidance
                        try:
                            bad_args = last_calls[-1][1]
                            old_str = str(bad_args.get("old_string") or "")
                            old_lines = old_str.splitlines()
                            half = len(old_lines) // 2
                            split_line = (
                                old_lines[half] if half < len(old_lines) else ""
                            )
                        except Exception:
                            split_line = ""
                        hint = (
                            "<decompose_hint>\n"
                            "You keep submitting the same edit that is too large. "
                            "You MUST split it into 2 or more separate apply_edit calls.\n\n"
                            "How to split:\n"
                            "1. Find a natural boundary in the old_string — a blank line, "
                            "the start of a method, or the end of a parameter list.\n"
                            "2. Call apply_edit once for the FIRST part (e.g. just the field "
                            "declarations or imports).\n"
                            "3. Call apply_edit again for the SECOND part (e.g. the constructor "
                            "body or method signature).\n"
                            "Each call must be under 80 lines.\n"
                        )
                        if split_line:
                            hint += f'Example split point (around line {half}): "{split_line.strip()[:80]}"\n'
                        hint += "</decompose_hint>"
                        round_tail_messages.append(HumanMessage(content=hint))
                        print(
                            f"[Recovery] injected decompose_hint after repeated size-cap rejection "
                            f"(round {round_num})"
                        )

        elif submit_calls:
            # submit_calls path already called _append_round above; nothing more to do here.
            pass

        # ── Automatic context injection for repeated apply_edit failures ─────────
        # When the LLM fails ≥2 times on the same file and has not yet received
        # an injected content block for it, read the actual on-disk content and
        # provide it so the LLM can build a correct old_string anchor.
        if toolkit is not None and hasattr(toolkit, "_failed_edit_tracker"):
            for _rel_file, _failed_anchors in list(
                toolkit._failed_edit_tracker.items()
            ):
                if (
                    len(_failed_anchors) >= 2
                    and _rel_file not in toolkit._context_injected_files
                ):
                    _full_path = os.path.join(toolkit.target_repo_path, _rel_file)
                    try:
                        with open(
                            _full_path, "r", encoding="utf-8", errors="replace"
                        ) as _cf:
                            _flines = _cf.readlines()
                        # Build grep-based relevant sections for the failed anchors
                        _relevant_sections: list[str] = []
                        _seen_ranges: set[tuple[int, int]] = set()
                        for _failed_anchor in _failed_anchors[:3]:
                            # Extract meaningful keywords (>5 chars, identifier-like)
                            import re as _re_inj

                            _keywords = [
                                w
                                for w in _re_inj.findall(
                                    r"[A-Za-z_][A-Za-z0-9_]{4,}", _failed_anchor
                                )
                                if w
                                not in {
                                    "import",
                                    "public",
                                    "private",
                                    "static",
                                    "void",
                                    "class",
                                    "return",
                                    "throws",
                                    "extends",
                                    "implements",
                                    "String",
                                    "boolean",
                                    "false",
                                    "true",
                                    "null",
                                }
                            ][:3]
                            for _kw in _keywords:
                                for _li, _line in enumerate(_flines):
                                    if _kw in _line:
                                        _rs = max(0, _li - 6)
                                        _re2 = min(len(_flines), _li + 12)
                                        _rkey = (_rs, _re2)
                                        if _rkey not in _seen_ranges:
                                            _seen_ranges.add(_rkey)
                                            _sec = "".join(
                                                f"    {_rs + _ri + 1}: {_flines[_rs + _ri]}"
                                                for _ri in range(_re2 - _rs)
                                            )
                                            _relevant_sections.append(
                                                f"  Lines {_rs + 1}-{_re2} "
                                                f"(contains '{_kw}'):\n{_sec}"
                                            )
                                        break  # one hit per keyword

                        _rel_sec_block = ""
                        if _relevant_sections:
                            _rel_sec_block = (
                                "\n\nKeyword-matched sections from failed old_string "
                                "attempts (most likely candidates for old_string):\n"
                                + "\n".join(_relevant_sections[:4])
                            )

                        _preview = "".join(
                            f"{i + 1}: {ln}"
                            for i, ln in enumerate(_flines[:500])  # increased from 250
                        )

                        _injection = (
                            f"<ACTUAL_FILE_CONTENT file='{_rel_file}'>\n"
                            f"Your apply_edit calls for '{_rel_file}' FAILED "
                            f"{len(_failed_anchors)} time(s).\n\n"
                            f"IMPORTANT: The target is an OLDER codebase. A symbol like "
                            f"`countdownAndMaybeContinue` from the mainline patch may NOT "
                            f"exist in the target. Instead, look for DIFFERENT code at "
                            f"the same semantic location (same method, similar context).\n\n"
                            f"Complete on-disk content of '{_rel_file}' "
                            f"(lines 1-{min(500, len(_flines))}):\n\n"
                            f"```java\n{_preview}\n```"
                            f"{_rel_sec_block}\n\n"
                            f"RULES:\n"
                            f"1. old_string MUST be copied VERBATIM from the lines above.\n"
                            f"2. If a mainline symbol does not appear in the file, look for "
                            f"   semantically equivalent code at the mapped line from "
                            f"   <per_hunk_target_mappings> in the system message.\n"
                            f"3. Constructor/method signatures in the TARGET differ from mainline.\n"
                            f"</ACTUAL_FILE_CONTENT>"
                        )
                        round_tail_messages.append(HumanMessage(content=_injection))
                        toolkit._context_injected_files.add(_rel_file)
                        print(
                            f"[Recovery] injected ACTUAL_FILE_CONTENT for {_rel_file} "
                            f"after {len(_failed_anchors)} failed apply_edit attempt(s) "
                            f"(round {round_num})"
                        )
                    except Exception as _cie:
                        print(
                            f"[Recovery] could not inject content for "
                            f"{_rel_file}: {_cie}"
                        )

        # After responding to all tool calls, check if investigation budget is exhausted.
        # Skip force_submit if the last action was a rejected submit — the rejection
        # tool message + <fix_and_resubmit> directive already tell the model what to do,
        # and force_submit would just nudge it to resubmit the same broken plan.
        if round_num >= max_investigation_rounds and not last_submit_rejected:
            print(
                f"[Recovery] Round {round_num} >= max_investigation_rounds, injecting force_submit"
            )
            # Build a state-aware message: if there are still unresolved files, give
            # targeted context rather than a blind nudge; otherwise ask for recovery_done.
            _force_parts: list[str] = []
            if toolkit is not None and hasattr(
                toolkit, "_compute_missing_patch_additions"
            ):
                _applied_fs = {e["target_file"] for e in toolkit._applied_edits}
                _missing_r = toolkit._compute_missing_patch_additions(_applied_fs)
                _failed_fs = {
                    f
                    for f, fails in toolkit._failed_edit_tracker.items()
                    if len(fails) >= 1
                }
                _actionable = (set(_missing_r.keys()) | _failed_fs) - _applied_fs
                if _actionable:
                    _force_parts.append(
                        "<force_submit>Investigation rounds exhausted. "
                        "The following files still have missing or failed edits — "
                        "make ONE final attempt for each using the file content "
                        "shown above (or call read_file if not yet shown), "
                        "then call recovery_done:\n"
                    )
                    for _af in sorted(_actionable):
                        _force_parts.append(f"  - {_af}\n")
                    _force_parts.append("</force_submit>")
                else:
                    _force_parts.append(
                        "<force_submit>All required edits appear to be applied. "
                        "Call recovery_done now to finalise.</force_submit>"
                    )
            else:
                _force_parts.append(
                    "<force_submit>You have used all investigation rounds. "
                    "Call recovery_done now to finalise. "
                    "Do not call any other tools.</force_submit>"
                )
            round_tail_messages.append(HumanMessage(content="".join(_force_parts)))
        # Reset for next round (cleared whether we injected fix_and_resubmit or not)
        last_submit_rejected = False

    print("[Recovery] Exited loop: max_rounds_exceeded")
    return _current_messages(), "max_rounds_exceeded"


# ═══════════════════════════════════════════════════════════════════════════
# REDESIGNED RECOVERY FLOW (3-phase: investigate → plan → format)
# ═══════════════════════════════════════════════════════════════════════════
#
# Why: the old apply_edit-driven loop burned 10+ LLM rounds on a single patch,
# each round re-reading the full message history → Gemma-4 timed out and tokens
# were wasted. The redesign splits recovery into three bounded phases:
#
#   Phase 1 — Investigation (≤2 rounds, READ-ONLY tools)
#     The LLM sees ALL context up-front (patch, preloaded files, dependency
#     graph, obligations) and issues every tool call it needs in ONE response.
#     Tools run in parallel. Results returned in one batch. A second round is
#     allowed only if the LLM explicitly requests more context.
#
#   Phase 2 — Plan generation (1 LLM call, NO tools)
#     The LLM writes a natural-language adaptation plan with per-file unified
#     diff blocks. This text is saved as `recovery_plan_text` artifact.
#
#   Phase 3 — Format conversion (1 LLM call, submit_recovery_plan forced)
#     A fresh LLM call converts the plan text into strict edit_ops JSON via
#     submit_recovery_plan, feeding the existing hunk_generator pipeline.
#
# Total LLM calls per recovery: ≤4 (vs ~13 in the old loop).

_RECOVERY_INVESTIGATION_SYSTEM = """You are a Java backport recovery INVESTIGATOR.

Your job: in ONE response, issue ALL the tool calls you need to fully understand how to adapt the mainline patch to the target repository.

You will see up-front:
- The mainline patch diff
- All target files referenced by the patch (PRELOADED — do NOT read_file them again)
- The dependency graph for those files
- Obligations listing what must be covered
- A deterministic recovery brief

PROTOCOL:
1. Read the context carefully.
2. In ONE assistant response, call `batch_tools` with EVERY tool invocation you need (grep, read_file for files NOT in the preloaded set, get_class_context, find_symbol_locations, read_mainline_file, etc.).
3. Do NOT call tools one at a time — batch them.
4. If the preloaded context is already sufficient, respond with exactly: `INVESTIGATION_COMPLETE` and nothing else.
5. After you see the tool results, either issue MORE batched calls (only if truly needed) OR respond with `INVESTIGATION_COMPLETE`.

Hard limit: 2 rounds of investigation. Use them wisely.

Available read-only tools: batch_tools, read_file, read_mainline_file, grep, glob, get_class_context, get_dependency_graph, find_symbol_locations, find_method_match, summarize_failure.

Do NOT edit files. Do NOT produce the plan yet — that comes after investigation.
"""

_RECOVERY_PLAN_SYSTEM = """You are a Java backport recovery PLANNER.

Using ONLY the investigation context gathered above, produce a complete adaptation plan.

OUTPUT FORMAT (strict):

# Adaptation Plan

## Intent
<1-2 sentences: what the patch does semantically>

## Per-file changes

### <target_file_path>
<1-3 sentences: what needs to change in this file and why>

```diff
<old-code-block>
---
<new-code-block>
```

<repeat the ### block for each target file that needs changes>

## No-change files
- <target_file>: <reason it needs no change in target>
- <repeat>

## Risk notes
- <concerns, dropped hunks, uncertainty>

RULES:
- Every old-code-block MUST be VERBATIM text copied from the target file content shown earlier. NOT from the mainline patch `-` lines.
- DO NOT USE ELLIPSIS (...) or placeholders to represent skipped code. The old-code-block must match the file content contiguous line for line.
- Prefer SHORT anchors (1-5 lines).
- One diff block per distinct edit. Multiple edits per file are allowed — repeat the ``` diff ``` block.
- Use `---` as the separator between old and new code inside each diff block.
- If a required file needs no change, list it under "No-change files" with a reason instead of a diff block.
- Do NOT output duplicate diff blocks. Provide your adaptation plan exactly once. Do not write drafts followed by clean versions.
- Do NOT call any tools. Just write the plan as markdown text.
"""

_RECOVERY_FORMATTER_SYSTEM = """You are a format-conversion agent. You will receive a natural-language recovery plan with diff blocks, and you MUST convert it into a strict edit_ops JSON by calling `submit_recovery_plan` exactly once.

You have NO other tools. You MUST call submit_recovery_plan. Do not produce any other output.

Schema for submit_recovery_plan:
{
  "edit_ops": {
    "<MAINLINE file path>": [
      {
        "hunk_index": <int, 0-based>,
        "target_file": "<TARGET file path>",
        "edit_type": "replace",
        "old_string": "<VERBATIM old code from the diff block>",
        "new_string": "<VERBATIM new code from the diff block>",
        "notes": "<brief reason>"
      }
    ]
  },
  "obligation_decisions": [
    {"obligation_id": "<id>", "status": "edited" | "verified_no_change", "reason": "<brief>", "evidence": ["<short>"]}
  ],
  "investigation_evidence": [
    {"kind": "note", "details": "<brief>"}
  ],
  "risk_notes": ["<risk>"]
}

RULES:
- One edit_ops entry per diff block in the plan. Keep old_string and new_string VERBATIM as they appear in the diff (do not re-indent, do not normalize whitespace).
- For every file listed under "No-change files" in the plan, emit an obligation_decision with status="verified_no_change".
- For every file with diff blocks, emit an obligation_decision with status="edited".
- mainline_file key in edit_ops should equal target_file unless the plan explicitly says otherwise.
- edit_type is always "replace" unless the diff clearly adds new code with no old anchor (then use "insert_after" and put the preceding line in old_string).
- hunk_index starts at 0 and increments per file.

Call submit_recovery_plan now.
"""


async def _run_recovery_redesign(
    llm,
    toolkit: Any,
    preloaded_context_xml: str,
    patch_diff: str,
    recovery_brief_json: str,
    recovery_obligations_json: str,
    dependency_graph_text: str,
    max_investigation_rounds: int = 2,
    max_partial_retries: int = 2,
) -> tuple[str, str, list[Any]]:
    """Run the 3-phase redesigned recovery flow.

    Returns (term_reason, plan_text, all_messages_for_token_accounting).
    """
    all_messages: list[Any] = []  # for token accounting only

    # ── PHASE 1: INVESTIGATION (read-only tools, ≤2 rounds) ────────────────
    read_only_tool_names = {
        "batch_tools",
        "read_file",
        "read_mainline_file",
        "grep",
        "glob",
        "get_class_context",
        "get_dependency_graph",
        "find_symbol_locations",
        "find_method_match",
        "summarize_failure",
    }
    all_tools = toolkit.get_tools(include_submit=False)
    investigation_tools = [t for t in all_tools if t.name in read_only_tool_names]
    tool_map = {t.name: t for t in investigation_tools}
    inv_bound_llm = llm.bind_tools(investigation_tools)

    investigation_context_parts: list[str] = [preloaded_context_xml]
    if dependency_graph_text:
        investigation_context_parts.append(
            f"<dependency_graph>\n{_truncate(dependency_graph_text, 6000)}\n</dependency_graph>"
        )
    investigation_context_parts.append(
        f"<mainline_patch>\n{_truncate(patch_diff, 6000)}\n</mainline_patch>"
    )
    investigation_context_parts.append(
        f"<recovery_brief>\n{_truncate(recovery_brief_json, 4000)}\n</recovery_brief>"
    )
    investigation_context_parts.append(
        f"<obligations>\n{_truncate(recovery_obligations_json, 4000)}\n</obligations>"
    )
    investigation_context_parts.append(
        "Now issue ALL the tool calls you need in ONE response via batch_tools. "
        "If the preloaded context is sufficient, reply with exactly INVESTIGATION_COMPLETE."
    )
    inv_messages: list[Any] = [
        SystemMessage(content=_RECOVERY_INVESTIGATION_SYSTEM),
        HumanMessage(content="\n\n".join(investigation_context_parts)),
    ]

    loop = asyncio.get_event_loop()

    async def _execute_tool_call(tc: dict) -> tuple[str, str]:
        name = str(tc.get("name") or "")
        args = dict(tc.get("args") or {})
        call_id = str(tc.get("id") or "")
        tool = tool_map.get(name)
        if not tool:
            return (
                call_id,
                f"ERROR: unknown tool {name!r} (investigation phase is read-only)",
            )
        try:
            result = await loop.run_in_executor(None, lambda: tool.invoke(args))
            result_str = str(result)
            if len(result_str) > 8000:
                result_str = (
                    result_str[:8000]
                    + "\n…[truncated — request narrower scope if needed]"
                )
            return call_id, result_str
        except Exception as exc:
            return call_id, f"ERROR executing {name}: {exc}"

    for inv_round in range(max_investigation_rounds):
        print(f"[Recovery-Redesign] === Investigation round {inv_round} ===")
        try:
            response = await asyncio.wait_for(
                inv_bound_llm.ainvoke(inv_messages),
                timeout=180.0,
            )
        except asyncio.TimeoutError:
            print(f"[Recovery-Redesign] investigation round {inv_round} timed out")
            return "llm_timeout", "", inv_messages

        inv_messages.append(response)
        resp_text = str(getattr(response, "content", "") or "")
        if isinstance(getattr(response, "content", None), list):
            resp_text = " ".join(
                str(p.get("text") or "") if isinstance(p, dict) else str(p)
                for p in response.content
            )

        tool_calls = list(getattr(response, "tool_calls", None) or [])
        if "INVESTIGATION_COMPLETE" in resp_text.upper() and not tool_calls:
            print(
                f"[Recovery-Redesign] LLM signaled INVESTIGATION_COMPLETE in round {inv_round}"
            )
            break
        if not tool_calls:
            print(
                f"[Recovery-Redesign] no tool calls in round {inv_round}, assuming investigation done"
            )
            break

        print(
            f"[Recovery-Redesign] round {inv_round}: executing {len(tool_calls)} tool call(s) in parallel"
        )
        results = await asyncio.gather(*[_execute_tool_call(tc) for tc in tool_calls])
        result_map = dict(results)
        for tc in tool_calls:
            content = result_map.get(str(tc.get("id") or ""), "")
            inv_messages.append(
                ToolMessage(
                    content=content,
                    tool_call_id=str(tc.get("id") or ""),
                    name=str(tc.get("name") or ""),
                )
            )
        if inv_round == max_investigation_rounds - 1:
            inv_messages.append(
                HumanMessage(
                    content="No more investigation rounds available. Reply with INVESTIGATION_COMPLETE now."
                )
            )

    all_messages.extend(inv_messages)

    # Shared base context for planning retries.
    investigation_summary_parts: list[str] = [preloaded_context_xml]
    if dependency_graph_text:
        investigation_summary_parts.append(
            f"<dependency_graph>\n{_truncate(dependency_graph_text, 4000)}\n</dependency_graph>"
        )
    investigation_summary_parts.append(
        f"<mainline_patch>\n{_truncate(patch_diff, 6000)}\n</mainline_patch>"
    )
    investigation_summary_parts.append(
        f"<obligations>\n{_truncate(recovery_obligations_json, 3000)}\n</obligations>"
    )
    investigation_summary_parts.append("<investigation_findings>")
    for m in inv_messages:
        if isinstance(m, ToolMessage):
            name = str(getattr(m, "name", "") or "")
            content = str(getattr(m, "content", "") or "")
            investigation_summary_parts.append(
                f'<finding tool="{name}">\n{_truncate(content, 4000)}\n</finding>'
            )
    investigation_summary_parts.append("</investigation_findings>")
    base_investigation_summary = "\n\n".join(investigation_summary_parts)

    def _parse_plan(
        text: str,
    ) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[str]]:
        import re as _re

        # Handle cases where the LLM inserts formatting backticks around the '---' separator
        text = _re.sub(r"```[ \t]*\n---\n(?:```[a-z]*[ \t]*\n)?", "\n---\n", text)

        parsed_edit_ops: dict[str, list[dict[str, Any]]] = {}
        parsed_decisions: list[dict[str, Any]] = []
        parsed_risk_notes: list[str] = []

        file_section_re = _re.compile(r"^### (.+)$", _re.MULTILINE)
        diff_block_re = _re.compile(r"```diff\n(.*?)```", _re.DOTALL)

        seen_edits: set[tuple[str, str, str]] = set()

        sections = list(file_section_re.finditer(text))
        for i, sec_match in enumerate(sections):
            file_path = sec_match.group(1).strip()
            sec_start = sec_match.end()
            sec_end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
            section_body = text[sec_start:sec_end]

            diffs = list(diff_block_re.finditer(section_body))
            if not diffs:
                parsed_decisions.append(
                    {
                        "obligation_id": file_path,
                        "status": "verified_no_change",
                        "reason": "No diff block in plan",
                        "evidence": [],
                    }
                )
                continue

            file_edits = parsed_edit_ops.setdefault(file_path, [])
            for hunk_idx, dm in enumerate(diffs):
                diff_body = dm.group(1)
                sep = "\n---\n"
                if sep in diff_body:
                    old_part, new_part = diff_body.split(sep, 1)
                else:
                    parts = _re.split(r"(?m)^---$", diff_body, maxsplit=1)
                    if len(parts) == 2:
                        old_part, new_part = parts
                    else:
                        print(
                            f"[Recovery-Redesign] cannot parse diff block in {file_path} hunk {hunk_idx}"
                        )
                        continue

                old_string = old_part.rstrip("\n")
                new_string = new_part.lstrip("\n").rstrip("\n")
                edit_sig = (file_path, old_string, new_string)
                if edit_sig in seen_edits:
                    print(
                        f"[Recovery-Redesign] Dropping duplicate diff block in {file_path}"
                    )
                    continue
                seen_edits.add(edit_sig)

                file_edits.append(
                    {
                        "hunk_index": hunk_idx,
                        "target_file": file_path,
                        "edit_type": "replace",
                        "old_string": old_string,
                        "new_string": new_string,
                        "verified": False,
                        "verification_result": "parsed_from_plan",
                        "notes": f"Parsed from recovery plan, section {file_path}",
                    }
                )

            parsed_decisions.append(
                {
                    "obligation_id": file_path,
                    "status": "edited",
                    "reason": f"{len(file_edits)} edit(s) extracted from plan",
                    "evidence": [f"hunk {h['hunk_index']}" for h in file_edits],
                }
            )

        risk_section = _re.search(r"## Risk notes\n(.*?)(?=\n## |\Z)", text, _re.DOTALL)
        if risk_section:
            for line in risk_section.group(1).splitlines():
                item = line.strip().lstrip("- ").strip()
                if item:
                    parsed_risk_notes.append(item)

        return parsed_edit_ops, parsed_decisions, parsed_risk_notes

    submit_tool = None
    for t in toolkit.get_tools(include_submit=True):
        if t.name == "submit_recovery_plan":
            submit_tool = t
            break
    if submit_tool is None:
        return "formatter_missing_submit_tool", "", all_messages

    latest_plan_text = ""
    last_submit_result = ""
    for redesign_iter in range(max_partial_retries + 1):
        print(
            f"[Recovery-Redesign] === Phase 2: plan generation (attempt {redesign_iter + 1}/{max_partial_retries + 1}) ==="
        )

        iteration_context = base_investigation_summary
        if redesign_iter > 0:
            feedback = _extract_partial_feedback(last_submit_result)
            mf = feedback.get("missing_files") or []
            mh = feedback.get("missing_hunks") or []
            af = feedback.get("anchor_failures") or []
            feedback_block = [
                "<partial_feedback>",
                "Previous submit_recovery_plan returned PARTIAL.",
                "Carry forward prior accepted edits automatically (submit_recovery_plan accumulator).",
                "Your next plan must include ONLY missing/failed edits.",
                "Do NOT resubmit files/edits that were already accepted.",
            ]
            if mf:
                feedback_block.append("Missing files:")
                feedback_block.extend([f"- {x}" for x in mf[:20]])
            if mh:
                feedback_block.append("Missing hunks:")
                feedback_block.extend([f"- {x}" for x in mh[:30]])
            if af:
                feedback_block.append(
                    "Anchor failures to fix (copy old_string VERBATIM):"
                )
                feedback_block.extend([f"- {x}" for x in af[:30]])
            feedback_block.append("</partial_feedback>")

            # Inject the actual target file content for missing files so the LLM
            # can copy verbatim anchors. This directly fixes anchor verification
            # failures on targeted replan attempts.
            missing_file_parts: list[str] = []
            for rel in (mf or [])[:3]:  # cap at 3 files to keep prompt bounded
                abs_path = os.path.join(
                    toolkit.target_repo_path, _normalize_rel_path(rel)
                )
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                        fc = fh.read()
                    # Generous limit for targeted replan (1-2 files)
                    if len(fc) > 24000:
                        fc = fc[:18000] + "\n...<truncated>...\n" + fc[-5000:]
                    numbered = "\n".join(
                        f"{i + 1:5d}: {ln}" for i, ln in enumerate(fc.splitlines())
                    )
                    missing_file_parts.append(
                        f'<missing_target_file path="{rel}">\n{numbered}\n</missing_target_file>'
                    )
                except Exception:
                    pass
            if missing_file_parts:
                feedback_block.insert(
                    1,  # after the opening tag
                    "CRITICAL: The following target files are shown with line numbers. "
                    "Copy old_string VERBATIM from these files — do NOT use mainline `-` lines as anchors.",
                )
                feedback_block[-1:-1] = (
                    missing_file_parts  # insert before </partial_feedback>
                )

            iteration_context = (
                base_investigation_summary + "\n\n" + "\n".join(feedback_block)
            )

        plan_messages: list[Any] = [
            SystemMessage(content=_RECOVERY_PLAN_SYSTEM),
            HumanMessage(content=iteration_context),
        ]
        try:
            # Bind max_tokens explicitly to prevent truncated plan output on
            # targeted replans where the LLM may otherwise cut off mid-diff.
            plan_llm = llm.bind(max_tokens=8192) if hasattr(llm, "bind") else llm
            plan_response = await asyncio.wait_for(
                plan_llm.ainvoke(plan_messages),
                timeout=180.0,
            )
        except asyncio.TimeoutError:
            print("[Recovery-Redesign] plan generation timed out")
            return "llm_timeout", latest_plan_text, all_messages

        plan_text = str(getattr(plan_response, "content", "") or "")
        if isinstance(getattr(plan_response, "content", None), list):
            plan_text = "\n".join(
                str(p.get("text") or "") if isinstance(p, dict) else str(p)
                for p in plan_response.content
            )
        latest_plan_text = plan_text
        plan_messages.append(plan_response)
        all_messages.extend(plan_messages)
        print(f"[Recovery-Redesign] plan generated, {len(plan_text)} chars")

        if not plan_text.strip():
            return "empty_plan", latest_plan_text, all_messages

        print("[Recovery-Redesign] === Phase 3: format conversion (Python parser) ===")
        edit_ops, obligation_decisions, risk_notes = _parse_plan(plan_text)
        total_edits = sum(len(v) for v in edit_ops.values())
        print(
            f"[Recovery-Redesign] parsed {total_edits} edit(s) across {len(edit_ops)} file(s)"
        )
        if not edit_ops:
            print(
                "[Recovery-Redesign] plan parser found no edit_ops — treating as no-change"
            )
            return "formatter_no_tool_calls", latest_plan_text, all_messages

        try:
            submit_result = str(
                submit_tool.invoke(
                    {
                        "edit_ops": edit_ops,
                        "obligation_decisions": obligation_decisions,
                        "investigation_evidence": [
                            {
                                "kind": "note",
                                "details": (
                                    f"Parsed from plan text (redesign_attempt={redesign_iter + 1})"
                                ),
                            }
                        ],
                        "risk_notes": risk_notes,
                    }
                )
            )
        except Exception as exc:
            submit_result = f"ERROR executing submit_recovery_plan: {exc}"
        last_submit_result = submit_result
        print(f"[Recovery-Redesign] submit_recovery_plan → {submit_result[:4000]}")

        if submit_result.startswith("ERROR"):
            return "formatter_submit_rejected", latest_plan_text, all_messages

        if submit_result.startswith("PARTIAL"):
            if redesign_iter < max_partial_retries:
                print(
                    "[Recovery-Redesign] PARTIAL submission; continuing targeted replanning."
                )
                continue
            print(
                "[Recovery-Redesign] PARTIAL submission after retry budget exhausted."
            )
            # Promote whatever the accumulator has so partial progress is not lost.
            if toolkit._accumulated_plan:
                toolkit._submitted_plan = dict(toolkit._accumulated_plan)
                toolkit._submitted_decisions = list(
                    toolkit._accumulated_decisions.values()
                )
                toolkit._submitted_status = {"status": "ok"}
                print(
                    f"[Recovery-Redesign] promoted accumulator ({len(toolkit._accumulated_plan)} file(s)) "
                    "to submitted_plan so partial progress is not discarded."
                )
                return "partial_submitted", latest_plan_text, all_messages
            return "formatter_submit_rejected", latest_plan_text, all_messages

        return "submitted", latest_plan_text, all_messages

    return "formatter_submit_rejected", latest_plan_text, all_messages


def _build_per_hunk_guidance(
    mapped_target_context: dict | None,
    target_repo_path: str,
    patch_diff: str,
) -> str:
    """Build a rich block that, for EACH mapped hunk, shows:

    * The mainline change intent  (+/- lines from the patch hunk)
    * The ACTUAL target-file content at the structurally-mapped location

    This is the critical bridge between the mainline patch and the target:
    the LLM must understand that the code to replace in the TARGET may look
    completely different from the mainline '-' lines.  Without this context
    it keeps searching for symbols that don't exist in the target.
    """
    if not mapped_target_context:
        return ""

    # Parse raw hunks from the mainline patch (one list per file)
    raw_hunks_by_file: dict[str, list[str]] = {}
    try:
        from utils.patch_analyzer import PatchAnalyzer as _PA

        _raw = _PA().extract_raw_hunks(patch_diff)
        raw_hunks_by_file = {_normalize_rel_path(k): v for k, v in _raw.items()}
    except Exception:
        pass

    parts: list[str] = []

    for mainline_file, hunk_map in mapped_target_context.items():
        if not isinstance(hunk_map, dict):
            continue
        norm_mf = _normalize_rel_path(str(mainline_file or ""))
        file_raw_hunks: list[str] = raw_hunks_by_file.get(norm_mf, [])

        for hunk_id, mapping in hunk_map.items():
            if not isinstance(mapping, dict):
                continue
            target_file = _normalize_rel_path(
                str(mapping.get("target_file") or mainline_file)
            )
            mapped_line_raw = (
                mapping.get("target_line_start")
                or mapping.get("line_start")
                or mapping.get("line")
            )
            if not mapped_line_raw:
                continue
            try:
                mapped_line = int(mapped_line_raw)
            except Exception:
                continue

            # Resolve hunk index (handles "<import>", "hunk_1", "1", etc.)
            hunk_idx: int | None = None
            hunk_id_str = str(hunk_id)
            if hunk_id_str == "<import>" or "import" in hunk_id_str.lower():
                hunk_idx = 0
            else:
                import re as _re_hg

                _m = _re_hg.search(r"(\d+)", hunk_id_str)
                if _m:
                    hunk_idx = int(_m.group(1)) - 1  # 0-based

            raw_hunk = (
                file_raw_hunks[hunk_idx]
                if hunk_idx is not None and 0 <= hunk_idx < len(file_raw_hunks)
                else ""
            )

            # Extract removed / added lines from hunk
            removed_lines: list[str] = []
            added_lines: list[str] = []
            for ln in (raw_hunk or "").splitlines():
                if ln.startswith("---") or ln.startswith("+++") or ln.startswith("@@"):
                    continue
                if ln.startswith("-"):
                    removed_lines.append(ln[1:])
                elif ln.startswith("+"):
                    added_lines.append(ln[1:])

            # Nothing useful in this hunk (e.g. pure context)
            if not removed_lines and not added_lines:
                continue

            # Read target file around mapped location
            target_abs = os.path.join(target_repo_path, target_file)
            try:
                with open(target_abs, "r", encoding="utf-8", errors="replace") as _f:
                    _tlines = _f.readlines()
                radius = max(18, len(removed_lines) + 10)
                start = max(0, mapped_line - radius - 1)
                end = min(len(_tlines), mapped_line + radius)
                target_excerpt = "".join(
                    f"    {start + i + 1}: {ln}"
                    for i, ln in enumerate(_tlines[start:end])
                )
            except Exception:
                continue

            removed_display = "\n".join(f"  - {l.rstrip()}" for l in removed_lines[:12])
            added_display = "\n".join(f"  + {l.rstrip()}" for l in added_lines[:15])

            parts.append(
                f'<hunk_guidance id="{hunk_id}" target="{target_file}" at_line="{mapped_line}">\n'
                f"Mainline removes these lines (DO NOT use as old_string — "
                f"the target has DIFFERENT code here):\n"
                f"{removed_display}\n\n"
                f"Mainline adds:\n"
                f"{added_display}\n\n"
                f"ACTUAL TARGET FILE content at the mapped location "
                f"(lines {start + 1}–{end}) — use these lines for old_string:\n"
                f"```java\n{target_excerpt}```\n"
                f"Find the section in the target above that is semantically equivalent "
                f"to the mainline removed lines.  That section may look completely "
                f"different.  Use THOSE target lines as old_string and replace with "
                f"the adapted added lines.\n"
                f"</hunk_guidance>"
            )

    if not parts:
        return ""

    return (
        "<per_hunk_target_mappings>\n"
        "CRITICAL: For each hunk below the target code at the STRUCTURALLY MAPPED "
        "location is shown.  The target is an OLDER codebase — its code at each "
        "location may look COMPLETELY DIFFERENT from the mainline '-' lines.\n"
        "old_string MUST come from the 'ACTUAL TARGET FILE content' block inside "
        "each <hunk_guidance>, NOT from the 'Mainline removes' block.\n\n"
        + "\n\n".join(parts)
        + "\n</per_hunk_target_mappings>"
    )


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
    # Verify that the symbols being patched actually exist in the obligation files.
    # If methods have moved (e.g. hoisted into a superclass), remap the obligation
    # to the file where they actually live before feeding the agent.
    recovery_obligations = _verify_and_remap_obligations(
        state, recovery_obligations, target_repo_path
    )
    # Persist obligations immediately so submit_recovery_plan can enforce
    # obligation decisions against the same canonical set during this run.
    state["recovery_obligations"] = recovery_obligations
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

    force_full_prompt = _should_force_full_recovery_prompt(state)
    # Default to compact prompt (≤8k chars) to keep per-round LLM context bounded.
    # Full 35k prompt only when explicitly requested via env var or forced by category.
    # Always use the full system prompt — it contains the failure context,
    # recovery brief, and obligations that the LLM needs to act correctly
    # without spending rounds re-reading files.  The compact prompt strips
    # all of this and was the cause of wasted investigation rounds.
    # Opt out with RECOVERY_COMPACT_PROMPT=1 only if token budget is critical.
    use_full_prompt = not _env_truthy("RECOVERY_COMPACT_PROMPT")
    compact_mode = not use_full_prompt

    if use_full_prompt:
        print(
            "Recovery Agent: using full system prompt (always-on — "
            "provides failure context + recovery brief to reduce wasted rounds)."
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
    else:
        print(
            "Recovery Agent: using compact system prompt (default — keeps per-round context bounded)."
        )
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

    # Wire the live cache dict into the toolkit so apply_edit can refresh it
    # on each successful edit. This prevents subsequent read_file calls from
    # returning stale pre-edit content within the same tool loop.
    toolkit._preloaded_cache = preloaded_cache

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

    # Determine if all patch files are preloaded — if so, the agent can use
    # preloaded content directly, but read_file and investigation tools remain
    # available to explore connected files (e.g. superclasses, callers).
    all_patch_files_preloaded = bool(patch_files) and all(
        f in preloaded_cache for f in patch_files
    )
    if all_patch_files_preloaded:
        read_files_note = (
            "NOTE: All primary target files are already in <target_files> above — "
            "do NOT call read_file on them again, you already have the full content. "
            "Use grep to find specific lines/methods, get_class_context for structure overview, "
            "or read_file ONLY for files NOT listed in <target_files>."
        )
    else:
        read_files_note = (
            "Use grep or get_class_context first for targeted lookups. "
            "Use read_file only when you need full content of a file not yet shown."
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
        "   IMPORTANT — mapped locations: when a hunk has a mapped target location shown in\n"
        "   <hunk_snippets>, your edit for that hunk MUST anchor inside that snippet's line range.\n"
        "   Do NOT introduce a new top-level method as a substitute for modifying the mapped location.\n"
        "   If the mainline patch modifies code inside an existing method, edit that method in the target;\n"
        "   only add a new method when the mainline patch's '+' lines define one that is truly absent.\n"
        "4. Submit your COMPLETE plan in a SINGLE call to submit_recovery_plan:\n"
        "   {\n"
        '     "investigation_evidence": [{"kind":"...","details":"..."}],\n'
        '     "obligation_decisions": [{"obligation_id":"...","status":"edited|verified_no_change","reason":"...","evidence":["..."]}],\n'
        '     "edit_ops": {\n'
        '       "path/to/MainlineFile.java": [\n'
        '         {"hunk_index":0,"target_file":"exact/target/path.java","edit_type":"replace",\n'
        '          "old_string":"EXACT target text","new_string":"replacement","notes":"why"}\n'
        "       ]\n"
        "     },\n"
        '     "risk_notes": ["..."]\n'
        "   }\n" + coverage_section + "\n</task>"
    )

    if compact_mode:
        file_checklist = (
            "\n".join(f"  - {f}" for f in patch_files)
            if patch_files
            else "  (see recovery brief)"
        )
        # Build dev-aux exclusion note: files handled by the validator automatically.
        # Telling the LLM not to touch them prevents wasted rounds.
        _dev_aux_excl = ""
        _dev_patch = str(state.get("developer_patch_diff") or "")
        if _dev_patch:
            try:
                _dev_aux_files = [
                    _normalize_rel_path(m.group(2))
                    for m in __import__("re").finditer(
                        r"^diff --git a/([^\s]+) b/([^\s]+)",
                        _dev_patch,
                        __import__("re").M,
                    )
                    if _normalize_rel_path(m.group(2)) not in patch_files
                ]
                if _dev_aux_files:
                    _dev_aux_excl = (
                        "\n\n<dev_aux_files>\n"
                        "DO NOT call apply_edit or read_file on these files — "
                        "the validator applies them automatically:\n"
                        + "\n".join(f"  - {_f}" for _f in _dev_aux_files[:10])
                        + "\n</dev_aux_files>"
                    )
            except Exception:
                pass

        task_xml = (
            "<task>\n"
            "DIRECT-APPLY MODE:\n"
            "1. The preloaded <target_files> above contain the ACTUAL target code.\n"
            "   old_string anchors MUST be copied VERBATIM from those numbered lines —\n"
            "   NOT from the mainline patch context lines (the target is an OLDER codebase\n"
            "   and its constructors/signatures DIFFER from mainline).\n"
            "2. Use grep/get_class_context if a file is not in <target_files>.\n"
            "3. Apply edits with apply_edit(target_file, old_string, new_string, edit_type).\n"
            "   One edit at a time. If apply_edit FAILS, re-read the actual file content\n"
            "   and try again with a correct verbatim anchor.\n"
            "4. Call mark_no_change(target_file, reason) for files where no edit is needed.\n"
            "5. Call recovery_done(summary) once ALL required files are edited or marked.\n\n"
            "Required files:\n" + file_checklist + _dev_aux_excl + "\n</task>"
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
    recovery_plan_text = ""

    # ── Fetch dependency graph up-front (deterministic, before any LLM call) ─
    print("Recovery Agent: fetching dependency graph for patch files...")
    dep_graph_text = ""
    if patch_files:
        try:
            dep_result = toolkit.get_dependency_graph(
                patch_files, explore_neighbors=True
            )
            dep_graph_text = json.dumps(dep_result, ensure_ascii=False, indent=2)
        except Exception as _dge:
            dep_graph_text = f"dependency graph unavailable: {_dge}"
        print(f"Recovery Agent: dependency graph: {len(dep_graph_text)} chars")

    # ── Build preloaded context XML for the redesign ─────────────────────────
    preloaded_context_xml = (
        (
            "<preloaded_target_files>\n"
            "These are the ACTUAL TARGET files (older codebase). "
            "Lines are shown with numbers. Do NOT include line number prefixes in old_string anchors.\n\n"
            + "\n\n".join(preloaded_file_parts)
            + "\n</preloaded_target_files>"
        )
        if preloaded_file_parts
        else "<preloaded_target_files>(none)</preloaded_target_files>"
    )

    if per_hunk_parts:
        preloaded_context_xml += (
            "\n\n<hunk_snippets>\n"
            "Exact target code at each location found by Structural Locator — precise old_string sources.\n\n"
            + "\n\n".join(per_hunk_parts)
            + "\n</hunk_snippets>"
        )

    # ── PRIMARY: DIRECT-APPLY REACT LOOP ─────────────────────────────────────
    # Build initial HumanMessage that includes the preloaded target files and
    # the mainline patch so the LLM can copy old_string anchors directly from
    # the shown file content without extra read_file calls.
    da_initial_parts: list[str] = []
    if preloaded_file_parts:
        da_initial_parts.append(
            "<target_files>\n"
            "These are the ACTUAL TARGET repo files (older codebase, different from mainline).\n"
            "Lines are numbered. old_string anchors MUST be copied verbatim from here — "
            "do NOT use mainline patch `-` lines as anchors.\n\n"
            + "\n\n".join(preloaded_file_parts)
            + "\n</target_files>"
        )

    # Per-hunk guidance: shows mainline intent AND actual target code at each
    # mapped location.  This is essential when the target has structurally
    # different code from what the mainline patch removes (e.g. the target
    # has `failure = t;` where mainline has `countdownAndMaybeContinue(...)`).
    _phg = _build_per_hunk_guidance(
        mapped_target_context=mapped_target_context,
        target_repo_path=target_repo_path,
        patch_diff=patch_diff,
    )
    if _phg:
        da_initial_parts.append(_phg)
    elif per_hunk_parts:
        da_initial_parts.append(
            "<hunk_snippets>\n"
            "Exact target code at each location mapped by Structural Locator. "
            "Use these as precise old_string sources.\n\n"
            + "\n\n".join(per_hunk_parts)
            + "\n</hunk_snippets>"
        )

    da_initial_parts.append(
        f"<mainline_patch>\n{_truncate(patch_diff, 6000)}\n</mainline_patch>"
    )
    da_initial_parts.append(task_xml)

    da_initial_message = "\n\n".join(filter(None, da_initial_parts))
    da_messages: list[Any] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=da_initial_message),
    ]

    all_tools = toolkit.get_tools(include_submit=False)  # exclude submit_recovery_plan
    print("Recovery Agent: starting direct-apply loop (apply_edit + recovery_done)...")
    try:
        _complexity = str(state.get("patch_complexity") or "").upper()
        _n_patch_files = len(patch_files)
        _max_rounds = (
            18
            if (_complexity in {"STRUCTURAL", "REWRITE"} or _n_patch_files >= 3)
            else 12
        )
        direct_messages, direct_term = await _run_parallel_tool_loop(
            llm=llm,
            tools=all_tools,
            initial_messages=da_messages,
            preloaded_cache=preloaded_cache,
            max_investigation_rounds=_max_rounds,
            toolkit=toolkit,
        )
        final_messages = direct_messages
        term_reason = direct_term
        recovery_plan_text = (
            f"Direct-apply loop terminated: {direct_term}. "
            f"edits={len(toolkit._applied_edits)}, done={toolkit._recovery_done}"
        )
    except Exception as exc:
        if _is_content_filter_error(exc):
            stagnation_reason = "content_filter_exhausted"
            final_messages = []
            term_reason = "content_filter_exhausted"
            recovery_plan_text = ""
        else:
            raise

    print(f"Recovery Agent: direct-apply loop finished, reason={term_reason}")

    # ── DIRECT-APPLY SUCCESS PATH ─────────────────────────────────────────────
    # If recovery_done was signalled (coverage satisfied), the files are already
    # modified on disk. Route straight to validation (skip hunk_generator).
    if getattr(toolkit, "_recovery_done", False):
        applied_edits = list(toolkit._applied_edits)
        no_change_files = sorted(toolkit._direct_no_change_files)
        edited_files = sorted({e["target_file"] for e in applied_edits})
        print(
            f"Recovery Agent: direct-apply complete — {len(applied_edits)} edit(s) "
            f"across {len(edited_files)} file(s). Routing to validation."
        )
        # Token accounting
        agg = aggregate_usage_from_messages(final_messages)
        if agg.get("input_tokens") or agg.get("output_tokens"):
            add_usage(
                token_usage,
                int(agg.get("input_tokens", 0) or 0),
                int(agg.get("output_tokens", 0) or 0),
                "recovery_agent.direct_apply",
            )
        da_summary = (
            f"Recovery Agent (direct-apply): {len(applied_edits)} edit(s) applied "
            f"to {len(edited_files)} file(s)"
            + (
                f"; {len(no_change_files)} file(s) marked no_change"
                if no_change_files
                else ""
            )
            + ". Files modified on disk — routing to validation."
        )
        return {
            "messages": [HumanMessage(content=da_summary)],
            "recovery_applied_directly": True,
            "recovery_agent_status": "ok",
            "recovery_agent_summary": da_summary,
            "recovery_agent_mode": True,
            "recovery_brief": deterministic_recovery_brief,
            "recovery_obligations": recovery_obligations,
            "recovery_investigation": [],
            "recovery_decisions": [],
            "recovery_scope_files": recovery_scope_files,
            "recovery_strategy_history": recovery_strategy_history,
            "recovery_plan_text": recovery_plan_text,
            "recovery_plan_version": 1,
            "recovery_risk_notes": [],
            "hunk_generation_plan": {},
            "last_plan_signature": "",
            "validation_repeated_plan_detected": False,
            "validation_failed_stage": state.get("validation_failed_stage"),
            "token_usage": token_usage,
        }

    # ── PARTIAL DIRECT-APPLY: some edits on disk but recovery_done not reached ─
    # If the LLM applied some edits without calling recovery_done, route to
    # validation anyway — let it attempt compilation; on failure the recovery
    # agent gets another shot (attempt 2) to complete the remaining edits.
    if getattr(toolkit, "_applied_edits", None):
        applied_edits = list(toolkit._applied_edits)
        edited_files = sorted({e["target_file"] for e in applied_edits})
        print(
            f"Recovery Agent: direct-apply partial — {len(applied_edits)} edit(s), "
            f"recovery_done not reached (reason={term_reason}). "
            "Routing to validation with partial result."
        )
        agg = aggregate_usage_from_messages(final_messages)
        if agg.get("input_tokens") or agg.get("output_tokens"):
            add_usage(
                token_usage,
                int(agg.get("input_tokens", 0) or 0),
                int(agg.get("output_tokens", 0) or 0),
                "recovery_agent.direct_apply",
            )
        da_summary = (
            f"Recovery Agent (partial direct-apply): {len(applied_edits)} edit(s) applied "
            f"to {len(edited_files)} file(s); recovery_done not reached (reason={term_reason})."
        )
        return {
            "messages": [HumanMessage(content=da_summary)],
            "recovery_applied_directly": True,
            "recovery_agent_status": "ok",
            "recovery_agent_summary": da_summary,
            "recovery_agent_mode": True,
            "recovery_brief": deterministic_recovery_brief,
            "recovery_obligations": recovery_obligations,
            "recovery_investigation": [],
            "recovery_decisions": [],
            "recovery_scope_files": recovery_scope_files,
            "recovery_strategy_history": recovery_strategy_history,
            "recovery_plan_text": recovery_plan_text,
            "recovery_plan_version": 1,
            "recovery_risk_notes": [],
            "hunk_generation_plan": {},
            "last_plan_signature": "",
            "validation_repeated_plan_detected": False,
            "validation_failed_stage": state.get("validation_failed_stage"),
            "token_usage": token_usage,
        }

    # ── FALLBACK: 3-PHASE REDESIGN ────────────────────────────────────────────
    # Direct-apply loop exited without applying any edits. Fall back to the
    # 3-phase (investigate → plan → format) approach.
    print(
        f"Recovery Agent: direct-apply loop ended with no edits (reason={term_reason}). "
        "Falling back to 3-phase redesign..."
    )
    # Reset term_reason and recovery_plan_text for the redesign path
    term_reason = "not_started"
    recovery_plan_text = ""
    try:
        term_reason, recovery_plan_text, final_messages = await _run_recovery_redesign(
            llm=llm,
            toolkit=toolkit,
            preloaded_context_xml=preloaded_context_xml,
            patch_diff=patch_diff,
            recovery_brief_json=recovery_brief_json,
            recovery_obligations_json=recovery_obligations_json,
            dependency_graph_text=dep_graph_text,
            max_investigation_rounds=2,
        )
    except Exception as exc:
        if _is_content_filter_error(exc):
            stagnation_reason = "content_filter_exhausted"
            final_messages = []
            term_reason = "content_filter_exhausted"
        else:
            raise

    # ── Save the plan text as an artifact for reference ───────────────────────
    if recovery_plan_text:
        try:
            import pathlib

            _eval_dir = pathlib.Path(target_repo_path).parent / "recovery_plans"
            _eval_dir.mkdir(parents=True, exist_ok=True)
            _commit = str(state.get("mainline_commit") or "unknown")[:12]
            _plan_file = _eval_dir / f"recovery_plan_{_commit}.md"
            _plan_file.write_text(recovery_plan_text, encoding="utf-8")
            print(f"[Recovery] plan artifact saved: {_plan_file}")
        except Exception as _save_exc:
            print(f"[Recovery] could not save plan artifact: {_save_exc}")

    print(f"Recovery Agent: 3-phase redesign finished, reason={term_reason}")

    # Token accounting
    agg = aggregate_usage_from_messages(final_messages)
    if agg.get("input_tokens") or agg.get("output_tokens"):
        add_usage(
            token_usage,
            int(agg.get("input_tokens", 0) or 0),
            int(agg.get("output_tokens", 0) or 0),
            "recovery_agent.redesign",
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
        elif term_reason == "partial_submitted":
            pass  # Accumulator promoted to submitted_plan; not a stagnation.
        elif term_reason in (
            "max_rounds_exceeded",
            "no_tool_calls",
            "formatter_no_tool_calls",
            "formatter_wrong_tool",
            "formatter_submit_rejected",
            "formatter_missing_submit_tool",
            "empty_plan",
        ):
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
        # Explicitly clear direct-apply flag — this path uses hunk_generator, not on-disk edits.
        "recovery_applied_directly": False,
        "recovery_brief": deterministic_recovery_brief,
        "recovery_obligations": recovery_obligations,
        "recovery_investigation": submitted_investigation,
        "recovery_decisions": submitted_decisions,
        "recovery_scope_files": recovery_scope_files,
        "recovery_strategy_history": recovery_strategy_history,
        "recovery_plan_text": recovery_plan_text,  # natural-language plan artifact
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
