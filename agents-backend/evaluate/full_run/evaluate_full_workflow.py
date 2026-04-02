"""
Full Workflow Evaluation Script (Phase 0-4) for Multiple Projects (Druid, CrateDB).

This evaluator differs from evaluate/pipeline/evaluate_full_pipeline.py:
- Uses the full workflow (does NOT skip phase 0).
- Runs build + relevant tests in phase 0 and phase 4.
- Restricts agentic adaptation to non-test Java code hunks only.
- Merges developer backport non-Java + test hunks during validation (phase 4).
"""

import asyncio
import csv
import difflib
import io
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from typing import Any

from unidiff import PatchSet

# Add src to path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

from graph import app
from utils.patch_analyzer import PatchAnalyzer
from dotenv import load_dotenv

load_dotenv()


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", "all_projects_final.csv")
REPOS_DIR = os.path.join(BASE_DIR, "temp_repo_storage")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
PHASE0_CACHE_DIR = os.path.join(os.path.dirname(__file__), "phase0_cache")

TARGET_PROJECTS = ["elasticsearch"]
MAX_PATCHES_PER_PROJECT = 4


def ensure_dirs() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(PHASE0_CACHE_DIR, exist_ok=True)
    for project in TARGET_PROJECTS:
        os.makedirs(os.path.join(RESULTS_DIR, project), exist_ok=True)


def _phase0_cache_file(project: str, backport_commit: str, original_commit: str) -> str:
    safe_project = (project or "unknown").strip().lower() or "unknown"
    safe_backport = (backport_commit or "unknown").strip() or "unknown"
    safe_original = (original_commit or "unknown").strip() or "unknown"
    filename = f"{safe_project}_{safe_backport[:12]}_{safe_original[:12]}.json"
    return os.path.join(PHASE0_CACHE_DIR, filename)


def _load_phase0_cache(
    project: str, backport_commit: str, original_commit: str
) -> dict[str, Any] | None:
    path = _phase0_cache_file(project, backport_commit, original_commit)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _is_phase0_cache_reusable(cache_payload: dict[str, Any] | None) -> tuple[bool, str]:
    """
    Reject stale/poisoned Phase 0 cache entries that cannot provide meaningful
    transition comparison data.
    """
    payload = cache_payload or {}
    baseline = payload.get("phase_0_baseline_test_result") or {}
    transition = payload.get("phase_0_transition_evaluation") or {}

    baseline_mode = (baseline.get("mode") or "").strip().lower()
    baseline_total = int(
        (baseline.get("test_state") or {}).get("summary", {}).get("total", 0) or 0
    )
    transition_reason = (transition.get("reason") or "").strip().lower()

    if baseline_mode == "baseline-apply-failed":
        return False, "baseline-apply-failed"
    if baseline_total == 0 and "no fail-to-pass or newly passing" in transition_reason:
        return False, "empty-baseline-and-empty-transition"
    if "inconclusive: relevant target tests were not observed" in transition_reason:
        return False, "inconclusive-target-tests-not-observed"
    return True, "ok"


def run_cmd(cmd, cwd, env=None, timeout=None):
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr or e.stdout
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout} seconds"
    except Exception as e:
        return False, str(e)


def _is_test_file(file_path: str) -> bool:
    lower_path = (file_path or "").lower()
    return "test" in lower_path or lower_path.endswith("test.java")


def _is_java_code_file(file_path: str) -> bool:
    p = (file_path or "").lower()
    return p.endswith(".java") and not _is_test_file(p)


def setup_repos(mainline_commit, backport_commit, mainline_repo_path, target_repo_path):
    success, output = run_cmd(
        ["git", "checkout", mainline_commit],
        cwd=mainline_repo_path,
        timeout=300,
    )
    if not success:
        return False, f"Failed to checkout mainline commit {mainline_commit}: {output}"

    success, output = run_cmd(
        ["git", "checkout", f"{backport_commit}^"],
        cwd=target_repo_path,
        timeout=300,
    )
    if not success:
        return False, f"Failed to checkout target commit {backport_commit}^: {output}"

    return True, "Repos set up successfully"


def generate_mainline_patch(mainline_commit, mainline_repo_path):
    patch_path = os.path.join(RESULTS_DIR, "temp_mainline.patch")

    success, output = run_cmd(
        ["git", "format-patch", "-1", mainline_commit, "--stdout"],
        cwd=mainline_repo_path,
        timeout=300,
    )

    if not success:
        return None, f"Failed to generate patch: {output}"

    try:
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(output)
        return patch_path, output
    except Exception as e:
        return None, f"Failed to write patch file: {str(e)}"


def generate_developer_backport_patch(backport_commit, target_repo_path):
    success, output = run_cmd(
        ["git", "show", "--format=", "--no-color", backport_commit],
        cwd=target_repo_path,
        timeout=300,
    )
    if not success:
        return (
            None,
            f"Failed to generate developer backport patch for {backport_commit}: {output}",
        )
    return output, None


