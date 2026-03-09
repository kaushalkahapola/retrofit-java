"""
Tests for Agent 3: Hunk Generator.
All LLM and toolkit calls are mocked.
"""
import unittest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agents.hunk_generator import (
    _extract_hunk_block,
    _check_intent,
    _format_consistency_map,
    _rewrite_hunk_symbols,
    _adjust_hunk_header,
)


# ---------------------------------------------------------------------------
# _extract_hunk_block
# ---------------------------------------------------------------------------

class TestExtractHunkBlock(unittest.TestCase):

    def test_extracts_bare_hunk(self):
        raw = "@@ -10,3 +10,4 @@\n public void foo() {\n-    old();\n+    newGuard();\n+    old();\n }\n"
        result = _extract_hunk_block(raw)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("@@"))
        self.assertIn("+    newGuard();", result)

    def test_strips_markdown_fence(self):
        raw = "```diff\n@@ -1,2 +1,3 @@\n public class Foo {\n+    int x;\n }\n```"
        result = _extract_hunk_block(raw)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("@@"))

    def test_strips_diff_language_fence(self):
        raw = "Here is the hunk:\n```\n@@ -5,3 +5,4 @@\n void bar() {\n+    check();\n }\n```"
        result = _extract_hunk_block(raw)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("@@"))

    def test_returns_none_on_no_hunk(self):
        result = _extract_hunk_block("No hunk here. Just plain text.")
        self.assertIsNone(result)

    def test_returns_none_on_empty_string(self):
        result = _extract_hunk_block("")
        self.assertIsNone(result)

    def test_returns_none_on_none_input(self):
        result = _extract_hunk_block(None)
        self.assertIsNone(result)

    def test_hunk_ends_with_newline(self):
        raw = "@@ -1,1 +1,2 @@\n int x;\n+int y;"
        result = _extract_hunk_block(raw)
        self.assertTrue(result.endswith("\n"))


# ---------------------------------------------------------------------------
# _check_intent
# ---------------------------------------------------------------------------

class TestCheckIntent(unittest.IsolatedAsyncioTestCase):

    async def test_yes_response_returns_true(self):
        mock_llm = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = "YES — the null guard correctly addresses the fix logic."
        mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
        blueprint = {"fix_logic": "add null guard", "dependent_apis": ["buf"]}
        result = await _check_intent(mock_llm, "@@ -1 +1 @@\n+if (buf==null) return;", blueprint)
        self.assertTrue(result)

    async def test_no_response_returns_false(self):
        mock_llm = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = "NO: the null guard is missing from the generated hunk."
        mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
        blueprint = {"fix_logic": "add null guard", "dependent_apis": ["buf"]}
        result = await _check_intent(mock_llm, "@@ -1 +1 @@\n+process(buf);", blueprint)
        self.assertFalse(result)

    async def test_llm_exception_fails_open(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("network error"))
        blueprint = {"fix_logic": "guard", "dependent_apis": []}
        result = await _check_intent(mock_llm, "@@ -1 +1 @@\n+x;", blueprint)
        self.assertTrue(result)  # fail-open

    async def test_lowercase_yes_returns_true(self):
        mock_llm = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = "yes it looks correct"
        mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
        blueprint = {"fix_logic": "guard", "dependent_apis": []}
        result = await _check_intent(mock_llm, "@@\n+x;", blueprint)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# _format_consistency_map
# ---------------------------------------------------------------------------

class TestFormatConsistencyMap(unittest.TestCase):

    def test_empty_map_returns_none_string(self):
        result = _format_consistency_map({})
        self.assertIn("none", result.lower())

    def test_single_rename_formatted_correctly(self):
        result = _format_consistency_map({"oldName": "newName"})
        self.assertIn("oldName", result)
        self.assertIn("newName", result)
        self.assertIn("→", result)

    def test_multiple_renames_newline_separated(self):
        cm = {"a": "b", "c": "d"}
        result = _format_consistency_map(cm)
        lines = [l for l in result.splitlines() if "→" in l]
        self.assertEqual(len(lines), 2)


# ---------------------------------------------------------------------------
# _rewrite_hunk_symbols
# ---------------------------------------------------------------------------

class TestRewriteHunkSymbols(unittest.TestCase):

    def test_renames_symbol_in_plus_line(self):
        hunk = "@@ -1,2 +1,2 @@\n public void foo() {\n+    legacy_buf.read();\n }\n"
        result = _rewrite_hunk_symbols(hunk, {"legacy_buf": "newBuf"})
        self.assertIn("newBuf.read()", result)

    def test_does_not_rename_in_context_line(self):
        hunk = "@@ -1,2 +1,2 @@\n old_sym.call();\n+    old_sym.call();\n"
        result = _rewrite_hunk_symbols(hunk, {"old_sym": "new_sym"})
        # Context line (space prefix) unchanged
        lines = result.splitlines()
        self.assertIn(" old_sym.call();", lines)
        # + line renamed
        self.assertTrue(any("new_sym" in l and l.startswith("+") for l in lines))

    def test_empty_map_returns_unchanged(self):
        hunk = "@@ -1 +1 @@\n+foo();\n"
        result = _rewrite_hunk_symbols(hunk, {})
        self.assertEqual(result, hunk)

    def test_no_partial_word_match(self):
        # "buf" should NOT rename inside "buffer"
        hunk = "@@ -1 +1 @@\n+    buffer.read();\n"
        result = _rewrite_hunk_symbols(hunk, {"buf": "newBuf"})
        self.assertIn("buffer.read()", result)
        self.assertNotIn("newBuffer", result)


