import os
import sys
import unittest
import tempfile
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from utils.patch_complexity import classify_patch_complexity


_SIMPLE_DIFF = """diff --git a/src/Foo.java b/src/Foo.java
index 1111111..2222222 100644
--- a/src/Foo.java
+++ b/src/Foo.java
@@ -1,2 +1,2 @@
-class Foo {}
+class Foo { int x; }
"""


class TestPatchComplexity(unittest.TestCase):
    @patch("utils.patch_complexity._git_apply_check_passes")
    def test_trivial_when_git_apply_check_passes(self, mock_apply):
        mock_apply.return_value = (True, "")
        with patch("utils.patch_complexity.PatchAnalyzer.analyze") as mock_analyze:
            mock_analyze.return_value = []
            out = classify_patch_complexity(
                patch_diff=_SIMPLE_DIFF,
                target_repo_path="/tmp/repo",
                with_test_changes=False,
            )

        self.assertEqual(out["complexity"], "TRIVIAL")
        self.assertEqual(out["reason"], "no_changes")

    @patch("utils.patch_complexity._git_apply_check_passes")
    @patch("utils.patch_complexity._anchor_match_ratio")
    def test_structural_when_files_exist_and_overlap(self, mock_ratio, mock_apply):
        mock_apply.return_value = (False, "patch failed")
        mock_ratio.return_value = 0.8

        fake_change = type("C", (), {})()
        fake_change.file_path = "src/Foo.java"
        fake_change.change_type = "MODIFIED"
        fake_change.is_test_file = False

        with patch("utils.patch_complexity.PatchAnalyzer.analyze") as mock_analyze:
            mock_analyze.return_value = [fake_change]
            with patch("utils.patch_complexity.os.path.isfile", return_value=True):
                out = classify_patch_complexity(
                    patch_diff=_SIMPLE_DIFF,
                    target_repo_path="/tmp/repo",
                    with_test_changes=False,
                )

        self.assertEqual(out["complexity"], "STRUCTURAL")

    @patch("utils.patch_complexity._git_apply_check_passes")
    @patch("utils.patch_complexity._anchor_match_ratio")
    def test_rewrite_when_low_overlap(self, mock_ratio, mock_apply):
        mock_apply.return_value = (False, "patch failed")
        mock_ratio.return_value = 0.1

        fake_change = type("C", (), {})()
        fake_change.file_path = "src/Foo.java"
        fake_change.change_type = "MODIFIED"
        fake_change.is_test_file = False

        with patch("utils.patch_complexity.PatchAnalyzer.analyze") as mock_analyze:
            mock_analyze.return_value = [fake_change]
            with patch("utils.patch_complexity.os.path.isfile", return_value=True):
                out = classify_patch_complexity(
                    patch_diff=_SIMPLE_DIFF,
                    target_repo_path="/tmp/repo",
                    with_test_changes=False,
                )

        self.assertEqual(out["complexity"], "REWRITE")

    @patch("utils.patch_complexity._git_apply_check_passes")
    @patch("utils.patch_complexity._anchor_match_ratio")
    def test_rewrite_when_structural_op_detected(self, mock_ratio, mock_apply):
        mock_apply.return_value = (False, "patch failed")
        mock_ratio.return_value = 0.9

        fake_change = type("C", (), {})()
        fake_change.file_path = "src/Foo.java"
        fake_change.change_type = "RENAMED"
        fake_change.is_test_file = False

        with patch("utils.patch_complexity.PatchAnalyzer.analyze") as mock_analyze:
            mock_analyze.return_value = [fake_change]
            with patch("utils.patch_complexity.os.path.isfile", return_value=True):
                out = classify_patch_complexity(
                    patch_diff=_SIMPLE_DIFF,
                    target_repo_path="/tmp/repo",
                    with_test_changes=False,
                )

        self.assertEqual(out["complexity"], "REWRITE")

    @patch("utils.patch_complexity._git_apply_check_passes")
    def test_structural_with_repeated_diff_prefixes(self, mock_apply):
        mock_apply.return_value = (False, "patch failed")

        repeated_prefix_diff = """diff --git a/a/src/Foo.java b/b/src/Foo.java
index 1111111..2222222 100644
--- a/a/src/Foo.java
+++ b/b/src/Foo.java
@@ -1,1 +1,1 @@
-class Foo {}
+class Foo { int x; }
"""

        with tempfile.TemporaryDirectory() as tmp_repo:
            src_dir = os.path.join(tmp_repo, "src")
            os.makedirs(src_dir, exist_ok=True)
            with open(os.path.join(src_dir, "Foo.java"), "w", encoding="utf-8") as f:
                f.write("class Foo {}\n")

            out = classify_patch_complexity(
                patch_diff=repeated_prefix_diff,
                target_repo_path=tmp_repo,
                with_test_changes=False,
            )

        self.assertEqual(out["complexity"], "STRUCTURAL")


if __name__ == "__main__":
    unittest.main()
