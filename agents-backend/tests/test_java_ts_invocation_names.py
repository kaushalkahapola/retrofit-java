import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from utils.java_ts_invocation_names import (
    callee_names_from_java_snippet_lines,
    collect_method_invocation_callee_names,
)


class TestJavaTsInvocationNames(unittest.TestCase):
    def test_callee_vs_argument(self):
        src = """class X { void m() { builder.startObject(COMPILATIONS_HISTORY); } }"""
        names = collect_method_invocation_callee_names(src)
        self.assertIn("startObject", names)
        self.assertNotIn("COMPILATIONS_HISTORY", names)

    def test_snippet_wrap_finds_xcontent_object(self):
        lines = [
            "ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);",
        ]
        names = callee_names_from_java_snippet_lines(lines)
        self.assertIn("xContentObject", names)
        self.assertNotIn("CACHE_EVICTIONS_HISTORY", names)


if __name__ == "__main__":
    unittest.main()
