"""
Tests for ValidationToolkit — specifically the new Phase 3 dry-run methods.
"""
import unittest
import sys
import os
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))


class TestApplyHunkDryRun(unittest.TestCase):
    """Tests for ValidationToolkit.apply_hunk_dry_run()"""

    def _make_toolkit(self):
        # Patch get_client so we don't need a live MCP server
        with patch("agents.validation_tools.get_client", return_value=MagicMock()):
            from agents.validation_tools import ValidationToolkit
            return ValidationToolkit("/fake/repo")

    def test_dry_run_success(self):
        toolkit = self._make_toolkit()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("agents.validation_tools.subprocess.run", return_value=mock_result):
            result = toolkit.apply_hunk_dry_run(
                "src/Foo.java",
                "@@ -1,2 +1,3 @@\n int x;\n+int y;\n"
            )
        self.assertTrue(result["success"])

    def test_dry_run_failure(self):
        toolkit = self._make_toolkit()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error: patch does not apply"

        with patch("agents.validation_tools.subprocess.run", return_value=mock_result):
            result = toolkit.apply_hunk_dry_run(
                "src/Foo.java",
                "@@ -999,2 +999,3 @@\n int x;\n+bad;\n"
            )
        self.assertFalse(result["success"])
        self.assertIn("error", result["output"])

    def test_temp_file_cleaned_up_on_success(self):
        """Temp file should be deleted even after a successful run."""
        created_paths = []

        toolkit = self._make_toolkit()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        original_unlink = os.unlink
        unlinked = []

        def capture_unlink(path):
            unlinked.append(path)

        with patch("agents.validation_tools.subprocess.run", return_value=mock_result), \
             patch("agents.validation_tools.os.unlink", side_effect=capture_unlink):
            result = toolkit.apply_hunk_dry_run("src/Foo.java", "@@ -1 +1 @@\n+x;\n")

        self.assertTrue(result["success"])
        # unlink should have been called once for the temp file
        self.assertEqual(len(unlinked), 1)

    def test_temp_file_cleaned_up_on_exception(self):
        """Temp file must be deleted even if subprocess.run raises."""
        toolkit = self._make_toolkit()
        unlinked = []

        with patch("agents.validation_tools.subprocess.run", side_effect=OSError("disk error")), \
             patch("agents.validation_tools.os.unlink", side_effect=lambda p: unlinked.append(p)):
            result = toolkit.apply_hunk_dry_run("src/Foo.java", "@@ -1 +1 @@\n+x;\n")

        self.assertFalse(result["success"])
        self.assertIn("disk error", result["output"])
        self.assertEqual(len(unlinked), 1)


class TestBuildPatchFile(unittest.TestCase):
    """Tests for ValidationToolkit._build_patch_file()"""

    def _make_toolkit(self):
        with patch("agents.validation_tools.get_client", return_value=MagicMock()):
            from agents.validation_tools import ValidationToolkit
            return ValidationToolkit("/fake/repo")

    def test_patch_file_has_expected_headers(self):
        toolkit = self._make_toolkit()
        result = toolkit._build_patch_file("src/Foo.java", "@@ -1 +1 @@\n+x;\n")
        self.assertIn("diff --git a/src/Foo.java b/src/Foo.java", result)
        self.assertIn("--- a/src/Foo.java", result)
        self.assertIn("+++ b/src/Foo.java", result)

    def test_leading_slash_stripped_from_path(self):
        toolkit = self._make_toolkit()
        result = toolkit._build_patch_file("/src/Foo.java", "@@ -1 +1 @@\n+x;\n")
        self.assertNotIn("//", result)
        self.assertIn("a/src/Foo.java", result)

    def test_hunk_appended_after_header(self):
        toolkit = self._make_toolkit()
        hunk = "@@ -5,3 +5,4 @@ void foo() {\n+    guard();\n"
        result = toolkit._build_patch_file("src/Foo.java", hunk)
        self.assertIn("@@ -5,3 +5,4 @@", result)
        self.assertIn("+    guard();", result)


