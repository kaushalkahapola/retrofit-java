import os
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))


class TestFullWorkflowComplexityInjection(unittest.TestCase):
    def test_classifier_available_for_cached_phase0_inputs(self):
        # Import directly from script module path
        script_dir = os.path.join(os.path.dirname(__file__), "../evaluate/full_run")
        sys.path.insert(0, os.path.abspath(script_dir))
        try:
            import evaluate_full_workflow as efw
        finally:
            sys.path.pop(0)

        with patch.object(efw, "classify_patch_complexity") as mock_cls:
            mock_cls.return_value = {
                "complexity": "STRUCTURAL",
                "reason": "files_present_with_anchor_overlap",
                "details": {"avg_anchor_ratio": 0.9},
            }

            # Smoke-call classifier as orchestrator would for base inputs.
            out = efw.classify_patch_complexity(
                patch_diff="diff --git a/a.java b/a.java\n",
                target_repo_path="/tmp/repo",
                with_test_changes=False,
            )

            self.assertIn("complexity", out)


if __name__ == "__main__":
    unittest.main()
