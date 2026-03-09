"""
Tests for ReasoningToolkit tools in Phase 5.
"""
import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
from agents.reasoning_tools import ReasoningToolkit

class TestReasoningToolkitPhase5(unittest.TestCase):
    def setUp(self):
        self.retriever = MagicMock()
        self.toolkit = ReasoningToolkit(
            retriever=self.retriever,
            target_repo_path="/fake/target",
            mainline_repo_path="/fake/mainline",
            patch_analysis=[]
        )

    @patch.object(ReasoningToolkit, "get_class_context")
    def test_get_function_body(self, mock_get_class_context):
        # Mock get_class_context to return a specific structure
        mock_get_class_context.return_value = {"context": "public void test() {}", "start_line": 10, "end_line": 12}
        
        result = self.toolkit.get_function_body("src/org/Test.java", "test", use_mainline=True)
        self.assertIn("public void test() {}", result)
        mock_get_class_context.assert_called_with("src/org/Test.java", focus_method="test", use_mainline=True)

    @patch("agents.reasoning_tools.subprocess.run")
    def test_git_log_follow(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "a1b2c3d Rename src/old to src/new"
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        res = self.toolkit.git_log_follow("src/new")
        self.assertEqual(res, "a1b2c3d Rename src/old to src/new")
        mock_run.assert_called_with(
            ["git", "log", "--follow", "--name-status", "--oneline", "--", "src/new"],
            capture_output=True, text=True, cwd="/fake/target", check=True
        )

    @patch("agents.reasoning_tools.subprocess.run")
    def test_git_blame_lines(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "a1b2c3d (User 2023-01-01 10) code line"
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        res = self.toolkit.git_blame_lines("src/Test.java", 10, 20)
        self.assertEqual(res, "a1b2c3d (User 2023-01-01 10) code line")
        mock_run.assert_called_with(
            ["git", "blame", "-L", "10,20", "--", "src/Test.java"],
            capture_output=True, text=True, cwd="/fake/target", check=True
        )

    def test_map_hunk_lines(self):
        target_body = "public void foo() {\n    int a = 1;\n    int b = 2;\n    return a + b;\n}"
        mainline_hunk = "@@ -2,3 +2,4 @@\n     int a = 1;\n+    int c = 3;\n     int b = 2;\n"
        
        # The context line is '    int a = 1;' which is line 2 of target_body (1-indexed)
        line_num = self.toolkit.map_hunk_lines(mainline_hunk, target_body)
        self.assertEqual(line_num, 2)
        
        # Test fallback
        line_num_fallback = self.toolkit.map_hunk_lines("@@ \n+ just insertion\n", target_body)
        self.assertEqual(line_num_fallback, 1)


if __name__ == "__main__":
    unittest.main()