class TestRunTargetedTests(unittest.TestCase):
    def _make_toolkit(self):
        with patch("agents.validation_tools.get_client", return_value=MagicMock()):
            from agents.validation_tools import ValidationToolkit
            return ValidationToolkit("/fake/repo")

    def test_run_targeted_tests_success(self):
        toolkit = self._make_toolkit()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Tests run: 1, Failures: 0"
        mock_result.stderr = ""
        with patch("agents.validation_tools.subprocess.run", return_value=mock_result):
            res = toolkit.run_targeted_tests(["org.example.MyTest"])
        self.assertTrue(res["success"])
        self.assertFalse(res["compile_error"])

    def test_run_targeted_tests_compile_error(self):
        toolkit = self._make_toolkit()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "COMPILATION ERROR\nFailure in build."
        mock_result.stderr = ""
        with patch("agents.validation_tools.subprocess.run", return_value=mock_result):
            res = toolkit.run_targeted_tests(["org.example.MyTest"])
        self.assertFalse(res["success"])
        self.assertTrue(res["compile_error"])

    def test_run_targeted_tests_test_failure(self):
        toolkit = self._make_toolkit()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "BUILD FAILURE\nThere are test failures."
        mock_result.stderr = ""
        with patch("agents.validation_tools.subprocess.run", return_value=mock_result):
            res = toolkit.run_targeted_tests(["org.example.MyTest"])
        self.assertFalse(res["success"])
        self.assertFalse(res["compile_error"])

class TestRestoreRepoState(unittest.TestCase):
    def _make_toolkit(self):
        with patch("agents.validation_tools.get_client", return_value=MagicMock()):
            from agents.validation_tools import ValidationToolkit
            return ValidationToolkit("/fake/repo")

    def test_restore_repo_success(self):
        toolkit = self._make_toolkit()
        with patch("agents.validation_tools.subprocess.run") as mock_run:
            res = toolkit.restore_repo_state()
            self.assertTrue(res)
            self.assertEqual(mock_run.call_count, 2)


class TestRunBuildScript(unittest.TestCase):
    def _make_toolkit(self):
        with patch("agents.validation_tools.get_client", return_value=MagicMock()):
            from agents.validation_tools import ValidationToolkit
            return ValidationToolkit("/fake/repo")
            
    @patch("agents.validation_tools.os.path.exists", return_value=False)
    @patch("agents.validation_tools.subprocess.run")
    def test_maven_build(self, mock_run, mock_exists):
        toolkit = self._make_toolkit()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "BUILD SUCCESS"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        res = toolkit.run_build_script()
        self.assertTrue(res["success"])
        mock_run.assert_called_with(
            ["mvn", "clean", "compile"],
            capture_output=True, text=True, cwd="/fake/repo"
        )
        
    @patch("agents.validation_tools.os.path.exists", return_value=True) # returns true for build.gradle
    @patch("agents.validation_tools.subprocess.run")
    def test_gradle_build(self, mock_run, mock_exists):
        toolkit = self._make_toolkit()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "BUILD SUCCESSFUL"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        res = toolkit.run_build_script()
        self.assertTrue(res["success"])
        mock_run.assert_called_with(
            ["gradle", "build", "-x", "test"],
            capture_output=True, text=True, cwd="/fake/repo"
        )

class TestRunTargetedTestsGradle(unittest.TestCase):
    def _make_toolkit(self):
        with patch("agents.validation_tools.get_client", return_value=MagicMock()):
            from agents.validation_tools import ValidationToolkit
            return ValidationToolkit("/fake/repo")
            
    @patch("agents.validation_tools.os.path.exists", return_value=True) # returns true for build.gradle
    @patch("agents.validation_tools.subprocess.run")
    def test_run_gradle_tests(self, mock_run, mock_exists):
        toolkit = self._make_toolkit()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "BUILD SUCCESSFUL"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        res = toolkit.run_targeted_tests(["org.example.TestA", "org.example.TestB"])
        self.assertTrue(res["success"])
        mock_run.assert_called_with(
            ["gradle", "test", "--tests", "org.example.TestA", "--tests", "org.example.TestB"],
            capture_output=True, text=True, cwd="/fake/repo"
        )


if __name__ == "__main__":
    unittest.main()