def _build_auxiliary_hunks_from_developer_patch(
    patch_diff: str,
) -> list[dict[str, Any]]:
    """
    Build hunks for developer-owned changes that agentic system should not generate:
    - all test file hunks
    - all non-Java file hunks
    """
    if not patch_diff.strip():
        return []

    patch_set = PatchSet(io.StringIO(patch_diff))
    hunks: list[dict[str, Any]] = []

    def _norm_path(path: str | None) -> str:
        p = (path or "").strip().replace("\\", "/")
        if p.startswith("a/") or p.startswith("b/"):
            p = p[2:]
        if p == "dev/null":
            return ""
        return p

    for patched_file in patch_set:
        file_path = _norm_path(patched_file.path)
        include = _is_test_file(file_path) or (not file_path.lower().endswith(".java"))
        if not include:
            continue

        source_path = _norm_path(getattr(patched_file, "source_file", None))
        target_path = (
            _norm_path(getattr(patched_file, "target_file", None)) or file_path
        )

        if patched_file.is_rename or (
            source_path and target_path and source_path != target_path
        ):
            op = "RENAMED"
        elif patched_file.is_added_file:
            op = "ADDED"
        elif patched_file.is_removed_file:
            op = "DELETED"
        else:
            op = "MODIFIED"

        for hunk in patched_file:
            lines = [
                f"@@ -{hunk.source_start},{hunk.source_length} +{hunk.target_start},{hunk.target_length} @@\n"
            ]
            for line in hunk:
                if line.is_added:
                    lines.append(f"+{line.value}")
                elif line.is_removed:
                    lines.append(f"-{line.value}")
                else:
                    lines.append(f" {line.value}")

            hunk_text = "".join(lines)
            if not hunk_text.endswith("\n"):
                hunk_text += "\n"

            hunks.append(
                {
                    "target_file": target_path,
                    "mainline_file": target_path,
                    "hunk_text": hunk_text,
                    "insertion_line": hunk.target_start,
                    "intent_verified": True,
                    "file_operation": op,
                    "old_target_file": source_path or None,
                }
            )

        # Preserve pure structural file-operations with no hunks.
        if len(list(patched_file)) == 0:
            hunks.append(
                {
                    "target_file": target_path,
                    "mainline_file": target_path,
                    "hunk_text": "",
                    "insertion_line": 0,
                    "intent_verified": True,
                    "file_operation": op,
                    "old_target_file": source_path or None,
                }
            )

    return hunks


def _build_hunk_comparison_markdown(adapted_code_hunks, developer_patch_diff, analyzer):
    developer_hunks_by_file = analyzer.extract_raw_hunks(
        developer_patch_diff, with_test_changes=False
    )
    developer_hunks_by_file = {
        file: hunks
        for file, hunks in developer_hunks_by_file.items()
        if _is_java_code_file(file)
    }

    generated_hunks_by_file = {}
    for hunk in adapted_code_hunks:
        file = hunk["target_file"]
        if file not in generated_hunks_by_file:
            generated_hunks_by_file[file] = []
        generated_hunks_by_file[file].append(hunk["hunk_text"])

    all_files = set(generated_hunks_by_file.keys()) | set(
        developer_hunks_by_file.keys()
    )

    markdown = ""
    for file in sorted(all_files):
        gen_hunks = generated_hunks_by_file.get(file, [])
        dev_hunks = developer_hunks_by_file.get(file, [])
        max_hunks = max(len(gen_hunks), len(dev_hunks))

        markdown += f"### {file}\n\n"
        for i in range(max_hunks):
            gen = gen_hunks[i] if i < len(gen_hunks) else "*No hunk*"
            dev = dev_hunks[i] if i < len(dev_hunks) else "*No hunk*"

            dev_lines = dev.splitlines(keepends=True)
            gen_lines = gen.splitlines(keepends=True)
            delta = "".join(
                difflib.unified_diff(
                    dev_lines,
                    gen_lines,
                    fromfile="developer",
                    tofile="generated",
                    lineterm="",
                )
            )
            if not delta:
                delta = "(No textual difference)\n"

            markdown += f"#### Hunk {i + 1}\n\n"
            markdown += "Developer\n"
            markdown += f"```diff\n{dev}\n```\n\n"
            markdown += "Generated\n"
            markdown += f"```diff\n{gen}\n```\n\n"
            markdown += "Developer -> Generated (Unified Diff)\n"
            markdown += f"```diff\n{delta}\n```\n\n"

        markdown += "\n"

    return markdown


def _normalize_hunk_header_for_operation(hunk_text: str, file_operation: str) -> str:
    if not hunk_text:
        return hunk_text

    lines = hunk_text.splitlines()
    if not lines:
        return hunk_text

    header = lines[0]
    m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$", header)
    if not m:
        return hunk_text

    old_start = int(m.group(1))
    old_len = int(m.group(2) or "1")
    new_start = int(m.group(3))
    new_len = int(m.group(4) or "1")
    suffix = m.group(5)

    op = (file_operation or "MODIFIED").upper()
    if op == "ADDED":
        old_start, old_len = 0, 0
        if new_start <= 0:
            new_start = 1
    elif op == "DELETED":
        new_start, new_len = 0, 0
        if old_start <= 0:
            old_start = 1

    lines[0] = f"@@ -{old_start},{old_len} +{new_start},{new_len} @@{suffix}"
    normalized = "\n".join(lines)
    if hunk_text.endswith("\n"):
        normalized += "\n"
    return normalized


