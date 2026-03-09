import unittest
from unittest.mock import MagicMock, patch
from utils.method_discovery import BodySimilarityMatcher, GitMethodTracer

class TestBodySimilarity(unittest.TestCase):
    def setUp(self):
        self.matcher = BodySimilarityMatcher()

    def test_exact_match(self):
        code = "public void foo() { int x = 1; }"
        score = self.matcher.calculate_similarity(code, code)
        self.assertAlmostEqual(score, 1.0)

    def test_minor_change(self):
        code_a = "public void foo() { int x = 1; }"
        code_b = "public void foo() { int x = 2; }" # 1 char diff
        score = self.matcher.calculate_similarity(code_a, code_b)
        self.assertGreater(score, 0.8)

    def test_different(self):
        code_a = "public void foo() { int x = 1; }"
        code_b = "private String bar() { return 'hi'; }"
        score = self.matcher.calculate_similarity(code_a, code_b)
        self.assertLess(score, 0.5)

class TestGitTracer(unittest.TestCase):
    def setUp(self):
        self.tracer = GitMethodTracer("/mock/repo")

    @patch('subprocess.check_output')
    def test_pickaxe_find(self, mock_subprocess):
        # Mock git log -S output
        mock_output = "a1b2c3d Commit Message\nsrc/main/java/com/example/NewFile.java\n"
        mock_subprocess.return_value = mock_output
        
        result = self.tracer.find_moved_method_by_pickaxe("foo", "void foo()")
        
        self.assertEqual(result, "src/main/java/com/example/NewFile.java")
        # Verify the command was correct
        mock_subprocess.assert_called_with(
            ['git', '-C', '/mock/repo', 'log', '-S', 'void foo()', '--name-only', '--oneline', '-n', '1'],
            text=True
        )

    @patch('subprocess.check_output')
    def test_pickaxe_not_found(self, mock_subprocess):
        mock_subprocess.return_value = ""
        result = self.tracer.find_moved_method_by_pickaxe("foo", "void foo()")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
