import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))


class TestSavePipelineLogRunId(unittest.TestCase):
    def test_save_pipeline_log_prefixes_run_id(self):
        script_dir = os.path.join(os.path.dirname(__file__), "../evaluate/full_run")
        sys.path.insert(0, os.path.abspath(script_dir))
        try:
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

            with tempfile.TemporaryDirectory() as td:
                old_results_dir = efw.RESULTS_DIR
                try:
                    efw.RESULTS_DIR = td
                    efw.save_pipeline_log(
                        "crate",
                        "crate_abc",
                        "phase0",
                        "body",
                        run_id="run123",
                    )
                    log_path = os.path.join(td, "crate", "crate_abc", "phase0_log.md")
                    with open(log_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.assertTrue(content.startswith("run_id=run123\n\n"))
                    self.assertIn("body", content)
                finally:
                    efw.RESULTS_DIR = old_results_dir
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    unittest.main()