def _build_generated_patch_from_hunks(adapted_code_hunks: list[dict[str, Any]]) -> str:
    hunks_by_file: dict[str, dict[str, Any]] = {}
    file_order: list[str] = []

    def _norm(path: str | None) -> str:
        p = (path or "").strip().replace("\\", "/")
        if p.startswith("a/") or p.startswith("b/"):
            p = p[2:]
        if p == "dev/null":
            return ""
        return p

    for hunk in adapted_code_hunks or []:
        target_file = _norm(hunk.get("target_file"))
        if not target_file:
            continue

        if target_file not in hunks_by_file:
            file_operation = (hunk.get("file_operation") or "MODIFIED").upper()
            old_target_file = _norm(
                hunk.get("old_target_file") or hunk.get("mainline_file")
            )
            hunks_by_file[target_file] = {
                "file_operation": file_operation,
                "old_target_file": old_target_file,
                "hunks": [],
            }
            file_order.append(target_file)

        # Prefer a non-empty old path if later hunks provide one.
        existing_old = hunks_by_file[target_file].get("old_target_file") or ""
        incoming_old = _norm(hunk.get("old_target_file") or hunk.get("mainline_file"))
        if not existing_old and incoming_old:
            hunks_by_file[target_file]["old_target_file"] = incoming_old

        hunks_by_file[target_file]["hunks"].append(hunk.get("hunk_text", ""))

    lines: list[str] = []
    for target_file in file_order:
        payload = hunks_by_file[target_file]
        op = (payload.get("file_operation") or "MODIFIED").upper()
        old_target_file = _norm(payload.get("old_target_file")) or target_file

        if op == "RENAMED" and old_target_file and old_target_file != target_file:
            lines.append(f"diff --git a/{old_target_file} b/{target_file}")
            lines.append(f"rename from {old_target_file}")
            lines.append(f"rename to {target_file}")
            lines.append(f"--- a/{old_target_file}")
            lines.append(f"+++ b/{target_file}")
        else:
            lines.append(f"diff --git a/{target_file} b/{target_file}")
            if op == "ADDED":
                lines.append("--- /dev/null")
                lines.append(f"+++ b/{target_file}")
            elif op == "DELETED":
                lines.append(f"--- a/{target_file}")
                lines.append("+++ /dev/null")
            else:
                lines.append(f"--- a/{target_file}")
                lines.append(f"+++ b/{target_file}")

        # If this is effectively an added file represented as MODIFIED, convert header.
        if op == "MODIFIED":
            has_full_create_hunk = any(
                (h or "").lstrip().startswith("@@ -0,0 +")
                for h in payload.get("hunks", [])
            )
            if has_full_create_hunk:
                lines[-2:] = ["--- /dev/null", f"+++ b/{target_file}"]
                op = "ADDED"

        if op == "ADDED" and lines[-2] != "--- /dev/null":
            lines.append("--- /dev/null")
            lines.append(f"+++ b/{target_file}")
        elif op == "DELETED" and lines[-1] != "+++ /dev/null":
            lines.append(f"--- a/{target_file}")
            lines.append("+++ /dev/null")

        for hunk_text in payload.get("hunks", []):
            if not hunk_text:
                continue
            normalized_hunk = _normalize_hunk_header_for_operation(hunk_text, op)
            if not hunk_text.endswith("\n"):
                lines.append(normalized_hunk)
            else:
                lines.append(normalized_hunk.rstrip("\n"))

    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _get_java_code_changed_files(commit, repo_path):
    success, output = run_cmd(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
        cwd=repo_path,
        timeout=300,
    )
    if not success:
        return None, output

    files = [line.strip() for line in output.splitlines() if line.strip()]
    files = [f for f in files if _is_java_code_file(f)]
    return sorted(set(files)), None


def _get_blob_id_from_commit(repo_path, commit, rel_path):
    success, output = run_cmd(
        ["git", "rev-parse", f"{commit}:{rel_path}"],
        cwd=repo_path,
        timeout=300,
    )
    if not success:
        return None
    return output.strip() or None


def _get_blob_id_from_index(repo_path, rel_path, env):
    success, output = run_cmd(
        ["git", "rev-parse", f":{rel_path}"],
        cwd=repo_path,
        env=env,
        timeout=300,
    )
    if not success:
        return None
    return output.strip() or None


def _get_blob_content(repo_path, blob_id):
    if not blob_id:
        return None

    success, output = run_cmd(
        ["git", "cat-file", "-p", blob_id],
        cwd=repo_path,
        timeout=300,
    )
    if not success:
        return None
    return output


