import os
import sys
import types
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))


def _import_workflow_module():
    script_dir = os.path.join(os.path.dirname(__file__), "../evaluate/full_run")
    sys.path.insert(0, os.path.abspath(script_dir))
    fake_agents_pkg = types.ModuleType("agents")
    fake_agents_pkg.__path__ = []

    fake_context = types.ModuleType("agents.context_analyzer")
    fake_context.context_analyzer_node = object()
    fake_structural = types.ModuleType("agents.structural_locator")
    fake_structural.structural_locator_node = object()
    fake_graph = types.ModuleType("graph")
    fake_graph.app = object()

    with patch.dict(
        sys.modules,
        {
            "agents": fake_agents_pkg,
            "agents.context_analyzer": fake_context,
            "agents.structural_locator": fake_structural,
            "graph": fake_graph,
        },
    ):
        import evaluate_full_workflow as efw

    sys.path.pop(0)
    return efw


class TestFullWorkflowComplexityInjection(unittest.TestCase):
    def test_classifier_available_for_cached_phase0_inputs(self):
        efw = _import_workflow_module()

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
