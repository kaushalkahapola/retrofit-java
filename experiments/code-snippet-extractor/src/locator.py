from .ast_utils import get_method_declarations, parse_file, get_lines_from_node, get_ast_fingerprint
import difflib

class TargetLocator:
    def __init__(self, target_path):
        self.tree_target, self.content_target = parse_file(target_path)
        self.target_methods = get_method_declarations(self.tree_target)

    def find_and_extract(self, context_info):
        """
        Locates the context in the target file using Structural Alignment.
        """
        anchor_sig = context_info['signature']
        anchor_node = context_info['anchor_node']
        
        # 1. Exact Signature Match
        if anchor_sig in self.target_methods:
            print(f"[+] Found exact match for {anchor_sig}")
            return self._format_output(self.target_methods[anchor_sig])

        print(f"[-] No exact match for {anchor_sig}. Attempting Structural Alignment...")
        
        # 2. Structural Similarity (FixMorph Strategy)
        # Compare the AST content (tokens, types, literals) of the Anchor vs Targets
        anchor_fingerprint = get_ast_fingerprint(anchor_node)
        
        best_node = None
        best_score = 0.0
        
        for t_sig, t_node in self.target_methods.items():
            target_fingerprint = get_ast_fingerprint(t_node)
            
            # Jaccard Similarity: intersection / union
            intersection = len(anchor_fingerprint.intersection(target_fingerprint))
            union = len(anchor_fingerprint.union(target_fingerprint))
            
            if union == 0: continue
            score = intersection / union
            
            # Debug print to see what's happening
            print(f"    Comparing with {t_sig} -> Score: {score:.2f}")
            
            if score > best_score:
                best_score = score
                best_node = t_node

        # Threshold can be adjusted (0.3 is usually enough for "similar logic")
        if best_node and best_score > 0.3:
            print(f"[+] Found structural match: {best_node.name} (Score: {best_score:.2f})")
            return self._format_output(best_node)
        return None

    def _format_output(self, node):
        raw_code = get_lines_from_node(self.content_target, node)
        lines = raw_code.splitlines()
        annotated_code = []
        annotated_code.append(f"// CONTEXT: {node.name}")
        annotated_code.extend(lines)
        
        # RETURN DICTIONARY instead of just string
        return {
            "method_name": node.name,
            "code": "\n".join(annotated_code)
        }