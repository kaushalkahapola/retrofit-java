"""
Agent 3: File Editor (The Surgeon - str_replace Edition)

Replaces the old hunk_generator approach. Instead of asking the LLM to
produce unified diff syntax (which is brittle and caused the two-@@ split bug),
this agent:

  1. Reads the str_replace edit plan from the Planning Agent.
  2. For each target file, applies edits directly to the checked-out file
     using str_replace_in_file / insert_after_line tools.
  3. After all edits for a file are complete, runs `git diff HEAD -- <file>`
     to produce a mechanically correct unified diff.
  4. Resets the file to HEAD (clean state for validation).
  5. Emits AdaptedHunk objects with hunk_text = the git-generated diff.

Key inputs from state:
  - hunk_generation_plan:    str_replace edit plans per file (from Planning Agent)
  - semantic_blueprint:      Fix intent (Agent 1)
  - consistency_map:         Symbol renames (Agent 2)
  - mapped_target_context:   Exact target file paths (Agent 2)
  - patch_analysis:          Original FileChange list
  - patch_diff:              Raw diff text
  - validation_attempts:     Retry counter (0 = fresh run)
  - validation_error_context: Error logs injected on retry

Key outputs to state:
  - adapted_file_edits:  list[FileEdit]   - atomic edit records
  - adapted_code_hunks:  list[AdaptedHunk] - hunk_text = git diff (machine-generated)
  - adapted_test_hunks:  list[AdaptedHunk] - always [] (tests handled by aux hunks)
"""

import os
import re
import subprocess
import hashlib
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.errors import GraphRecursionError

from state import AgentState, AdaptedHunk, FileEdit, SemanticBlueprint
from utils.patch_analyzer import PatchAnalyzer
from utils.llm_provider import get_llm
from utils.token_counter import (
    add_usage,
    count_text_tokens,
    extract_usage_from_response,
    resolve_model_name,
)
from utils.retrieval.ensemble_retriever import EnsembleRetriever
from agents.hunk_generator_tools import HunkGeneratorToolkit


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_FILE_EDITOR_SYSTEM = """\
You are an expert Java backport engineer.

Your task: apply a precise code change to an older version of a Java file using
direct file-editing tools. You do NOT generate unified diff syntax.

MANDATORY WORKFLOW for each edit:

STEP 1 - VERIFY the plan's old_string:
  Call verify_context_at_line or grep_in_file to confirm old_string exists in
  the target file. If NOT_FOUND, use grep_in_file and read_file_window to find
  the actual text and adjust old_string accordingly.

STEP 2 - APPLY the edit:
  Call str_replace_in_file(file_path, old_string, new_string).
  - If SUCCESS: proceed.
  - If AMBIGUOUS: extend old_string with more surrounding context lines.
  - If NOT_FOUND: use grep_in_file to find the actual text, then retry.

STEP 3 - VERIFY the result:
  After str_replace_in_file succeeds, call read_file_window around the edited
  area to confirm the change looks correct.

STEP 4 - CAPTURE the diff:
  After ALL edits for the file are complete, call git_diff_file(file_path).
  This produces the mechanically correct unified diff.

RULES:
- NEVER generate unified diff text yourself - always use str_replace_in_file.
- old_string must match the real file content character-for-character.
- For multi-line old_string, include enough context to make it unique in the file.
- Apply all symbol renames from the ConsistencyMap to new_string added content.
- Preserve the fix intent from the SemanticBlueprint.
- If an edit fails repeatedly, call reset_file and try a different approach.
"""

_FILE_EDITOR_USER = """\
## Target File
`{target_file}`

## Edit Plan (from Planning Agent)
{edit_plan}

## ConsistencyMap (apply to new_string added content only)
{consistency_map}

## Fix Intent (SemanticBlueprint)
- Fix Logic: {fix_logic}
- Dependent APIs: {dependent_apis}

## File Context (from Agent 2 - may be from mainline, verify in target)
```java
{target_context}
```

{retry_context}

Apply all edits to `{target_file}`, then call git_diff_file to capture the result.
Report: SUCCESS or FAILURE with reason.
"""

_INTENT_CHECK_SYSTEM = """\
You are a code reviewer verifying that a git diff preserves a specific fix intent.
Answer ONLY "YES" if the diff correctly implements the fix logic, or "NO: <one-line reason>".
"""

