import json
import os
import subprocess
from unidiff import PatchSet

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REPOS_DIR = os.path.join(BASE_DIR, "temp_repo_storage")
PHASE2_RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "phase2", "structural_locator_results.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "hunk_generator_results_gt.json")

def run_cmd(cmd, cwd):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout

def main():
    if not os.path.exists(PHASE2_RESULTS_PATH):
        print("Phase 2 results not found.")
        return

    with open(PHASE2_RESULTS_PATH, "r") as f:
        data = json.load(f)

    gt_results = []

    for entry in data:
        project = entry["project"]
        backport_commit = entry["backport_commit"]
        repo_path = os.path.join(REPOS_DIR, project)
        
        if not os.path.exists(repo_path):
            continue

        print(f"Extracting GT for {project} @ {backport_commit}")
        
        # Get the diff of the backport commit
        success, diff_text = run_cmd(["git", "show", "-1", backport_commit, "--no-prefix", "-U3"], repo_path)
        if not success:
            print(f"Failed to get diff for {backport_commit}")
            continue

        patch = PatchSet(diff_text)
        
        code_hunks = []
        test_hunks = []
        
        for patched_file in patch:
            target_file = patched_file.path
            is_test = "test" in target_file.lower()
            
            for hunk in patched_file:
                # Reconstruct the hunk text
                hunk_text = str(hunk)
                
                hunk_dict = {
                    "target_file": target_file,
                    "mainline_file": "gt_extracted",
                    "hunk_text": hunk_text,
                    "insertion_line": hunk.target_start,
                    "intent_verified": True
                }
                
                if is_test:
                    test_hunks.append(hunk_dict)
                else:
                    code_hunks.append(hunk_dict)

        gt_entry = {
            "project": project,
            "mainline_commit": entry["mainline_commit"],
            "backport_commit": backport_commit,
            "patch_type": entry["patch_type"],
            "all_hunks_applied": True, # These are real so they apply
            "adapted_code_hunks": code_hunks,
            "adapted_test_hunks": test_hunks,
            "root_cause": entry.get("root_cause", ""),
            "fix_logic": entry.get("fix_logic", ""),
            "dependent_apis": entry.get("dependent_apis", [])
        }
        gt_results.append(gt_entry)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(gt_results, f, indent=2)
    
    print(f"Ground truth hunks saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
