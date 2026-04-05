"""
Java AST Editor using Tree-sitter.
Provides utilities for syntactically aware code transformations.
"""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any, Tuple
from tree_sitter import Language, Parser, Node

class JavaASTEditor:
    def __init__(self):
        self._parser = self._initialize_parser()

    def _initialize_parser(self) -> Optional[Parser]:
        try:
            import tree_sitter_java
            lang = Language(tree_sitter_java.language())
            parser = Parser(lang)
            return parser
        except ImportError:
            return None
        except Exception:
            return None

    def parse(self, source_code: str) -> Optional[Node]:
        if not self._parser:
            return None
        tree = self._parser.parse(bytes(source_code, "utf8"))
        if self._tree_has_error(tree.root_node):
            # We still return the root node but maybe log a warning
            pass
        return tree.root_node

    def _tree_has_error(self, node: Node) -> bool:
        if node.type == "ERROR" or getattr(node, "is_missing", False):
            return True
        for i in range(node.child_count):
            if self._tree_has_error(node.child(i)):
                return True
        return False

    def find_method_declaration(self, root: Node, method_name: str) -> Optional[Node]:
        """Find a method declaration node by name."""
        def visit(node: Node) -> Optional[Node]:
            if node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                if name_node and name_node.text.decode("utf8") == method_name:
                    return node
            
            for i in range(node.child_count):
                res = visit(node.child(i))
                if res:
                    return res
            return None
        
        return visit(root)

    def find_class_declaration(self, root: Node, class_name: str) -> Optional[Node]:
        """Find a class declaration node by name."""
        def visit(node: Node) -> Optional[Node]:
            if node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node and name_node.text.decode("utf8") == class_name:
                    return node
            
            for i in range(node.child_count):
                res = visit(node.child(i))
                if res:
                    return res
            return None
        
        return visit(root)

    def get_node_text(self, node: Node, source_code: str) -> str:
        return source_code[node.start_byte : node.end_byte]

    def replace_node(self, source_code: str, node: Node, replacement: str) -> str:
        """Replace a node's text in the source code."""
        return (
            source_code[:node.start_byte] +
            replacement +
            source_code[node.end_byte:]
        )

    def insert_before_node(self, source_code: str, node: Node, text: str) -> str:
        """Insert text before a node."""
        return (
            source_code[:node.start_byte] +
            text +
            source_code[node.start_byte:]
        )

    def insert_after_node(self, source_code: str, node: Node, text: str) -> str:
        """Insert text after a node."""
        return (
            source_code[:node.end_byte] +
            text +
            source_code[node.end_byte:]
        )

    def find_nodes_by_type(self, root: Node, node_type: str) -> List[Node]:
        """Find all nodes of a specific type."""
        out = []
        def visit(node: Node):
            if node.type == node_type:
                out.append(node)
            for i in range(node.child_count):
                visit(node.child(i))
        visit(root)
        return out
