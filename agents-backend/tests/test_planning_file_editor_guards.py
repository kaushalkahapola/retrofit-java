import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agents.file_editor import _collect_required_symbols_from_invariants
from agents.planning_agent import (
    _decompose_hunk_to_required_entries,
    _ensure_required_coverage,
    _enforce_required_replace_lines,
    _preserve_target_only_lines_in_new,
    _preserve_old_argument_lines_in_new,
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
        # Callee-shaped identifiers are not Type V hard requirements (see
        # _type_v_symbol_gate_should_enforce + tree-sitter callee filtering).
        self.assertNotIn("snapshotsInProgress", symbols)


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


class TestPlannerRequiredReplaceGuard(unittest.TestCase):
    def test_enforce_required_replace_keeps_constructor_arg_line(self):
        required = [
            {
                "hunk_index": 3,
                "operation_index": 0,
                "edit_type": "replace",
                "old_string": "            indexNameExpressionResolver,\n            TransportGetAllocationStatsAction.Response::new,\n            threadPool.executor(ThreadPool.Names.MANAGEMENT)\n        );",
                "new_string": "            indexNameExpressionResolver,\n            TransportGetAllocationStatsAction.Response::new,\n            // DIRECT is ok here because we fork the allocation stats computation onto a MANAGEMENT thread if needed, or else we return\n            // very cheaply.\n            EsExecutors.DIRECT_EXECUTOR_SERVICE\n        );\n        final var managementExecutor = threadPool.executor(ThreadPool.Names.MANAGEMENT);\n        this.allocationStatsSupplier = new SingleResultDeduplicator<>(\n            threadPool.getThreadContext(),\n            l -> managementExecutor.execute(ActionRunnable.supply(l, allocationStatsService::stats))\n        );",
                "notes": "required_op_replace",
            }
        ]
        planned = [
            {
                "hunk_index": 3,
                "operation_index": 0,
                "edit_type": "replace",
                "old_string": required[0]["old_string"],
                "new_string": required[0]["new_string"].replace(
                    "            indexNameExpressionResolver,",
                    "            TransportGetAllocationStatsAction.Request::new,",
                ),
                "notes": "required_op_replace|llm",
                "verified": True,
            }
        ]
        target_content = "x\n" + required[0]["old_string"] + "\ny\n"

        out = _enforce_required_replace_lines(planned, required, target_content)
        self.assertEqual(len(out), 1)
        self.assertIn("indexNameExpressionResolver", out[0]["new_string"])
        self.assertEqual(out[0]["new_string"], required[0]["new_string"])
        self.assertIn(
            "required_replace_enforced", out[0].get("verification_result", "")
        )

    def test_preserve_target_only_lines_in_new_keeps_extra_arg(self):
        old_source = """            TransportGetAllocationStatsAction.Request::new,
            TransportGetAllocationStatsAction.Response::new,
            threadPool.executor(ThreadPool.Names.MANAGEMENT)
        );"""
        new_source = """            TransportGetAllocationStatsAction.Request::new,
            TransportGetAllocationStatsAction.Response::new,
            EsExecutors.DIRECT_EXECUTOR_SERVICE
        );"""
        resolved_old_target = """            TransportGetAllocationStatsAction.Request::new,
            indexNameExpressionResolver,
            TransportGetAllocationStatsAction.Response::new,
            threadPool.executor(ThreadPool.Names.MANAGEMENT)
        );"""

        out = _preserve_target_only_lines_in_new(
            old_source=old_source,
            new_source=new_source,
            resolved_old_target=resolved_old_target,
        )
        self.assertIn("indexNameExpressionResolver,", out)

    def test_preserve_old_argument_lines_in_new_keeps_removed_arg(self):
        old_source = """            indexNameExpressionResolver,
            TransportGetAllocationStatsAction.Response::new,
            threadPool.executor(ThreadPool.Names.MANAGEMENT)
        );"""
        new_source = """            TransportGetAllocationStatsAction.Request::new,
            TransportGetAllocationStatsAction.Response::new,
            EsExecutors.DIRECT_EXECUTOR_SERVICE
        );"""

        out = _preserve_old_argument_lines_in_new(
            old_source=old_source,
            new_source=new_source,
        )
        self.assertIn("indexNameExpressionResolver,", out)


if __name__ == "__main__":
    unittest.main()
