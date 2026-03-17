"""
Full Pipeline Evaluation Script (Phase 0-4)

Runs the complete H-MABS pipeline end-to-end for druid and elasticsearch patches.
Saves all outputs from each phase for analysis.

NOTE: Skips phase 0 completely and uses compile-only mode (no test execution).
"""

import asyncio
import csv
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Any

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from state import AgentState
from graph import app
from utils.patch_analyzer import PatchAnalyzer
from dotenv import load_dotenv

load_dotenv()

# Configuration
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", "all_projects_final.csv")
REPOS_DIR = os.path.join(BASE_DIR, "temp_repo_storage")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

TARGET_PROJECTS = ["druid"]
MAX_PATCHES_PER_PROJECT = 5  # Limit for testing; set to None for all


def ensure_dirs():
    """Create necessary directories."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    for project in TARGET_PROJECTS:
        os.makedirs(os.path.join(RESULTS_DIR, project), exist_ok=True)


def run_cmd(cmd, cwd, env=None, timeout=None):
    """Run a shell command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr or e.stdout
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout} seconds"
    except Exception as e:
        return False, str(e)


def setup_repos(mainline_commit, backport_commit, project, mainline_repo_path, target_repo_path):
    """Set up mainline and target repositories at specified commits."""
    # Checkout mainline
    success, output = run_cmd(
        ["git", "checkout", mainline_commit],
        cwd=mainline_repo_path,
        timeout=30
    )
    if not success:
        return False, f"Failed to checkout mainline commit {mainline_commit}: {output}"
    
    # Checkout target (parent of backport commit for experiment mode)
    success, output = run_cmd(
        ["git", "checkout", f"{backport_commit}^"],
        cwd=target_repo_path,
        timeout=30
    )
    if not success:
        return False, f"Failed to checkout target commit {backport_commit}^: {output}"
    
    return True, "Repos set up successfully"


def generate_mainline_patch(mainline_commit, mainline_repo_path):
    """Generate patch from mainline commit."""
    patch_path = os.path.join(RESULTS_DIR, "temp_mainline.patch")
    
    success, output = run_cmd(
        ["git", "format-patch", "-1", mainline_commit, "--stdout"],
        cwd=mainline_repo_path,
        timeout=30
    )
    
    if not success:
        return None, f"Failed to generate patch: {output}"
    
    # Write patch to file
    try:
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(output)
        return patch_path, output
    except Exception as e:
        return None, f"Failed to write patch file: {str(e)}"


def generate_developer_backport_patch(backport_commit, target_repo_path):
    """Generate developer backport patch from the committed backport change."""
    success, output = run_cmd(
        ["git", "show", "--format=", "--no-color", backport_commit],
        cwd=target_repo_path,
        timeout=30,
    )
    if not success:
        return None, f"Failed to generate developer backport patch for {backport_commit}: {output}"
    return output, None


def _build_hunk_comparison_markdown(adapted_code_hunks, developer_patch_diff, analyzer):
    """
    Build a markdown string with hunk-by-hunk stacked comparison.
    For each hunk: Developer block first, Generated block below it.
    """
    # Extract developer hunks by file
    developer_hunks_by_file = analyzer.extract_raw_hunks(developer_patch_diff, with_test_changes=False)
    
    # Group generated hunks by file
    generated_hunks_by_file = {}
    for hunk in adapted_code_hunks:
        file = hunk['target_file']
        if file not in generated_hunks_by_file:
            generated_hunks_by_file[file] = []
        generated_hunks_by_file[file].append(hunk['hunk_text'])
    
    # Get all files
    all_files = set(generated_hunks_by_file.keys()) | set(developer_hunks_by_file.keys())
    
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


def _build_generated_patch_from_hunks(adapted_code_hunks: list[dict[str, Any]]) -> str:
    """Build a code-only unified diff from Agent 3 generated hunks."""
    hunks_by_file: dict[str, dict[str, Any]] = {}
    file_order: list[str] = []

    for hunk in adapted_code_hunks or []:
        target_file = hunk.get("target_file")
        if not target_file:
            continue

        if target_file not in hunks_by_file:
            hunks_by_file[target_file] = {
                "file_operation": hunk.get("file_operation") or "MODIFIED",
                "hunks": [],
            }
            file_order.append(target_file)

        hunks_by_file[target_file]["hunks"].append(hunk.get("hunk_text", ""))

    lines: list[str] = []
    for target_file in file_order:
        payload = hunks_by_file[target_file]
        op = (payload.get("file_operation") or "MODIFIED").upper()

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


