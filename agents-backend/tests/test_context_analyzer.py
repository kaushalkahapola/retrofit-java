"""
Tests for Agent 1: Context Analyzer.
Uses unittest.mock to avoid real LLM calls.
"""
import unittest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

# Import the utils we need to mock
from utils.patch_analyzer import PatchAnalyzer, FileChange
from state import SemanticBlueprint


MOCK_BLUEPRINT_JSON = """{
    "root_cause_hypothesis": "Missing null check before buffer dereference",
    "fix_logic": "Added if (buf == null) return; guard before buffer read",
    "dependent_apis": ["buf", "MAX_SIZE", "readBuffer"]
}"""

SAMPLE_DIFF = (
    "diff --git a/src/main/java/com/example/NetUtils.java"
    " b/src/main/java/com/example/NetUtils.java\n"
    "index 83a2a08..1234567 100644\n"
    "--- a/src/main/java/com/example/NetUtils.java\n"
    "+++ b/src/main/java/com/example/NetUtils.java\n"
    "@@ -10,3 +10,4 @@ public class NetUtils {\n"
    "     public void readBuffer() {\n"
    "-        process(buf);\n"
    "+        if (buf == null) return;\n"
    "+        process(buf);\n"
    "     }\n"
    " }\n"
)


class TestContextAnalyzerBlueprintParsing(unittest.TestCase):
    """Tests _parse_blueprint() in isolation."""

    def setUp(self):
        from agents.context_analyzer import _parse_blueprint
        self._parse = _parse_blueprint

    def test_valid_json_parses_correctly(self):
        result = self._parse(MOCK_BLUEPRINT_JSON)
        self.assertIsNotNone(result)
        self.assertEqual(result["root_cause_hypothesis"], "Missing null check before buffer dereference")
        self.assertEqual(result["fix_logic"], "Added if (buf == null) return; guard before buffer read")
        self.assertIn("buf", result["dependent_apis"])
        self.assertIn("MAX_SIZE", result["dependent_apis"])

    def test_json_with_markdown_fences_parses(self):
        fenced = f"```json\n{MOCK_BLUEPRINT_JSON}\n```"
        result = self._parse(fenced)
        self.assertIsNotNone(result)
        self.assertEqual(result["root_cause_hypothesis"], "Missing null check before buffer dereference")

    def test_invalid_json_returns_none(self):
        result = self._parse("not json at all")
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        result = self._parse("")
        self.assertIsNone(result)


class TestInferMethodName(unittest.TestCase):
    """Tests _infer_method_name() in isolation."""

    def setUp(self):
        from agents.context_analyzer import _infer_method_name
        self._infer = _infer_method_name

    def test_infers_from_removed_lines(self):
        change = FileChange(
            file_path="Foo.java",
            change_type="MODIFIED",
            removed_lines=["    public void readBuffer() {"],
            added_lines=[],
            is_test_file=False,
        )
        result = self._infer(change)
        self.assertEqual(result, "readBuffer")

    def test_skips_java_keywords(self):
        change = FileChange(
            file_path="Foo.java",
            change_type="MODIFIED",
            removed_lines=["        if (buf == null) {"],
            added_lines=[],
            is_test_file=False,
        )
        result = self._infer(change)
        self.assertIsNone(result)

    def test_falls_back_to_added_lines(self):
        change = FileChange(
            file_path="Foo.java",
            change_type="MODIFIED",
            removed_lines=[],
            added_lines=["    private static void validateBuf() {"],
            is_test_file=False,
        )
        result = self._infer(change)
        self.assertEqual(result, "validateBuf")


class TestContextAnalyzerNodeIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration test for context_analyzer_node with mocked LLM and MCP."""

    async def test_node_produces_semantic_blueprint(self):
        from agents.context_analyzer import context_analyzer_node

        # Build a real FileChange via PatchAnalyzer
        analyzer = PatchAnalyzer()
        changes = analyzer.analyze(SAMPLE_DIFF)

        state = {
            "patch_diff": SAMPLE_DIFF,
            "patch_analysis": changes,
            "mainline_repo_path": "/fake/mainline",
            "target_repo_path": "/fake/target",
            "original_commit": "abc123",
            "messages": [],
        }

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = MOCK_BLUEPRINT_JSON

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # Mock MCP client to avoid real server calls
        mock_mcp = MagicMock()
        mock_mcp.call_tool.return_value = {
            "context": "public void readBuffer() { process(buf); }",
            "start_line": 10,
            "end_line": 14,
        }

        with patch("agents.context_analyzer.ChatGoogleGenerativeAI", return_value=mock_llm), \
             patch("agents.context_analyzer.get_client", return_value=mock_mcp):
            result = await context_analyzer_node(state, {})

        self.assertIn("semantic_blueprint", result)
        bp = result["semantic_blueprint"]
        self.assertIn("root_cause_hypothesis", bp)
        self.assertIn("fix_logic", bp)
        self.assertIn("dependent_apis", bp)
        # Verify LLM was called
        self.assertTrue(mock_llm.ainvoke.called)

    async def test_node_returns_error_on_missing_patch_diff(self):
        from agents.context_analyzer import context_analyzer_node

        state = {
            "patch_diff": "",
            "patch_analysis": [],
            "messages": [],
        }
        result = await context_analyzer_node(state, {})
        # Should return an error message without crashing
        self.assertIn("messages", result)
        self.assertTrue(any("Error" in str(m.content) for m in result["messages"]))


if __name__ == "__main__":
    unittest.main()