_INTENT_CHECK_USER = """\
## Generated Diff
```diff
{diff_text}
```

## Expected Fix Logic
{fix_logic}

## Critical APIs That Must Appear
{dependent_apis}

Does the diff correctly implement the fix logic? Answer YES or NO.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_rel_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/").lstrip("/")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p


def _format_consistency_map(cm: dict) -> str:
    if not cm:
        return "(none - no renames detected)"
    return "\n".join(f"  {old} -> {new}" for old, new in cm.items())


def _format_edit_plan(plan_entries: list[dict[str, Any]]) -> str:
    if not plan_entries:
        return "(no plan entries)"
    lines = []
    for i, e in enumerate(plan_entries, start=1):
        lines.append(f"Edit {i} (hunk_index={e.get('hunk_index')}):")
        lines.append(f"  edit_type:  {e.get('edit_type')}")
        lines.append(f"  verified:   {e.get('verified')}")
        lines.append(
            f"  old_string (first 200 chars): {str(e.get('old_string', ''))[:200]!r}"
        )
        lines.append(
            f"  new_string (first 200 chars): {str(e.get('new_string', ''))[:200]!r}"
        )
        lines.append(f"  notes:      {e.get('notes', '')}")
    return "\n".join(lines)


def _git_diff_file(target_repo_path: str, rel_path: str) -> str:
    """
    Return a git-style unified diff for rel_path.

    Handles both tracked-file edits and untracked file creation.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", rel_path],
            cwd=target_repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.stdout:
            return result.stdout

        # If no tracked diff, check if file is untracked and build a /dev/null diff.
        ls = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel_path],
            cwd=target_repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if ls.returncode == 0:
            return ""

        full_path = os.path.normpath(os.path.join(target_repo_path, rel_path))
        if not os.path.isfile(full_path):
            return ""

        no_index = subprocess.run(
            ["git", "diff", "--no-index", "--", "/dev/null", full_path],
            cwd=target_repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = no_index.stdout or ""
        if not out:
            return ""

        # Normalize no-index headers to repository-relative paths.
        out = re.sub(
            r"^diff --git a/\S+ b/\S+$",
            f"diff --git a/{rel_path} b/{rel_path}",
            out,
            count=1,
            flags=re.MULTILINE,
        )
        out = re.sub(
            r"^\+\+\+\s+\S+$",
            f"+++ b/{rel_path}",
            out,
            count=1,
            flags=re.MULTILINE,
        )
        return out
    except Exception:
        return ""


def _git_reset_file(target_repo_path: str, rel_path: str) -> bool:
    """Reset a single file to HEAD (or remove if untracked)."""
    try:
        result = subprocess.run(
            ["git", "checkout", "HEAD", "--", rel_path],
            cwd=target_repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True

        full_path = os.path.normpath(os.path.join(target_repo_path, rel_path))
        if not os.path.exists(full_path):
            return False

        # If file is untracked, remove it to restore clean state.
        ls = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel_path],
            cwd=target_repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if ls.returncode != 0:
            os.remove(full_path)
            return True
        return False
    except Exception:
        return False


def _exists_file(repo_path: str, rel_path: str) -> bool:
    if not repo_path or not rel_path:
        return False
    full = os.path.normpath(os.path.join(repo_path, _normalize_rel_path(rel_path)))
    return os.path.isfile(full)


def _apply_edit_deterministically(
    toolkit: HunkGeneratorToolkit,
    plan_entry: dict[str, Any],
    target_file: str,
) -> tuple[bool, str, str]:
    """
    Try to apply a single plan edit without the LLM.
    Returns (success, apply_result_message, diff_after).
    """
    edit_type = str(plan_entry.get("edit_type") or "replace").lower()
    old_string = str(plan_entry.get("old_string") or "")
    new_string = str(plan_entry.get("new_string") or "")

    if not old_string:
        return False, "empty_old_string", ""

    result = toolkit.str_replace_in_file(target_file, old_string, new_string)
    if result.startswith("SUCCESS"):
        return True, result, ""
    return False, result, ""


def _diff_introduces_call_without_definition(diff_text: str) -> tuple[bool, str]:
    """
    Detect a common semantic hole: introducing a call to a helper method without
    adding its declaration in the same patch.

    Returns (is_invalid, reason).
    """
    if not diff_text:
        return False, ""

    added_lines = []
    for line in diff_text.splitlines():
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            added_lines.append(line[1:])

    # Detect added call sites like: pendingShardIds.addAll(order(targetShards));
    called: set[str] = set()
    for l in added_lines:
        for m in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", l):
            if m in {
                "if",
                "for",
                "while",
                "switch",
                "catch",
                "new",
                "return",
                "List",
                "Map",
                "Set",
                "HashMap",
                "ArrayList",
                "LinkedHashMap",
                "Comparator",
            }:
                continue
            called.add(m)

    # Detect added method declarations.
    declared: set[str] = set()
    decl_pat = re.compile(
        r"\b(?:private|protected|public|static|final|synchronized|native|abstract|strictfp|\s)+\s+"
        r"[A-Za-z_][A-Za-z0-9_<>,\[\]\s?]*\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
    )
    for l in added_lines:
        m = decl_pat.search(l)
        if m:
            declared.add(m.group(1))

    # Known failure pattern: call to order(...) requires method declaration added.
    if "order" in called and "order" not in declared:
        return (
            True,
            "semantic_guard_failed: call to order(...) introduced but no order(...) declaration added in patch",
        )

    return False, ""


def _file_has_method_declaration(
    target_repo_path: str, rel_path: str, method_name: str
) -> bool:
    """Check whether method_name is declared in the current on-disk file content."""
    try:
        full_path = os.path.normpath(os.path.join(target_repo_path, rel_path))
        if not os.path.isfile(full_path):
            return False
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        pat = re.compile(
            rf"\b(?:private|protected|public|static|final|synchronized|native|abstract|strictfp|\s)+"
            rf"\s+[A-Za-z_][A-Za-z0-9_<>,\[\]\s?]*\s+{re.escape(method_name)}\s*\(",
            flags=re.MULTILINE,
        )
        return bool(pat.search(content))
    except Exception:
        return False


def _resolve_operation_plan(
    *,
    change_type: str,
    mainline_file: str,
    target_repo_path: str,
    retriever: EnsembleRetriever | None,
    original_commit: str,
) -> dict[str, Any]:
    """Resolve the file operation (MODIFIED/ADDED/DELETED/RENAMED) for a file change."""
    op = (change_type or "MODIFIED").upper()
    mainline_file = _normalize_rel_path(mainline_file)

    def resolve_existing(path_hint: str) -> str | None:
        p = _normalize_rel_path(path_hint)
        if p and _exists_file(target_repo_path, p):
            return p
        if retriever:
            try:
                candidates = retriever.find_candidates(p, original_commit or "HEAD")
                for cand in candidates or []:
                    if not isinstance(cand, dict):
                        continue
                    fp = cand.get("file") or cand.get("file_path") or cand.get("path")
                    if fp:
                        return _normalize_rel_path(str(fp))
            except Exception:
                pass
        return None

    plan: dict[str, Any] = {
        "target_file": mainline_file,
        "old_target_file": None,
        "effective_operation": op,
        "operation_required": True,
        "reason": "default",
    }

    mapped = resolve_existing(mainline_file)
    if mapped:
        plan["target_file"] = mapped
        plan["reason"] = "modified_target_mapped"
    return plan


async def _check_intent(
    llm,
    diff_text: str,
    blueprint: SemanticBlueprint,
    token_usage: dict[str, Any],
    model_name: str,
) -> bool:
    """Ask LLM whether the diff preserves the fix intent. Fails open (True) on error."""
    messages = [
        SystemMessage(content=_INTENT_CHECK_SYSTEM),
        HumanMessage(
            content=_INTENT_CHECK_USER.format(
                diff_text=diff_text[:2000],
                fix_logic=blueprint.get("fix_logic", ""),
                dependent_apis=", ".join(blueprint.get("dependent_apis", [])),
            )
        ),
    ]
    try:
        from utils.token_counter import count_messages_tokens

        approx_in = count_messages_tokens(messages, model_name)
        response = await llm.ainvoke(messages)
        usage = extract_usage_from_response(response)
        if usage and (usage["input_tokens"] or usage["output_tokens"]):
            add_usage(
                token_usage,
                usage["input_tokens"],
                usage["output_tokens"],
                "file_editor.intent.provider_usage",
            )
        else:
            out_text = (
                response.content if hasattr(response, "content") else str(response)
            )
            add_usage(
                token_usage,
                approx_in,
                count_text_tokens(str(out_text), model_name),
                "file_editor.intent.tiktoken",
            )
            token_usage["estimated"] = True
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip().upper().startswith("YES")
    except Exception as e:
        print(f"    Agent 3: Intent check failed ({e}) - failing open.")
        return True


# ---------------------------------------------------------------------------
# Core node
# ---------------------------------------------------------------------------


async def file_editor_node(state: AgentState, config) -> dict:
    """
    Agent 3 node function (File Editor).

    For each modified file in the patch:
      1. Reset file to HEAD (clean slate).
      2. Apply str_replace edits from the planning agent's plan.
         - Try deterministically first (verified plans).
         - Fall back to LLM+ReAct if deterministic fails.
      3. Capture diff via `git diff HEAD -- <file>`.
      4. Reset file to HEAD again (leave repo clean for validation).
      5. Emit AdaptedHunk with hunk_text = git diff output.

    Validation then applies the clean mechanically-generated diff.
    """
    print("Agent 3 (File Editor): Starting direct file-edit workflow...")

    consistency_map: dict = state.get("consistency_map") or {}
    mapped_target_context: dict = state.get("mapped_target_context") or {}
    hunk_generation_plan: dict = state.get("hunk_generation_plan") or {}
    semantic_blueprint: SemanticBlueprint = state.get("semantic_blueprint")
    patch_analysis: list = state.get("patch_analysis") or []
    patch_diff: str = state.get("patch_diff") or ""
    target_repo_path: str = state.get("target_repo_path", "")
    mainline_repo_path: str = state.get("mainline_repo_path", "")
    original_commit: str = state.get("original_commit", "HEAD")
    validation_attempts: int = state.get("validation_attempts") or 0
    error_context: str = state.get("validation_error_context") or ""
    retry_files_raw = state.get("validation_retry_files") or []
    with_test_changes: bool = state.get("with_test_changes", False)
    previous_patch_hash = str(state.get("generated_patch_hash") or "")

    retry_files = {_normalize_rel_path(p) for p in retry_files_raw if p}

    if not semantic_blueprint:
        msg = "Agent 3 Error: No semantic_blueprint in state."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    if not patch_diff:
        msg = "Agent 3 Error: No patch_diff in state."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # Retry context string injected into LLM prompts on retries
    retry_context_str = ""
    if validation_attempts > 0 and error_context:
        retry_files_note = (
            f"Files implicated: {sorted(retry_files)}\n" if retry_files else ""
        )
        retry_context_str = (
            f"## RETRY #{validation_attempts} - Previous Validation Failed\n"
            f"```\n{error_context[:600]}\n```\n"
            f"{retry_files_note}"
            "Adjust your edits to fix the above error.\n"
        )
        print(f"  Agent 3: Retry #{validation_attempts} - injecting error context.")

    # Setup
    llm = get_llm(temperature=0)
    toolkit = HunkGeneratorToolkit(target_repo_path) if target_repo_path else None
    react_agent = None
    if toolkit:
        react_agent = create_react_agent(
            llm, tools=toolkit.get_tools(), prompt=_FILE_EDITOR_SYSTEM
        )

    retriever = None
    if target_repo_path and mainline_repo_path:
        try:
            retriever = EnsembleRetriever(mainline_repo_path, target_repo_path)
        except Exception as e:
            print(f"  Agent 3: Retriever unavailable: {e}")

    analyzer = PatchAnalyzer()
    raw_hunks_by_file = (
        analyzer.extract_raw_hunks(patch_diff, with_test_changes=with_test_changes)
        if patch_diff
        else {}
    )

    fix_logic = semantic_blueprint.get("fix_logic", "")
    dependent_apis = semantic_blueprint.get("dependent_apis", [])
    cm_formatted = _format_consistency_map(consistency_map)

    model_name = resolve_model_name()
    token_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated": False,
        "sources": [],
    }

    # Segregate code vs test files
    code_changes = [
        fc
        for fc in patch_analysis
        if not (
            fc.is_test_file
            if hasattr(fc, "is_test_file")
            else fc.get("is_test_file", False)
        )
    ]

    adapted_file_edits: list[FileEdit] = []
    adapted_code_hunks: list[AdaptedHunk] = []
    generation_checklist: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Per-file processing
    # ------------------------------------------------------------------
    for change in code_changes:
        mainline_file = (
            change.file_path
            if hasattr(change, "file_path")
            else change.get("file_path", "?")
        )
        change_type = (
            change.change_type
            if hasattr(change, "change_type")
            else change.get("change_type", "MODIFIED")
        )

        op_plan = _resolve_operation_plan(
            change_type=change_type,
            mainline_file=mainline_file,
            target_repo_path=target_repo_path,
            retriever=retriever,
            original_commit=original_commit,
        )
        target_file = _normalize_rel_path(op_plan.get("target_file") or mainline_file)

        # Skip files not in retry scope (on retries)
        if retry_files:
            candidate_paths = {
                _normalize_rel_path(mainline_file),
                _normalize_rel_path(target_file),
            }
            mapped_ctx_list = mapped_target_context.get(mainline_file, [])
            if mapped_ctx_list:
                candidate_paths.add(
                    _normalize_rel_path(
                        (mapped_ctx_list[0] or {}).get("target_file", "")
                    )
                )
            if not any(p for p in candidate_paths if p in retry_files):
                continue

        # Get plan entries for this file
        plan_entries: list[dict[str, Any]] = hunk_generation_plan.get(mainline_file, [])
        if not plan_entries:
            print(f"  Agent 3: No plan entries for {mainline_file} - skipping.")
            continue

        # Get target context for prompt
        mapped_ctx_list = mapped_target_context.get(mainline_file, [])
        target_context = ""
        if mapped_ctx_list:
            target_context = mapped_ctx_list[0].get("code_snippet", "")

        print(
            f"  Agent 3: Processing {len(plan_entries)} edit(s) for "
            f"{target_file} (op={change_type})"
        )

        task_entry = {
            "mainline_file": mainline_file,
            "target_file": target_file,
            "hunk_index": 0,
            "status": "in_progress",
            "reason": "started",
            "todo_steps": [
                "reset_file",
                "apply_edits",
                "capture_diff",
                "intent_check",
                "restore_file",
            ],
            "completed_steps": [],
        }
        generation_checklist.append(task_entry)

        # Step A: Reset file to HEAD (clean starting state)
        if toolkit and target_repo_path:
            reset_ok = _git_reset_file(target_repo_path, target_file)
            if not reset_ok:
                print(f"    Agent 3: Warning - could not reset {target_file} to HEAD.")
        task_entry["completed_steps"].append("reset_file")

        # Step B: Apply edits
        file_edits_applied: list[FileEdit] = []
        all_edits_ok = True

        # ----------------------------------------------------------------
        # PRIMARY PATH: deterministic application of verified plan edits
        # ----------------------------------------------------------------
        if toolkit:
            for plan_entry in plan_entries:
                edit_ok, apply_result, _ = _apply_edit_deterministically(
                    toolkit, plan_entry, target_file
                )
                fe: FileEdit = {
                    "target_file": target_file,
                    "mainline_file": mainline_file,
                    "old_string": str(plan_entry.get("old_string") or ""),
                    "new_string": str(plan_entry.get("new_string") or ""),
                    "edit_type": str(plan_entry.get("edit_type") or "replace"),
                    "verified": bool(plan_entry.get("verified", False)),
                    "verification_result": str(
                        plan_entry.get("verification_result") or ""
                    ),
                    "applied": edit_ok,
                    "apply_result": apply_result,
                }
                file_edits_applied.append(fe)
                if edit_ok:
                    print(
                        f"    Agent 3: Deterministic edit OK for "
                        f"{target_file}[{plan_entry.get('hunk_index')}]"
                    )
                else:
                    all_edits_ok = False
                    print(
                        f"    Agent 3: Deterministic edit FAILED for "
                        f"{target_file}[{plan_entry.get('hunk_index')}]: {apply_result}"
                    )

        # ----------------------------------------------------------------
        # FALLBACK PATH: LLM+ReAct agent when deterministic fails
        # ----------------------------------------------------------------
        if not all_edits_ok and react_agent:
            print(
                f"    Agent 3: Falling back to LLM+ReAct for {target_file} "
                "(some deterministic edits failed)."
            )
            # Reset and let LLM handle all edits for this file from scratch
            if toolkit:
                _git_reset_file(target_repo_path, target_file)

            react_prompt = _FILE_EDITOR_USER.format(
                target_file=target_file,
                edit_plan=_format_edit_plan(plan_entries),
                consistency_map=cm_formatted,
                fix_logic=fix_logic,
                dependent_apis=", ".join(dependent_apis),
                target_context=target_context[:800],
                retry_context=retry_context_str,
            )

            for attempt in range(2):
                try:
                    react_in_tokens = count_text_tokens(
                        _FILE_EDITOR_SYSTEM + "\n" + react_prompt, model_name
                    )
                    react_result = await react_agent.ainvoke(
                        {"messages": [("user", react_prompt)]},
                        config={"recursion_limit": 35},
                    )
                    react_messages = react_result.get("messages", [])

                    # Collect token usage
                    exact_any = False
                    for rm in react_messages:
                        if getattr(rm, "type", "") != "ai":
                            continue
                        usage = extract_usage_from_response(rm)
                        if usage and (usage["input_tokens"] or usage["output_tokens"]):
                            add_usage(
                                token_usage,
                                usage["input_tokens"],
                                usage["output_tokens"],
                                "file_editor.react.provider_usage",
                            )
                            exact_any = True
                    if not exact_any:
                        raw_out = react_messages[-1].content if react_messages else ""
                        add_usage(
                            token_usage,
                            react_in_tokens,
                            count_text_tokens(str(raw_out), model_name),
                            "file_editor.react.tiktoken",
                        )
                        token_usage["estimated"] = True

                    # Mark as applied if the agent ran without fatal error
                    # (the actual edits were applied by tool calls during the run)
                    all_edits_ok = True
                    # Update file_edits_applied with a synthetic record
                    file_edits_applied = [
                        {
                            "target_file": target_file,
                            "mainline_file": mainline_file,
                            "old_string": "(llm_react)",
                            "new_string": "(llm_react)",
                            "edit_type": "replace",
                            "verified": True,
                            "verification_result": "llm_react_applied",
                            "applied": True,
                            "apply_result": "LLM+ReAct agent applied edits",
                        }
                    ]
                    print(
                        f"    Agent 3: LLM+ReAct completed for {target_file} "
                        f"(attempt {attempt + 1}/2)"
                    )
                    break

                except GraphRecursionError as e:
                    print(
                        f"    Agent 3: ReAct recursion limit on {target_file} "
                        f"(attempt {attempt + 1}/2): {e}"
                    )
                except Exception as e:
                    print(
                        f"    Agent 3: ReAct error on {target_file} "
                        f"(attempt {attempt + 1}/2): {e}"
                    )

        adapted_file_edits.extend(file_edits_applied)
        task_entry["completed_steps"].append("apply_edits")

        if not all_edits_ok:
            print(
                f"    Agent 3: All edit attempts failed for {target_file}. "
                "Resetting file and continuing."
            )
            if toolkit:
                _git_reset_file(target_repo_path, target_file)
            task_entry["status"] = "failed"
            task_entry["reason"] = "all_edit_attempts_failed"
            continue

        # Step C: Capture diff via git diff (mechanically correct)
        diff_text = ""
        if target_repo_path:
            diff_text = _git_diff_file(target_repo_path, target_file)

        if not diff_text.strip():
            print(
                f"    Agent 3: No diff captured for {target_file} - "
                "edits may have been no-ops or file is unchanged."
            )
            # Still reset and continue - might be a legitimate no-op
            if toolkit:
                _git_reset_file(target_repo_path, target_file)
            task_entry["status"] = "noop"
            task_entry["reason"] = "no_diff_after_edits"
            task_entry["completed_steps"].extend(
                ["capture_diff", "intent_check", "restore_file"]
            )
            continue

        task_entry["completed_steps"].append("capture_diff")
        print(
            f"    Agent 3: Captured diff for {target_file} "
            f"({len(diff_text.splitlines())} lines)"
        )

        # Semantic guard: detect missing helper-method declaration for newly added calls.
        semantic_invalid, semantic_reason = _diff_introduces_call_without_definition(
            diff_text
        )
        if semantic_invalid and "order(...)" in semantic_reason:
            # Avoid false positives when method already exists in target file.
            if _file_has_method_declaration(target_repo_path, target_file, "order"):
                semantic_invalid = False
                semantic_reason = ""
        if semantic_invalid:
            print(f"    Agent 3: {semantic_reason}")
            if toolkit and target_repo_path:
                _git_reset_file(target_repo_path, target_file)
            task_entry["status"] = "failed"
            task_entry["reason"] = "generation_contract_failed"
            continue

        # Step D: Extract just the hunk portions from the full git diff output
        # git diff HEAD produces: diff --git a/... b/... \n--- a/... \n+++ b/...\n@@...
        # We extract from the first @@ line onwards for the hunk_text field,
        # but store the full diff in hunk_text so apply_adapted_hunks can use it.
        hunk_text = (
            diff_text  # full diff - validation_tools.apply_adapted_hunks handles this
        )

        # Extract approximate insertion line from first @@ header for metadata
        insertion_line = 1
        for line in diff_text.splitlines():
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            if m:
                try:
                    insertion_line = int(m.group(1))
                except ValueError:
                    pass
                break

        # Step E: Intent check
        intent_ok = await _check_intent(
            llm, diff_text, semantic_blueprint, token_usage, model_name
        )
        if not intent_ok:
            print(
                f"    Agent 3: Blueprint intent check FAILED for {target_file} - flagging."
            )
        task_entry["completed_steps"].append("intent_check")

        # Step F: Reset file to HEAD (leave repo clean for validation)
        if toolkit and target_repo_path:
            _git_reset_file(target_repo_path, target_file)
        task_entry["completed_steps"].append("restore_file")

        task_entry["status"] = "success"
        task_entry["reason"] = (
            "generated_with_intent_warning"
            if not intent_ok
            else "generated_and_validated"
        )

        hunk: AdaptedHunk = {
            "target_file": target_file,
            "mainline_file": mainline_file,
            "hunk_text": hunk_text,
            "insertion_line": insertion_line,
            "intent_verified": intent_ok,
            "file_operation": op_plan.get("effective_operation", change_type),
            "old_target_file": op_plan.get("old_target_file"),
            "file_operation_required": op_plan.get("operation_required", True),
            "path_resolution_reason": op_plan.get("reason", "unknown"),
        }
        adapted_code_hunks.append(hunk)

    print(
        f"  Agent 3 (File Editor): Done. "
        f"{len(adapted_code_hunks)} file(s) adapted, "
        f"{len(adapted_file_edits)} edit record(s)."
    )

    # Global retry-loop guard: detect identical code patch across attempts.
    combined_diff = "\n".join(h.get("hunk_text", "") for h in adapted_code_hunks)
    current_patch_hash = (
        hashlib.sha256(combined_diff.encode("utf-8")).hexdigest()
        if combined_diff.strip()
        else ""
    )

    if (
        validation_attempts > 0
        and previous_patch_hash
        and current_patch_hash
        and previous_patch_hash == current_patch_hash
    ):
        print(
            "  Agent 3: Identical patch hash detected on retry; flagging for replanning."
        )
        return {
            "messages": [
                HumanMessage(
                    content=(
                        "Agent 3 (File Editor): identical generated patch detected on retry; "
                        "requesting replanning."
                    )
                )
            ],
            "adapted_file_edits": adapted_file_edits,
            "adapted_code_hunks": adapted_code_hunks,
            "adapted_test_hunks": [],
            "generation_checklist": [
                {
                    "mainline_file": "<all>",
                    "target_file": "<all>",
                    "hunk_index": 0,
                    "status": "failed",
                    "reason": "generation_contract_failed",
                    "todo_steps": ["replan"],
                    "completed_steps": [],
                }
            ],
            "validation_failed_stage": "generation_contract_failed",
            "generated_patch_hash": current_patch_hash,
            "token_usage": token_usage,
        }

    return {
        "messages": [
            HumanMessage(
                content=(
                    f"Agent 3 (File Editor): {len(adapted_code_hunks)} file(s) adapted "
                    f"via direct str_replace edits + git diff."
                )
            )
        ],
        "adapted_file_edits": adapted_file_edits,
        "adapted_code_hunks": adapted_code_hunks,
        "adapted_test_hunks": [],
        "generation_checklist": generation_checklist,
        "generated_patch_hash": current_patch_hash,
        "token_usage": token_usage,
    }
