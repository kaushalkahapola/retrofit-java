"""
Tests for the PatchAnalyzer — including the new extract_raw_hunks() method.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from utils.patch_analyzer import PatchAnalyzer

SAMPLE_DIFF = (
    "diff --git a/src/main/java/com/example/App.java b/src/main/java/com/example/App.java\n"
    "index 83a2a08..1234567 100644\n"
    "--- a/src/main/java/com/example/App.java\n"
    "+++ b/src/main/java/com/example/App.java\n"
    "@@ -10,4 +10,5 @@ public class App {\n"
    "     public void oldMethod() {\n"
    "-        System.out.println(\"Old\");\n"
    "+        if (buf == null) return;\n"
    "+        System.out.println(\"New\");\n"
    "     }\n"
    " }\n"
    "diff --git a/src/test/java/com/example/AppTest.java b/src/test/java/com/example/AppTest.java\n"
    "new file mode 100644\n"
    "index 0000000..1234567\n"
    "--- /dev/null\n"
    "+++ b/src/test/java/com/example/AppTest.java\n"
    "@@ -0,0 +1,5 @@\n"
    "+public class AppTest {\n"
    "+    @Test\n"
    "+    public void testApp() {\n"
    "+    }\n"
    "+}\n"
)


class TestPatchAnalyzerExisting(unittest.TestCase):
    def setUp(self):
        self.analyzer = PatchAnalyzer()

    def test_analyze_modified_file(self):
        diff_text = """\
diff --git a/src/main/java/com/example/App.java b/src/main/java/com/example/App.java
index 83a2a08..1234567 100644
--- a/src/main/java/com/example/App.java
+++ b/src/main/java/com/example/App.java
@@ -10,4 +10,5 @@ public class App {
     public void oldMethod() {
-        System.out.println("Old");
+        System.out.println("New");
+        System.out.println("Added");
     }
 }"""
        changes = self.analyzer.analyze(diff_text)
        self.assertEqual(len(changes), 1)
        change = changes[0]
        self.assertEqual(change.file_path, "src/main/java/com/example/App.java")
        self.assertEqual(change.change_type, "MODIFIED")
        self.assertIn('System.out.println("New");', change.added_lines)
        self.assertIn('System.out.println("Old");', change.removed_lines)
        self.assertFalse(change.is_test_file)

    def test_analyze_added_test_file(self):
        diff_text = """\
diff --git a/src/test/java/com/example/AppTest.java b/src/test/java/com/example/AppTest.java
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/test/java/com/example/AppTest.java
@@ -0,0 +1,5 @@
+public class AppTest {
+    @Test
+    public void testApp() {
+    }
+}"""
        changes = self.analyzer.analyze(diff_text)
        self.assertEqual(len(changes), 1)
        self.assertTrue(changes[0].is_test_file)


class TestExtractRawHunks(unittest.TestCase):
    def setUp(self):
        self.analyzer = PatchAnalyzer()

    def test_extract_returns_dict_keyed_by_file_path(self):
        result = self.analyzer.extract_raw_hunks(SAMPLE_DIFF)
        self.assertIsInstance(result, dict)
        self.assertIn("src/main/java/com/example/App.java", result)
        self.assertIn("src/test/java/com/example/AppTest.java", result)

    def test_code_file_has_one_hunk(self):
        result = self.analyzer.extract_raw_hunks(SAMPLE_DIFF)
        code_hunks = result["src/main/java/com/example/App.java"]
        self.assertEqual(len(code_hunks), 1)

    def test_hunk_contains_added_line(self):
        result = self.analyzer.extract_raw_hunks(SAMPLE_DIFF)
        hunk = result["src/main/java/com/example/App.java"][0]
        self.assertIn("+", hunk)  # has an addition
        self.assertIn("@@", hunk)  # has the hunk header

    def test_hunk_contains_removed_line(self):
        result = self.analyzer.extract_raw_hunks(SAMPLE_DIFF)
        hunk = result["src/main/java/com/example/App.java"][0]
        self.assertIn("-", hunk)

    def test_test_file_has_one_hunk(self):
        result = self.analyzer.extract_raw_hunks(SAMPLE_DIFF)
        test_hunks = result["src/test/java/com/example/AppTest.java"]
        self.assertGreaterEqual(len(test_hunks), 1)

    def test_hunk_segregation_via_analyze(self):
        """Verifies that is_test_file flag correctly separates code from test hunks."""
        changes = self.analyzer.analyze(SAMPLE_DIFF)
        code = [c for c in changes if not c.is_test_file]
        tests = [c for c in changes if c.is_test_file]
        self.assertEqual(len(code), 1)
        self.assertEqual(len(tests), 1)
        self.assertEqual(code[0].file_path, "src/main/java/com/example/App.java")
        self.assertEqual(tests[0].file_path, "src/test/java/com/example/AppTest.java")


if __name__ == "__main__":
    unittest.main()