def _normalize_hunk_header_for_operation(hunk_text: str, file_operation: str) -> str:
    """
    Normalize hunk header ranges for ADDED/DELETED files so git apply --cached
    can apply against a tree-backed temporary index.
    """
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


def _is_test_file(file_path: str) -> bool:
    lower_path = (file_path or "").lower()
    return "test" in lower_path or lower_path.endswith("test.java")


def _get_non_test_changed_files(commit, repo_path):
    """Get non-test files touched by a commit."""
    success, output = run_cmd(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
        cwd=repo_path,
        timeout=30,
    )
    if not success:
        return None, output

    files = [line.strip() for line in output.splitlines() if line.strip()]
    files = [f for f in files if not _is_test_file(f)]
    return sorted(set(files)), None


def _get_blob_id_from_commit(repo_path, commit, rel_path):
    """Return blob id for commit:path, or None if file does not exist."""
    success, output = run_cmd(
        ["git", "rev-parse", f"{commit}:{rel_path}"],
        cwd=repo_path,
        timeout=30,
    )
    if not success:
        return None
    return output.strip() or None


def _get_blob_id_from_index(repo_path, rel_path, env):
    """Return blob id for :path from a temporary git index, or None if missing."""
    success, output = run_cmd(
        ["git", "rev-parse", f":{rel_path}"],
        cwd=repo_path,
        env=env,
        timeout=30,
    )
    if not success:
        return None
    return output.strip() or None


def _apply_patch_with_temp_index(repo_path, patch_file_path, env):
    """Apply patch to a temporary index only (no checkout/worktree mutation)."""
    attempts = [
        ["git", "apply", "--cached", "--recount", "--whitespace=nowarn", patch_file_path],
        [
            "git", "apply", "--cached", "--recount", "--ignore-space-change",
            "--ignore-whitespace", "--whitespace=nowarn", patch_file_path,
        ],
    ]

    errors = []
    for cmd in attempts:
        success, output = run_cmd(cmd, cwd=repo_path, env=env, timeout=30)
        if success:
            return True, ""
        errors.append(output)

    return False, "\n\n".join(errors)


def compare_generated_with_developer_patch(adapted_code_hunks, developer_patch_diff, backport_commit, target_repo_path):
    """
    Compare generated vs developer patch by final non-test file state.
    This avoids false negatives caused by hunk/header formatting differences.
    """
    generated_patch_diff = _build_generated_patch_from_hunks(adapted_code_hunks or [])
    generated_files = sorted(
        {
            h.get("target_file")
            for h in (adapted_code_hunks or [])
            if h.get("target_file") and not _is_test_file(h.get("target_file"))
        }
    )

    developer_files, files_err = _get_non_test_changed_files(backport_commit, target_repo_path)
    if files_err:
        return {
            "exact_developer_patch": False,
            "comparison_method": "file_state",
            "error": f"Failed to get changed files for {backport_commit}: {files_err}",
            "generated_patch_diff": generated_patch_diff,
        }

    files_to_compare = sorted(set((developer_files or []) + generated_files))

    with tempfile.NamedTemporaryFile(prefix="git_index_", suffix=".tmp", delete=False) as index_file:
        temp_index_path = index_file.name

    with tempfile.NamedTemporaryFile(prefix="generated_eval_", suffix=".patch", delete=False, mode="w", encoding="utf-8") as patch_file:
        patch_file.write(generated_patch_diff)
        generated_patch_file = patch_file.name

    index_env = dict(os.environ)
    index_env["GIT_INDEX_FILE"] = temp_index_path

    try:
        # Seed temporary index with parent-of-backport tree.
        success, output = run_cmd(
            ["git", "read-tree", f"{backport_commit}^"],
            cwd=target_repo_path,
            env=index_env,
            timeout=60,
        )
        if not success:
            return {
                "exact_developer_patch": False,
                "comparison_method": "file_state",
                "error": f"Failed to seed temporary index from {backport_commit}^: {output}",
                "generated_patch_diff": generated_patch_diff,
            }

        if generated_patch_diff.strip():
            apply_ok, apply_err = _apply_patch_with_temp_index(target_repo_path, generated_patch_file, index_env)
            if not apply_ok:
                return {
                    "exact_developer_patch": False,
                    "comparison_method": "file_state",
                    "error": f"Failed to apply generated patch in temporary index: {apply_err}",
                    "generated_patch_diff": generated_patch_diff,
                }

        mismatched_files = []
        for rel_path in files_to_compare:
            developer_blob = _get_blob_id_from_commit(target_repo_path, backport_commit, rel_path)
            generated_blob = _get_blob_id_from_index(target_repo_path, rel_path, index_env)
            if developer_blob != generated_blob:
                mismatched_files.append(rel_path)

        return {
            "exact_developer_patch": len(mismatched_files) == 0,
            "comparison_method": "file_state",
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

    return {
        "exact_developer_patch": False,
        "comparison_method": "file_state",
        "error": "Unexpected comparison flow exit",
        "generated_patch_diff": generated_patch_diff,
    }


def save_agent_state(project, patch_id, phase_name, state_dict, agent_name=None):
    """Save agent state/output to JSON file."""
    project_dir = os.path.join(RESULTS_DIR, project, patch_id)
    os.makedirs(project_dir, exist_ok=True)
    
    output_file = os.path.join(
        project_dir,
        f"{phase_name}_{agent_name}.json" if agent_name else f"{phase_name}_state.json"
    )
    
    # Convert state to serializable format
    serializable_state = {}
    for key, value in state_dict.items():
        try:
            json.dumps(value)  # Test if serializable
            serializable_state[key] = value
        except (TypeError, ValueError):
            # Skip non-serializable values
            serializable_state[key] = str(value)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable_state, f, indent=2, default=str)
    
    return output_file