def _normalize_content_for_code_line_compare(content: str | None) -> list[str] | None:
    if content is None:
        return None

    normalized_lines = []
    for line in content.splitlines():
        normalized_lines.append(re.sub(r"\s+", "", line))
    return normalized_lines


def _apply_patch_with_temp_index(repo_path, patch_file_path, env):
    attempts = [
        [
            "git",
            "apply",
            "--cached",
            "--recount",
            "--whitespace=nowarn",
            patch_file_path,
        ],
        [
            "git",
            "apply",
            "--cached",
            "--recount",
            "--ignore-space-change",
            "--ignore-whitespace",
            "--whitespace=nowarn",
            patch_file_path,
        ],
    ]

    errors = []
    for cmd in attempts:
        success, output = run_cmd(cmd, cwd=repo_path, env=env, timeout=300)
        if success:
            return True, ""
        errors.append(output)

    return False, "\n\n".join(errors)


def compare_generated_with_developer_patch(
    adapted_code_hunks, developer_patch_diff, backport_commit, target_repo_path
):
    generated_patch_diff = _build_generated_patch_from_hunks(adapted_code_hunks or [])
    generated_files = sorted(
        {
            h.get("target_file")
            for h in (adapted_code_hunks or [])
            if h.get("target_file") and _is_java_code_file(h.get("target_file"))
        }
    )

    developer_files, files_err = _get_java_code_changed_files(
        backport_commit, target_repo_path
    )
    if files_err:
        return {
            "exact_developer_patch": False,
            "comparison_method": "file_state",
            "error": f"Failed to get changed files for {backport_commit}: {files_err}",
            "generated_patch_diff": generated_patch_diff,
        }

    files_to_compare = sorted(set((developer_files or []) + generated_files))

    with tempfile.NamedTemporaryFile(
        prefix="git_index_", suffix=".tmp", delete=False
    ) as index_file:
        temp_index_path = index_file.name

    with tempfile.NamedTemporaryFile(
        prefix="generated_eval_",
        suffix=".patch",
        delete=False,
        mode="w",
        encoding="utf-8",
    ) as patch_file:
        patch_file.write(generated_patch_diff)
        generated_patch_file = patch_file.name

    index_env = dict(os.environ)
    index_env["GIT_INDEX_FILE"] = temp_index_path

    try:
        success, output = run_cmd(
            ["git", "read-tree", f"{backport_commit}^"],
            cwd=target_repo_path,
            env=index_env,
            timeout=300,
        )
        if not success:
            return {
                "exact_developer_patch": False,
                "comparison_method": "file_state",
                "error": f"Failed to seed temporary index from {backport_commit}^: {output}",
                "generated_patch_diff": generated_patch_diff,
            }

        if generated_patch_diff.strip():
            apply_ok, apply_err = _apply_patch_with_temp_index(
                target_repo_path, generated_patch_file, index_env
            )
            if not apply_ok:
                return {
                    "exact_developer_patch": False,
                    "comparison_method": "file_state",
                    "error": f"Failed to apply generated patch in temporary index: {apply_err}",
                    "generated_patch_diff": generated_patch_diff,
                }

        mismatched_files = []
        for rel_path in files_to_compare:
            developer_blob = _get_blob_id_from_commit(
                target_repo_path, backport_commit, rel_path
            )
            generated_blob = _get_blob_id_from_index(
                target_repo_path, rel_path, index_env
            )
            if developer_blob == generated_blob:
                continue

            developer_content = _get_blob_content(target_repo_path, developer_blob)
            generated_content = _get_blob_content(target_repo_path, generated_blob)

            developer_normalized = _normalize_content_for_code_line_compare(
                developer_content
            )
            generated_normalized = _normalize_content_for_code_line_compare(
                generated_content
            )

            if developer_normalized != generated_normalized:
                mismatched_files.append(rel_path)

        return {
            "exact_developer_patch": len(mismatched_files) == 0,
            "comparison_method": "file_state",
            "comparison_normalization": "line_by_line_whitespace_insensitive",
            "compared_files": files_to_compare,
            "mismatched_files": mismatched_files,
            "developer_files": developer_files,
            "generated_files": generated_files,
            "generated_patch_diff": generated_patch_diff,
        }
    finally:
        try:
            os.remove(temp_index_path)
        except Exception:
            pass
        try:
            os.remove(generated_patch_file)
        except Exception:
            pass


def save_agent_state(project, patch_id, phase_name, state_dict, agent_name=None):
    project_dir = os.path.join(RESULTS_DIR, project, patch_id)
    os.makedirs(project_dir, exist_ok=True)

    output_file = os.path.join(
        project_dir,
        f"{phase_name}_{agent_name}.json" if agent_name else f"{phase_name}_state.json",
    )

    serializable_state = {}
    for key, value in state_dict.items():
        try:
            json.dumps(value)
            serializable_state[key] = value
        except (TypeError, ValueError):
            serializable_state[key] = str(value)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable_state, f, indent=2, default=str)

    return output_file


