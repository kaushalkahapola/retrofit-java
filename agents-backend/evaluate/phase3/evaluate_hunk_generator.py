import json
import os
import csv
import subprocess
import asyncio
import argparse
from dotenv import load_dotenv
from collections import defaultdict

# Needed because we might run this from the evaluate/phase3 dir
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from state import AgentState
from agents.hunk_generator import hunk_generator_node
from utils.patch_analyzer import PatchAnalyzer

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", "all_projects_final.csv")
REPOS_DIR = os.path.join(BASE_DIR, "temp_repo_storage")

PHASE2_RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "phase2", "structural_locator_results.json")
OUTPUT_JSON_PATH = os.path.join(os.path.dirname(__file__), "hunk_generator_results.json")
SUMMARY_TXT_PATH = os.path.join(os.path.dirname(__file__), "summary.txt")

def run_cmd(cmd, cwd, env=None):
    try:
        result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, env=env)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr or e.stdout


def extract_raw_hunks(diff_text: str) -> dict:
    """
    Simple hunk extraction from diff text.
    Returns {file_path: [hunk_texts]}
    """
    hunks_by_file = {}
    current_file = None
    current_hunk = []
    
    for line in diff_text.splitlines(keepends=True):
        # File header
        if line.startswith("+++"):
            if current_hunk and current_file:
                hunks_by_file.setdefault(current_file, []).append("".join(current_hunk))
                current_hunk = []
            # Extract filename from +++ b/path/to/file
            current_file = line[6:].strip() if len(line) > 6 else None
        # Hunk header
        elif line.startswith("@@"):
            if current_hunk and current_file:
                hunks_by_file.setdefault(current_file, []).append("".join(current_hunk))
            current_hunk = [line]
        # Hunk content
        elif current_hunk and line and line[0] in (" ", "+", "-", "\\"):
            current_hunk.append(line)
    
    if current_hunk and current_file:
        hunks_by_file.setdefault(current_file, []).append("".join(current_hunk))
    
    return hunks_by_file


def try_apply_hunk(repo_path: str, target_file: str, hunk_text: str) -> tuple[bool, str]:
    """
    Try to apply a single hunk to the target file using git apply.
    Returns (success, output_message)
    """
    try:
        # Construct a proper unified diff patch with file headers
        patch_content = f"""--- a/{target_file}
+++ b/{target_file}
{hunk_text}"""
        
        # Write patch to a temporary file
        patch_file = f"/tmp/{target_file.replace('/', '_')}_temp.patch"
        with open(patch_file, "w") as f:
            f.write(patch_content)
        
        # Try to apply with git apply --check (dry-run)
        success, output = run_cmd(["git", "apply", "--check", patch_file], cwd=repo_path)
        if success:
            # Actually apply it
            success, output = run_cmd(["git", "apply", patch_file], cwd=repo_path)
            return success, output
        else:
            return False, f"Dry-run failed: {output}"
    except Exception as e:
        return False, str(e)


