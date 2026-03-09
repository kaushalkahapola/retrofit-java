import subprocess
import os
from typing import Optional, Tuple, Dict, List
import difflib
import re

class GitMethodTracer:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def trace_method(self, file_path: str, start_line: int, end_line: int, start_commit: str) -> Optional[Dict]:
        """
        Traces a method's evolution using `git log -L`.
        Returns the final location/status of the method.
        """
        # Construct the -L argument: start,end:file
        range_arg = f"{start_line},{end_line}:{file_path}"
        
        # We want to see the history from start_commit to HEAD
        # Note: git log -L traces BACKWARDS from the commit pointer.
        # But we want to go FORWARDS from start_commit (Mainline) to HEAD (Target).
        # This is tricky with standard git log. 
        # Strategy: 
        # 1. We are usually given the Mainline version (older).
        # 2. We want to find where it went in Target (newer).
        # OR, usually we are backporting, so Mainline is "Newer" in time, but we want to apply to Target "Older".
        # Actually, in backporting:
        # Mainline = Source of Truth (Contains the patch).
        # Target = Destination (Missing the patch).
        # We need to find the equivalent of Mainline's "Old Method" in the Target.
        # So we trace from Mainline Commit -> Common Ancestor -> Target Commit?
        # NO. We just want to find the method in the TARGET.
        # The best way is to trace from the Target HEAD *backwards* to see if we hit the Mainline commit?
        # No, that assumes the method exists in Target HEAD. Use 'pickaxe' or similar?
        
        # Let's stick to the prompt's implication: 
        # "Trace the content of the method from the Original Commit to the Target."
        # If Mainline and Target are divergent branches, we can't just linear trace.
        # However, if we treat Mainline as "Current" and we want to find it in "Target" which might be an ancestor or cousin.
        
        # Actually, standard use case:
        # We have the method in Mainline.
        # We want to find it in Target.
        # If Target is an older version (Backport), the method *should* be there, maybe with an older name?
        # A forward trace isn't standard in Git.
        
        # Alternative: We assume the user creates a synthetic branch or we use common ancestor.
        
        # SIMPLEST BASELINE STRATEGY:
        # If we are looking for a method in Target, and we know its path in Mainline.
        # We check if that path exists in Target. 
        # If not, we check `git log --follow <path>` in Target to see if it was renamed.
        # `git log -L` is powerful for tracking content, but usually works backwards.
        
        # Let's pivot slightly for "Forward Tracing":
        # We can't easily force git log -L to go forward across branches without a merge base.
        # BUT, if we have the SHA of the file blob in Mainline, we can search for it in Target (Blob Hunting!).
        # That's what we did for files.
        # For METHODS, it's harder.
        
        # Let's implement the standard BACKWARD trace from Target assuming we have a guess,
        # OR, implement "Line History" on the Target branch to see if we can find a matching block.
        
        # Wait, the user said "Trace from Original Commit". 
        # If Mainline is `feature` and Target is `master`.
        # Attempts to look at `git log -L start,end:file start_commit..target_commit`?
        # Git doesn't support range for -L.
        
        # Revised Baseline Strategy defined in Plan:
        # "Follow lines 50-60 from commit A to commit B."
        # This implies we assume a linear history or we are clever.
        # Let's implement `git log -L` on the TARGET branch using the known file path.
        # If the file exists in Target, we trace IT backwards to see if it matches the Mainline version at some point?
        # No, that verifies identity, doesn't find it.
        
        # Correct approach for "Backporting" localization:
        # We are looking for the "Old Version" of the code in the Target.
        # 1. Identify the Mainline Method.
        # 2. Look for it in Target.
        # 3. If missing/renamed, how do we use Git?
        # We can search for the "Method Header" string in the git history of the Target?
        # `git log -S "void methodName"` (Pickaxe).
        # This finds when it was added/removed/touched.
        
        cmd = [
            'git', '-C', self.repo_path, 'log', 
            '-L', f'{start_line},{end_line}:{file_path}',
            '--no-patch'
        ]
        
        # Strategy: Use Pickaxe (-S) to find where this method string appears/disappears
        # 1. Extract a unique-ish string from the method (e.g. signature or first line)
        # 2. Search in target history
        
        # Placeholder for complex git logic. 
        # For now, we return None to force fallback to Body Similarity (Tier 2).
        # Real implementation requires 'git log -S "void myMethod()"' parse.
        return None
        
    def find_moved_method_by_pickaxe(self, method_name: str, signature_snippet: str) -> Optional[str]:
        """
        Uses git log -S to find the file containing the method signature in the latest history.
        """
        # Search for the signature addition
        try:
             # Look for commits that added the signature string
             log = subprocess.check_output(
                 ['git', '-C', self.repo_path, 'log', '-S', signature_snippet, '--name-only', '--oneline', '-n', '1'],
                 text=True
             )
             if log:
                 # Extract filename from the log output
                 parts = log.splitlines()
                 if len(parts) >= 2:
                     filename = parts[1].strip()
                     return filename
        except:
             pass
        return None

class BodySimilarityMatcher:
    def _tokenize(self, code: str) -> List[str]:
        # Simple regex tokenizer for Java
        return re.findall(r'\w+|[^\w\s]', code)

    def calculate_similarity(self, code_a: str, code_b: str) -> float:
        """
        Calculates similarity between two method bodies.
        Uses a blend of Difflib (Text) and Jaccard (Token).
        """
        if not code_a or not code_b:
            return 0.0
            
        # 1. Difflib (Character level behavior similar to Levenshtein)
        # ratio() returns a float in [0, 1]
        text_ratio = difflib.SequenceMatcher(None, code_a, code_b).ratio()
        
        # 2. Jaccard (Token set level)
        tokens_a = set(self._tokenize(code_a))
        tokens_b = set(self._tokenize(code_b))
        
        if not tokens_a and not tokens_b:
            jaccard = 1.0
        elif not tokens_a or not tokens_b:
            jaccard = 0.0
        else:
            intersection = len(tokens_a.intersection(tokens_b))
            union = len(tokens_a.union(tokens_b))
            jaccard = intersection / union
            
        # Weighted Average (Prefer Token Jaccard for resilience against whitespace/formatting)
        return (text_ratio * 0.4) + (jaccard * 0.6)
