import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))


try:
    from agents.file_editor import _apply_edit_deterministically
except Exception:
    _apply_edit_deterministically = None


class _FakeToolkit:
    def __init__(self):
        self.calls = []

    def str_replace_in_file(self, target_file, old_string, new_string):
        self.calls.append((target_file, old_string, new_string))
        return "SUCCESS"


class TestFileEditorStrictExact(unittest.TestCase):
    def test_strict_exact_rejects_trimmed_multiline_match(self):
        if _apply_edit_deterministically is None:
            self.skipTest("agents.file_editor import unavailable in this environment")

        import tempfile

        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "A.java")
            with open(fp, "w", encoding="utf-8") as f:
                f.write("x\nindexNameExpressionResolver,\n")

            tk = _FakeToolkit()
            plan = {
                "edit_type": "replace",
                "old_string": "x\n            indexNameExpressionResolver,\n",
                "new_string": "x\n            TransportGetAllocationStatsAction.Request::new,\n",
            }

            ok, msg, _, _, reason = _apply_edit_deterministically(
                tk,
                td,
                plan,
                "A.java",
                strict_exact=True,
            )

            self.assertFalse(ok)
            self.assertIn("old_resolution_failed", msg)
            self.assertEqual(reason, "not_found_multiline_strict")
            self.assertEqual(len(tk.calls), 0)


if __name__ == "__main__":
    unittest.main()