async def main():
    parser = argparse.ArgumentParser(description="Evaluate Phase 3 Hunk Generator")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of new rows to evaluate per run")
    args = parser.parse_args()

    print("Starting Phase 3 evaluation (Hunk Generator)...")

    if not os.path.exists(PHASE2_RESULTS_PATH):
        print(f"Phase 2 results not found at: {PHASE2_RESULTS_PATH}")
        return

    # Load Phase 2 results
    with open(PHASE2_RESULTS_PATH, "r", encoding="utf-8") as f:
        phase2_data = json.load(f)

    # Filter for successful Phase 2 analyses (file_match + region_overlap)
    eligible_backports = [d for d in phase2_data if d.get("overall_file_match") and d.get("overall_region_overlap")]
    print(f"Found {len(eligible_backports)} successful Phase 2 analyses (file_match + region_overlap) to evaluate.")

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

        # 2. Extract mainline patch for analysis and hunk extraction
        success, patch_diff = run_cmd(["git", "format-patch", "-1", mainline_commit, "--stdout"], cwd=repo_path)
        if not success:
            print(f"  [ERROR] Failed to extract mainline patch.")
            continue

        patch_analysis = analyzer.analyze(patch_diff)

        # 3. Build state for hunk_generator_node
        # Get the semantic blueprint and consistency map from phase2 results
        semantic_blueprint = {
            "root_cause_hypothesis": entry.get("root_cause", ""),
            "fix_logic": entry.get("fix_logic", ""),
            "dependent_apis": entry.get("dependent_apis", [])
        }
        
        consistency_map = entry.get("consistency_map", {})
        mapped_target_context = {}
        
        # Reconstruct mapped_target_context from phase2 results
        for file_result in entry.get("results", []):
            mainline_file = file_result.get("mainline_file")
            target_file = file_result.get("mapped_target_file")
            start_line = file_result.get("mapped_range", [None, None])[0]
            end_line = file_result.get("mapped_range", [None, None])[1]
            
            if mainline_file and target_file and start_line is not None:
                mapped_target_context[mainline_file] = {
                    "target_file": target_file,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code_snippet": ""  # Will be empty for now; hunk_generator can work with this
                }

        # Set up environment variables for LLM
        os.environ["STRUCTURAL_LOCATOR_PROVIDER"] = "azure"
        os.environ["HUNK_GENERATOR_PROVIDER"] = "azure"
        os.environ["AZURE_CHAT_DEPLOYMENT"] = "apim-4o-mini"
        os.environ["AZURE_CHAT_VERSION"] = "2024-02-01"
        os.environ["AZURE_ENDPOINT"] = "https://apim-ai-aus.openai.azure.com/"
        
        state = {
            "semantic_blueprint": semantic_blueprint,
            "consistency_map": consistency_map,
            "mapped_target_context": mapped_target_context,
            "patch_analysis": patch_analysis,
            "patch_diff": patch_diff,
            "target_repo_path": repo_path,
            "mainline_repo_path": repo_path,
            "validation_attempts": 0,
            "validation_error_context": ""
        }

        try:
            print("  Running hunk_generator_node...")
            result_state = await hunk_generator_node(state, config=None)
            
            adapted_code_hunks = result_state.get("adapted_code_hunks", [])
            adapted_test_hunks = result_state.get("adapted_test_hunks", [])
            
            print(f"  Generated {len(adapted_code_hunks)} code hunks and {len(adapted_test_hunks)} test hunks")
            
            # 4. Try to apply the hunks and evaluate
            evaluation = {
                "project": project,
                "mainline_commit": mainline_commit,
                "backport_commit": backport_commit,
                "patch_type": patch_type,
                "generated_hunks": len(adapted_code_hunks),
                "generated_test_hunks": len(adapted_test_hunks),
                "adapted_code_hunks": adapted_code_hunks,
                "adapted_test_hunks": adapted_test_hunks,
                "hunk_results": [],
                "all_hunks_applied": False,
                "status": "Generated"
            }
            
            # Reset repo to backport parent again (in case hunk_generator modified it)
            run_cmd(["git", "reset", "--hard", "HEAD"], cwd=repo_path)
            
            successful_applications = 0
            failed_applications = 0
            
            # Try to apply code hunks
            for hunk in adapted_code_hunks:
                target_file = hunk.get("target_file")
                hunk_text = hunk.get("hunk_text")
                
                apply_success, apply_msg = try_apply_hunk(repo_path, target_file, hunk_text)
                
                if apply_success:
                    successful_applications += 1
                    result = "Applied"
                else:
                    failed_applications += 1
                    result = f"Failed: {apply_msg[:100]}"
                
                evaluation["hunk_results"].append({
                    "target_file": target_file,
                    "application_status": result,
                    "hunk_size_lines": len(hunk_text.splitlines()),
                    "hunk_text": hunk_text
                })
                
                print(f"    {target_file}: {result}")
            
            evaluation["all_hunks_applied"] = (failed_applications == 0 and successful_applications > 0)
            
            print(f"  -> SUCCESS. Applied: {successful_applications}, Failed: {failed_applications}")
            results.append(evaluation)

        except Exception as e:
            print(f"  [ERROR] Hunk Generator failed: {e}")
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

    # 5. Final Summary
    print("\n" + "="*80)
    print("PHASE 3 EVALUATION SUMMARY")
    print("="*80)
    
    total_evals = len([r for r in results if "all_hunks_applied" in r])
    all_applied = len([r for r in results if r.get("all_hunks_applied")])
    
    summary_data = {
        "total_evaluated": total_evals,
        "all_hunks_applied": all_applied,
        "success_rate": (all_applied / total_evals * 100) if total_evals > 0 else 0
    }
    
    print(f"\nTotal evaluated: {total_evals}")
    print(f"All hunks applied: {all_applied}")
    print(f"Success rate: {summary_data['success_rate']:.2f}%")
    
    # Per project stats
    project_stats = defaultdict(lambda: {"total": 0, "applied": 0})
    for r in results:
        if "all_hunks_applied" in r:
            proj = r.get("project")
            project_stats[proj]["total"] += 1
            if r.get("all_hunks_applied"):
                project_stats[proj]["applied"] += 1
    
    print("\nPer-project statistics:")
    for proj, stats in sorted(project_stats.items()):
        rate = (stats["applied"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"  {proj}: {stats['applied']}/{stats['total']} ({rate:.2f}%)")
    
    # Write summary
    with open(SUMMARY_TXT_PATH, "w", encoding="utf-8") as f:
        f.write("# Phase 3 (Hunk Generator) Evaluation Summary\n\n")
        f.write(f"Total evaluated: {total_evals}\n")
        f.write(f"All hunks applied: {all_applied}\n")
        f.write(f"Success rate: {summary_data['success_rate']:.2f}%\n\n")
        f.write("Per-project statistics:\n")
        for proj, stats in sorted(project_stats.items()):
            rate = (stats["applied"] / stats["total"] * 100) if stats["total"] > 0 else 0
            f.write(f"  {proj}: {stats['applied']}/{stats['total']} ({rate:.2f}%)\n")
    
    print(f"\nSummary written to: {SUMMARY_TXT_PATH}")
    print(f"Results written to: {OUTPUT_JSON_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
