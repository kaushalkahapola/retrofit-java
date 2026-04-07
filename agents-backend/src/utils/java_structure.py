"""
Java Structure Parser — Tree-sitter based utilities for navigating and modifying Java files.

Provides deterministic anchors for typed-change insertion:
- find_imports_section: locate import block
- find_class_body: locate class definition body
- find_class_final_brace: find closing brace of a class
- find_method_body: locate method body within a class
- find_field_declarations_end: find where fields end in a class
- has_import: check if an import already exists
"""

from __future__ import annotations
from typing import Optional, Tuple
import os
import re

try:
    import tree_sitter_java
    from tree_sitter import Language, Parser, Node

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

    _HAS_TREE_SITTER = True
except Exception:
    _HAS_TREE_SITTER = False


def find_imports_section(file_path: str) -> Tuple[int, int]:
    """
    Find the line range (1-indexed, inclusive) of the imports section in a Java file.

    Returns: (start_line, end_line) or raises ValueError if no imports found.
    """
    if not os.path.isfile(file_path):
        raise ValueError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    import_start = None
    import_end = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import "):
            if import_start is None:
                import_start = i + 1  # 1-indexed
            import_end = i + 1
        elif import_start is not None and stripped and not stripped.startswith("//"):
            # end of imports section
            break

    if import_start is None:
        raise ValueError(f"No imports found in {file_path}")

    return (import_start, import_end)


def has_import(file_path: str, import_statement: str) -> bool:
    """
    Check if an import statement already exists in the file.

    import_statement: e.g. "java.util.List" or "import static io.crate.execution..."
    """
    if not os.path.isfile(file_path):
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Normalize: if input is "java.util.List", look for "import java.util.List"
    if not import_statement.startswith("import "):
        normalized = f"import {import_statement};"
    else:
        normalized = import_statement if import_statement.endswith(";") else f"{import_statement};"

    return normalized in content


def find_class_body(file_path: str, class_name: str) -> Tuple[int, int]:
    """
    Find the line range (1-indexed) of a class body in a file.

    Returns: (opening_brace_line, closing_brace_line) or raises ValueError if class not found.
    """
    if not os.path.isfile(file_path):
        raise ValueError(f"File not found: {file_path}")

    parser = _get_parser() if _HAS_TREE_SITTER else None
    if parser:
        return _find_class_body_tree_sitter(file_path, class_name, parser)
    else:
        return _find_class_body_regex(file_path, class_name)


def _find_class_body_tree_sitter(file_path: str, class_name: str, parser) -> Tuple[int, int]:
    """Tree-sitter based class body search."""
    with open(file_path, "rb") as f:
        source_bytes = f.read()

    tree = parser.parse(source_bytes)
    root = tree.root_node

    def visit(node: Node) -> Optional[Tuple[int, int]]:
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            body_node = node.child_by_field_name("body")

            if name_node and body_node:
                name_text = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8")
                if name_text == class_name:
                    # body_node is a class_body; its first child is '{', last is '}'
                    open_brace_line = node.start_point[0] + 1  # 0-indexed → 1-indexed
                    close_brace_line = body_node.end_point[0] + 1
                    return (open_brace_line, close_brace_line)

        for i in range(node.child_count):
            result = visit(node.child(i))
            if result:
                return result
        return None

    result = visit(root)
    if result:
        return result
    raise ValueError(f"Class '{class_name}' not found in {file_path}")


