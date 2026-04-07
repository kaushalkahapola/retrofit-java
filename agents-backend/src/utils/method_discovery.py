import subprocess
import os
import difflib
import re
from typing import Optional, Tuple, Dict, List

class GitMethodTracer:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def trace_method(self, file_path: str, start_line: int, end_line: int, start_commit: str) -> Optional[Dict]:
        """
        Traces a method's evolution using `git log -L`.
        Returns the final location/status of the method.
        """
        range_arg = f"{start_line},{end_line}:{file_path}"
        
        cmd = [
            'git', '-C', self.repo_path, 'log', 
            '-L', range_arg,
            '--no-patch'
        ]
        
        # Placeholder for complex git logic. 
        # For now, we return None to force fallback to Body Similarity (Tier 2).
        return None
        
    def find_moved_method_by_pickaxe(self, method_name: str, signature_snippet: str) -> Optional[str]:
        """
        Uses git log -S to find the file containing the method signature in the latest history.
        """
        try:
             log = subprocess.check_output(
                 ['git', '-C', self.repo_path, 'log', '-S', signature_snippet, '--name-only', '--oneline', '-n', '1'],
                 text=True,
                 stderr=subprocess.DEVNULL
             )
             if log:
                 parts = log.splitlines()
                 if len(parts) >= 2:
                     filename = parts[1].strip()
                     return filename
        except subprocess.CalledProcessError:
             pass
        return None


class BodySimilarityMatcher:
    def _tokenize(self, code: str) -> List[str]:
        return re.findall(r'\w+|[^\w\s]', code)

    def calculate_similarity(self, code_a: str, code_b: str) -> float:
        """
        Calculates similarity between two method bodies using Difflib and Jaccard.
        """
        if not code_a or not code_b:
            return 0.0
            
        text_ratio = difflib.SequenceMatcher(None, code_a, code_b).ratio()
        
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
            
        return (text_ratio * 0.4) + (jaccard * 0.6)


class JavaStructureLocator:
    """
    Enhances AST mapping by capturing Fields, Constructors, Class Signatures, 
    and Methods to prevent the 'Mapped hunk to None' blindspot in Agent 2.
    """
    def __init__(self, file_content: str):
        self.file_content = file_content
        self.lines = file_content.splitlines()

    def find_enclosing_structure(self, start_line: int, end_line: int) -> Optional[Dict]:
        """
        Scans backwards from the hunk's start_line to find the nearest structural owner.
        """
        if not self.lines:
            return None
            
        # Convert to 0-based index and ensure we don't go out of bounds
        start_idx = max(0, start_line - 1)
        
        # Keywords to ignore so we don't accidentally map to a control flow block
        control_flow = {'if', 'else', 'for', 'while', 'switch', 'catch', 'try', 'finally', 'return'}
        
        for i in range(start_idx, -1, -1):
            line = self.lines[i].strip()
            
            # Skip empty lines, comments, and annotations
            if not line or line.startswith('//') or line.startswith('@') or line.startswith('*'):
                continue
            
            # 1. Class / Interface / Enum Signatures
            class_match = re.search(r'\b(?:class|interface|enum)\s+(\w+)', line)
            if class_match:
                return {
                    "type": "class_signature",
                    "name": class_match.group(1),
                    "line": i + 1,
                    "signature": line.strip('{ ').strip()
                }
            
            # 2. Field Declarations
            # Looks for standard Java field definitions (e.g., private final int SIZE = 10;)
            field_match = re.search(r'^(?:public|protected|private|static|final|volatile|transient|\s)+[\w\<\>\[\]\?]+\s+(\w+)\s*(?:=.*?)?;', line)
            if field_match:
                return {
                    "type": "field_declaration",
                    "name": field_match.group(1),
                    "line": i + 1,
                    "signature": line.strip()
                }
            
            # 3. Methods & Constructors
            # Looks for method definitions but ignores lines ending in semicolons (which are usually invocations)
            method_match = re.search(r'^(?:public|protected|private|static|final|abstract|synchronized|native|\s)*(?:[\w\<\>\[\]\?\.\,]+\s+)?(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w\s\,]+)?\s*\{?$', line)
            
            if method_match and not line.endswith(';'):
                name = method_match.group(1)
                if name not in control_flow:
                    # Heuristic for constructors: Name is capitalized and no return type before it
                    is_constructor = name[0].isupper() and 'class ' not in line
                    
                    return {
                        "type": "constructor" if is_constructor else "method",
                        "name": name,
                        "line": i + 1,
                        "signature": method_match.group(0).strip(' {')
                    }
        
        return None