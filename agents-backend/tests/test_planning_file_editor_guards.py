import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agents.file_editor import _collect_required_symbols_from_invariants
from agents.planning_agent import _decompose_hunk_to_required_entries


class TestPlannerAnchorGuards(unittest.TestCase):
    def test_insertion_avoids_weak_brace_anchor(self):
        raw_hunk = """@@ -1,3 +1,6 @@
 public class A {
     int x;
+    // inserted one
+    // inserted two
 }
 """
        entries = _decompose_hunk_to_required_entries(
            hunk_idx=0,
            raw_hunk=raw_hunk,
            target_file="A.java",
            consistency_map={},
        )
        self.assertTrue(entries)
        self.assertNotEqual((entries[0].get("old_string") or "").strip(), "}")


class TestFileEditorSymbolGuards(unittest.TestCase):
    def test_required_symbols_ignores_this_super(self):
        invariants = [
            "this(clusterService);",
            "super(config);",
            "snapshotsInProgress(s, repo);",
        ]
        symbols = _collect_required_symbols_from_invariants(invariants)
        self.assertNotIn("this", symbols)
        self.assertNotIn("super", symbols)
        self.assertIn("snapshotsInProgress", symbols)


if __name__ == "__main__":
    unittest.main()
