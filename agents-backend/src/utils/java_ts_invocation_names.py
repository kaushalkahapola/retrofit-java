"""
Tree-sitter Java: collect simple method-invocation callee names from snippets.

Used to avoid brittle text heuristics for Type V gates: a token like
``startObject`` is the *callee* of a ``method_invocation``, while
``CACHE_EVICTIONS_HISTORY`` in ``builder.startObject(CACHE_EVICTIONS_HISTORY)``
is only an argument, not a callee. This generalizes to new fluent APIs without
maintaining a denylist.

This is not semantic diff across versions (``startObject`` vs ``xContentObject``
are still different callees); compilation and tests remain the real proof.
When parsing fails, helpers return an empty set (fall open).
"""

from __future__ import annotations

_ts_parser = None


def _java_parser():
    global _ts_parser
    if _ts_parser is not None:
        return _ts_parser
    try:
        from tree_sitter import Language, Parser
        import tree_sitter_java

        lang = Language(tree_sitter_java.language())
        _ts_parser = Parser(lang)
        return _ts_parser
    except Exception:
        return None


def _tree_has_error(node) -> bool:
    if node.type == "ERROR" or getattr(node, "is_missing", False):
        return True
    for i in range(node.child_count):
        if _tree_has_error(node.child(i)):
            return True
    return False


def collect_method_invocation_callee_names(java_source: str) -> set[str]:
    """
    Return identifiers that appear as the ``name`` field of ``method_invocation``.
    """
    p = _java_parser()
    if not p or not (java_source or "").strip():
        return set()
    data = java_source.encode("utf8")
    try:
        tree = p.parse(data)
    except Exception:
        return set()
    if _tree_has_error(tree.root_node):
        return set()
    out: set[str] = set()

    def visit(n):
        if n.type == "method_invocation":
            nm = n.child_by_field_name("name")
            if nm is not None and nm.type == "identifier":
                out.add(data[nm.start_byte : nm.end_byte].decode("utf8"))
        for i in range(n.child_count):
            visit(n.child(i))

    visit(tree.root_node)
    return out


def callee_names_from_java_snippet_lines(lines: list[str]) -> set[str]:
    """
    Wrap snippet lines in a minimal class/method so tree-sitter can parse them,
    then return callee names from method invocations inside.
    """
    parts: list[str] = []
    for raw in lines or []:
        s = str(raw or "").strip()
        if s:
            parts.append(s)
    if not parts:
        return set()
    body = ";\n".join(parts)
    if body[-1] not in ";}":
        body += ";"
    wrapped = f"class __TSProbe {{ void __m() {{ {body} }} }}"
    return collect_method_invocation_callee_names(wrapped)
