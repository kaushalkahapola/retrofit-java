import json
import os
import csv
import subprocess
import asyncio
import argparse
from dotenv import load_dotenv

# Needed because we might run this from the evaluate/phase2 dir
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from state import AgentState
from agents.structural_locator import structural_locator_node
from utils.patch_analyzer import PatchAnalyzer

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", "all_projects_final.csv")
REPOS_DIR = os.path.join(BASE_DIR, "temp_repo_storage")

PHASE1_RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "phase1", "phase1_context_analyzer_results.json")
OUTPUT_JSON_PATH = os.path.join(os.path.dirname(__file__), "structural_locator_results.json")
SUMMARY_TXT_PATH = os.path.join(os.path.dirname(__file__), "summary.txt")

def run_cmd(cmd, cwd, env=None):
    try:
        result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, env=env)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr or e.stdout

def get_actual_backport_locations(repo_path, backport_commit):
    """
    Parses the backport commit to find the actual target files and line ranges modified.
    Returns: { file_path: [ (start, end), ... ] }
    """
    success, diff = run_cmd(["git", "show", backport_commit], cwd=repo_path)
    if not success:
        return {}
    
    analyzer = PatchAnalyzer()
    changes = analyzer.analyze(diff)
    locations = {}
    
    # We also need the raw hunks to get line numbers
    patch_set = analyzer.parse_diff(diff)
    for patched_file in patch_set:
        file_path = patched_file.path
        ranges = []
        for hunk in patched_file:
            # target_start and target_length correspond to the file AFTER the patch (the backport state)
            # source_start and source_length correspond to the file BEFORE the patch (the backport parent)
            # Structural locator aims to find locations in the backport parent.
            ranges.append((hunk.source_start, hunk.source_start + hunk.source_length - 1))
        locations[file_path] = ranges
        
    return locations