def save_pipeline_log(project, patch_id, phase_name, log_content):
    project_dir = os.path.join(RESULTS_DIR, project, patch_id)
    os.makedirs(project_dir, exist_ok=True)

    log_file = os.path.join(project_dir, f"{phase_name}_log.md")

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(log_content)

    return log_file


def _extract_transition_eval_from_outputs(
    phase_outputs: dict[str, Any],
) -> dict[str, Any] | None:
    phase0_eval = (
        phase_outputs.get("phase0", {})
        .get("phase_0_optimistic", {})
        .get("outputs", {})
        .get("phase_0_transition_evaluation")
    )
    if phase0_eval:
        return phase0_eval

    phase4_eval = (
        phase_outputs.get("phase4_validation", {})
        .get("validation", {})
        .get("outputs", {})
        .get("phase_0_transition_evaluation")
    )
    if phase4_eval:
        return phase4_eval

    return (
        phase_outputs.get("phase4_validation", {})
        .get("validation", {})
        .get("outputs", {})
        .get("validation_results", {})
        .get("tests", {})
        .get("state_transition")
    )


def _extract_touched_test_classes(
    phase_outputs: dict[str, Any], phase0_cache: dict[str, Any] | None = None
) -> list[str]:
    phase0_targets = (
        phase_outputs.get("phase0", {})
        .get("phase_0_optimistic", {})
        .get("outputs", {})
        .get("phase_0_test_targets", {})
    )
    if not phase0_targets and phase0_cache:
        phase0_targets = phase0_cache.get("phase_0_test_targets", {})

    targets = list((phase0_targets or {}).get("test_targets") or [])
    classes = []
    for item in targets:
        if ":" in item:
            classes.append(item.split(":", 1)[1].strip())
        elif item:
            classes.append(str(item).strip())

    return sorted({c for c in classes if c})


