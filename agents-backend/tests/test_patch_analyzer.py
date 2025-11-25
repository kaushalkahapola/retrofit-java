import unittest
from src.utils.patch_analyzer import PatchAnalyzer

class TestPatchAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = PatchAnalyzer()

    def test_analyze_modified_file(self):
        diff_text = """diff --git a/src/main/java/com/example/App.java b/src/main/java/com/example/App.java
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
        self.assertIn("System.out.println(\"New\");", change.added_lines)
        self.assertIn("System.out.println(\"Old\");", change.removed_lines)
        self.assertFalse(change.is_test_file)

    def test_analyze_added_test_file(self):
        diff_text = """diff --git a/src/test/java/com/example/AppTest.java b/src/test/java/com/example/AppTest.java
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
        change = changes[0]
        self.assertEqual(change.change_type, "ADDED")
        self.assertTrue(change.is_test_file)

if __name__ == '__main__':
    unittest.main()