def save_pipeline_log(project, patch_id, phase_name, log_content):
    """Save pipeline execution log to markdown file."""
    project_dir = os.path.join(RESULTS_DIR, project, patch_id)
    os.makedirs(project_dir, exist_ok=True)
    
    log_file = os.path.join(project_dir, f"{phase_name}_log.md")
    
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(log_content)
    
    return log_file


async def run_full_pipeline(
    project,
    patch_id,
    mainline_commit,
    backport_commit,
    mainline_repo_path,
    target_repo_path
):
    """
    Run the full H-MABS pipeline for a single patch.
    
    Returns:
        dict: Results with status and agent outputs
    """
    results = {
        "project": project,
        "patch_id": patch_id,
        "mainline_commit": mainline_commit,
        "backport_commit": backport_commit,
        "timestamp": datetime.now().isoformat(),
        "phases": {}
    }
    
    try:
        # Setup repositories
        print(f"\n[{project}/{patch_id}] Setting up repositories...")
        success, output = setup_repos(
            mainline_commit,
            backport_commit,
            project,
            mainline_repo_path,
            target_repo_path
        )
        if not success:
            results["setup_error"] = output
            return results
        
        # Generate mainline patch
        print(f"[{project}/{patch_id}] Generating mainline patch...")
        patch_path, patch_output = generate_mainline_patch(mainline_commit, mainline_repo_path)
        if not patch_path:
            results["patch_generation_error"] = patch_output
            return results
        
        # Save patch info
        save_pipeline_log(
            project, patch_id, "phase0",
            f"# Phase 0: Patch Information\n\n"
            f"**Mainline Commit**: {mainline_commit}\n\n"
            f"**Patch Content**:\n```diff\n{patch_output}\n```"
        )
        
        # Parse patch analysis
        analyzer = PatchAnalyzer()
        patch_analysis = analyzer.analyze(patch_output)
        
        # Prepare graph inputs
        inputs = {
            "messages": ["Start"],
            "patch_path": patch_path,
            "patch_diff": patch_output,
            "patch_analysis": patch_analysis,
            "target_repo_path": target_repo_path,
            "mainline_repo_path": mainline_repo_path,
            "experiment_mode": True,
            "backport_commit": backport_commit,
            "original_commit": mainline_commit,
            "skip_phase_0": True,
            "compile_only": True,
            "with_test_changes": False  # Ignore test changes by default
        }
        
        # Run graph and collect outputs
        print(f"[{project}/{patch_id}] Running full pipeline...")
        phase_outputs = defaultdict(dict)
        current_phase = None
        
        latest_adapted_code_hunks = []

        async for output in app.astream(inputs):
            for node_name, node_output in output.items():
                print(f"  Completed: {node_name}")

                if isinstance(node_output, dict) and "adapted_code_hunks" in node_output:
                    latest_adapted_code_hunks = node_output.get("adapted_code_hunks") or []
                
                # Determine phase from node name
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
                
                # Extract key outputs from node
                phase_data = {
                    "node": node_name,
                    "outputs": {}
                }
                
                # Skip some large outputs
                skip_keys = {"messages"}
                for key, value in node_output.items():
                    if key not in skip_keys:
                        phase_data["outputs"][key] = value
                
                # Save phase outputs
                if current_phase:
                    save_agent_state(project, patch_id, current_phase, phase_data["outputs"], node_name)
                    phase_outputs[current_phase][node_name] = phase_data

        # Post-pipeline evaluation step (outside the agent workflow)
        print(f"[{project}/{patch_id}] Comparing generated patch with developer backport patch...")
        developer_patch_diff, patch_err = generate_developer_backport_patch(backport_commit, target_repo_path)
        if patch_err:
            results["exact_developer_patch"] = False
            results["developer_patch_compare_error"] = patch_err
        else:
            comparison = compare_generated_with_developer_patch(
                adapted_code_hunks=latest_adapted_code_hunks,
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
                "## Hunk-by-Hunk Comparison\n\n" +
                _build_hunk_comparison_markdown(latest_adapted_code_hunks, developer_patch_diff, analyzer) +
                "\n## Full Generated Patch (code-only)\n"
                f"```diff\n{comparison['generated_patch_diff']}\n```\n"
                "## Full Developer Backport Patch (full commit diff)\n"
                f"```diff\n{developer_patch_diff}\n```\n",
            )
        
        # Save summary of all phases
        results["phases"] = dict(phase_outputs)
        results["status"] = "completed"
        
        # Save full results
        results_file = os.path.join(RESULTS_DIR, project, patch_id, "pipeline_results.json")
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"[{project}/{patch_id}] Pipeline completed!")
        return results
        
    except Exception as e:
        results["error"] = str(e)
        results["status"] = "failed"
        print(f"[{project}/{patch_id}] Pipeline failed: {e}")
        return results


