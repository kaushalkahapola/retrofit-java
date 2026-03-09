import csv
import os
import sys
import re
import subprocess
import json
from typing import List, Dict, Tuple

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../agents-backend/src'))

from utils.method_discovery import GitMethodTracer, BodySimilarityMatcher

PROJECT = "druid"
REPO_PATH = "temp_repo_storage/" + PROJECT
DATASET_PATH = "datasets/combined_with_originals_filtered.csv"
OUTPUT_FILE = "scripts/results/evaluation_results_method_baseline.json"

import tree_sitter_java
from tree_sitter import Language, Parser

def get_changed_lines_from_patch(patch_text: str) -> Dict[str, List[int]]:
    """
    Parses patch to find modified line numbers per file.
    Returns: { "path/to/File.java": [10, 15, 20] }
    """
    changes = {}
    current_file = None
    current_line = 0
    
    for line in patch_text.splitlines():
        if line.startswith('+++ b/'):
            current_file = line[6:].strip()
            changes[current_file] = []
        elif line.startswith('@@'):
            # Parse header: @@ -old_start,old_len +new_start,new_len @@
            # We care about OLD lines (original commit) to find the ORIGINAL method.
            # So looking at "-old_start,old_len"
            match = re.search(r'@@ -(\d+),', line)
            if match:
                current_line = int(match.group(1))
        elif line.startswith('-') and not line.startswith('---'):
            # This line existed in old version and was removed/changed
            if current_file:
                changes[current_file].append(current_line)
            current_line += 1
        elif line.startswith(' ') and not line.startswith('---'):
            # Context line exists in old version
            current_line += 1
        # + lines don't exist in old version, so we skip incrementing old line counter
            
    return changes

def extract_methods_from_file_at_lines(file_content: str, line_numbers: List[int]) -> List[str]:
    """
    Uses Tree-sitter to find which methods cover the given line numbers.
    """
    JAVA_LANGUAGE = Language(tree_sitter_java.language())
    parser = Parser(JAVA_LANGUAGE)
    tree = parser.parse(bytes(file_content, "utf8"))
    
    found_methods = set()
    
    def visit(node):
        # check coverage
        start_row = node.start_point[0] + 1 # 1-based logic for comparison with patch
        end_row = node.end_point[0] + 1
        
        if node.type == 'method_declaration':
            # Check if any target line falls within this method
            for line in line_numbers:
                if start_row <= line <= end_row:
                    # Found it! Extract name.
                    # child logic to find name identifier
                    name_node = node.child_by_field_name('name')
                    if name_node:
                        found_methods.add(name_node.text.decode('utf8'))
                        return # Found for this node
        
        # Recurse
        if node.child_count > 0:
            for i in range(node.child_count):
                visit(node.child(i))
                
    visit(tree.root_node)
    return list(found_methods)

def parse_patch_for_methods(patch_text: str) -> List[Tuple[str, str]]:
    """
    Wrapper to match the expected interface, but relies on GLOBAL access to 'original_commit' 
    which is dirty. 
    Ideally pass 'original_commit' to this function.
    Wait, the previous `evaluate_baseline` loop calls `parse_patch_for_methods(patch)`.
    I need to Change the CALLER to pass `original_commit` too.
    Legacy signature support? 
    No, let's change the caller first or make this function accept `original_commit` if possible?
    The `evaluate_baseline` function iterates and calls it.
    I will update this function to accept `original_commit` (and `repo_path` implicitly or explicitly) 
    AND I will update the caller in the next tool call.
    For now, I'll define `parse_patch_for_methods_with_commit` and make `parse_patch_for_methods` fail or forward?
    
    Actually, I can just redefine `parse_patch_for_methods(patch_text, original_commit)` here
    and assume I will update the caller in the next step.
    """
    return []

# Redefining properly
def parse_patch_finding_methods(patch_text: str, original_commit: str) -> List[Tuple[str, str]]:
    modified_files = get_changed_lines_from_patch(patch_text)
    results = []
    
    for file_path, lines in modified_files.items():
        if not file_path.endswith('.java'): continue
        if not lines: continue
        
        try:
            # Fetch file content from OLD commit
            file_content = subprocess.check_output(
                ['git', '-C', REPO_PATH, 'show', f'{original_commit}:{file_path}'], 
                text=True, stderr=subprocess.DEVNULL
            )
            
            methods = extract_methods_from_file_at_lines(file_content, lines)
            for m in methods:
                 results.append((file_path, f"{m}(")) 
        except Exception as e:
            pass
            
    return results

