"""
Shared heuristics for scanning + lines in unified Java diffs.

Unified diffs often split a local declaration across lines (e.g. `List<T> x =`
on one + line and the RHS on the next). Those must not be treated as
truncated/dangling assignments.
"""

from __future__ import annotations

import re


def should_flag_dangling_equals_on_added_line(s: str) -> bool:
    """
    Return True if a stripped added line ending with `=` looks like a real
    syntax error, not a wrapped local declaration.
    """
    if not s.endswith("=") or s.endswith("=="):
        return False
    head = s[:-1].rstrip()
    if "<" in head:
        return False
    if re.search(r"\b(var|final)\s+[A-Za-z_]\w*\s*$", head):
        return False
    if re.search(
        r"\b(?:byte|short|int|long|float|double|boolean|char)\s+[A-Za-z_]\w*\s*$",
        head,
    ):
        return False
    if re.search(
        r"\b(?:String|Object|Class|Void|Integer|Long|Double|Float|Boolean)\s+"
        r"[A-Za-z_]\w*\s*$",
        head,
    ):
        return False
    return True
