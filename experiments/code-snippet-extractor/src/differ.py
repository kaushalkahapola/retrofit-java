import difflib
from .ast_utils import get_method_declarations, parse_file, get_ast_fingerprint

class MainlineDiffer:
    def __init__(self, before_path, after_path):
        self.tree_before, self.content_before = parse_file(before_path)
        self.tree_after, self.content_after = parse_file(after_path)

    def identify_changed_context(self):
        """
        Identifies relevant anchors, handling Modifications AND Renames.
        """
        methods_before = get_method_declarations(self.tree_before)
        methods_after = get_method_declarations(self.tree_after)
        
        relevant_contexts = []
        
        # Track which signatures we have processed
        processed_sigs_after = set()

        # 1. Direct Matches (Same Name/Signature)
        for sig, node_before in methods_before.items():
            if sig in methods_after:
                processed_sigs_after.add(sig)
                node_after = methods_after[sig]
                
                if str(node_before) != str(node_after):
                    relevant_contexts.append({
                        'signature': sig,
                        'type': 'MODIFIED',
                        'anchor_node': node_before
                    })

        # 2. Rename Detection (Orphaned Before vs Orphaned After)
        # Identify methods in 'before' that didn't match anything in 'after'
        orphans_before = {k: v for k, v in methods_before.items() if k not in methods_after}
        
        # Identify methods in 'after' that weren't matched yet
        orphans_after = {k: v for k, v in methods_after.items() if k not in processed_sigs_after}

        for sig_before, node_before in orphans_before.items():
            best_match_sig = None
            best_score = 0.0

            # Get fingerprint of the old method
            fp_before = get_ast_fingerprint(node_before)

            for sig_after, node_after in orphans_after.items():
                # Constraint: Renames usually keep same parameter types/counts
                # You can relax this, but it helps precision.
                if len(node_before.parameters) != len(node_after.parameters):
                    continue

                fp_after = get_ast_fingerprint(node_after)
                
                # Jaccard Similarity on AST tokens
                intersection = len(fp_before.intersection(fp_after))
                union = len(fp_before.union(fp_after))
                
                if union == 0: continue
                score = intersection / union
                
                if score > best_score:
                    best_score = score
                    best_match_sig = sig_after

            # Threshold: If > 50% similar, assume it's a rename
            if best_match_sig and best_score > 0.5:
                print(f"[Diff] Detected Rename: {sig_before} -> {best_match_sig} (Score: {best_score:.2f})")
                
                # IMPORTANT: We use the OLD signature (sig_before) as the anchor 
                # because we need to find the OLD version in the target file.
                relevant_contexts.append({
                    'signature': sig_before, 
                    'type': 'RENAMED',
                    'anchor_node': node_before
                })

        return relevant_contexts