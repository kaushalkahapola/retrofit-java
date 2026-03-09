import pandas as pd
import os
import json
from git import Repo
# Import our backend
import sys
sys.path.append(os.path.abspath("agents-backend/src"))
from utils.retrieval.ensemble_retriever import EnsembleRetriever
from utils.structural_matcher import find_best_matches

# Configuration
REPO_NAME = "elasticsearch"
REPO_PATH = os.path.abspath("temp_repo_storage/elasticsearch")
DATASET_PATH = "datasets/combined_with_originals_filtered.csv"
OUTPUT_FILE = "evaluation_results_elasticsearch.json"
MAX_SAMPLES = 10 # Pilot size

def get_modified_files(repo, commit):
    """Get list of files modified in a commit."""
    try:
        return repo.git.show("--name-only", "--format=", commit).splitlines()
    except:
        return []

def evaluate():
    print(f"Loading dataset from {DATASET_PATH}...")
    df = pd.read_csv(DATASET_PATH)
    
    # Filter for elasticsearch
    df_elasticsearch = df[df['repo'] == REPO_NAME].head(MAX_SAMPLES)
    print(f"Evaluating {len(df_elasticsearch)} samples for {REPO_NAME}...")
    
    results = []
    
    # Initialize Repo Object
    target_repo = Repo(REPO_PATH)
    
    # Initialize Retriever (Mainline is trickier since we don't have it? 
    # WAIT. The user said 'combined_with_originals', implying we have original commits.
    # But we only cloned elasticsearch (Target).
    # Does elasticsearch contain the Mainline commits? 
    # If it's a backport within the SAME repo (e.g. master -> branch), yes.
    # If it's a fork, maybe not.
    # Let's assume for 'elasticsearch' (Apache project), backports are usually cherry-picks from master.
    # So the 'original_commit' SHOULD exist in the same repo history.
    # If not, we might fail to get mainline content.
    # Let's assume Single-Repo scenario for now.)
    
    # We use the SAME repo object for both Mainline and Target if it's a self-backport.
    retriever = EnsembleRetriever(REPO_PATH, REPO_PATH) 
    
    for idx, row in df_elasticsearch.iterrows():
        try:
            target_commit = row['commit']
            original_commit = row['original_commit']
            patch_id = row.get('key', str(idx))
            
            print(f"\n--- Evaluating Patch {patch_id} ---")
            print(f"Target: {target_commit}, Original: {original_commit}")
            
            # 1. Determine Ground Truth (Files modified in Target Backport)
            ground_truth_files = get_modified_files(target_repo, target_commit)
            # Filter: Java files ONLY, and split out Tests if requested
            ground_truth_files = [
                f for f in ground_truth_files 
                if f.endswith(".java") 
                and "src/test/" not in f 
                and not f.endswith("Test.java")
            ]
            
            if not ground_truth_files:
                print("Skipping: No production Java files modified in backport.")
                continue
                
            print(f"Ground Truth Files: {ground_truth_files}")
            
            # 2. Setup Target State (Checkout Parent of Backport)
            # We want to see if we can find these files BEFORE they were modified/created by the patch.
            # But wait. If the patch CREATES a file, we can't 'find' it in the target (it doesn't exist yet).
            # We can only match files that EXIST in target and are being modified.
            # Or rename targets.
            # For simplicity, we focus on Modified/Renamed files.
            
            try:
                # Force checkout to overwrite any untracked files from previous states
                target_repo.git.checkout(f"{target_commit}^", force=True)
            except Exception as e:
                print(f"Error checking out parent: {e}")
                continue
            
            # Re-index Retriever at this state
            # Note: Building index for every patch is slow. For pilot it's fine.
            # retriever.build_index("HEAD")  <-- DISABLED for speed. Using initial index.
            
            # 3. Identify Source Files from Mainline
            # We need to know what files were modified in the ORIGINAL commit.
            mainline_files = get_modified_files(target_repo, original_commit) # Assuming same repo
            mainline_files = [
                f for f in mainline_files 
                if f.endswith(".java")
                and "src/test/" not in f
                and not f.endswith("Test.java")
            ]
             
            print(f"Mainline Source Files: {mainline_files}")
            
            patch_metrics = {
                "patch_id": patch_id,
                "ground_truth_total": len(ground_truth_files),
                "ground_truth_files": ground_truth_files,
                "candidates_found_total": 0,
                "matcher_found_total": 0,
                "files_metrics": []
            }
            
            # 4. Run Retrieval & Matching per File
            # Evaluating mapping: Mainline -> Target
            # Heuristic: We try to match each Mainline file to a Target file.
            # If the set of matched target files overlaps with Ground Truth, it's a hit.
            
            for src_file in mainline_files:
                print(f"Searching for match for: {src_file}")
                
                # A. Retrieval Phase (Candidates)
                candidates = retriever.find_candidates(src_file, original_commit)
                # Candidates structure: [{'file': path, 'score': ...}, ...]
                candidate_paths = [c['file'] for c in candidates]
                
                # Check Candidate Recall
                # Which GT files are in the candidate list?
                gt_in_candidates = [gt for gt in ground_truth_files if gt in candidate_paths]
                
                # B. Matcher Phase
                top_1 = candidate_paths[:1] if candidate_paths else []
                top_5 = candidate_paths[:5] if candidate_paths else []
                
                gt_in_top1 = [gt for gt in ground_truth_files if gt in top_1]
                gt_in_top5 = [gt for gt in ground_truth_files if gt in top_5]
                
                # Extract method for each candidate
                candidate_methods = {}
                for c in candidates:
                    # 'method' key might vary slightly depending on phase
                    # Phase 1: 'method' (e.g., GIT_EXACT)
                    # Phase 2: 'reason' (e.g., SYMBOL + TF-IDF)
                    m = c.get('method', c.get('reason', 'UNKNOWN'))
                    candidate_methods[c['file']] = m

                file_metric = {
                    "source_file": src_file,
                    "candidates_count": len(candidates),
                    "candidates": candidate_paths,
                    "candidate_methods": candidate_methods, # New Field
                    "ground_truth_matches_in_candidates": gt_in_candidates,
                    "ground_truth_matches_in_top1": gt_in_top1,
                    "ground_truth_matches_in_top5": gt_in_top5,
                    "candidate_recall": len(gt_in_candidates) > 0,
                    "top1_accuracy": len(gt_in_top1) > 0,
                    "top5_accuracy": len(gt_in_top5) > 0
                }
                patch_metrics["files_metrics"].append(file_metric)
                
            # Aggregation for Patch
            # How many UNIQUE GT files did we find across all source files?
            found_gt_candidates = set()
            found_gt_top1 = set()
            
            for m in patch_metrics["files_metrics"]:
                found_gt_candidates.update(m["ground_truth_matches_in_candidates"])
                found_gt_top1.update(m["ground_truth_matches_in_top1"])
                
            patch_metrics["candidates_found_total"] = len(found_gt_candidates)
            patch_metrics["matcher_found_total"] = len(found_gt_top1) # Assuming Top-1 is our "Match"
            
            results.append(patch_metrics)
            
        except Exception as e:
            print(f"Error evaluating patch {row.get('key')}: {e}")
            
    # Save Report
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nEvaluation Complete. Results saved to {OUTPUT_FILE}")
    
    # Print Summary
    total_gt = sum(r["ground_truth_total"] for r in results)
    total_found_cands = sum(r["candidates_found_total"] for r in results)
    total_found_top1 = sum(r["matcher_found_total"] for r in results)
    
    print("\n--- Summary ---")
    print(f"Total Ground Truth Files: {total_gt}")
    if total_gt > 0:
        print(f"Found in Candidates (Recall): {total_found_cands}/{total_gt} ({total_found_cands/total_gt*100:.1f}%)")
        print(f"Found in Top-1 (Precision): {total_found_top1}/{total_gt} ({total_found_top1/total_gt*100:.1f}%)")
    else:
        print("No ground truth files found in the evaluated samples.")

if __name__ == "__main__":
    evaluate()
