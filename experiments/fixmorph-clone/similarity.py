#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List
from ast_parser import CodeSegment
from difflib import SequenceMatcher


class SimilarityCalculator:
    """Calculate similarity between code segments"""
    
    def __init__(self):
        self.name_weight = 0.5
        self.signature_weight = 0.3
        self.structure_weight = 0.2
    
    def calculate_class_similarity(self, seg1: CodeSegment, seg2: CodeSegment) -> float:
        """Calculate similarity between two classes"""
        # Name similarity
        name_sim = self.calculate_name_similarity(seg1.name, seg2.name)
        
        # Signature similarity
        sig_sim = self.calculate_string_similarity(seg1.signature, seg2.signature)
        
        # Combined score
        similarity = (name_sim * self.name_weight + 
                     sig_sim * (1 - self.name_weight))
        
        return similarity
    
    def calculate_method_similarity(self, seg1: CodeSegment, seg2: CodeSegment) -> float:
        """Calculate similarity between two methods"""
        # Name similarity
        name_sim = self.calculate_name_similarity(seg1.name, seg2.name)
        
        # Parameter similarity
        param_sim = self.calculate_parameter_similarity(seg1.parameters, seg2.parameters)
        
        # Return type similarity
        return_sim = 1.0 if seg1.return_type == seg2.return_type else 0.5
        
        # Parent class similarity
        parent_sim = 1.0
        if seg1.parent_class and seg2.parent_class:
            parent_sim = self.calculate_name_similarity(
                seg1.parent_class, seg2.parent_class
            )
        
        # Weighted combination
        similarity = (
            name_sim * 0.4 + 
            param_sim * 0.3 + 
            return_sim * 0.15 + 
            parent_sim * 0.15
        )
        
        return similarity
    
    def calculate_field_similarity(self, seg1: CodeSegment, seg2: CodeSegment) -> float:
        """Calculate similarity between two fields"""
        # Name similarity
        name_sim = self.calculate_name_similarity(seg1.name, seg2.name)
        
        # Type similarity
        type_sim = 1.0 if seg1.return_type == seg2.return_type else 0.0
        
        # Parent class similarity
        parent_sim = 1.0
        if seg1.parent_class and seg2.parent_class:
            parent_sim = self.calculate_name_similarity(
                seg1.parent_class, seg2.parent_class
            )
        
        # Weighted combination
        similarity = (
            name_sim * 0.5 + 
            type_sim * 0.3 + 
            parent_sim * 0.2
        )
        
        return similarity
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names"""
        if name1 == name2:
            return 1.0
        
        # Case-insensitive comparison
        if name1.lower() == name2.lower():
            return 0.95
        
        # Use sequence matcher for fuzzy matching
        return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
    
    def calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        if str1 == str2:
            return 1.0
        
        return SequenceMatcher(None, str1, str2).ratio()
    
    def calculate_parameter_similarity(self, params1: List[str], params2: List[str]) -> float:
        """Calculate similarity between parameter lists"""
        if not params1 and not params2:
            return 1.0
        
        if len(params1) != len(params2):
            # Penalize different parameter counts
            return 0.3
        
        # Extract types from parameters
        types1 = [self._extract_type(p) for p in params1]
        types2 = [self._extract_type(p) for p in params2]
        
        # Count matching types
        matches = sum(1 for t1, t2 in zip(types1, types2) if t1 == t2)
        
        if len(types1) == 0:
            return 1.0
        
        return matches / len(types1)
    
    def _extract_type(self, param: str) -> str:
        """Extract type from parameter string (e.g., 'String name' -> 'String')"""
        parts = param.strip().split()
        if parts:
            return parts[0]
        return ''
    
    def calculate_signature_distance(self, sig1: str, sig2: str) -> float:
        """
        Calculate distance between signatures (lower is more similar).
        This is an alternative metric to similarity.
        """
        return 1.0 - self.calculate_string_similarity(sig1, sig2)