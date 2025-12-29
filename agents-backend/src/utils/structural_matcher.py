from typing import List, Dict, Set, Optional, Tuple

def normalize_type(type_name: str) -> str:
    """Removes generics and package names for looser matching."""
    if "<" in type_name:
        type_name = type_name.split("<")[0]
    return type_name.split(".")[-1]

class RichNode:
    def __init__(self, data: Dict):
        self.class_name = data.get("className", "")
        self.simple_name = data.get("simpleName", "")
        self.superclass = data.get("superclass", "")
        self.interfaces = set(data.get("interfaces", []))
        self.fields = data.get("fields", []) # list of {name, type}
        # Parse methods (handle legacy list of strings or new list of dicts)
        raw_methods = data.get("methods", [])
        self.methods = set()
        for m in raw_methods:
            if isinstance(m, dict):
                self.methods.add(m.get("signature", ""))
            else:
                self.methods.add(str(m))

        self.outgoing_calls = set(data.get("outgoingCalls", []))

    def get_features(self) -> Set[str]:
        """Returns a set of 'features' (method signatures + important field types)."""
        features = set()
        for m in self.methods:
            features.add(f"METHOD:{m}")
        for f in self.fields:
            features.add(f"FIELD:{normalize_type(f['type'])}")
        return features

def calculate_structure_score(mainline: RichNode, target: RichNode) -> float:
    score = 0.0
    
    # 1. Inheritance (Weight: 0.3)
    # Check superclass
    if mainline.superclass:
        if normalize_type(mainline.superclass) == normalize_type(target.superclass):
            score += 0.2
        elif target.superclass and "Base" in target.superclass: # Loose matching for refactored Base classes
             score += 0.1
    
    # Check interfaces
    if mainline.interfaces:
        common_interfaces = mainline.interfaces.intersection(target.interfaces)
        if common_interfaces:
            score += 0.1
            
    # 2. Outgoing Calls (Weight: 0.4)
    # This is the "Social Network" check.
    if mainline.outgoing_calls:
        # We normalize to "TargetClass.method" 
        mainline_calls = {c.split(".")[-1] for c in mainline.outgoing_calls}
        target_calls = {c.split(".")[-1] for c in target.outgoing_calls}
        
        intersection = mainline_calls.intersection(target_calls)
        if len(mainline_calls) > 0:
            call_overlap = len(intersection) / len(mainline_calls)
            score += 0.4 * call_overlap
            
    # 3. Fields (Weight: 0.1)
    if mainline.fields:
        main_fields = {normalize_type(f['type']) for f in mainline.fields}
        target_fields = {normalize_type(f['type']) for f in target.fields}
        
        field_overlap = len(main_fields.intersection(target_fields))
        if len(main_fields) > 0:
            score += 0.1 * (field_overlap / len(main_fields))
            
    # 4. Name Similarity (Weight: 0.2)
    # Bonus if the name is similar
    if mainline.simple_name in target.simple_name or target.simple_name in mainline.simple_name:
        score += 0.2
        
    return score

def find_best_matches(mainline_data: Dict, candidates_data: List[Dict]) -> List[Dict]:
    """
    Finds the best matching candidate(s).
    Supports 1-to-N matching (Feature Coverage).
    """
    mainline_node = RichNode(mainline_data)
    candidate_nodes = [RichNode(c) for c in candidates_data]
    
    # 1. Individual Scoring
    scored_candidates = []
    for node, raw_data in zip(candidate_nodes, candidates_data):
        score = calculate_structure_score(mainline_node, node)
        scored_candidates.append({
            "data": raw_data,
            "score": score,
            "node": node
        })
    
    # Sort by score
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)
    
    if not scored_candidates:
        return []
        
    top_candidate = scored_candidates[0]
    
    # Case 1: Strong individual match
    if top_candidate["score"] > 0.6:
        return [top_candidate]
        
    # Case 2: Multi-File Match (Refactoring)
    # If the top score is weak, check if the top 2-3 candidates combined cover the features
    mainline_features = mainline_node.get_features()
    if not mainline_features:
        return [top_candidate] # Fallback if no features to cover
        
    # Take top 3
    top_k = scored_candidates[:3]
    combined_features = set()
    selected_candidates = []
    
    for cand in top_k:
        cand_features = cand["node"].get_features()
        # Calculate marginal gain
        new_features = cand_features.intersection(mainline_features) - combined_features
        if len(new_features) > 0:
            selected_candidates.append(cand)
            combined_features.update(new_features)
            
    # If combined coverage is significantly better than single coverage
    single_coverage = len(top_candidate["node"].get_features().intersection(mainline_features))
    combined_coverage = len(combined_features)
    
    if combined_coverage > single_coverage * 1.5:
        return selected_candidates
        
    return [top_candidate]
