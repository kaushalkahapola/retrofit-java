"""
RepoMap Utility - Compressed Symbol Map for Cross-File Analysis

Builds a map of classes, methods, and inheritance to detect API drifts that 
span multiple files (e.g., methods moved to parent classes).
"""

from __future__ import annotations
import os
import re
import json
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict

@dataclass
class MethodInfo:
    name: str
    signature: str
    return_type: str
    parameters: List[Dict[str, str]]
    is_static: bool
    is_public: bool

@dataclass
class ClassInfo:
    name: str
    file_path: str
    superclass: Optional[str]
    interfaces: List[str]
    methods: Dict[str, MethodInfo]
    fields: List[str]

class RepoMap:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.classes: Dict[str, ClassInfo] = {}
        self.symbol_to_classes: Dict[str, Set[str]] = {} # method_name -> set of class_names

    def add_class(self, class_info: ClassInfo):
        self.classes[class_info.name] = class_info
        for method_name in class_info.methods:
            if method_name not in self.symbol_to_classes:
                self.symbol_to_classes[method_name] = set()
            self.symbol_to_classes[method_name].add(class_info.name)

    def find_method_in_hierarchy(self, class_name: str, method_name: str) -> Optional[tuple[ClassInfo, MethodInfo]]:
        """
        Recursively searches for a method in the class hierarchy.
        """
        if class_name not in self.classes:
            return None
        
        cls = self.classes[class_name]
        if method_name in cls.methods:
            return cls, cls.methods[method_name]
        
        if cls.superclass and cls.superclass in self.classes:
            return self.find_method_in_hierarchy(cls.superclass, method_name)
        
        for iface in cls.interfaces:
            if iface in self.classes:
                res = self.find_method_in_hierarchy(iface, method_name)
                if res:
                    return res
        
        return None

    def get_compressed_map(self, focus_files: List[str]) -> str:
        """
        Returns a string representation of the map, focused on the given files and their neighbors.
        """
        relevant_classes = set()
        for f in focus_files:
            for cls_name, cls in self.classes.items():
                if cls.file_path == f:
                    relevant_classes.add(cls_name)
                    if cls.superclass: relevant_classes.add(cls.superclass)
                    relevant_classes.update(cls.interfaces)

        # Add one level of children/parents for context
        extended_relevant = set(relevant_classes)
        for cls_name in relevant_classes:
            if cls_name in self.classes:
                cls = self.classes[cls_name]
                if cls.superclass: extended_relevant.add(cls.superclass)
                extended_relevant.update(cls.interfaces)

        output = []
        for cls_name in sorted(extended_relevant):
            if cls_name not in self.classes:
                continue
            cls = self.classes[cls_name]
            line = f"class {cls_name}"
            if cls.superclass: line += f" extends {cls.superclass}"
            if cls.interfaces: line += f" implements {', '.join(cls.interfaces)}"
            output.append(line + " {")
            for m_name, m in cls.methods.items():
                if m.is_public:
                    output.append(f"  {m.signature}")
            output.append("}")
        
        return "\n".join(output)

def build_repomap_from_analysis(repo_path: str, structural_analyses: List[Dict[str, Any]]) -> RepoMap:
    """
    Constructs a RepoMap from a list of structural analysis results (from get_structural_analysis).
    """
    rm = RepoMap(repo_path)
    for analysis in structural_analyses:
        file_path = analysis.get("file_path", "")
        for cls_data in analysis.get("classes", []):
            methods = {}
            for m_data in cls_data.get("methods", []):
                name = m_data.get("name", "")
                methods[name] = MethodInfo(
                    name=name,
                    signature=m_data.get("signature", ""),
                    return_type=m_data.get("returnType", ""),
                    parameters=m_data.get("parameters", []),
                    is_static=m_data.get("isStatic", False),
                    is_public=m_data.get("isPublic", True)
                )
            
            cls_info = ClassInfo(
                name=cls_data.get("name", ""),
                file_path=file_path,
                superclass=cls_data.get("superclass"),
                interfaces=cls_data.get("interfaces", []),
                methods=methods,
                fields=[f.get("name") for f in cls_data.get("fields", [])]
            )
            rm.add_class(cls_info)
    return rm
