"""Regression: dependent_apis extraction must not assume text before '(' is non-empty."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agents.context_analyzer import context_analyzer_node
from utils.patch_analyzer import PatchAnalyzer


class TestDependentApisLeadingParen(unittest.IsolatedAsyncioTestCase):
    async def test_added_line_starting_with_paren_tuple_no_indexerror(self):
        diff = (
            "diff --git a/server/src/main/java/io/crate/X.java"
            " b/server/src/main/java/io/crate/X.java\n"
            "index 111..222 100644\n"
            "--- a/server/src/main/java/io/crate/X.java\n"
            "+++ b/server/src/main/java/io/crate/X.java\n"
            "@@ -1,1 +1,2 @@\n"
            " a\n"
            '+("errcode", flags),\n'
        )
        changes = PatchAnalyzer().analyze(diff)
        state = {
            "patch_diff": diff,
            "patch_analysis": changes,
            "with_test_changes": False,
            "mainline_repo_path": "",
        }
        result = await context_analyzer_node(state, {})
        self.assertIn("semantic_blueprint", result)
        self.assertIsInstance(result["semantic_blueprint"]["dependent_apis"], list)


if __name__ == "__main__":
    unittest.main()
