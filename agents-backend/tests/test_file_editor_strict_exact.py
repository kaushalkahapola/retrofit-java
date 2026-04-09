import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))


try:
    from agents.file_editor import _apply_edit_deterministically
    from agents.file_editor import _should_use_mainline_fast_path
except Exception:
    _apply_edit_deterministically = None
    _should_use_mainline_fast_path = None


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


class TestMainlineFastPathGuard(unittest.TestCase):
    def test_disabled_when_recovery_mode_active(self):
        if _should_use_mainline_fast_path is None:
            self.skipTest("agents.file_editor import unavailable in this environment")
        state = {"recovery_agent_mode": True}
        self.assertFalse(_should_use_mainline_fast_path(state))

    def test_disabled_when_recovery_plan_exists(self):
        if _should_use_mainline_fast_path is None:
            self.skipTest("agents.file_editor import unavailable in this environment")
        state = {"recovery_plan_text": "plan"}
        self.assertFalse(_should_use_mainline_fast_path(state))

    def test_enabled_for_normal_flow(self):
        if _should_use_mainline_fast_path is None:
            self.skipTest("agents.file_editor import unavailable in this environment")
        state = {}
        self.assertTrue(_should_use_mainline_fast_path(state))


if __name__ == "__main__":
    unittest.main()
