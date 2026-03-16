#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Dict, Any, Tuple, Optional
from ast_parser import JavaASTParser, CodeSegment
from similarity import SimilarityCalculator


class BackportDetector:
    """Main detector for finding backport targets in Java code"""
    
    def __init__(self, mainline_before: str, mainline_after: str, 
                 target_before: str, similarity_threshold: float = 0.4):
        self.mainline_before_path = mainline_before
        self.mainline_after_path = mainline_after
        self.target_before_path = target_before
        self.similarity_threshold = similarity_threshold
        
        # Parsers
        self.parser_mainline_before = JavaASTParser(mainline_before)
        self.parser_mainline_after = JavaASTParser(mainline_after)
        self.parser_target = JavaASTParser(target_before)
        
        # Extracted segments
        self.segments_mainline_before = {}
        self.segments_mainline_after = {}
        self.segments_target = {}
        
        # Similarity calculator
        self.similarity_calc = SimilarityCalculator()
    
    def parse_files(self):
        """Parse all input files"""
        print("  Parsing mainline_before...")
        if not self.parser_mainline_before.parse():
            raise Exception("Failed to parse mainline_before")
        self.segments_mainline_before = self.parser_mainline_before.extract_all_segments()
        
        print("  Parsing mainline_after...")
        if not self.parser_mainline_after.parse():
            raise Exception("Failed to parse mainline_after")
        self.segments_mainline_after = self.parser_mainline_after.extract_all_segments()
        
        print("  Parsing target_before...")
        if not self.parser_target.parse():
            raise Exception("Failed to parse target_before")
        self.segments_target = self.parser_target.extract_all_segments()
    
    def detect_mainline_changes(self) -> List[Dict[str, Any]]:
        """
        Detect what changed between mainline_before and mainline_after.
        Returns list of changed segments.
        """
        changes = []
        
        # Detect class changes
        changes.extend(self._detect_class_changes())
        
        # Detect enum changes
        changes.extend(self._detect_enum_changes())
        
        # Detect method changes
        changes.extend(self._detect_method_changes())
        
        # Detect field changes
        changes.extend(self._detect_field_changes())
        
        return changes
    
    def find_target_segments(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        For each changed segment in mainline, find corresponding segment in target.
        Returns list of target segments that need backporting.
        
        IMPORTANT: Only includes segments that were MODIFIED (not added/deleted)
        since we need existing code in target to backport changes to.
        """
        results = []
        seen_segments = set()  # Track to avoid duplicates
        
        for change in changes:
            # ONLY process modifications - skip additions and deletions
            if change['operation'] != 'modify':
                continue
            
            seg_type = change['type']
            
            if seg_type == 'class' or seg_type == 'interface':
                matches = self._find_class_matches(change)
            elif seg_type == 'enum':
                matches = self._find_enum_matches(change)
            elif seg_type == 'method':
                matches = self._find_method_matches(change)
            elif seg_type == 'field':
                matches = self._find_field_matches(change)
            else:
                continue
            
            if matches:
                # Take best match only
                best_match = max(matches, key=lambda x: x['similarity'])
                
                # Check if similarity meets threshold
                if best_match['similarity'] >= self.similarity_threshold:
                    # Create unique identifier to avoid duplicates
                    segment_id = (
                        best_match['segment_type'],
                        best_match['name'],
                        best_match['start_line'],
                        best_match['parent_class']
                    )
                    
                    # Only add if not already seen
                    if segment_id not in seen_segments:
                        seen_segments.add(segment_id)
                        results.append(best_match)
        
        return results
    
    def _detect_class_changes(self) -> List[Dict[str, Any]]:
        """Detect changed/added/removed classes"""
        changes = []
        
        before_classes = {c.name: c for c in self.segments_mainline_before['classes']}
        after_classes = {c.name: c for c in self.segments_mainline_after['classes']}
        
        # Check for modifications and additions
        for name, after_class in after_classes.items():
            if name in before_classes:
                before_class = before_classes[name]
                if self._has_class_changed(before_class, after_class):
                    changes.append({
                        'type': 'class',
                        'name': name,
                        'operation': 'modify',
                        'segment': after_class
                    })
            else:
                changes.append({
                    'type': 'class',
                    'name': name,
                    'operation': 'add',
                    'segment': after_class
                })
        
        # Check for deletions
        for name in before_classes:
            if name not in after_classes:
                changes.append({
                    'type': 'class',
                    'name': name,
                    'operation': 'delete',
                    'segment': before_classes[name]
                })
        
        return changes
    
    def _detect_enum_changes(self) -> List[Dict[str, Any]]:
        """Detect changed/added/removed enums"""
        changes = []
        
        before_enums = {e.name: e for e in self.segments_mainline_before['enums']}
        after_enums = {e.name: e for e in self.segments_mainline_after['enums']}
        
        for name, after_enum in after_enums.items():
            if name in before_enums:
                before_enum = before_enums[name]
                if before_enum.signature != after_enum.signature:
                    changes.append({
                        'type': 'enum',
                        'name': name,
                        'operation': 'modify',
                        'segment': after_enum
                    })
            else:
                changes.append({
                    'type': 'enum',
                    'name': name,
                    'operation': 'add',
                    'segment': after_enum
                })
        
        for name in before_enums:
            if name not in after_enums:
                changes.append({
                    'type': 'enum',
                    'name': name,
                    'operation': 'delete',
                    'segment': before_enums[name]
                })
        
        return changes
    
    def _detect_method_changes(self) -> List[Dict[str, Any]]:
        """Detect changed/added/removed methods"""
        changes = []
        
        before_methods = {self._method_key(m): m for m in self.segments_mainline_before['methods']}
        after_methods = {self._method_key(m): m for m in self.segments_mainline_after['methods']}
        
        for key, after_method in after_methods.items():
            if key in before_methods:
                before_method = before_methods[key]
                if self._has_method_changed(before_method, after_method):
                    changes.append({
                        'type': 'method',
                        'name': after_method.name,
                        'operation': 'modify',
                        'segment': after_method
                    })
            else:
                changes.append({
                    'type': 'method',
                    'name': after_method.name,
                    'operation': 'add',
                    'segment': after_method
                })
        
        for key, before_method in before_methods.items():
            if key not in after_methods:
                changes.append({
                    'type': 'method',
                    'name': before_method.name,
                    'operation': 'delete',
                    'segment': before_method
                })
        
        return changes
    
    def _detect_field_changes(self) -> List[Dict[str, Any]]:
        """Detect changed/added/removed fields"""
        changes = []
        
        before_fields = {self._field_key(f): f for f in self.segments_mainline_before['fields']}
        after_fields = {self._field_key(f): f for f in self.segments_mainline_after['fields']}
        
        for key, after_field in after_fields.items():
            if key in before_fields:
                before_field = before_fields[key]
                if before_field.signature != after_field.signature:
                    changes.append({
                        'type': 'field',
                        'name': after_field.name,
                        'operation': 'modify',
                        'segment': after_field
                    })
            else:
                changes.append({
                    'type': 'field',
                    'name': after_field.name,
                    'operation': 'add',
                    'segment': after_field
                })
        
        for key, before_field in before_fields.items():
            if key not in after_fields:
                changes.append({
                    'type': 'field',
                    'name': before_field.name,
                    'operation': 'delete',
                    'segment': before_field
                })
        
        return changes
    
    def _find_class_matches(self, change: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find matching classes in target"""
        matches = []
        changed_segment = change['segment']
        
        for target_class in self.segments_target['classes']:
            similarity = self.similarity_calc.calculate_class_similarity(
                changed_segment, target_class
            )
            
            if similarity > 0:
                matches.append({
                    'segment_type': 'class',
                    'name': target_class.name,
                    'signature': target_class.signature,
                    'file_path': target_class.file_path,
                    'start_line': target_class.start_line,
                    'end_line': target_class.end_line,
                    'similarity': similarity
                })
        
        return matches
    
    def _find_enum_matches(self, change: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find matching enums in target"""
        matches = []
        changed_segment = change['segment']
        
        for target_enum in self.segments_target['enums']:
            similarity = self.similarity_calc.calculate_name_similarity(
                changed_segment.name, target_enum.name
            )
            
            if similarity > 0:
                matches.append({
                    'segment_type': 'enum',
                    'name': target_enum.name,
                    'signature': target_enum.signature,
                    'file_path': target_enum.file_path,
                    'start_line': target_enum.start_line,
                    'end_line': target_enum.end_line,
                    'similarity': similarity
                })
        
        return matches
    
    def _find_method_matches(self, change: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find matching methods in target"""
        matches = []
        changed_segment = change['segment']
        
        for target_method in self.segments_target['methods']:
            similarity = self.similarity_calc.calculate_method_similarity(
                changed_segment, target_method
            )
            
            if similarity > 0:
                matches.append({
                    'segment_type': 'method',
                    'name': target_method.name,
                    'signature': target_method.signature,
                    'file_path': target_method.file_path,
                    'start_line': target_method.start_line,
                    'end_line': target_method.end_line,
                    'parent_class': target_method.parent_class,
                    'similarity': similarity
                })
        
        return matches
    
    def _find_field_matches(self, change: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find matching fields in target"""
        matches = []
        changed_segment = change['segment']
        
        for target_field in self.segments_target['fields']:
            similarity = self.similarity_calc.calculate_field_similarity(
                changed_segment, target_field
            )
            
            if similarity > 0:
                matches.append({
                    'segment_type': 'field',
                    'name': target_field.name,
                    'signature': target_field.signature,
                    'file_path': target_field.file_path,
                    'start_line': target_field.start_line,
                    'end_line': target_field.end_line,
                    'parent_class': target_field.parent_class,
                    'similarity': similarity
                })
        
        return matches
    
    def _has_class_changed(self, before: CodeSegment, after: CodeSegment) -> bool:
        """Check if class has changed"""
        return before.signature != after.signature
    
    def _has_method_changed(self, before: CodeSegment, after: CodeSegment) -> bool:
        """Check if method body has changed"""
        return before.body_hash != after.body_hash
    
    def _method_key(self, method: CodeSegment) -> str:
        """Generate unique key for method"""
        parent = method.parent_class or ''
        params = ','.join(method.parameters)
        return f"{parent}.{method.name}({params})"
    
    def _field_key(self, field: CodeSegment) -> str:
        """Generate unique key for field"""
        parent = field.parent_class or ''
        return f"{parent}.{field.name}"