def get_touched_methods_in_commit(commit_id: str) -> List[str]:
    """
    Returns a list of strings found in the hunk headers of the commit.
    """
    try:
        # We need to get the patch content
        out = subprocess.check_output(['git', '-C', REPO_PATH, 'show', '-U20', commit_id], text=True)
        # Use the Tree-sitter parser, passing the verify commit ID as the source of file content
        return parse_patch_finding_methods(out, commit_id)
    except:
        return []

def evaluate_baseline():
    results = []
    
    with open(DATASET_PATH, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    print(f"Evaluating {len(rows)} samples...")
    
    correct_count = 0
    total_count = 0
    
    tracer = GitMethodTracer(REPO_PATH)
    
    for i, row in enumerate(rows[:20]): # Pilot limit
        original_commit = row.get('original_commit')
        target_commit = row.get('commit') # Backport commit
        patch = row.get('patch') # Original patch
        
        if not original_commit or not target_commit:
            continue
            
        print(f"\nSample {i+1}: {original_commit} -> {target_commit}")
        
        # 1. Get Original Patch from Git
        try:
            # We assume original_commit exists in the repo (self-contained history)
            # Use -U20 to get more context, increasing chance of seeing the method header
            patch = subprocess.check_output(['git', '-C', REPO_PATH, 'show', '-U20', original_commit], text=True)
        except subprocess.CalledProcessError:
            print(f"  Skipping: Original commit {original_commit} not found in repo.")
            continue
            
        # 2. Identify Target Method (The 'Query')
        # We pass original_commit so we can fetch file content
        query_methods = parse_patch_finding_methods(patch, original_commit)
        if not query_methods:
            print("  Skipping: No methods found in patch.")
            continue
            
        # 2. Setup Repo State (Target Parent)
        try:
             # Checkout Parent of Target Commit to simulate "Before Backport" state
             subprocess.run(['git', '-C', REPO_PATH, 'checkout', f'{target_commit}^'], 
                            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"  Error checking out {target_commit}^: {e}")
            continue

        for q_file, q_sig in query_methods:
            print(f"  Query: {q_sig} in {q_file}")
            
            # 3. Run Method Discovery
            # Extract method name from signature (heuristic)
            # e.g. "public void foo(int a)" -> "foo"
            # Simple regex: last word before '('
            m_name_match = re.search(r'\s(\w+)\(', q_sig)
            if not m_name_match:
                m_name_match = re.search(r'^(\w+)\(', q_sig)
                
            if m_name_match:
                method_name = m_name_match.group(1)
                
                # RUN THE TOOL
                found_path = tracer.find_moved_method_by_pickaxe(method_name, q_sig)
                
                # 4. Verification
                # Did we find a file/method that was actualy modified in the backport?
                # Check ground truth
                actual_modifications = get_touched_methods_in_commit(target_commit)
                # actual_modifications is List[(file, sig)]
                
                # Check if our 'found_path' is in the actual modified files
                hit = False
                if found_path:
                    # Check if 'found_path' matches any file modified in target_commit
                    # And ideally if the method signature is similar?
                    for act_file, act_sig in actual_modifications:
                        if found_path in act_file:
                             hit = True
                             print(f"    SUCCESS: Found in {act_file}")
                             break
                
                if hit:
                    correct_count += 1
                else:
                    print(f"    FAIL: Predicted {found_path}, Actual Modified: {[m[0] for m in actual_modifications]}")
                
                total_count += 1
                
                # Save Detailed Result
                results.append({
                    "sample_index": i,
                    "original_commit": original_commit,
                    "target_commit": target_commit,
                    "query_method_signature": q_sig,
                    "query_file": q_file,
                    "predicted_file": found_path,
                    "ground_truth_modifications": [m[0] for m in actual_modifications],
                    "status": "SUCCESS" if hit else "FAIL",
                    "reason": "Found in modified files" if hit else "Prediction not in modified files"
                })
                
    accuracy = (correct_count / total_count) if total_count > 0 else 0
    print(f"\nResults: {correct_count}/{total_count} ({accuracy:.2%})")
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Detailed results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    evaluate_baseline()
