"""
Unit tests for Dependency Analyzer and related utilities.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock langchain before imports
mock_lc = MagicMock()
sys.modules["langchain_core"] = mock_lc
sys.modules["langchain_core.messages"] = mock_lc
sys.modules["langchain_openai"] = mock_lc
sys.modules["langchain_anthropic"] = mock_lc
sys.modules["langchain_community"] = mock_lc
sys.modules["langchain_community.chat_models"] = mock_lc

# Mock state.py to avoid typing issues
mock_state = MagicMock()
sys.modules["state"] = mock_state

# Mock utils.dependency_graph to avoid complex imports
mock_graph = MagicMock()
sys.modules["utils.dependency_graph"] = mock_graph

from dependency_analyzer import dependency_analyzer_node

class TestDependencyAnalyzer(unittest.TestCase):
    def setUp(self):
        self.repo_path = "/tmp/test_repo"
        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path)
            
    def test_dependency_analyzer_node_basic(self):
        """Test the dependency analyzer node with mock state."""
        state = {
            "target_repo_path": self.repo_path,
            "validation_build_missing_symbols": ["forUpdate"],
            "semantic_blueprint": {
                "dependent_apis": ["sizeEstimateForUpdate"]
            },
            "retry_files": ["File1.java"]
        }
        
        # Mock the analyzer
        with patch("dependency_analyzer.JavaDependencyAnalyzer") as MockAnalyzer:
            mock_instance = MockAnalyzer.return_value
            mock_instance.find_all_call_sites.side_effect = lambda symbol: [
                {"file": "File2.java", "line": 10, "context": "obj.forUpdate()"}
            ] if symbol == "forUpdate" else [
                {"file": "File3.java", "line": 20, "context": "obj.sizeEstimateForUpdate()"}
            ]
            
            result = dependency_analyzer_node(state)
            
            # Check results
            self.assertIn("retry_files", result)
            self.assertIn("File1.java", result["retry_files"])
            self.assertIn("File2.java", result["retry_files"])
            self.assertIn("File3.java", result["retry_files"])
            self.assertIn("dep_analyzer_added_2_files", result["notes"])

    def test_dependency_analyzer_node_no_repo(self):
        """Test the node when no repo path is provided."""
        state = {}
        result = dependency_analyzer_node(state)
        self.assertEqual(result, {})

    def test_dependency_analyzer_node_no_symbols(self):
        """Test the node when no symbols are found."""
        state = {
            "target_repo_path": self.repo_path,
            "validation_build_missing_symbols": [],
            "semantic_blueprint": {"dependent_apis": []}
        }
        result = dependency_analyzer_node(state)
        self.assertEqual(result, {})

if __name__ == "__main__":
    unittest.main()
