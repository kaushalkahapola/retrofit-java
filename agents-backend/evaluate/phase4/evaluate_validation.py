import json
import os
import subprocess
import asyncio
import argparse
from dotenv import load_dotenv

# Path setup for src
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from state import AgentState
from agents.validation_agent import validation_agent
from agents.validation_tools import ValidationToolkit
from utils.mcp_client import get_client

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REPOS_DIR = os.path.join(BASE_DIR, "temp_repo_storage")

PHASE3_RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "phase3", "hunk_generator_results.json")
OUTPUT_JSON_PATH = os.path.join(os.path.dirname(__file__), "validation_results.json")
SUMMARY_TXT_PATH = os.path.join(os.path.dirname(__file__), "summary.txt")

def run_cmd(cmd, cwd):
    try:
        result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr or e.stdout

async def main():
    parser = argparse.ArgumentParser(description="Evaluate Phase 4 Validation Agent")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of commits to evaluate")
    parser.add_argument("--input", type=str, default=PHASE3_RESULTS_PATH, help="Path to Phase 3 results JSON")
    parser.add_argument("--compile-only", action="store_true", help="Only verify compilation (skip full validation loop)")
    args = parser.parse_args()

    print(f"Starting Phase 4 evaluation (Validation) using input: {args.input}")

    if not os.path.exists(args.input):
        print(f"Input file not found at: {args.input}")
        return

    with open(args.input, "r", encoding="utf-8") as f:
        phase3_data = json.load(f)

    # Filter for commits where all hunks were successfully generated/applied in dry-run
    eligible = [d for d in phase3_data if d.get("all_hunks_applied")]
    print(f"Found {len(eligible)} successful Phase 3 results to evaluate.")

    results = []
    evaluated_commits = set()
    if os.path.exists(OUTPUT_JSON_PATH):
        try:
            with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
                for r in results:
                    evaluated_commits.add(r.get("mainline_commit"))
        except: pass

    processed = 0
    for entry in eligible:
        mainline_commit = entry['mainline_commit']
        if mainline_commit in evaluated_commits: continue
        if args.limit and processed >= args.limit: break
        
        processed += 1
        project = entry['project']
        backport_commit = entry['backport_commit']
        
        print(f"\n[{processed}] Evaluating: {project} @ {mainline_commit}")
        
        repo_path = os.path.join(REPOS_DIR, project)
        if not os.path.exists(repo_path):
            print(f"  [ERROR] Repo path missing: {repo_path}")
            continue

        # Prepare repo: checkout backport parent
        run_cmd(["git", "am", "--abort"], repo_path)
        run_cmd(["git", "reset", "--hard", "HEAD"], repo_path)
        run_cmd(["git", "clean", "-fd"], repo_path)
        success, _ = run_cmd(["git", "checkout", f"{backport_commit}^"], repo_path)
        if not success:
            print(f"  [ERROR] Failed checkout: {backport_commit}^")
            continue

        # Setup State
        os.environ["VALIDATION_PROVIDER"] = "azure"
        os.environ["AZURE_CHAT_DEPLOYMENT"] = "apim-4o-mini"
        os.environ["AZURE_CHAT_VERSION"] = "2024-02-01"
        os.environ["AZURE_ENDPOINT"] = "https://apim-ai-aus.openai.azure.com/"

        # Shared State
        state = {
            "project": project,
            "mainline_commit": mainline_commit,
            "target_repo_path": repo_path,
            "semantic_blueprint": {
                "root_cause_hypothesis": entry.get("root_cause", ""),
                "fix_logic": entry.get("fix_logic", ""),
                "dependent_apis": entry.get("dependent_apis", [])
            },
            "adapted_code_hunks": entry.get("adapted_code_hunks", []),
            "adapted_test_hunks": entry.get("adapted_test_hunks", []),
            "validation_attempts": 0,
            "compile_only": args.compile_only
        }

        try:
            print(f"  Running {'streamline compilation' if args.compile_only else 'validation_agent'}...")
            final_state = await validation_agent(state, config=None)
            
            res = {
                "project": project,
                "mainline_commit": mainline_commit,
                "backport_commit": backport_commit,
                "validation_passed": final_state.get("validation_passed"),
                "attempts": final_state.get("validation_attempts"),
                "error_context": final_state.get("validation_error_context"),
                "validation_results": final_state.get("validation_results")
            }
            results.append(res)
            print(f"  Result: {'PASSED' if res['validation_passed'] else 'FAILED'}")
            
        except Exception as e:
            print(f"  [ERROR] Validation failed: {e}")
            results.append({
                "project": project,
                "mainline_commit": mainline_commit,
                "status": f"Error: {e}"
            })

        with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    # Summary
    total = len(results)
    passed = len([r for r in results if r.get("validation_passed")])
    summary = f"Phase 4 Summary:\nTotal: {total}\nPassed: {passed}\nAccuracy: {(passed/total*100) if total>0 else 0:.2f}%"
    print("\n" + summary)
    with open(SUMMARY_TXT_PATH, "w") as f: f.write(summary)

if __name__ == "__main__":
    asyncio.run(main())