def is_patch_processed(project, patch_id):
    """Check if a patch has already been processed by looking for results folder."""
    patch_results_dir = os.path.join(RESULTS_DIR, project, patch_id)
    # Consider a patch processed if the directory exists and contains a pipeline_results.json
    results_file = os.path.join(patch_results_dir, "pipeline_results.json")
    return os.path.exists(results_file)


async def main():
    """Main evaluation pipeline."""
    print("=" * 80)
    print("FULL PIPELINE EVALUATION (Phase 0-4)")
    print("=" * 80)
    
    ensure_dirs()
    
    # Read dataset
    if not os.path.exists(DATASET_PATH):
        print(f"ERROR: Dataset not found at {DATASET_PATH}")
        return
    
    data = []
    with open(DATASET_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Project'] in TARGET_PROJECTS:
                data.append(row)
    
    print(f"\nFound {len(data)} total patches for target projects: {TARGET_PROJECTS}")
    
    # Apply per-project limit if specified
    if MAX_PATCHES_PER_PROJECT:
        data_limited = defaultdict(list)
        for row in data:
            data_limited[row['Project']].append(row)
        
        data = []
        for project in TARGET_PROJECTS:
            data.extend(data_limited[project][:MAX_PATCHES_PER_PROJECT])
    
    print(f"Processing {len(data)} patches")
    
    # Process each patch
    all_results = []
    skipped_patches = []
    for idx, row in enumerate(data, 1):
        project = row['Project']
        mainline_commit = row['Original Commit']
        backport_commit = row['Backport Commit']
        patch_id = f"{project}_{mainline_commit[:8]}"
        
        # Check if patch has already been processed
        if is_patch_processed(project, patch_id):
            print(f"\n[{idx}/{len(data)}] SKIPPING (already processed): {patch_id}")
            skipped_patches.append(patch_id)
            continue
        
        print(f"\n[{idx}/{len(data)}] Processing: {patch_id}")
        
        # Get repo paths
        mainline_repo_path = os.path.join(REPOS_DIR, project)
        target_repo_path = os.path.join(REPOS_DIR, project)  # Same repo, different commits
        
        # Clean up repositories before processing
        print(f"[{project}/{patch_id}] Cleaning repositories...")
        for repo_path in [mainline_repo_path, target_repo_path]:
            if os.path.exists(repo_path):
                subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_path, capture_output=True)
                subprocess.run(["git", "clean", "-fd"], cwd=repo_path, capture_output=True)
        
        # Verify repos exist
        if not os.path.exists(mainline_repo_path):
            print(f"  ERROR: Repository not found at {mainline_repo_path}")
            continue
        
        # Run pipeline
        result = await run_full_pipeline(
            project,
            patch_id,
            mainline_commit,
            backport_commit,
            mainline_repo_path,
            target_repo_path
        )
        all_results.append(result)
        
        # Clean up temp patch file
        temp_patch_path = os.path.join(RESULTS_DIR, "temp_mainline.patch")
        if os.path.exists(temp_patch_path):
            try:
                os.remove(temp_patch_path)
            except Exception as e:
                print(f"  Warning: Could not remove temp patch file: {e}")
    
    # Save summary report
    summary_file = os.path.join(RESULTS_DIR, "pipeline_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    
    # Print summary
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
