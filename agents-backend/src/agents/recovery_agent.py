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

import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from state import AgentState
from utils.llm_provider import get_llm
from utils.plan_validator import consolidate_plan_entries_java
from utils.token_counter import add_usage, aggregate_usage_from_messages


_RECOVERY_SYSTEM = """<context>
This is a technical software development environment focused on code adaptation and backporting changes between codebases.
</context>

<role>
You are an Adaptation Assistant — a senior software engineer specializing in adapting patches from a newer mainline codebase to an older target repository.
Your goal is to produce a correct, minimal adaptation plan and submit it using the submit_recovery_plan tool.
</role>

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
2. Analyze the actual target code provided in <target_files>.
3. Identify differences (e.g., constructor signatures, field order, imports, error handling).
4. Create minimal, semantically correct edits that achieve the same goal in the target's structure.
5. Submit the plan via the submit_recovery_plan tool.
</objectives>

<rules>
1. Base all edits on the target code visible in <target_files> or retrieved via tools.
2. Prefer small, precise edits using exact matching anchors from the target.
3. Avoid no-op edits, comment-only changes, or unnecessary modifications.
4. Submit the plan only via the submit_recovery_plan tool — do not output raw JSON outside the tool.
</rules>

<analysis_steps>
A) Summarize the required adaptation and why it is needed.
B) Extract the main intent from the <mainline_patch>.
C) Examine <target_files> for actual signatures, declarations, and structure.
D) Compare mainline intent vs. target's current code.
E) Build adapted edits: use old_string from target, new_string reflecting the intended change.
F) Submit the plan.
</analysis_steps>

<example>
If the mainline patch adds parameters to a constructor that looks different in the target:
- WRONG: copy old_string from mainline patch context lines.
- CORRECT: copy old_string from the target's actual constructor in <target_files>, then adapt the new_string accordingly.
</example>

<submission_rules>
- The plan must include at least one valid edit for every file listed in <agent_eligible_files> (test files are out of scope).
- Prioritize files in <retry_scope>.
- submit_recovery_plan accepts a dict keyed by mainline file path → list of edit operations.
</submission_rules>

<output_contract>
Each operation in the plan:
{{
  "hunk_index": int,
  "target_file": str,
  "edit_type": "replace" | "insert_before" | "insert_after" | "delete",
  "old_string": str,           // must exist verbatim in the target file
  "new_string": str,
  "verified": false,
  "verification_result": "ready_to_apply",
  "notes": str
}}
</output_contract>

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

def _extract_lines_around(repo_path: str, rel_path: str, center: int, radius: int = 20) -> str:
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
        self, state: AgentState, target_repo_path: str, mainline_repo_path: str
    ):
        self.state = state
        self.target_repo_path = target_repo_path
        self.mainline_repo_path = mainline_repo_path
        self._submitted_plan: dict[str, list[dict[str, Any]]] = {}
        self._submitted_status: dict[str, Any] | None = None
        self._todo: list[dict[str, str]] = []
        self._todo_counter = 0

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
            res = subprocess.run(
                ["rg", "-n", "--no-heading", "-g", inc, pat, "."],
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
    def submit_recovery_plan(self, plan: dict[str, Any]) -> str:
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

        if "plan" in plan and isinstance(plan.get("plan"), dict):
            plan = plan.get("plan") or {}
        if not isinstance(plan, dict) or not plan:
            return "ERROR: plan must be an object keyed by mainline file."

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

        for mainline_file, ops in plan.items():
            if not isinstance(ops, list):
                continue
            entries: list[dict[str, Any]] = []
            for idx, op in enumerate(ops):
                if not isinstance(op, dict):
                    continue
                edit_type = str(op.get("edit_type") or "replace").strip().lower()
                if edit_type not in allowed_edit_types:
                    continue

                old_string = str(op.get("old_string") or "")
                new_string = str(op.get("new_string") or "")
                if not old_string:
                    continue
                if edit_type != "delete" and not new_string:
                    continue

                if self._contains_only_comment_or_whitespace_change(
                    old_string, new_string
                ):
                    filtered_low_value += 1
                    continue

                target_file = _normalize_rel_path(str(op.get("target_file") or ""))
                if target_file:
                    touched_files.add(target_file)

                # HARD ANCHOR VERIFICATION: the old_string must exist verbatim in
                # the on-disk target file. This is the contract that keeps the LLM
                # from copying mainline `-` lines as anchors.
                tf_content = _load_target(target_file) if target_file else None
                if tf_content is not None and tf_content != "":
                    if old_string not in tf_content:
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

            if not entries:
                continue
            cleaned[_normalize_rel_path(str(mainline_file))] = entries
            op_count += len(entries)
        # If any anchors failed verification, reject the ENTIRE submission so the
        # agent must resubmit with correct anchors. Otherwise the plan proceeds
        # with broken anchors that file_editor cannot apply.
        if anchor_errors:
            # Do not store the plan — force a retry.
            self._submitted_plan = {}
            err_lines = "\n  - ".join(anchor_errors[:10])
            return (
                "ERROR: plan rejected — anchor verification failed. "
                "Each old_string MUST exist VERBATIM in the on-disk target file. "
                "Stop copying mainline `-` lines; copy anchors from the PRELOADED "
                "TARGET FILE CONTENTS shown in the system prompt (or call "
                "read_file on the target). Failures:\n  - " + err_lines
            )

        if not cleaned:
            if filtered_low_value > 0:
                return (
                    "ERROR: plan had only low-value/no-op edits "
                    f"(filtered={filtered_low_value})."
                )
            return "ERROR: plan had no valid operation entries."

        # Coverage gate: the plan must touch EVERY agent-eligible file.
        # This is the primary defense against the recovery agent silently
        # narrowing a multi-file problem to a single-file plan (which is
        # exactly how crate_30abc0f9 slipped through with imports-only).
        agent_eligible = self._agent_eligible_files()
        if agent_eligible:
            missing = agent_eligible - touched_files
            if missing:
                self._submitted_plan = {}
                return (
                    "ERROR: plan does not cover all agent-eligible files. "
                    "The recovery plan MUST contain at least one valid edit "
                    "for EVERY file listed in <agent_eligible_files>. "
                    f"missing={sorted(missing)} touched={sorted(touched_files)}"
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

        self._submitted_plan = cleaned
        self._submitted_status = {"status": "ok"}
        return (
            f"SUCCESS: recovery plan submitted ({len(cleaned)} files, {op_count} ops)."
        )

    def get_submitted_plan(self) -> dict[str, list[dict[str, Any]]]:
        return dict(self._submitted_plan or {})

    def get_submitted_status(self) -> dict[str, Any] | None:
        return (
            dict(self._submitted_status)
            if isinstance(self._submitted_status, dict)
            else None
        )

    def get_tools(self, include_submit: bool = True) -> list[StructuredTool]:
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
                coroutine=self.agenttool,
                name="agenttool",
                description="Delegate bounded exploration to a subagent and return evidence JSON.",
            ),
        ]
        if include_submit:
            tools.append(
                StructuredTool.from_function(
                    func=self.submit_recovery_plan,
                    name="submit_recovery_plan",
                    description="Submit final recovery plan for File Editor.",
                )
            )
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

    toolkit = RecoveryPlanToolkit(state, target_repo_path, mainline_repo_path)

    # Build rich failure context including mainline patch and what was tried
    patch_diff = str(state.get("patch_diff") or "")
    validation_error = str(state.get("validation_error_context") or "")
    adapted_edits = state.get("adapted_file_edits") or []

    # Construct failure context with mainline patch and dumb run attempt
    failure_context_parts = []
    failure_context_parts.append("=== MAINLINE PATCH ===")
    failure_context_parts.append(_truncate(patch_diff, 4000))
    failure_context_parts.append("\n=== DUMB RUN FAILURE ===")
    failure_context_parts.append(_truncate(validation_error, 4000))
    if adapted_edits:
        failure_context_parts.append(f"\n=== DUMB RUN EDITS ATTEMPTED ({len(adapted_edits)} edits) ===")
        for edit in adapted_edits[:5]:  # Show first 5 edits attempted
            failure_context_parts.append(f"File: {edit.get('target_file')}, Type: {edit.get('edit_type')}, Applied: {edit.get('applied')}")

    failure_context = _truncate("\n".join(failure_context_parts), 12000)

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
    attempt_artifacts = _truncate(_summarize_attempt_artifacts(state), 12000)

    # Full agent-eligible file list — coverage contract for submit_recovery_plan.
    agent_eligible_list = sorted(toolkit._agent_eligible_files())
    agent_eligible_files_str = (
        "\n".join(f"- {f}" for f in agent_eligible_list)
        if agent_eligible_list
        else "(unknown — patch_diff unavailable)"
    )

    system_prompt = _RECOVERY_SYSTEM.format(
        failure_context=failure_context,
        agent_eligible_files=agent_eligible_files_str,
        retry_scope=retry_scope,
        existing_plan=existing_plan,
        attempt_artifacts=attempt_artifacts,
    )

    llm = get_llm(temperature=0.0)
    agent = create_react_agent(llm, tools=toolkit.get_tools(), prompt=system_prompt)

    max_iters = 8
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
    retry_files_list = [_normalize_rel_path(f) for f in (state.get("validation_retry_files") or [])]
    files_to_preload = list(dict.fromkeys(patch_files + retry_files_list))[:6]

    preloaded_file_parts: list[str] = []
    for rel in files_to_preload:
        abs_path = os.path.join(target_repo_path, rel)
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception as e:
            content = f"<<unreadable: {e}>>"
        # Cap per-file to keep prompt bounded; large files get head+tail slice.
        if len(content) > 16000:
            content = content[:12000] + "\n...<truncated>...\n" + content[-3000:]
        numbered = "\n".join(
            f"{i + 1:5d}: {ln}" for i, ln in enumerate(content.splitlines())
        )
        preloaded_file_parts.append(
            f"<file path=\"{rel}\">\n{numbered}\n</file>"
        )

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
            line_num = mapping.get("target_line_start") or mapping.get("line_start") or mapping.get("line")
            if not line_num:
                continue
            snippet = _extract_lines_around(target_repo_path, t_file, int(line_num), radius=20)
            if snippet:
                per_hunk_parts.append(
                    f"<hunk id=\"{hunk_id}\" file=\"{t_file}\" mapped_line=\"{line_num}\">\n"
                    f"{snippet}\n"
                    f"</hunk>"
                )

    # ── Build initial HumanMessage — preloaded content FIRST ────────────────
    # Structure: <target_files> → <hunk_snippets> → <task>
    # The agent sees the actual target code before any instructions, so it
    # cannot mistake mainline context lines for target code.
    target_files_xml = (
        "<target_files>\n"
        "These are the ACTUAL files in the TARGET REPO — an older codebase, DIFFERENT from mainline.\n"
        "Copy your old_string anchors exclusively from these files.\n\n"
        + "\n\n".join(preloaded_file_parts)
        + "\n</target_files>"
    ) if preloaded_file_parts else ""

    hunk_snippets_xml = (
        "<hunk_snippets>\n"
        "Exact target code at each location found by Structural Locator.\n"
        "Use these as precise old_string sources — they are already extracted for you.\n\n"
        + "\n\n".join(per_hunk_parts)
        + "\n</hunk_snippets>"
    ) if per_hunk_parts else ""

    task_xml = (
        "<task>\n"
        "WORKFLOW:\n"
        "1. Read <target_files> and <hunk_snippets> above — those are your anchor sources.\n"
        "   Do NOT call read_file on the files listed there; you already have their contents.\n"
        "2. Read <mainline_patch> in the system prompt to understand the INTENT of the change.\n"
        "3. For each required edit, find the corresponding code in <target_files> / <hunk_snippets>\n"
        "   and write old_string = EXACT text from those sections.\n"
        "4. Submit via submit_recovery_plan with this structure:\n"
        "   {\n"
        '     "path/to/MainlineFile.java": [\n'
        "       {\n"
        '         "hunk_index": 0,\n'
        '         "target_file": "exact/target/path.java",\n'
        '         "edit_type": "replace",\n'
        '         "old_string": "EXACT text from <target_files> — not from mainline",\n'
        '         "new_string": "adapted replacement",\n'
        '         "verified": false,\n'
        '         "verification_result": "ready_to_apply",\n'
        '         "notes": "reason"\n'
        "       }\n"
        "     ]\n"
        "   }\n"
        "</task>"
    )

    initial_message = "\n\n".join(filter(None, [target_files_xml, hunk_snippets_xml, task_xml]))
    messages: list[Any] = [HumanMessage(content=initial_message)]
    seen_plan_sig = ""
    stagnation_reason = ""
    tool_call_history: list[tuple[str, Any]] = []

    for iteration in range(1, max_iters + 1):
        print(f"Recovery loop iteration {iteration}")
        response = await agent.ainvoke(
            {"messages": messages}, config={"recursion_limit": 60}
        )
        chunk_msgs = (response or {}).get("messages") or []

        agg = aggregate_usage_from_messages(chunk_msgs)
        if agg.get("input_tokens") or agg.get("output_tokens"):
            add_usage(
                token_usage,
                int(agg.get("input_tokens", 0) or 0),
                int(agg.get("output_tokens", 0) or 0),
                f"recovery_agent.loop.iter_{iteration}",
            )

        # Collect tool calls for stagnation detection.
        calls = _extract_tool_calls(chunk_msgs)
        if calls:
            simple_calls = [(nm, args) for (nm, args, _cid) in calls]
            tool_call_history.extend(simple_calls)
            if len(tool_call_history) > 64:
                tool_call_history = tool_call_history[-64:]

            is_stuck, reason = _detect_stagnation(simple_calls, limit=4)
            if not is_stuck and len(tool_call_history) >= 4:
                is_stuck, reason = _detect_stagnation(tool_call_history[-16:], limit=4)
            if is_stuck:
                stagnation_reason = reason
                print(f"Recovery Agent: stagnation detected: {reason}")
                break

        # Check whether plan has been submitted.
        submitted = toolkit.get_submitted_plan()
        submitted_status = toolkit.get_submitted_status() or {}
        if submitted:
            plan_sig = hashlib.sha256(
                json.dumps(submitted, sort_keys=True).encode("utf-8")
            ).hexdigest()
            if seen_plan_sig and seen_plan_sig == plan_sig:
                stagnation_reason = "repeated_plan"
                break
            seen_plan_sig = plan_sig
            break

        if str(submitted_status.get("status") or "") == "no_fix_found":
            stagnation_reason = "no_fix_found: " + str(
                submitted_status.get("reason") or "unspecified"
            )
            break

        # Continue loop with accumulated messages.
        messages = _sanitize_messages_for_reinvoke(list(chunk_msgs))
        messages.append(
            HumanMessage(
                content=(
                    "<reminder>Target files are in <target_files> of your first message — "
                    "do NOT call read_file on those files again. Produce the adapted plan "
                    "now using old_strings from <target_files>/<hunk_snippets> and submit "
                    "via submit_recovery_plan. Your plan MUST include at least one edit "
                    "for EVERY file listed in <agent_eligible_files> or it will be "
                    "rejected.</reminder>"
                )
            )
        )

    raw_plan = toolkit.get_submitted_plan()
    # NOTE: Do NOT fall back to scraping plans from raw LLM text. Any scraped
    # plan bypasses the on-disk anchor verification in submit_recovery_plan,
    # which is exactly how broken plans (mainline `-` lines used as anchors)
    # were reaching file_editor. If the agent didn't call submit_recovery_plan,
    # that is a failure and we return an empty plan.

    normalized_plan = _normalize_recovery_plan(raw_plan, state, target_repo_path)

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

    return {
        "messages": [HumanMessage(content=summary)],
        "hunk_generation_plan": normalized_plan,
        "last_plan_signature": plan_sig,
        "validation_repeated_plan_detected": repeated,
        "recovery_agent_mode": True,
        "recovery_agent_status": (
            "no_fix_found" if stagnation_reason.startswith("no_fix_found:") else "ok"
        ),
        "recovery_agent_summary": summary,
        "validation_failed_stage": (
            "recovery_no_fix_found"
            if stagnation_reason.startswith("no_fix_found:")
            else state.get("validation_failed_stage")
        ),
        "token_usage": token_usage,
    }
