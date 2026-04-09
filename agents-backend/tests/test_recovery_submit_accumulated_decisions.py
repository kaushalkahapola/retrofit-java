import os
import sys
import tempfile
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

try:
    from agents.recovery_agent import RecoveryPlanToolkit
    from agents.recovery_agent import _extract_partial_feedback
except Exception:
    RecoveryPlanToolkit = None
    _extract_partial_feedback = None


class TestRecoverySubmitAccumulatedDecisions(unittest.TestCase):
    def test_submit_reuses_prior_obligation_decisions(self):
        if RecoveryPlanToolkit is None:
            self.skipTest(
                "agents.recovery_agent import unavailable in this environment"
            )
        with tempfile.TemporaryDirectory() as td:
            rel = "A.java"
            fp = os.path.join(td, rel)
            with open(fp, "w", encoding="utf-8") as f:
                f.write("class A {\n    int x = 1;\n}\n")

            patch_diff = (
                "diff --git a/A.java b/A.java\n"
                "index 0000000..1111111 100644\n"
                "--- a/A.java\n"
                "+++ b/A.java\n"
                "@@ -1,3 +1,3 @@\n"
                " class A {\n"
                "-    int x = 1;\n"
                "+    int x = 2;\n"
                " }\n"
            )

            state = {
                "patch_diff": patch_diff,
                "mapped_target_context": {},
                "recovery_obligations": [
                    {
                        "obligation_id": "patch_file:A.java:",
                        "required_file": "A.java",
                        "status": "pending",
                    }
                ],
            }

            tk = RecoveryPlanToolkit(
                state=state,
                target_repo_path=td,
                mainline_repo_path=td,
                required_patch_files=[rel],
            )

            first = tk.submit_recovery_plan(
                edit_ops={
                    rel: [
                        {
                            "hunk_index": 1,
                            "target_file": rel,
                            "edit_type": "replace",
                            "old_string": "    int x = 1;",
                            "new_string": "    int x = 2;",
                        }
                    ]
                },
                obligation_decisions=[
                    {
                        "obligation_id": "patch_file:A.java:",
                        "status": "edited",
                        "reason": "applied",
                    }
                ],
            )
            self.assertTrue(first.startswith("SUCCESS:"), first)

            second = tk.submit_recovery_plan(
                edit_ops={
                    rel: [
                        {
                            "hunk_index": 1,
                            "target_file": rel,
                            "edit_type": "replace",
                            "old_string": "    int x = 1;",
                            "new_string": "    int x = 2;",
                        }
                    ]
                }
            )
            self.assertTrue(second.startswith("SUCCESS:"), second)
            self.assertEqual(len(tk.get_submitted_decisions()), 1)


class TestRecoveryPartialFeedbackParser(unittest.TestCase):
    def test_extracts_missing_files_hunks_and_anchor_failures(self):
        if _extract_partial_feedback is None:
            self.skipTest(
                "agents.recovery_agent import unavailable in this environment"
            )
        msg = (
            "PARTIAL: some ops accepted into accumulator, but anchor verification failed for others AND coverage is still incomplete.\n"
            "Accumulator now covers: ['A.java']\n"
            "Still missing files:\n"
            "  - B.java\n"
            "Still missing hunks: B.java#h1, C.java#h2\n"
            "Anchor failures (fix old_string to match target VERBATIM):\n"
            "  - B.java#op[0]: old_string NOT FOUND in target file\n"
            "Next call: submit ops ONLY for the still-missing files.\n"
        )
        out = _extract_partial_feedback(msg)
        self.assertEqual(out.get("missing_files"), ["B.java"])
        self.assertEqual(out.get("missing_hunks"), ["B.java#h1", "C.java#h2"])
        self.assertEqual(
            out.get("anchor_failures"),
            ["B.java#op[0]: old_string NOT FOUND in target file"],
        )


if __name__ == "__main__":
    unittest.main()
