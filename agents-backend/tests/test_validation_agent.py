"""
Tests for Agent 4: Validation Agent ("Prove Red, Make Green" loop).
"""
import unittest
import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agents.validation_agent import validation_agent, _extract_test_classes

class TestExtractTestClasses(unittest.TestCase):
    def test_extracts_from_java_path(self):
        hunks = [{"target_file": "src/test/java/org/example/MyTest.java"}]
        classes = _extract_test_classes(hunks)
        self.assertEqual(classes, ["org.example.MyTest"])
        
    def test_no_java_path_safe_fallback(self):
        hunks = [{"target_file": "src/tests/MyTest.cpp"}]
        classes = _extract_test_classes(hunks)
        self.assertEqual(classes, [])


class TestValidationAgentIntegration(unittest.IsolatedAsyncioTestCase):

    def _make_state(self, code_hunks=None, test_hunks=None, attempts=0):
        if code_hunks is None:
            code_hunks = [{"target_file": "src/main/Foo.java", "hunk_text": "@@\n+fix"}]
        if test_hunks is None:
            test_hunks = [{"target_file": "src/test/java/org/FooTest.java", "hunk_text": "@@\n+test"}]
            
        return {
            "target_repo_path": "/fake/repo",
            "adapted_code_hunks": code_hunks,
            "adapted_test_hunks": test_hunks,
            "validation_attempts": attempts,
            "semantic_blueprint": {"root_cause_hypothesis": "bug", "fix_logic": "fix"},
            "messages": []
        }

    @patch("agents.validation_agent.ValidationToolkit")
    async def test_happy_path(self, mock_toolkit_class):
        mock_toolkit = MagicMock()
        mock_toolkit_class.return_value = mock_toolkit
        
        # Phase 1: test apply yields success
        # Phase 3: code+test apply yields success
        mock_toolkit.apply_adapted_hunks.side_effect = [
            {"success": True, "output": "ok"}, # Phase 1
            {"success": True, "output": "ok"}  # Phase 3
        ]
        
        # Phase 2: targeted test fails (prove red)
        # Phase 4: targeted test passes (make green)
        mock_toolkit.run_targeted_tests.side_effect = [
            {"success": False, "compile_error": False, "output": "test failed - expected"}, # Phase 2
            {"success": True, "compile_error": False, "output": "tests passed!"} # Phase 4
        ]
        
        state = self._make_state()
        result = await validation_agent(state, {})
        
        self.assertTrue(result.get("validation_passed"))
        self.assertEqual(mock_toolkit.run_targeted_tests.call_count, 2)
        self.assertEqual(mock_toolkit.apply_adapted_hunks.call_count, 2)
        
    @patch("agents.validation_agent.ValidationToolkit")
    async def test_compile_error_in_phase_2_fails_agent(self, mock_toolkit_class):
        mock_toolkit = MagicMock()
        mock_toolkit_class.return_value = mock_toolkit
        
        mock_toolkit.apply_adapted_hunks.return_value = {"success": True, "output": "ok"}
        
        # Tests fail to compile!
        mock_toolkit.run_targeted_tests.return_value = {"success": False, "compile_error": True, "output": "compilation error"}
        
        state = self._make_state()
        result = await validation_agent(state, {})
        
        self.assertFalse(result.get("validation_passed"))
        self.assertIn("compilation error", result.get("validation_error_context", "").lower())
        
    @patch("agents.validation_agent.ValidationToolkit")
    async def test_test_passes_initially_fails_agent(self, mock_toolkit_class):
        mock_toolkit = MagicMock()
        mock_toolkit_class.return_value = mock_toolkit
        
        mock_toolkit.apply_adapted_hunks.return_value = {"success": True, "output": "ok"}
        
        # Tests PASSED initially (did not prove red)
        mock_toolkit.run_targeted_tests.return_value = {"success": True, "compile_error": False, "output": "passed"}
        
        state = self._make_state()
        result = await validation_agent(state, {})
        
        self.assertFalse(result.get("validation_passed"))
        self.assertIn("BEFORE the fix was applied", result.get("validation_error_context", ""))
        
    @patch("agents.validation_agent.ValidationToolkit")
    async def test_test_fails_after_fix_fails_agent(self, mock_toolkit_class):
        mock_toolkit = MagicMock()
        mock_toolkit_class.return_value = mock_toolkit
        
        mock_toolkit.apply_adapted_hunks.return_value = {"success": True, "output": "ok"}
        
        # Phase 2: fails properly. Phase 4: fails STILL
        mock_toolkit.run_targeted_tests.side_effect = [
            {"success": False, "compile_error": False, "output": "failed"},
            {"success": False, "compile_error": False, "output": "still failed!"}
        ]
        
        state = self._make_state()
        result = await validation_agent(state, {})
        
        self.assertFalse(result.get("validation_passed"))
        self.assertIn("tests failed or compile aborted", result.get("validation_error_context", ""))

    @patch("agents.validation_agent.ValidationToolkit")
    @patch("agents.validation_agent.ChatGoogleGenerativeAI")
    async def test_synthesis_triggered_if_no_tests(self, mock_llm_class, mock_toolkit_class):
        mock_llm = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = "@@ -1 +1 @@\n+ public void testVuln() {}"
        mock_llm.ainvoke.return_value = mock_resp
        mock_llm_class.return_value = mock_llm
        
        mock_toolkit = MagicMock()
        mock_toolkit_class.return_value = mock_toolkit
        
        mock_toolkit.apply_hunk_dry_run.return_value = {"success": True}
        
        mock_toolkit.apply_adapted_hunks.return_value = {"success": True, "output": "ok"}
        mock_toolkit.run_targeted_tests.side_effect = [
            {"success": False, "compile_error": False, "output": "fail"},
            {"success": True, "compile_error": False, "output": "pass"}
        ]
        
        # No test hunks!
        state = self._make_state(test_hunks=[])
        result = await validation_agent(state, {})
        
        self.assertTrue(result.get("validation_passed"))
        self.assertEqual(len(result.get("adapted_test_hunks", [])), 1)
        
        
if __name__ == "__main__":
    unittest.main()