def _find_class_body_regex(file_path: str, class_name: str) -> Tuple[int, int]:
    """Fallback: regex-based class body search (when tree-sitter unavailable)."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    class_pattern = re.compile(rf"\bclass\s+{re.escape(class_name)}\b")
    class_line = None

    for i, line in enumerate(lines):
        if class_pattern.search(line):
            class_line = i
            break

    if class_line is None:
        raise ValueError(f"Class '{class_name}' not found in {file_path}")

    # Find opening brace
    brace_depth = 0
    open_brace_line = None
    for i in range(class_line, len(lines)):
        brace_depth += lines[i].count("{") - lines[i].count("}")
        if brace_depth > 0 and open_brace_line is None:
            open_brace_line = i + 1  # 1-indexed

    if open_brace_line is None:
        raise ValueError(f"Opening brace for class '{class_name}' not found")

    # Find closing brace
    for i in range(open_brace_line, len(lines)):
        brace_depth += lines[i].count("{") - lines[i].count("}")
        if brace_depth == 0:
            return (open_brace_line, i + 1)  # 1-indexed

    raise ValueError(f"Closing brace for class '{class_name}' not found")


def find_class_final_brace(file_path: str, class_name: str) -> int:
    """
    Find the line number (1-indexed) of the closing brace of a class.
    """
    _, closing_line = find_class_body(file_path, class_name)
    return closing_line


def find_method_body(file_path: str, class_name: str, method_name: str) -> Tuple[int, int, str]:
    """
    Find the line range (1-indexed) and source text of a method body within a class.

    Returns: (opening_line, closing_line, method_source_text)
    """
    if not os.path.isfile(file_path):
        raise ValueError(f"File not found: {file_path}")

    parser = _get_parser() if _HAS_TREE_SITTER else None
    if parser:
        return _find_method_body_tree_sitter(file_path, class_name, method_name, parser)
    else:
        return _find_method_body_regex(file_path, class_name, method_name)


def _find_method_body_tree_sitter(
    file_path: str, class_name: str, method_name: str, parser
) -> Tuple[int, int, str]:
    """Tree-sitter based method body search."""
    with open(file_path, "rb") as f:
        source_bytes = f.read()

    with open(file_path, "r", encoding="utf-8") as f:
        source_text = f.read()
        lines = source_text.splitlines()

    tree = parser.parse(source_bytes)
    root = tree.root_node

    def visit(node: Node, in_class: Optional[str] = None) -> Optional[Tuple[int, int, str]]:
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name_text = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8")
                if name_text == class_name:
                    in_class = class_name

        if node.type == "method_declaration" and in_class == class_name:
            name_node = node.child_by_field_name("name")
            body_node = node.child_by_field_name("body")

            if name_node and body_node:
                name_text = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8")
                if name_text == method_name:
                    start_line = node.start_point[0] + 1  # 0-indexed → 1-indexed
                    end_line = body_node.end_point[0] + 1
                    method_text = "\n".join(lines[start_line - 1:end_line])
                    return (start_line, end_line, method_text)

        for i in range(node.child_count):
            result = visit(node.child(i), in_class)
            if result:
                return result
        return None

    result = visit(root)
    if result:
        return result
    raise ValueError(f"Method '{method_name}' in class '{class_name}' not found in {file_path}")


def _find_method_body_regex(
    file_path: str, class_name: str, method_name: str
) -> Tuple[int, int, str]:
    """Fallback: regex-based method body search."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find class first
    class_pattern = re.compile(rf"\bclass\s+{re.escape(class_name)}\b")
    class_start = None

    for i, line in enumerate(lines):
        if class_pattern.search(line):
            class_start = i
            break

    if class_start is None:
        raise ValueError(f"Class '{class_name}' not found in {file_path}")

    # Find method within class
    method_pattern = re.compile(rf"\b{re.escape(method_name)}\s*\(")
    method_line = None

    for i in range(class_start, len(lines)):
        if method_pattern.search(lines[i]):
            method_line = i
            break

    if method_line is None:
        raise ValueError(f"Method '{method_name}' in class '{class_name}' not found")

    # Find opening brace of method
    brace_depth = 0
    open_brace_line = None
    for i in range(method_line, len(lines)):
        brace_depth += lines[i].count("{") - lines[i].count("}")
        if brace_depth > 0 and open_brace_line is None:
            open_brace_line = i + 1  # 1-indexed

    if open_brace_line is None:
        raise ValueError(f"Opening brace for method '{method_name}' not found")

    # Find closing brace of method
    for i in range(open_brace_line, len(lines)):
        brace_depth += lines[i].count("{") - lines[i].count("}")
        if brace_depth == 0:
            method_text = "".join(lines[open_brace_line - 1:i + 1])
            return (open_brace_line, i + 1, method_text)  # 1-indexed

    raise ValueError(f"Closing brace for method '{method_name}' not found")


def find_field_declarations_end(file_path: str, class_name: str) -> int:
    """
    Find the line number (1-indexed) where field declarations end in a class
    (i.e., the first line of the first method or the class closing brace if no methods).

    Returns: 1-indexed line number
    """
    if not os.path.isfile(file_path):
        raise ValueError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find class
    class_pattern = re.compile(rf"\bclass\s+{re.escape(class_name)}\b")
    class_start = None

    for i, line in enumerate(lines):
        if class_pattern.search(line):
            class_start = i
            break

    if class_start is None:
        raise ValueError(f"Class '{class_name}' not found in {file_path}")

    # Look for first method declaration after class start
    method_pattern = re.compile(r"\b(public|private|protected)\b.*\(.*\)\s*\{?")

    for i in range(class_start + 1, len(lines)):
        line = lines[i]
        # Skip comments, empty lines
        if line.strip().startswith("//") or not line.strip():
            continue
        # If we see a method signature, this is where fields end
        if method_pattern.search(line) and "(" in line and ")" in line:
            return i + 1  # 1-indexed, return the line BEFORE the method

    # No methods found, return the class closing brace line
    _, closing_brace = find_class_body(file_path, class_name)
    return closing_brace - 1