async def main():
    parser = argparse.ArgumentParser(description="Evaluate Phase 2 Structural Locator")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of new rows to evaluate per run")
    args = parser.parse_args()

    print("Starting Phase 2 evaluation (Structural Locator)...")

    if not os.path.exists(PHASE1_RESULTS_PATH):
        print(f"Phase 1 results not found at: {PHASE1_RESULTS_PATH}")
        return

    # Load Phase 1 results
    with open(PHASE1_RESULTS_PATH, "r", encoding="utf-8") as f:
        phase1_data = json.load(f)

    # Filter for successful Phase 1 analyses
    eligible_backports = [d for d in phase1_data if d.get("status") == "Success"]
    print(f"Found {len(eligible_backports)} successful Phase 1 analyses to evaluate.")

    results = []
    evaluated_commits = set()
    
    # Load existing results for resumability
    if os.path.exists(OUTPUT_JSON_PATH):
        try:
            with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
                for r in results:
                    evaluated_commits.add(r.get("mainline_commit"))
            print(f"Loaded {len(results)} existing results. Will skip these.")
        except json.JSONDecodeError:
            print(f"Warning: Could not read {OUTPUT_JSON_PATH}. Starting fresh.")

    analyzer = PatchAnalyzer()
    processed_in_this_run = 0

    for i, entry in enumerate(eligible_backports):
        mainline_commit = entry['mainline_commit']
        
        if mainline_commit in evaluated_commits:
            continue
            
        if args.limit and processed_in_this_run >= args.limit:
            print(f"\nReached the limit of {args.limit} evaluations. Stopping.")
            break
            
        processed_in_this_run += 1
        
        project = entry['project']
        backport_commit = entry['backport_commit']
        patch_type = entry['patch_type']
        
        print(f"\n[{processed_in_this_run}/{args.limit if args.limit else len(eligible_backports)}] Evaluating: {project}, {patch_type}")
        print(f"  Mainline: {mainline_commit}")
        print(f"  Backport: {backport_commit}")

        repo_path = os.path.join(REPOS_DIR, project)
        if not os.path.exists(repo_path):
            print(f"  [ERROR] Repository path does not exist: {repo_path}")
            continue

        # 1. Prepare repository state (checkout backport parent)
        run_cmd(["git", "am", "--abort"], cwd=repo_path)
        run_cmd(["git", "reset", "--hard", "HEAD"], cwd=repo_path)
        run_cmd(["git", "clean", "-fd"], cwd=repo_path)
        
        success, out = run_cmd(["git", "checkout", f"{backport_commit}^"], cwd=repo_path)
        if not success:
            print(f"  [ERROR] Failed to checkout backport parent: {out}")
            continue

        # 2. Extract mainline patch for analysis (required for state)
        success, patch_diff = run_cmd(["git", "format-patch", "-1", mainline_commit, "--stdout"], cwd=repo_path)
        if not success:
             # Try fetching from origin if it's missing (though it should be there if phase 1 worked)
            print(f"  [ERROR] Failed to extract mainline patch.")
            continue

        patch_analysis = analyzer.analyze(patch_diff)

        # 3. Get ground truth locations from the backport commit
        ground_truth = get_actual_backport_locations(repo_path, backport_commit)

        # 4. Run Structural Locator
        os.environ["STRUCTURAL_LOCATOR_PROVIDER"] = "azure"
        os.environ["AZURE_CHAT_DEPLOYMENT"] = "apim-4o-mini"
        os.environ["AZURE_CHAT_VERSION"] = "2024-02-01"
        os.environ["AZURE_ENDPOINT"] = "https://apim-ai-aus.openai.azure.com/"
        
        state = {
            "semantic_blueprint": {
                "root_cause_hypothesis": entry.get("root_cause"),
                "fix_logic": entry.get("fix_logic"),
                "dependent_apis": entry.get("dependent_apis", [])
            },
            "patch_analysis": patch_analysis,
            "patch_diff": patch_diff,
            "target_repo_path": repo_path,
            "mainline_repo_path": repo_path, # In this eval setup, we use the same repo dir but different commits
            "original_commit": mainline_commit
        }

        try:
            print("  Running structural_locator_node...")
            result_state = await structural_locator_node(state, config=None)
            
            mapped_context = result_state.get("mapped_target_context", {})
            consistency_map = result_state.get("consistency_map", {})
            
            # 5. Evaluate results
            evaluation = {
                "project": project,
                "mainline_commit": mainline_commit,
                "backport_commit": backport_commit,
                "patch_type": patch_type,
                "results": [],
                "overall_file_match": False,
                "overall_region_overlap": False
            }
            
            file_matches = 0
            region_overlaps = 0
            total_files = 0
            
            code_changes = [fc for fc in patch_analysis if not fc.is_test_file]
            
            for change in code_changes:
                mainline_file = change.file_path
                mapping = mapped_context.get(mainline_file)
                
                total_files += 1
                target_file = mapping.get("target_file") if mapping else None
                start_line = mapping.get("start_line") if mapping else None
                end_line = mapping.get("end_line") if mapping else None
                
                # Ground truth check
                gt_ranges = ground_truth.get(target_file, []) if target_file else []
                file_match = target_file in ground_truth if target_file else False
                region_overlap = False
                
                # If target_file is not found by name, check if mainline_file path exists in GT
                if not file_match and mainline_file in ground_truth:
                    gt_ranges = ground_truth.get(mainline_file)
                    # We don't mark file_match=True here because the agent failed to find it
                
                if file_match and start_line is not None and end_line is not None:
                    for gt_start, gt_end in gt_ranges:
                        if max(start_line, gt_start) <= min(end_line, gt_end):
                            region_overlap = True
                            break
                
                if file_match: file_matches += 1
                if region_overlap: region_overlaps += 1
                
                evaluation["results"].append({
                    "mainline_file": mainline_file,
                    "mapped_target_file": target_file,
                    "mapped_range": [start_line, end_line],
                    "gt_available": mainline_file in ground_truth,
                    "gt_ranges": gt_ranges,
                    "file_match": file_match,
                    "region_overlap": region_overlap,
                    "status": "Mapped" if target_file else "Failed to map"
                })

            evaluation["overall_file_match"] = (file_matches == total_files) if total_files > 0 else False
            evaluation["overall_region_overlap"] = (region_overlaps == total_files) if total_files > 0 else False
            evaluation["consistency_map"] = consistency_map
            
            print(f"  -> SUCCESS. File Match: {evaluation['overall_file_match']}, Region Overlap: {evaluation['overall_region_overlap']}")
            results.append(evaluation)

        except Exception as e:
            print(f"  [ERROR] Structural Locator failed: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "project": project,
                "mainline_commit": mainline_commit,
                "backport_commit": backport_commit,
                "status": f"Error: {e}"
            })

        # Save results after each iteration
        with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    # 6. Final Summary
    total_evals = len([r for r in results if "overall_file_match" in r])
    file_match_count = len([r for r in results if r.get("overall_file_match")])
    region_overlap_count = len([r for r in results if r.get("overall_region_overlap")])
    
    summary = (
        "Phase 2 (Structural Locator) Evaluation Summary\n"
        "==============================================\n"
        f"Total evaluated: {total_evals}\n"
        f"File Mapping Accuracy: {file_match_count}/{total_evals} ({ (file_match_count/total_evals*100) if total_evals > 0 else 0 :.2f}%)\n"
        f"Region Mapping Accuracy: {region_overlap_count}/{total_evals} ({ (region_overlap_count/total_evals*100) if total_evals > 0 else 0 :.2f}%)\n"
    )
    
    with open(SUMMARY_TXT_PATH, "w", encoding="utf-8") as f:
        f.write(summary)
        
    print("\n" + summary)
    print(f"Results saved to {OUTPUT_JSON_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
