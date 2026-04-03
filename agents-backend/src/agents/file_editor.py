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

from state import AgentState, AdaptedHunk, FileEdit, SemanticBlueprint
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
    target_repo_path: str,
    plan_entry: dict[str, Any],
    target_file: str,
) -> tuple[bool, str, str, str, str]:
    """
    Apply a single plan operation deterministically with anchor resolution.

    Returns:
      (success, apply_result_message, resolved_old, resolved_new, resolution_reason)
    """
    edit_type = str(plan_entry.get("edit_type") or "replace").lower()
    old_string = str(plan_entry.get("old_string") or "")
    new_string = str(plan_entry.get("new_string") or "")

    if not old_string:
        return False, "empty_old_string", "", "", "empty_old"

    full_path = os.path.normpath(os.path.join(target_repo_path, target_file))
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as exc:
        return False, f"read_error:{exc}", "", "", "read_failed"

    def _resolve_old(content_text: str, candidate: str) -> tuple[str, str]:
        content_text = (content_text or "").replace("\r\n", "\n").replace("\r", "\n")
        candidate = (candidate or "").replace("\r\n", "\n").replace("\r", "\n")

        if candidate in content_text:
            return candidate, "exact"

        # Pass 1.5: Whitespace-agnostic (trailing and line endings)
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

        # Single-line: find unique stripped-line match and adopt exact file line.
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

        # Multi-line: match by stripped-line equivalence window.
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

        # Secondary fallback: anchor-line reconstruction for diverged multiline blocks.
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

    resolved_old, reason = _resolve_old(content, old_string)
    if not resolved_old:
        return False, f"old_resolution_failed:{reason}", "", "", reason

    resolved_new = new_string
    if edit_type in {"insert_before", "insert_after"}:
        # Recompose insertion around resolved anchor to avoid whitespace mismatch.
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

        # Fallback: infer payload using stripped-line suffix/prefix relationship.
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
            return (
                False,
                "insert_payload_derivation_failed",
                resolved_old,
                "",
                "payload_missing",
            )

        if edit_type == "insert_before" and payload and not payload.endswith("\n"):
            payload += "\n"
        if edit_type == "insert_after" and payload and not payload.startswith("\n"):
            payload = "\n" + payload

        resolved_new = (
            payload + resolved_old
            if edit_type == "insert_before"
            else resolved_old + payload
        )

    result = toolkit.str_replace_in_file(target_file, resolved_old, resolved_new)
    if result.startswith("SUCCESS"):
        return True, result, resolved_old, resolved_new, reason
    return False, result, resolved_old, resolved_new, reason


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


def _parse_numbered_lines_block(block_output: str) -> list[str]:
    out: list[str] = []
    for line in (block_output or "").splitlines():
        m = re.match(r"\s*(\d+):\s?(.*)$", line)
        if m:
            out.append(m.group(2))
    return out


def _retry_with_file_check(
    toolkit: HunkGeneratorToolkit,
    target_repo_path: str,
    plan_entry: dict[str, Any],
    target_file: str,
) -> tuple[bool, str, str, str, str]:
    """
    Retry failed deterministic replacement by probing target file directly via
    grep/read tools and reconstructing an exact old_string from file content.
    """
    old_string = str(plan_entry.get("old_string") or "")
    if not old_string:
        return False, "file_check_retry_empty_old", "", "", "file_check_empty_old"

    old_lines = old_string.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    if not old_lines:
        return False, "file_check_retry_no_lines", "", "", "file_check_no_lines"

    # Pick the strongest non-empty line as grep anchor.
    anchor_idx = -1
    anchor_line = ""
    best_len = -1
    for i, line in enumerate(old_lines):
        s = line.strip()
        if not s:
            continue
        if len(s) > best_len:
            best_len = len(s)
            anchor_idx = i
            anchor_line = s

    if not anchor_line:
        return False, "file_check_retry_no_anchor", "", "", "file_check_no_anchor"

    grep_out = toolkit.grep_in_file(
        file_path=target_file,
        search_text=anchor_line,
        is_regex=False,
        max_results=50,
    )
    hits = _parse_grep_hits(grep_out)
    if not hits:
        return (
            False,
            f"file_check_retry_grep_no_hits:{anchor_line}",
            "",
            "",
            "file_check_grep_no_hits",
        )

    n = len(old_lines)
    for line_no, _ in hits:
        start = max(1, line_no - anchor_idx)
        end = start + n - 1
        block_out = toolkit.get_exact_lines(target_file, start, end)
        candidate_lines = _parse_numbered_lines_block(block_out)
        if len(candidate_lines) != n:
            continue

        candidate_old = "\n".join(candidate_lines)
        retry_entry = dict(plan_entry)
        retry_entry["old_string"] = candidate_old
        ok, msg, resolved_old, resolved_new, reason = _apply_edit_deterministically(
            toolkit,
            target_repo_path,
            retry_entry,
            target_file,
        )
        if ok:
            return (
                True,
                f"{msg} | retried_with_file_check(start_line={start})",
                resolved_old,
                resolved_new,
                f"file_check_retry_success:{reason}",
            )

    return (
        False,
        "file_check_retry_exhausted",
        "",
        "",
        "file_check_retry_exhausted",
    )


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


