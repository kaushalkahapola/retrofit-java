import json
import os
import csv
import subprocess
import asyncio
from collections import defaultdict
import argparse
from dotenv import load_dotenv

# Needed because we might run this from the evaluate/phase1 dir
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from state import AgentState
from agents.context_analyzer import context_analyzer_node
from utils.patch_analyzer import PatchAnalyzer

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", "all_projects_final.csv")
REPOS_DIR = os.path.join(BASE_DIR, "temp_repo_storage")

TARGET_PROJECTS = ["druid", "elasticsearch"]

OUTPUT_JSON_PATH = os.path.join(os.path.dirname(__file__), "phase1_context_analyzer_results.json")
SUMMARY_TXT_PATH = os.path.join(os.path.dirname(__file__), "summary.txt")

def run_cmd(cmd, cwd, env=None):
    try:
        result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, env=env)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr or e.stdout

async def main():
    parser = argparse.ArgumentParser(description="Evaluate Phase 1 Context Analyzer")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of new rows to evaluate per run")
    args = parser.parse_args()

    print("Starting Phase 1 evaluation...")

    if not os.path.exists(DATASET_PATH):
        print(f"Dataset not found at: {DATASET_PATH}")
        return

    # Read dataset
    data = []
    with open(DATASET_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Project'] in TARGET_PROJECTS:
                data.append(row)

    print(f"Found {len(data)} backports to evaluate in target projects: {TARGET_PROJECTS}")

    results = []
    evaluated_commits = set()
    
    # Load existing results to support resumability
    if os.path.exists(OUTPUT_JSON_PATH):
        try:
            with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
                for r in results:
                    evaluated_commits.add(r.get("mainline_commit"))
            print(f"Loaded {len(results)} existing results from JSON. Will skip these.")
        except json.JSONDecodeError:
            print(f"Warning: Could not read {OUTPUT_JSON_PATH}. Starting fresh.")

    if args.limit:
        print(f"Limiting to evaluate `{args.limit}` new patches this run.")

    analyzer = PatchAnalyzer()
    processed_in_this_run = 0

    for i, row in enumerate(data):
        mainline_commit = row['Original Commit']
        
        # Skip if already evaluated
        if mainline_commit in evaluated_commits:
            continue
            
        # Check limit
        if args.limit and processed_in_this_run >= args.limit:
            print(f"\nReached the limit of {args.limit} new evaluations. Stopping.")
            break
            
        processed_in_this_run += 1
        
        project = row['Project']
        backport_commit = row['Backport Commit']
        patch_type = row['Type']

        print(f"\n[{processed_in_this_run}/{args.limit if args.limit else 'ALL'}] Evaluating: {project}, {patch_type}")
        print(f"  Mainline: {mainline_commit}")

        repo_path = os.path.join(REPOS_DIR, project)
        if not os.path.exists(repo_path):
            print(f"  [ERROR] Repository path does not exist: {repo_path}")
            continue

        # Clean git state
        run_cmd(["git", "am", "--abort"], cwd=repo_path)
        run_cmd(["git", "reset", "--hard", "HEAD"], cwd=repo_path)
        run_cmd(["git", "clean", "-fd"], cwd=repo_path)

        # 1. Generate patch
        patch_path = os.path.join(os.path.dirname(__file__), f"temp_{project}.patch")
        success, out = run_cmd(["git", "format-patch", "-1", mainline_commit, "--stdout"], cwd=repo_path)
        
        if not success:
            print(f"  [WARNING] Failed to format-patch for {mainline_commit}.")
            results.append({
                "project": project,
                "mainline_commit": mainline_commit,
                "backport_commit": backport_commit,
                "patch_type": patch_type,
                "status": "Failed to extract mainline patch",
                "root_cause": "",
                "fix_logic": "",
                "dependent_apis": [],
                "token_usage": {}
            })
            continue

        patch_diff = out
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(patch_diff)

        # 2. Analyze
        patch_analysis = analyzer.analyze(patch_diff)
        state = {
            "patch_diff": patch_diff,
            "patch_analysis": patch_analysis,
            "mainline_repo_path": repo_path,
            "original_commit": mainline_commit
        }
        
        try:
            print("  Running context_analyzer_node...")
            result_state = await context_analyzer_node(state, config=None)
            blueprint = result_state.get("semantic_blueprint", {})
            tokens = result_state.get("token_usage", {})
            
            root_cause = blueprint.get("root_cause_hypothesis", "")
            fix_logic = blueprint.get("fix_logic", "")
            dependent_apis = blueprint.get("dependent_apis", [])
            
            print(f"  -> SUCCESS. Tokens used: {tokens.get('total_tokens', 0)}")
            
            results.append({
                "project": project,
                "mainline_commit": mainline_commit,
                "backport_commit": backport_commit,
                "patch_type": patch_type,
                "status": "Success",
                "root_cause": root_cause,
                "fix_logic": fix_logic,
                "dependent_apis": dependent_apis,
                "token_usage": tokens
            })
        except Exception as e:
            print(f"  [ERROR] Context Analyzer failed: {e}")
            results.append({
                "project": project,
                "mainline_commit": mainline_commit,
                "backport_commit": backport_commit,
                "patch_type": patch_type,
                "status": f"Error: {e}",
                "root_cause": "",
                "fix_logic": "",
                "dependent_apis": [],
                "token_usage": {}
            })
            
        # Clean up
        if os.path.exists(patch_path):
            os.remove(patch_path)

        # intermediate save
        with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} total results to {OUTPUT_JSON_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
