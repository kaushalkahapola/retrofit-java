import Levenshtein
from typing import List, Dict, Optional, Set
from tree_sitter import Language, Parser, Query
import tree_sitter_java
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class MethodFingerprinter:
    def __init__(self):
        # Initialize Tree-sitter
        self.JAVA_LANGUAGE = Language(tree_sitter_java.language())
        self.parser = Parser(self.JAVA_LANGUAGE)
        
        # AST Node Types to Count for Fingerprint
        self.NODE_TYPES = [
            "if_statement", "for_statement", "while_statement", "try_statement",
            "return_statement", "throw_statement", "assignment_expression",
            "method_invocation", "object_creation_expression", "variable_declarator"
        ]

    def _get_ast_vector(self, source_code: str) -> np.ndarray:
        """Parses code and returns a vector of node type counts."""
        try:
            tree = self.parser.parse(bytes(source_code, "utf8"))
            vector = np.zeros(len(self.NODE_TYPES))
            
            # Simple traversal to count nodes
            cursor = tree.walk()
            
            visited_children = False
            while True:
                if not visited_children:
                    if cursor.node.type in self.NODE_TYPES:
                        idx = self.NODE_TYPES.index(cursor.node.type)
                        vector[idx] += 1
                        
                    if cursor.goto_first_child():
                        continue
                
                if cursor.goto_next_sibling():
                    visited_children = False
                elif cursor.goto_parent():
                    visited_children = True
                else:
                    break
                    
            return vector
        except Exception as e:
            # print(f"Error parsing AST: {e}")
            return np.zeros(len(self.NODE_TYPES))

    def _compute_jaccard(self, set1: Set[str], set2: Set[str]) -> float:
        """Computes Jaccard Similarity between two sets of strings."""
        if not set1 and not set2: return 1.0 # Both empty = match
        if not set1 or not set2: return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union

    def find_match(self, 
                   old_method_name: str, 
                   old_signature: str,
                   old_code: str,
                   old_calls: List[str],
                   candidate_methods: List[Dict]) -> Dict:
        """
        Finds the best matching method in the candidate list for the old method.
        
        Args:
            old_method_name: Name of the method in Mainline.
            old_signature: Signature (e.g., "void foo(int a)") in Mainline.
            old_code: Full source code of the method body in Mainline.
            old_calls: List of methods called by this method in Mainline.
            candidate_methods: List of method dicts from Target (from GetDependencyTool).
                               Each dict must have: 'simpleName', 'signature', 'calls'.
                               For AST match, we ideally need the body, but for now we'll rely on available info.
                               If candidate_methods includes 'body', we use AST.
        
        Returns:
            Dict: {"match": candidate_dict, "confidence": float, "reason": str}
        """
        
        # --- TIER 1: EXACT MATCH ---
        for cand in candidate_methods:
            if cand['simpleName'] == old_method_name:
                # Optional: Add logic verification here if we had the body
                return {"match": cand, "confidence": 1.0, "reason": "Exact Name Match"}

        # --- TIER 2: SIGNATURE MATCH ---
        # Heuristic: Check parameters (simplified from signature)
        # Old: "void foo(int a, String b)" -> "(int a, String b)"
        old_params = old_signature[old_signature.find("("):] if "(" in old_signature else ""
        
        for cand in candidate_methods:
            cand_sig = cand.get('signature', "")
            cand_params = cand_sig[cand_sig.find("("):] if "(" in cand_sig else ""
            
            # If params match exactly and return type matches (simplified check)
            if old_params == cand_params and len(cand_params) > 2: # Ignore empty ()
                 return {"match": cand, "confidence": 0.9, "reason": "Signature Match"}

        # --- TIER 3: NAME SIMILARITY ---
        best_name_sim = 0
        best_name_cand = None
        
        for cand in candidate_methods:
            sim = Levenshtein.ratio(old_method_name, cand['simpleName'])
            if sim > best_name_sim:
                best_name_sim = sim
                best_name_cand = cand
        
        if best_name_sim > 0.8:
             return {"match": best_name_cand, "confidence": 0.8, "reason": f"Name Similarity ({best_name_sim:.2f})"}

        # --- TIER 4: STRUCTURAL FINGERPRINT (CALL GRAPH) ---
        # Note: We can only do AST matching if we have the method body. 
        # GetDependencyTool currently returns 'calls' but NOT body for all methods.
        # So we focus on Call Graph matching here.
        
        best_graph_score = 0
        best_graph_cand = None
        
        old_calls_set = set(old_calls)
        
        for cand in candidate_methods:
            cand_calls_set = set(cand.get('calls', []))
            score = self._compute_jaccard(old_calls_set, cand_calls_set)
            
            if score > best_graph_score:
                best_graph_score = score
                best_graph_cand = cand
                
        if best_graph_score > 0.3: # Threshold for graph similarity
            return {"match": best_graph_cand, "confidence": 0.7 + (best_graph_score * 0.2), "reason": f"Call Graph Match ({best_graph_score:.2f})"}

        return {"match": None, "confidence": 0.0, "reason": "No match found"}