def _looks_structurally_truncated(diff_text: str) -> tuple[bool, str]:
    """
    Cheap syntax artifact guard on added lines.
    Detects obviously truncated declarations emitted by malformed edits.
    """
    added = [
        line[1:]
        for line in (diff_text or "").splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    for line in added:
        s = line.strip()
        if s == "private static final":
            return (
                True,
                "syntax_guard_failed: truncated declaration 'private static final'",
            )
        if re.match(r"^(private|public|protected)\s+(static\s+)?(final\s+)?$", s):
            return True, f"syntax_guard_failed: truncated declaration '{s}'"
        if s.endswith("=") and not s.endswith("=="):
            return True, f"syntax_guard_failed: dangling assignment in added line '{s}'"
    return False, ""


def _check_static_field_in_method_body(diff_text: str) -> tuple[bool, str]:
    """
    Detect the pattern where a static field is inserted inside a method body.
    This causes 'illegal start of expression' errors.
    """
    lines = (diff_text or "").splitlines()
    context_before = []
    for line in lines:
        if line.startswith("@@"):
            context_before = []
            continue
        if line.startswith(" ") or line.startswith("-"):
            context_before.append(line[1:])
        if line.startswith("+") and not line.startswith("+++"):
            l = line[1:].strip()
            # If we see a static field declaration
            if re.match(r"^(private|public|protected)\s+static\s+final\s+", l):
                # Check brace depth in context
                combined = "\n".join(context_before[-20:])
                open_braces = combined.count("{")
                close_braces = combined.count("}")
                depth = open_braces - close_braces
                if depth > 1:  # 0 = outside class, 1 = inside class, >1 = inside method
                    return (
                        True,
                        f"semantic_guard_failed: static field inserted inside method body (brace depth={depth})",
                    )
    return False, ""


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
         - Deterministic-only execution with on-disk anchor resolution.
      3. Capture diff via `git diff HEAD -- <file>`.
      4. Reset file to HEAD again (leave repo clean for validation).
      5. Emit AdaptedHunk with hunk_text = git diff output.

    Validation then applies the clean mechanically-generated diff.
    """
    print("Agent 3 (File Editor): Starting direct file-edit workflow...")

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

    if validation_attempts > 0 and error_context:
        print(
            f"  Agent 3: Retry #{validation_attempts} - deterministic re-application with failure context."
        )

    # Setup
    llm = get_llm(temperature=0)
    toolkit = HunkGeneratorToolkit(target_repo_path) if target_repo_path else None

    retriever = None
    if target_repo_path and mainline_repo_path:
        try:
            retriever = EnsembleRetriever(mainline_repo_path, target_repo_path)
        except Exception as e:
            print(f"  Agent 3: Retriever unavailable: {e}")

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

        if any(
            "mapping_low_confidence" in str((e or {}).get("notes") or "")
            for e in plan_entries
        ):
            print(
                f"  Agent 3: Mapping confidence is low for {target_file}; "
                "requesting structural remap before editing."
            )
            generation_checklist.append(
                {
                    "mainline_file": mainline_file,
                    "target_file": target_file,
                    "hunk_index": 0,
                    "status": "failed",
                    "reason": "mapping_required",
                    "todo_steps": ["remap"],
                    "completed_steps": [],
                }
            )
            continue

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

        # Deterministic-only execution with per-op anchor resolution.
        if toolkit:
            for op_idx, plan_entry in enumerate(plan_entries):
                edit_ok, apply_result, resolved_old, resolved_new, resolution_reason = (
                    _apply_edit_deterministically(
                        toolkit,
                        target_repo_path,
                        plan_entry,
                        target_file,
                    )
                )

                if not edit_ok and str(apply_result).startswith(
                    "old_resolution_failed:not_found"
                ):
                    (
                        retry_ok,
                        retry_result,
                        retry_old,
                        retry_new,
                        retry_reason,
                    ) = _retry_with_file_check(
                        toolkit,
                        target_repo_path,
                        plan_entry,
                        target_file,
                    )
                    if retry_ok:
                        edit_ok = True
                        apply_result = retry_result
                        resolved_old = retry_old
                        resolved_new = retry_new
                        resolution_reason = retry_reason
                    else:
                        apply_result = f"{apply_result} | retry={retry_result}"

                fe: FileEdit = {
                    "target_file": target_file,
                    "mainline_file": mainline_file,
                    "old_string": resolved_old
                    if resolved_old
                    else str(plan_entry.get("old_string") or ""),
                    "new_string": resolved_new
                    if resolved_new
                    else str(plan_entry.get("new_string") or ""),
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
                        f"{target_file}[{plan_entry.get('hunk_index')}:{op_idx}] "
                        f"(resolve={resolution_reason})"
                    )
                else:
                    all_edits_ok = False
                    print(
                        f"    Agent 3: Deterministic edit FAILED for "
                        f"{target_file}[{plan_entry.get('hunk_index')}:{op_idx}]: {apply_result}"
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
            task_entry["reason"] = "generation_contract_failed"
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

        truncated_invalid, truncated_reason = _looks_structurally_truncated(diff_text)
        if truncated_invalid:
            print(f"    Agent 3: {truncated_reason}")
            if toolkit and target_repo_path:
                _git_reset_file(target_repo_path, target_file)
            task_entry["status"] = "failed"
            task_entry["reason"] = "generation_contract_failed"
            continue

        # Semantic guard: detect static fields in method bodies.
        static_field_invalid, static_field_reason = _check_static_field_in_method_body(
            diff_text
        )
        if static_field_invalid:
            print(f"    Agent 3: {static_field_reason}")
            if toolkit and target_repo_path:
                _git_reset_file(target_repo_path, target_file)
            task_entry["status"] = "failed"
            task_entry["reason"] = "generation_contract_failed"
            continue

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
