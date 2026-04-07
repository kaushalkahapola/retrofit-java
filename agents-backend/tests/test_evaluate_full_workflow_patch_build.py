import io
import os
import sys
import types
import unittest
from unittest.mock import patch

from unidiff import PatchSet


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


class TestBuildAgentEligiblePatch(unittest.TestCase):
    def test_does_not_emit_double_prefix_paths(self):
        efw = _import_workflow_module()

        patch_diff = """diff --git a/server/src/main/java/org/example/Foo.java b/server/src/main/java/org/example/Foo.java
index 1111111..2222222 100644
--- a/server/src/main/java/org/example/Foo.java
+++ b/server/src/main/java/org/example/Foo.java
@@ -1,1 +1,1 @@
-class Foo {}
+class Foo { int x; }
"""

        out = efw._build_agent_eligible_patch(patch_diff)
        self.assertIn(
            "diff --git a/server/src/main/java/org/example/Foo.java b/server/src/main/java/org/example/Foo.java",
            out,
        )
        self.assertNotIn("a/a/server/", out)
        self.assertNotIn("b/b/server/", out)

        patch_set = PatchSet(io.StringIO(out))
        self.assertEqual(len(list(patch_set)), 1)
        parsed = list(patch_set)[0]
        self.assertFalse(parsed.is_rename)
        self.assertEqual(parsed.path, "server/src/main/java/org/example/Foo.java")


if __name__ == "__main__":
    unittest.main()
