"""
Tests for Agent 2: Structural Locator.
Uses mocks to avoid real MCP / repo calls.
"""
import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from utils.patch_analyzer import PatchAnalyzer, FileChange
from agents.structural_locator import (
    _infer_modified_methods,
    _find_target_test_file,
    _extract_line_range,
    _locate_method_with_reflection,
)


class TestInferModifiedMethods(unittest.TestCase):
    def test_single_method_from_removed_line(self):
        change = FileChange(
            file_path="Foo.java",
            change_type="MODIFIED",
            removed_lines=["    public void processData() {"],
            added_lines=[],
            is_test_file=False,
        )
        result = _infer_modified_methods(change)
        self.assertIn("processData", result)

    def test_multiple_methods_deduped(self):
        change = FileChange(
            file_path="Foo.java",
            change_type="MODIFIED",
            removed_lines=["    public void processData() {", "    public void processData() {"],
            added_lines=["    private void validate() {"],
            is_test_file=False,
        )
        result = _infer_modified_methods(change)
        self.assertEqual(result.count("processData"), 1)
        self.assertIn("validate", result)

    def test_skips_keywords(self):
        change = FileChange(
            file_path="Foo.java",
            change_type="MODIFIED",
            removed_lines=["        if (x > 0) {", "        for (int i = 0; i < n; i++) {"],
            added_lines=[],
            is_test_file=False,
        )
        result = _infer_modified_methods(change)
        self.assertNotIn("if", result)
        self.assertNotIn("for", result)

    def test_empty_change_returns_empty_list(self):
        change = FileChange(
            file_path="Foo.java",
            change_type="MODIFIED",
            removed_lines=[],
            added_lines=[],
            is_test_file=False,
        )
        result = _infer_modified_methods(change)
        self.assertEqual(result, [])


class TestExtractLineRange(unittest.TestCase):
    def test_dict_with_explicit_lines(self):
        ctx = {"context": "void foo() {}", "start_line": 42, "end_line": 55}
        start, end, snippet = _extract_line_range(ctx)
        self.assertEqual(start, 42)
        self.assertEqual(end, 55)
        self.assertIn("void foo()", snippet)

    def test_dict_without_lines_returns_none(self):
        ctx = {"context": "void foo() {}"}
        start, end, snippet = _extract_line_range(ctx)
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_raw_string_fallback(self):
        start, end, snippet = _extract_line_range("some code string")
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertEqual(snippet, "some code string")


class TestFindTargetTestFile(unittest.TestCase):
    def test_returns_none_for_nonexistent(self):
        result = _find_target_test_file("src/test/Foo.java", "/nonexistent/path")
        self.assertIsNone(result)


class TestLocateMethodReflection(unittest.TestCase):
    """Tests _locate_method_with_reflection with mocked MCP."""

    def test_returns_target_method_on_direct_match(self):
        mock_mcp = MagicMock()
        mock_mcp.call_tool.return_value = {
            "context": "public void readBuffer() { process(buf); }",
            "start_line": 20,
            "end_line": 30,
        }
        result = _locate_method_with_reflection(
            mcp=mock_mcp,
            toolkit=None,
            target_file="src/Foo.java",
            mainline_method="readBuffer",
            target_repo_path="/fake",
            dependent_apis={"buf"},
            consistency_map={},
            trace_lines=[],
            max_attempts=1,
        )
        self.assertEqual(result["target_method"], "readBuffer")
        self.assertEqual(result["start_line"], 20)
        self.assertEqual(result["end_line"], 30)
        self.assertEqual(result["divergence"], "ok")

    def test_detects_missing_dependent_api(self):
        mock_mcp = MagicMock()
        mock_mcp.call_tool.return_value = {
            "context": "public void readBuffer() { }",   # buf missing
            "start_line": 20,
            "end_line": 30,
        }
        result = _locate_method_with_reflection(
            mcp=mock_mcp,
            toolkit=None,
            target_file="src/Foo.java",
            mainline_method="readBuffer",
            target_repo_path="/fake",
            dependent_apis={"buf"},
            consistency_map={},
            trace_lines=[],
            max_attempts=0,  # no retries, should record divergence immediately
        )
        self.assertIn("missing", result["divergence"])

    def test_rename_populates_consistency_map(self):
        """When fingerprinter finds a renamed method, consistency_map is populated."""
        import json

        mock_mcp = MagicMock()
        # First call: method not found (empty context)
        # Second call (renamed method): found
        mock_mcp.call_tool.side_effect = [
            {"context": "", "start_line": None, "end_line": None},   # direct miss
            {"context": "public void legacyReadBuf() { buf.read(); }", "start_line": 5, "end_line": 12},  # rename found
        ]

        mock_toolkit = MagicMock()
        mock_toolkit.find_method_match.return_value = json.dumps({
            "match": {"simpleName": "legacyReadBuf"},
            "confidence": 0.9,
            "reason": "Name Similarity",
        })

        consistency_map: dict = {}
        result = _locate_method_with_reflection(
            mcp=mock_mcp,
            toolkit=mock_toolkit,
            target_file="src/Foo.java",
            mainline_method="readBuffer",
            target_repo_path="/fake",
            dependent_apis=set(),
            consistency_map=consistency_map,
            trace_lines=[],
            max_attempts=1,
        )
        self.assertEqual(consistency_map.get("readBuffer"), "legacyReadBuf")
        self.assertEqual(result["target_method"], "legacyReadBuf")


class TestStructuralLocatorNodeIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_node_produces_maps(self):
        from agents.structural_locator import structural_locator_node

        analyzer = PatchAnalyzer()
        diff = """\
diff --git a/src/main/java/Foo.java b/src/main/java/Foo.java
index 0000000..1111111 100644
--- a/src/main/java/Foo.java
+++ b/src/main/java/Foo.java
@@ -1,3 +1,4 @@
 public class Foo {
     public void process() {
+        if (buf == null) return;
     }
 }"""
        changes = analyzer.analyze(diff)

        state = {
            "semantic_blueprint": {
                "root_cause_hypothesis": "missing null check",
                "fix_logic": "add null guard",
                "dependent_apis": ["buf"],
            },
            "patch_analysis": changes,
            "target_repo_path": "/fake/target",
            "mainline_repo_path": "/fake/mainline",
            "messages": [],
        }

        mock_agent = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.content = """{
            "mappings": [
                {
                    "mainline_method": "process",
                    "target_file": "src/main/java/Foo.java",
                    "target_method": "process",
                    "start_line": 1,
                    "end_line": 5,
                    "code_snippet": "void process() { buf.read(); }"
                }
            ],
            "consistency_map_entries": {}
        }"""
        mock_msg.type = "ai"
        mock_response = {"messages": [mock_msg]}
        mock_agent.ainvoke = AsyncMock(return_value=mock_response)

        mock_retriever = MagicMock()
        mock_retriever.target_repo.working_dir = "/fake/target"

        with patch("agents.structural_locator.create_react_agent", return_value=mock_agent), \
             patch("agents.structural_locator.ChatGoogleGenerativeAI", return_value=MagicMock()), \
             patch("agents.structural_locator.EnsembleRetriever", return_value=mock_retriever), \
             patch("agents.structural_locator.ReasoningToolkit", return_value=MagicMock()):
            result = await structural_locator_node(state, {})

        self.assertIn("consistency_map", result)
        self.assertIn("mapped_target_context", result)
        self.assertIsInstance(result["consistency_map"], dict)
        self.assertIsInstance(result["mapped_target_context"], dict)


if __name__ == "__main__":
    unittest.main()