def _extract_baseline_and_patched_test_results(
    phase_outputs: dict[str, Any], phase0_cache: dict[str, Any] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    phase0_outputs = (
        phase_outputs.get("phase0", {}).get("phase_0_optimistic", {}).get("outputs", {})
    )

    baseline_result = (
        phase0_outputs.get("phase_0_baseline_test_result")
        or (phase0_cache or {}).get("phase_0_baseline_test_result")
        or {}
    )

    patched_result = (
        phase0_outputs.get("phase_0_post_patch_test_result")
        or (
            phase_outputs.get("phase4_validation", {})
            .get("validation", {})
            .get("outputs", {})
            .get("validation_results", {})
            .get("tests", {})
        )
        or (phase0_cache or {}).get("phase_0_post_patch_test_result")
        or {}
    )

    return baseline_result, patched_result


def _build_touched_test_state_markdown(
    touched_classes: list[str],
    baseline_result: dict[str, Any],
    patched_result: dict[str, Any],
) -> str:
    if not touched_classes:
        return "- Touched tests (from patch): []\n"

    baseline_state = (baseline_result or {}).get("test_state") or {}
    patched_state = (patched_result or {}).get("test_state") or {}

    baseline_cases = baseline_state.get("test_cases") or {}
    patched_cases = patched_state.get("test_cases") or {}
    baseline_classes = baseline_state.get("classes") or {}
    patched_classes = patched_state.get("classes") or {}

    lines = [f"- Touched tests (from patch): {touched_classes}"]
    for cls in touched_classes:
        class_case_keys = sorted(
            {
                key
                for key in set(baseline_cases.keys()) | set(patched_cases.keys())
                if key.startswith(f"{cls}#")
            }
        )
        if class_case_keys:
            for key in class_case_keys:
                old_status = baseline_cases.get(key, "absent")
                new_status = patched_cases.get(key, "absent")
                lines.append(f"  - {key}: baseline={old_status}, patched={new_status}")
        else:
            old_status = baseline_classes.get(cls, "absent")
            new_status = patched_classes.get(cls, "absent")
            lines.append(f"  - {cls}: baseline={old_status}, patched={new_status}")

    return "\n".join(lines) + "\n"


def _build_transition_summary_markdown(
    transition_eval: dict[str, Any] | None,
    source_label: str,
    phase_outputs: dict[str, Any] | None = None,
    phase0_cache: dict[str, Any] | None = None,
) -> str:
    if not transition_eval:
        return "# Transition Summary\n\nNo transition evaluation available.\n"

    fail_to_pass = transition_eval.get("fail_to_pass", []) or []
    newly_passing = transition_eval.get("newly_passing", []) or []
    pass_to_fail = transition_eval.get("pass_to_fail", []) or []
    reason = transition_eval.get("reason", "Unknown reason.")
    valid = bool(transition_eval.get("valid_backport_signal", False))
    phase_outputs = phase_outputs or {}

    touched_classes = _extract_touched_test_classes(phase_outputs, phase0_cache)
    baseline_result, patched_result = _extract_baseline_and_patched_test_results(
        phase_outputs, phase0_cache
    )
    touched_state_markdown = _build_touched_test_state_markdown(
        touched_classes, baseline_result, patched_result
    )

    return (
        "# Transition Summary\n\n"
        f"- Source: {source_label}\n"
        f"- Valid backport signal: {valid}\n"
        f"- Reason: {reason}\n"
        f"- fail->pass ({len(fail_to_pass)}): {fail_to_pass}\n"
        f"- newly passing ({len(newly_passing)}): {newly_passing}\n"
        f"- pass->fail ({len(pass_to_fail)}): {pass_to_fail}\n"
        "\n## Touched Test States\n"
        f"{touched_state_markdown}"
    )


async def run_full_pipeline(
    project,
    patch_id,
    mainline_commit,
    backport_commit,
    mainline_repo_path,
    target_repo_path,
):
    results = {
        "project": project,
        "patch_id": patch_id,
        "mainline_commit": mainline_commit,
        "backport_commit": backport_commit,
        "timestamp": datetime.now().isoformat(),
        "phases": {},
    }

    try:
        print(f"\n[{project}/{patch_id}] Setting up repositories...")
        success, output = setup_repos(
            mainline_commit,
            backport_commit,
            mainline_repo_path,
            target_repo_path,
        )
        if not success:
            results["setup_error"] = output
            return results

        print(f"[{project}/{patch_id}] Generating mainline patch...")
        patch_path, patch_output = generate_mainline_patch(
            mainline_commit, mainline_repo_path
        )
        if not patch_path:
            results["patch_generation_error"] = patch_output
            return results

        developer_patch_diff, patch_err = generate_developer_backport_patch(
            backport_commit, target_repo_path
        )
        if patch_err:
            results["developer_patch_error"] = patch_err
            return results

        # Save both patches to the results folder
        project_dir = os.path.join(RESULTS_DIR, project, patch_id)
        os.makedirs(project_dir, exist_ok=True)
        
        mainline_patch_file = os.path.join(project_dir, "mainline.patch")
        with open(mainline_patch_file, "w", encoding="utf-8") as f:
            f.write(patch_output)
        print(f"[{project}/{patch_id}] Saved mainline patch to {mainline_patch_file}")
        
        target_patch_file = os.path.join(project_dir, "target.patch")
        with open(target_patch_file, "w", encoding="utf-8") as f:
            f.write(developer_patch_diff)
        print(f"[{project}/{patch_id}] Saved target patch to {target_patch_file}")

        analyzer = PatchAnalyzer()
        full_patch_analysis = analyzer.analyze(patch_output, with_test_changes=True)
        java_only_patch_analysis = [
            fc for fc in full_patch_analysis if _is_java_code_file(fc.file_path)
        ]
        developer_aux_hunks = _build_auxiliary_hunks_from_developer_patch(
            developer_patch_diff
        )

        save_pipeline_log(
            project,
            patch_id,
            "phase0",
            f"# Phase 0 Inputs\n\n"
            f"- Mainline commit: {mainline_commit}\n"
            f"- Backport commit: {backport_commit}\n"
            f"- Java-only files for agentic phases: {len(java_only_patch_analysis)}\n"
            f"- Developer auxiliary hunks (test + non-Java): {len(developer_aux_hunks)}\n\n"
            f"## Mainline Patch\n```diff\n{patch_output}\n```\n",
        )

        inputs = {
            "messages": ["Start"],
            "patch_path": patch_path,
            "patch_diff": patch_output,
            "patch_analysis": java_only_patch_analysis,
            "target_repo_path": target_repo_path,
            "mainline_repo_path": mainline_repo_path,
            "experiment_mode": True,
            "backport_commit": backport_commit,
            "original_commit": mainline_commit,
            "skip_phase_0": False,
            "compile_only": False,
            "apply_only_validation": False,
            "skip_compilation_checks": False,
            "evaluation_full_workflow": True,
            "with_test_changes": False,
            "developer_auxiliary_hunks": developer_aux_hunks,
            "use_phase_0_cache": True,
        }

        phase0_cache = _load_phase0_cache(project, backport_commit, mainline_commit)
        phase0_cache_transition = None
        if phase0_cache:
            reusable, reuse_reason = _is_phase0_cache_reusable(phase0_cache)
            if not reusable:
                print(
                    f"[{project}/{patch_id}] Ignoring stale Phase 0 cache "
                    f"(reason={reuse_reason}). Running fresh Phase 0."
                )
                save_pipeline_log(
                    project,
                    patch_id,
                    "phase0_cache_reuse",
                    "# Phase 0 Cache Reuse\n\n"
                    f"- Cache file: {_phase0_cache_file(project, backport_commit, mainline_commit)}\n"
                    "- Decision: ignored\n"
                    f"- Reason: {reuse_reason}\n",
                )
                phase0_cache = None

        if phase0_cache:
            print(
                f"[{project}/{patch_id}] Found cached Phase 0 results. Skipping Phase 0 and reusing baseline test state."
            )
            inputs["skip_phase_0"] = True
            inputs["phase_0_test_targets"] = phase0_cache.get(
                "phase_0_test_targets", {}
            )
            inputs["phase_0_baseline_test_result"] = phase0_cache.get(
                "phase_0_baseline_test_result", {}
            )
            phase0_cache_transition = phase0_cache.get("phase_0_transition_evaluation")
            phase0_cached_success = bool(phase0_cache.get("fast_path_success", False))
            save_pipeline_log(
                project,
                patch_id,
                "phase0_cache_reuse",
                "# Phase 0 Cache Reuse\n\n"
                f"- Cache file: {_phase0_cache_file(project, backport_commit, mainline_commit)}\n"
                f"- Reused targets: {phase0_cache.get('phase_0_test_targets', {})}\n"
                f"- Reused baseline mode: {(phase0_cache.get('phase_0_baseline_test_result') or {}).get('mode', 'unknown')}\n",
            )

            if phase0_cached_success:
                print(
                    f"[{project}/{patch_id}] Cached Phase 0 fast-path success. Skipping agentic workflow."
                )
                save_pipeline_log(
                    project,
                    patch_id,
                    "transition_summary",
                    _build_transition_summary_markdown(
                        phase0_cache_transition,
                        "phase0_cache",
                        phase_outputs={},
                        phase0_cache=phase0_cache,
                    ),
                )

                results["phases"] = {
                    "phase0_cache": {
                        "phase_0_optimistic": {
                            "outputs": {
                                "fast_path_success": True,
                                "phase_0_test_targets": phase0_cache.get(
                                    "phase_0_test_targets", {}
                                ),
                                "phase_0_baseline_test_result": phase0_cache.get(
                                    "phase_0_baseline_test_result", {}
                                ),
                                "phase_0_post_patch_test_result": phase0_cache.get(
                                    "phase_0_post_patch_test_result", {}
                                ),
                                "phase_0_transition_evaluation": phase0_cache_transition,
                            }
                        }
                    }
                }
                results["status"] = "completed"
                results["cache_decision"] = {
                    "phase0_cache_used": True,
                    "phase0_fast_path_success": True,
                    "agentic_workflow_skipped": True,
                }
                results["exact_developer_patch"] = None
                results["developer_patch_comparison"] = {
                    "skipped": True,
                    "reason": "Skipped: cached Phase 0 fast-path success.",
                }

                results_file = os.path.join(
                    RESULTS_DIR, project, patch_id, "pipeline_results.json"
                )
                with open(results_file, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, default=str)

                print(
                    f"[{project}/{patch_id}] Completed from cache without agentic workflow."
                )
                return results

        print(f"[{project}/{patch_id}] Running full workflow graph...")
        phase_outputs = defaultdict(dict)
        current_phase = None
        latest_adapted_code_hunks = []

        async for output in app.astream(inputs):
            for node_name, node_output in output.items():
                print(f"  Completed: {node_name}")

                if (
                    isinstance(node_output, dict)
                    and "adapted_code_hunks" in node_output
                ):
                    latest_adapted_code_hunks = (
                        node_output.get("adapted_code_hunks") or []
                    )

                if node_name in ["phase_0_optimistic"]:
                    current_phase = "phase0"
                elif node_name in ["context_analyzer"]:
                    current_phase = "phase1_context_analyzer"
                elif node_name in ["structural_locator"]:
                    current_phase = "phase2_structural_locator"
                elif node_name in ["hunk_generator"]:
                    current_phase = "phase3_hunk_generator"
                elif node_name in ["validation"]:
                    current_phase = "phase4_validation"
                else:
                    current_phase = node_name

                phase_data = {
                    "node": node_name,
                    "outputs": {},
                }

                skip_keys = {"messages"}
                for key, value in node_output.items():
                    if key not in skip_keys:
                        phase_data["outputs"][key] = value

                if current_phase:
                    save_agent_state(
                        project,
                        patch_id,
                        current_phase,
                        phase_data["outputs"],
                        node_name,
                    )
                    phase_outputs[current_phase][node_name] = phase_data

        # Full comparison input: Java hunks generated by agents + developer-owned auxiliary hunks.
        final_adapted_code_hunks = latest_adapted_code_hunks + (
            developer_aux_hunks or []
        )

        comparison = compare_generated_with_developer_patch(
            adapted_code_hunks=final_adapted_code_hunks,
            developer_patch_diff=developer_patch_diff,
            backport_commit=backport_commit,
            target_repo_path=target_repo_path,
        )
        results["exact_developer_patch"] = comparison["exact_developer_patch"]
        results["developer_patch_comparison"] = {
            "comparison_method": comparison.get("comparison_method", "file_state"),
            "compared_files": comparison.get("compared_files", []),
            "mismatched_files": comparison.get("mismatched_files", []),
            "developer_files": comparison.get("developer_files", []),
            "generated_files": comparison.get("generated_files", []),
            "error": comparison.get("error"),
        }

        save_pipeline_log(
            project,
            patch_id,
            "post_pipeline_developer_patch_compare",
            "# Post-Pipeline Developer Patch Comparison\n\n"
            f"**Exact Developer Patch (code-only)**: {comparison['exact_developer_patch']}\n\n"
            f"**Comparison Method**: {comparison.get('comparison_method', 'file_state')}\n\n"
            "## File State Comparison\n"
            f"- Compared files: {comparison.get('compared_files', [])}\n"
            f"- Mismatched files: {comparison.get('mismatched_files', [])}\n"
            f"- Error: {comparison.get('error')}\n\n"
            "## Hunk-by-Hunk Comparison\n\n"
            + _build_hunk_comparison_markdown(
                final_adapted_code_hunks, developer_patch_diff, analyzer
            )
            + "\n## Full Generated Patch (code-only)\n"
            f"```diff\n{comparison['generated_patch_diff']}\n```\n"
            "## Full Developer Backport Patch (full commit diff)\n"
            f"```diff\n{developer_patch_diff}\n```\n",
        )

        transition_eval = _extract_transition_eval_from_outputs(dict(phase_outputs))
        transition_source = "phase_outputs"
        if not transition_eval and phase0_cache_transition:
            transition_eval = phase0_cache_transition
            transition_source = "phase0_cache"

        save_pipeline_log(
            project,
            patch_id,
            "transition_summary",
            _build_transition_summary_markdown(
                transition_eval,
                transition_source,
                phase_outputs=dict(phase_outputs),
                phase0_cache=phase0_cache,
            ),
        )

        results["phases"] = dict(phase_outputs)
        results["status"] = "completed"

        results_file = os.path.join(
            RESULTS_DIR, project, patch_id, "pipeline_results.json"
        )
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)

        print(f"[{project}/{patch_id}] Full workflow completed!")
        return results

    except Exception as e:
        results["error"] = str(e)
        results["status"] = "failed"
        print(f"[{project}/{patch_id}] Workflow failed: {e}")
        return results


