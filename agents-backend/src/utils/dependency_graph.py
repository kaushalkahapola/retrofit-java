"""
Dependency Graph and Call-site Discovery for Java.
"""

import os
import subprocess
from typing import List, Dict, Any, Optional
from utils.java_ast_editor import JavaASTEditor

class JavaDependencyAnalyzer:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.ast_editor = JavaASTEditor()

    def find_all_call_sites(self, method_name: str, target_file_hint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find all files and line numbers where a method is called.
        """
        # 1. Grep for the method name to find candidate files
        try:
            # -l: list files, -r: recursive, -w: word match
            # Grep -l returns file names with matches
            # Grep -r search recursively
            # Grep -w search for word
            output = subprocess.check_output(
                ["grep", "-r", "-l", "-w", method_name, "."],
                cwd=self.repo_path,
                text=True,
                stderr=subprocess.DEVNULL
            )
            candidate_files = [f.strip().lstrip("./") for f in output.splitlines() if f.strip().endswith(".java")]
        except subprocess.CalledProcessError:
            return []

        call_sites = []
        for file_rel_path in candidate_files:
            file_abs_path = os.path.join(self.repo_path, file_rel_path)
            # 2. Verify with AST
            try:
                with open(file_abs_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                
                root = self.ast_editor.parse(content)
                if not root:
                    continue
                
                # Find all method_invocation nodes
                invocations = self.ast_editor.find_nodes_by_type(root, "method_invocation")
                for node in invocations:
                    name_node = node.child_by_field_name("name")
                    if name_node and name_node.text.decode("utf-8") == method_name:
                        line_num = node.start_point[0] + 1
                        call_sites.append({
                            "file": file_rel_path,
                            "line": line_num,
                            "context": content.splitlines()[line_num-1].strip()
                        })
            except Exception:
                continue
        
        return call_sites

    def find_all_method_definitions(self, method_name: str) -> List[Dict[str, Any]]:
        """
        Find all files where a method is defined.
        """
        try:
            output = subprocess.check_output(
                ["grep", "-r", "-l", "-w", method_name, "."],
                cwd=self.repo_path,
                text=True,
                stderr=subprocess.DEVNULL
            )
            candidate_files = [f.strip().lstrip("./") for f in output.splitlines() if f.strip().endswith(".java")]
        except subprocess.CalledProcessError:
            return []

        definitions = []
        for file_rel_path in candidate_files:
            file_abs_path = os.path.join(self.repo_path, file_rel_path)
            try:
                with open(file_abs_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                
                root = self.ast_editor.parse(content)
                if not root:
                    continue
                
                # Find method_declaration nodes
                node = self.ast_editor.find_method_declaration(root, method_name)
                if node:
                    line_num = node.start_point[0] + 1
                    definitions.append({
                        "file": file_rel_path,
                        "line": line_num,
                        "context": content.splitlines()[line_num-1].strip()
                    })
            except Exception:
                continue
        
        return definitions
