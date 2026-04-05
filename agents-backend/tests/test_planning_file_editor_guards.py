import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agents.file_editor import _collect_required_symbols_from_invariants
from agents.planning_agent import (
    _decompose_hunk_to_required_entries,
    _ensure_required_coverage,
)


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


class TestCoverageMatchingGuards(unittest.TestCase):
    def test_operation_index_alone_does_not_mask_missing_required_insert(self):
        req = {
            "hunk_index": 2,
            "operation_index": 3,
            "edit_type": "insert_before",
            "old_string": "    @VisibleForTesting",
            "new_string": "        this.clusterService = clusterService;\n    @VisibleForTesting",
        }
        got = {
            "hunk_index": 2,
            "operation_index": 3,
            "edit_type": "insert_before",
            "old_string": "     }",
            "new_string": "        this.clusterService = clusterService;\n     }",
        }

        out = _ensure_required_coverage([got], [req])
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
