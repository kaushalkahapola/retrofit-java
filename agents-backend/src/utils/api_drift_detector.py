"""
API Drift Detector - Tree-sitter Based Signature Comparison

Detects structural changes (drift) in method signatures between mainline and target versions.
Identifies:
  - ADD_PARAMETER / REMOVE_PARAMETER
  - RENAME_METHOD / RENAME_PARAMETER
  - TYPE_CHANGE
  - MISSING_METHOD
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Set
import tree_sitter_java
from tree_sitter import Language, Parser, Query, Node

_ts_parser = None

def _get_parser():
    global _ts_parser
    if _ts_parser is not None:
        return _ts_parser
    try:
        lang = Language(tree_sitter_java.language())
        _ts_parser = Parser(lang)
        return _ts_parser
    except Exception:
        return None

def extract_method_signatures(source_code: str) -> Dict[str, Any]:
    """
    Extracts all method signatures and class info from Java source code using tree-sitter.
    """
    parser = _get_parser()
    if not parser or not (source_code or "").strip():
        return {"methods": {}, "classes": []}
    
    data = source_code.encode("utf8")
    tree = parser.parse(data)
    root = tree.root_node
    
    methods = {}
    classes = []
    
    def visit(node: Node, current_class: Optional[str] = None):
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                current_class = data[name_node.start_byte:name_node.end_byte].decode("utf8")
                classes.append(current_class)

        if node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            type_node = node.child_by_field_name("type")
            
            if name_node:
                name = data[name_node.start_byte:name_node.end_byte].decode("utf8")
                
                # Extract parameters
                params = []
                if params_node:
                    for i in range(params_node.named_child_count):
                        p = params_node.named_child(i)
                        if p.type == "formal_parameter":
                            p_type = p.child_by_field_name("type")
                            p_name = p.child_by_field_name("name")
                            if p_type and p_name:
                                params.append({
                                    "type": data[p_type.start_byte:p_type.end_byte].decode("utf8"),
                                    "name": data[p_name.start_byte:p_name.end_byte].decode("utf8")
                                })
                
                # Extract return type
                ret_type = "void"
                if type_node:
                    ret_type = data[type_node.start_byte:type_node.end_byte].decode("utf8")
                
                # Full signature string for exact matching
                sig_str = f"{ret_type} {name}({', '.join([f'{p['type']} {p['name']}' for p in params])})"
                
                methods[name] = {
                    "name": name,
                    "class": current_class,
                    "return_type": ret_type,
                    "parameters": params,
                    "signature": sig_str,
                    "param_types": [p["type"] for p in params],
                    "param_names": [p["name"] for p in params]
                }
                
        for i in range(node.child_count):
            visit(node.child(i), current_class)
            
    visit(root)
    return {"methods": methods, "classes": classes}

def detect_drift(mainline_source: str, target_source: str, repomap: Optional[Any] = None) -> Dict[str, Any]:
    """
    Compares mainline and target source code to identify structural drifts.
    If repomap is provided, it also checks for methods moved to parent classes.
    """
    m_info = extract_method_signatures(mainline_source)
    t_info = extract_method_signatures(target_source)
    
    mainline_sigs = m_info["methods"]
    target_sigs = t_info["methods"]
    target_classes = t_info["classes"]
    
    drift_map = {}
    
    for method_name, m_sig in mainline_sigs.items():
        if method_name not in target_sigs:
            # Check for potential renames (heuristic: same param types, different name)
            rename_found = False
            for t_name, t_sig in target_sigs.items():
                if m_sig["param_types"] == t_sig["param_types"] and m_sig["return_type"] == t_sig["return_type"]:
                    drift_map[method_name] = {
                        "drift": "RENAME_METHOD",
                        "mainline_name": method_name,
                        "target_name": t_name,
                        "mainline_signature": m_sig["signature"],
                        "target_signature": t_sig["signature"]
                    }
                    rename_found = True
                    break
            
            if not rename_found and repomap and target_classes:
                # Check parent classes
                for t_cls in target_classes:
                    res = repomap.find_method_in_hierarchy(t_cls, method_name)
                    if res:
                        cls_info, meth_info = res
                        drift_map[method_name] = {
                            "drift": "MOVED_TO_PARENT",
                            "mainline_signature": m_sig["signature"],
                            "target_class": cls_info.name,
                            "target_signature": meth_info.signature,
                            "target_file": cls_info.file_path
                        }
                        rename_found = True
                        break

            if not rename_found:
                drift_map[method_name] = {
                    "drift": "MISSING_METHOD",
                    "mainline_signature": m_sig["signature"]
                }
            continue
            
        t_sig = target_sigs[method_name]
        
        # Compare parameters
        m_params = m_sig["parameters"]
        t_params = t_sig["parameters"]
        
        if m_sig["signature"] != t_sig["signature"]:
            drift_info = {
                "drift": "SIGNATURE_MISMATCH",
                "mainline_signature": m_sig["signature"],
                "target_signature": t_sig["signature"],
                "details": []
            }
            
            if len(m_params) > len(t_params):
                drift_info["drift"] = "ADD_PARAMETER"
                added = [p for p in m_params if p["type"] not in t_sig["param_types"]]
                drift_info["details"].append(f"Added parameters: {added}")
            elif len(m_params) < len(t_params):
                drift_info["drift"] = "REMOVE_PARAMETER"
                removed = [p for p in t_params if p["type"] not in m_sig["param_types"]]
                drift_info["details"].append(f"Removed parameters: {removed}")
            elif m_sig["param_types"] != t_sig["param_types"]:
                drift_info["drift"] = "TYPE_CHANGE"
                changes = []
                for i in range(min(len(m_params), len(t_params))):
                    if m_params[i]["type"] != t_params[i]["type"]:
                        changes.append(f"Param {i}: {t_params[i]['type']} -> {m_params[i]['type']}")
                drift_info["details"].append(f"Type changes: {changes}")
            
            drift_map[method_name] = drift_info
            
    return drift_map