def is_patch_processed(project, patch_id):
    patch_results_dir = os.path.join(RESULTS_DIR, project, patch_id)
    results_file = os.path.join(patch_results_dir, "pipeline_results.json")
    return os.path.exists(results_file)


async def main():
    configure_logging()
    print("=" * 80)
    print(f"FULL WORKFLOW EVALUATION (Phase 0-4, {', '.join(TARGET_PROJECTS)})")
    print("=" * 80)

    ensure_dirs()

    if not os.path.exists(DATASET_PATH):
        print(f"ERROR: Dataset not found at {DATASET_PATH}")
        return

    data = []
    with open(DATASET_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Project"] in TARGET_PROJECTS:
                data.append(row)

    print(f"\nFound {len(data)} total patches for target projects: {TARGET_PROJECTS}")

    if MAX_PATCHES_PER_PROJECT:
        data_limited = defaultdict(list)
        for row in data:
            data_limited[row["Project"]].append(row)

        data = []
        for project in TARGET_PROJECTS:
            data.extend(data_limited[project][:MAX_PATCHES_PER_PROJECT])

    print(f"Processing {len(data)} patches")

    all_results = []
    skipped_patches = []
    for idx, row in enumerate(data, 1):
        project = row["Project"]
        mainline_commit = row["Original Commit"]
        backport_commit = row["Backport Commit"]
        patch_id = f"{project}_{mainline_commit[:8]}"

        if is_patch_processed(project, patch_id):
            print(f"\n[{idx}/{len(data)}] SKIPPING (already processed): {patch_id}")
            skipped_patches.append(patch_id)
            continue

        print(f"\n[{idx}/{len(data)}] Processing: {patch_id}")

        mainline_repo_path = os.path.join(REPOS_DIR, project)
        target_repo_path = os.path.join(REPOS_DIR, project)

        print(f"[{project}/{patch_id}] Cleaning repositories...")
        for repo_path in [mainline_repo_path, target_repo_path]:
            if os.path.exists(repo_path):
                subprocess.run(
                    ["git", "reset", "--hard", "HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "clean", "-fd"], cwd=repo_path, capture_output=True
                )

        if not os.path.exists(mainline_repo_path):
            print(f"  ERROR: Repository not found at {mainline_repo_path}")
            continue

        result = await run_full_pipeline(
            project,
            patch_id,
            mainline_commit,
            backport_commit,
            mainline_repo_path,
            target_repo_path,
        )
        all_results.append(result)

        temp_patch_path = os.path.join(RESULTS_DIR, "temp_mainline.patch")
        if os.path.exists(temp_patch_path):
            try:
                os.remove(temp_patch_path)
            except Exception as e:
                print(f"  Warning: Could not remove temp patch file: {e}")

    summary_file = os.path.join(RESULTS_DIR, "pipeline_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)

    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    completed = sum(1 for r in all_results if r.get("status") == "completed")
    failed = sum(1 for r in all_results if r.get("status") == "failed")
    print(f"Total Patches in Dataset: {len(data)}")
    print(f"Skipped (already processed): {len(skipped_patches)}")
    print(f"Newly Processed: {len(all_results)}")
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    if skipped_patches:
        print(f"\nSkipped Patches: {', '.join(skipped_patches)}")
    print(f"Results Directory: {RESULTS_DIR}")
    print(f"Summary Report: {summary_file}")


if __name__ == "__main__":
    asyncio.run(main())
