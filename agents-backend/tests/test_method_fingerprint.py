import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from utils.method_fingerprinter import MethodFingerprinter

class TestMethodFingerprinter(unittest.TestCase):
    def setUp(self):
        self.fp = MethodFingerprinter()

    def test_exact_match(self):
        print("\nTesting Exact Match...")
        candidates = [{"simpleName": "targetMethod", "signature": "void targetMethod()", "calls": []}]
        result = self.fp.find_match("targetMethod", "void targetMethod()", "", [], candidates)
        self.assertEqual(result["match"]["simpleName"], "targetMethod")
        self.assertEqual(result["reason"], "Exact Name Match")
        print("PASS")

    def test_signature_match(self):
        print("\nTesting Signature Match...")
        # Name mismatch, signature match
        candidates = [{"simpleName": "renamedMethod", "signature": "void renamedMethod(int a)", "calls": []}]
        result = self.fp.find_match("oldMethod", "void oldMethod(int a)", "", [], candidates)
        self.assertEqual(result["match"]["simpleName"], "renamedMethod")
        self.assertEqual(result["reason"], "Signature Match")
        print("PASS")

    def test_name_similarity(self):
        print("\nTesting Name Similarity...")
        # Name similar
        candidates = [{"simpleName": "calculateTotal", "signature": "void calculateTotal()", "calls": []}]
        result = self.fp.find_match("calculateTotals", "void calculateTotals()", "", [], candidates)
        self.assertEqual(result["match"]["simpleName"], "calculateTotal")
        self.assertTrue("Name Similarity" in result["reason"])
        print("PASS")

    def test_call_graph_match(self):
        print("\nTesting Call Graph Match...")
        # Logic mismatch, name mismatch, signature mismatch -> Fingerprint
        candidates = [
            {"simpleName": "wrongMethod", "calls": ["a", "b"]},
            {"simpleName": "targetMethod", "calls": ["log", "process", "validate"]}
        ]
        # oldMethod called log, process, validate, and extra. Jaccard should be high for targetMethod.
        result = self.fp.find_match("oldMethod", "void oldMethod()", "", ["log", "process", "validate", "extra"], candidates)
        self.assertEqual(result["match"]["simpleName"], "targetMethod")
        self.assertTrue("Call Graph Match" in result["reason"])
        print("PASS")

if __name__ == '__main__':
    unittest.main()
