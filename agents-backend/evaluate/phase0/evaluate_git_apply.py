import os
import csv
import subprocess
from collections import defaultdict

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", "all_projects_final.csv")
REPOS_DIR = os.path.join(BASE_DIR, "temp_repo_storage")

TARGET_PROJECTS = ["druid", "elasticsearch"]

OUTPUT_CSV_PATH = os.path.join(os.path.dirname(__file__), "git_apply_results.csv")
SUMMARY_TXT_PATH = os.path.join(os.path.dirname(__file__), "summary.txt")


def run_cmd(cmd, cwd, env=None):
    try:
        result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, env=env)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr or e.stdout


def main():
    print("Starting Phase 0 evaluation...")

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
    summary = defaultdict(lambda: defaultdict(lambda: {"total": 0, "success": 0}))

    for i, row in enumerate(data):
        project = row['Project']
        mainline_commit = row['Original Commit']
        backport_commit = row['Backport Commit']
        patch_type = row['Type']

        print(f"\n[{i+1}/{len(data)}] Evaluating project: {project}, patch_type: {patch_type}")
        print(f"  Mainline: {mainline_commit}")
        print(f"  Backport: {backport_commit}")

        repo_path = os.path.join(REPOS_DIR, project)
        if not os.path.exists(repo_path):
            print(f"  [ERROR] Repository path does not exist: {repo_path}")
            continue

        # Clean git state just in case
        run_cmd(["git", "am", "--abort"], cwd=repo_path)
        run_cmd(["git", "reset", "--hard", "HEAD"], cwd=repo_path)
        run_cmd(["git", "clean", "-fd"], cwd=repo_path)

        # 1. Generate patch from mainline commit
        # The mainline might be fetched or checked out, but git format-patch works directly on the commit hash if it exists.
        patch_path = os.path.join(os.path.dirname(__file__), f"temp_{project}.patch")
        
        success, out = run_cmd(["git", "format-patch", "-1", mainline_commit, "--stdout"], cwd=repo_path)
        if not success:
            print(f"  [WARNING] Failed to format-patch for {mainline_commit}. Trying generic apply skipping if object doesn't exist.")
            # Some repos might not have the mainline object if clones are shallow/specific. 
            # In our setup `temp_repo_storage` typically has both depending on how they were cloned.
            # Assuming it does have it here.
            results.append({
                "project": project,
                "mainline_commit": mainline_commit,
                "backport_commit": backport_commit,
                "git_apply_success": False,
                "patch_type": patch_type,
                "error": "Failed to extract mainline patch"
            })
            continue

        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(out)

        # 2. Checkout to backport parent
        success, out = run_cmd(["git", "checkout", f"{backport_commit}^"], cwd=repo_path)
        if not success:
            print(f"  [ERROR] Failed to checkout {backport_commit}^: {out}")
            results.append({
                "project": project,
                "mainline_commit": mainline_commit,
                "backport_commit": backport_commit,
                "git_apply_success": False,
                "patch_type": patch_type,
                "error": "Failed checkout"
            })
            if os.path.exists(patch_path):
                os.remove(patch_path)
            continue

        # 3. Apply check
        success, apply_out = run_cmd(["git", "apply", "--check", patch_path], cwd=repo_path)
        
        results.append({
            "project": project,
            "mainline_commit": mainline_commit,
            "backport_commit": backport_commit,
            "git_apply_success": success,
            "patch_type": patch_type,
            "error": None if success else apply_out.splitlines()[0] if apply_out else "Unknown error"
        })

        if success:
            print("  -> Git apply SUCCESS")
        else:
            print("  -> Git apply FAILED")

        summary[project][patch_type]["total"] += 1
        if success:
            summary[project][patch_type]["success"] += 1

        # Clean up
        if os.path.exists(patch_path):
            os.remove(patch_path)

    # Save CSV
    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["project", "mainline_commit", "backport_commit", "git_apply_success", "patch_type", "error"])
        writer.writeheader()
        writer.writerows(results)
    print(f"\nSaved CSV results to {OUTPUT_CSV_PATH}")

    # Save summary
    with open(SUMMARY_TXT_PATH, "w", encoding="utf-8") as f:
        f.write("Phase 0 (git apply --check) Evaluation Summary\n")
        f.write("==============================================\n\n")

        for proj, type_data in summary.items():
            f.write(f"Project: {proj}\n")
            f.write("-" * 20 + "\n")
            proj_total = 0
            proj_success = 0
            for t, stats in type_data.items():
                t_total = stats["total"]
                t_success = stats["success"]
                proj_total += t_total
                proj_success += t_success
                perc = (t_success / t_total * 100) if t_total > 0 else 0
                f.write(f"  {t}: {t_success}/{t_total} ({perc:.2f}%)\n")
            overall_perc = (proj_success / proj_total * 100) if proj_total > 0 else 0
            f.write(f"  OVERALL: {proj_success}/{proj_total} ({overall_perc:.2f}%)\n\n")
            
    print(f"Saved summary to {SUMMARY_TXT_PATH}")
    
    # Also print summary
    with open(SUMMARY_TXT_PATH, "r", encoding="utf-8") as f:
        print("\n" + f.read())

if __name__ == "__main__":
    main()
