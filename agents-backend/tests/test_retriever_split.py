import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock all external dependencies before import
sys.modules["git"] = MagicMock()
sys.modules["sklearn"] = MagicMock()
sys.modules["sklearn.feature_extraction.text"] = MagicMock()
sys.modules["sklearn.metrics.pairwise"] = MagicMock()
sys.modules["tree_sitter"] = MagicMock()
sys.modules["tree_sitter_java"] = MagicMock()
sys.modules["numpy"] = MagicMock()

from utils.retrieval.ensemble_retriever import EnsembleRetriever

class TestSplitRetriever(unittest.TestCase):
    
    def setUp(self):
        # Mock Repos
        self.mock_main_repo = MagicMock()
        self.mock_target_repo = MagicMock()
        with patch('utils.retrieval.ensemble_retriever.Repo') as MockRepo:
            self.retriever = EnsembleRetriever("mock_main", "mock_target")
            self.retriever.main_repo = self.mock_main_repo
            self.retriever.target_repo = self.mock_target_repo
            
        # Mock dependencies
        self.retriever.target_files = ["src/Target.java", "src/Renamed.java"]
        self.retriever.extract_symbols = MagicMock(return_value={"MethodA"})
        self.retriever.symbol_index = {}
        self.retriever.symbol_counts = {}
        self.retriever.vectorizer = None # Disable TF-IDF for now

    def test_phase1_exact_match(self):
        """Phase 1 should return immediately if exact path exists."""
        results = self.retriever.find_candidates("src/Target.java", "HEAD")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["method"], "GIT_EXACT")
        self.assertEqual(results[0]["file"], "src/Target.java")
        
        # Ensure Phase 2 (get_symbol_candidates) was NOT called
        self.retriever.extract_symbols.assert_not_called()

    def test_phase1_rename_match(self):
        """Phase 1 should trace renames using git log."""
        # Setup mock git log to return the renamed file
        # 'git log --follow --name-only ...' -> returns history of names
        self.mock_main_repo.git.log.return_value = "src/OldName.java\nsrc/Renamed.java\n"
        
        results = self.retriever.find_candidates("src/OldName.java", "HEAD")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["method"], "GIT_RENAME")
        self.assertEqual(results[0]["file"], "src/Renamed.java")
        
        # Verify git log was called
        self.mock_main_repo.git.log.assert_called_once()
        
    def test_phase2_fallback(self):
        """If Phase 1 fails, it should enter Phase 2."""
        self.mock_main_repo.git.log.return_value = "" # No history/rename found
        
        # Setup Phase 2 mocks
        self.retriever.get_symbol_candidates = MagicMock(return_value=[{"file": "src/Target.java", "score": 0.8, "method": "SYMBOL"}])
        self.retriever.get_tfidf_candidates = MagicMock(return_value=[])
        
        results = self.retriever.find_candidates("src/NonExistent.java", "HEAD")
        
        # Should have called Phase 2 methods
        self.retriever.get_symbol_candidates.assert_called_once()
        self.assertEqual(len(results), 1)
        self.assertIn("SYMBOL", results[0]["reason"])

if __name__ == '__main__':
    unittest.main()