# ---------------------------------------------------------------------------
# _adjust_hunk_header
# ---------------------------------------------------------------------------

class TestAdjustHunkHeader(unittest.TestCase):

    def test_adjusts_start_line(self):
        hunk = "@@ -10,4 +10,5 @@ public void foo() {\n"
        result = _adjust_hunk_header(hunk, 42)
        self.assertIn("-42,4", result)
        self.assertIn("+42,5", result)

    def test_preserves_context_comment(self):
        hunk = "@@ -10,3 +10,4 @@ class Bar {\n"
        result = _adjust_hunk_header(hunk, 1)
        self.assertIn("class Bar {", result)

    def test_noop_on_none_line(self):
        hunk = "@@ -10,3 +10,4 @@\n+x;\n"
        result = _adjust_hunk_header(hunk, None)
        self.assertEqual(result, hunk)


# ---------------------------------------------------------------------------
# Integration: hunk_generator_node
# ---------------------------------------------------------------------------

class TestHunkGeneratorNodeIntegration(unittest.IsolatedAsyncioTestCase):

    async def _make_state(self, validation_attempts=0, error_context=""):
        from utils.patch_analyzer import PatchAnalyzer, FileChange
        diff = (
            "diff --git a/src/main/java/Foo.java b/src/main/java/Foo.java\n"
            "index 0000000..1111111 100644\n"
            "--- a/src/main/java/Foo.java\n"
            "+++ b/src/main/java/Foo.java\n"
            "@@ -10,3 +10,4 @@ public class Foo {\n"
            "     public void process() {\n"
            "-        buf.read();\n"
            "+        if (buf == null) return;\n"
            "+        buf.read();\n"
            "     }\n"
        )
        analyzer = PatchAnalyzer()
        changes = analyzer.analyze(diff)
        return {
            "patch_diff": diff,
            "patch_analysis": changes,
            "semantic_blueprint": {
                "root_cause_hypothesis": "missing null check",
                "fix_logic": "add null guard before buf.read()",
                "dependent_apis": ["buf"],
            },
            "consistency_map": {},
            "mapped_target_context": {
                "src/main/java/Foo.java": {
                    "target_file": "src/main/java/Foo.java",
                    "method": "process",
                    "start_line": 10,
                    "end_line": 15,
                    "code_snippet": "public void process() { buf.read(); }",
                },
            },
            "target_repo_path": "/fake/target",
            "validation_attempts": validation_attempts,
            "validation_error_context": error_context,
            "messages": [],
        }

    async def test_node_produces_adapted_code_hunks(self):
        from agents.hunk_generator import hunk_generator_node

        state = await self._make_state()
        mock_resp = MagicMock()
        mock_resp.content = (
            "@@ -10,3 +10,4 @@ public class Foo {\n"
            "     public void process() {\n"
            "+        if (buf == null) return;\n"
            "-        buf.read();\n"
            "+        buf.read();\n"
            "     }\n"
        )
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_resp)

        mock_toolkit = MagicMock()
        mock_toolkit.apply_hunk_dry_run.return_value = {"success": True, "output": "ok"}

        with patch("agents.hunk_generator.ChatGoogleGenerativeAI", return_value=mock_llm), \
             patch("agents.hunk_generator.ValidationToolkit", return_value=mock_toolkit):
            result = await hunk_generator_node(state, {})

        self.assertIn("adapted_code_hunks", result)
        hunks = result["adapted_code_hunks"]
        self.assertGreater(len(hunks), 0)
        h = hunks[0]
        self.assertIn("target_file", h)
        self.assertIn("hunk_text", h)
        self.assertIn("insertion_line", h)
        self.assertIn("intent_verified", h)

    async def test_retry_injects_error_context(self):
        from agents.hunk_generator import hunk_generator_node

        state = await self._make_state(validation_attempts=1, error_context="compile error: cannot find symbol")
        mock_resp = MagicMock()
        mock_resp.content = "@@ -10,3 +10,4 @@\n+guard();\n"

        call_args_list = []
        async def capture_invoke(messages):
            call_args_list.append(messages)
            return mock_resp

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=capture_invoke)
        mock_toolkit = MagicMock()
        mock_toolkit.apply_hunk_dry_run.return_value = {"success": True, "output": "ok"}

        with patch("agents.hunk_generator.ChatGoogleGenerativeAI", return_value=mock_llm), \
             patch("agents.hunk_generator.ValidationToolkit", return_value=mock_toolkit):
            await hunk_generator_node(state, {})

        # Check that the error context string appears in at least one LLM call
        combined = " ".join(str(args) for args in call_args_list)
        self.assertIn("compile error", combined)

    async def test_empty_mapped_context_produces_no_hunks(self):
        from agents.hunk_generator import hunk_generator_node

        state = await self._make_state()
        state["mapped_target_context"] = {}  # No mapping → nothing to do

        mock_llm = AsyncMock()
        mock_toolkit = MagicMock()

        with patch("agents.hunk_generator.ChatGoogleGenerativeAI", return_value=mock_llm), \
             patch("agents.hunk_generator.ValidationToolkit", return_value=mock_toolkit):
            result = await hunk_generator_node(state, {})

        self.assertEqual(result["adapted_code_hunks"], [])
        self.assertEqual(result["adapted_test_hunks"], [])
        # LLM should never have been called
        mock_llm.ainvoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
