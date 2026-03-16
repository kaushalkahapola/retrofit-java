"""
Full Pipeline Evaluation Script (Phase 0-4)

Runs the complete H-MABS pipeline end-to-end for druid and elasticsearch patches.
Saves all outputs from each phase for analysis.

NOTE: Skips phase 0 completely and uses compile-only mode (no test execution).
"""

import asyncio
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

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
MAX_PATCHES_PER_PROJECT = 1  # Limit for testing; set to None for all


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
            "compile_only": True
        }
        
        # Run graph and collect outputs
        print(f"[{project}/{patch_id}] Running full pipeline...")
        phase_outputs = defaultdict(dict)
        current_phase = None
        
        async for output in app.astream(inputs):
            for node_name, node_output in output.items():
                print(f"  Completed: {node_name}")
                
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
