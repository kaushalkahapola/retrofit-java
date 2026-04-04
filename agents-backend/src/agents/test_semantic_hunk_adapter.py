"""
Unit tests for semantic_hunk_adapter.py - Phase A

Tests for:
  - HunkIntent extraction
  - Operation type detection
  - Equivalent location finding
  - Confidence scoring
"""

import unittest
from agents.semantic_hunk_adapter import (
    SemanticHunkAdapter,
    HunkIntent,
    HunkOperationType,
    AdaptationResult,
    AdaptationStrategy,
)


class TestHunkIntentExtraction(unittest.TestCase):
    """Test HunkIntent extraction for various hunk types"""

    def setUp(self):
        self.adapter = SemanticHunkAdapter()

    def test_import_operation_detection(self):
        """Test detection of import addition"""
        old = "import org.elasticsearch.action.ActionRequest;"
        new = "import org.elasticsearch.action.ActionRequest;\nimport java.util.List;"

        intent = self.adapter._extract_hunk_intent(old, new)

        self.assertEqual(intent.operation_type, HunkOperationType.IMPORT_ADDITION)
        self.assertGreater(intent.confidence, 0.9)
        self.assertIn("List", intent.target_entity)

    def test_method_call_detection(self):
        """Test detection of method call modification"""
        old = "builder.startObject(COMPILATIONS_HISTORY);"
        new = "ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictions);"

        intent = self.adapter._extract_hunk_intent(old, new)

        self.assertEqual(intent.operation_type, HunkOperationType.METHOD_CALL)
        self.assertGreater(intent.confidence, 0.7)

    def test_method_signature_detection(self):
        """Test detection of method signature change"""
        old = "public void setup() {"
        new = "public void setUp() throws Exception {"

        intent = self.adapter._extract_hunk_intent(old, new)

        self.assertEqual(intent.operation_type, HunkOperationType.METHOD_DEFINITION)
        self.assertGreater(intent.confidence, 0.8)

    def test_field_declaration_detection(self):
        """Test detection of field declaration change"""
        old = "private String name;"
        new = 'private String name = "default";'

        intent = self.adapter._extract_hunk_intent(old, new)

        self.assertEqual(intent.operation_type, HunkOperationType.FIELD_DECLARATION)
        self.assertGreater(intent.confidence, 0.7)

    def test_object_initialization_detection(self):
        """Test detection of object initialization change"""
        old = "Builder builder = new Builder();"
        new = "ObjectBuilder ob = new ObjectBuilder();"

        intent = self.adapter._extract_hunk_intent(old, new)

        self.assertEqual(intent.operation_type, HunkOperationType.OBJECT_INITIALIZATION)
        self.assertGreater(intent.confidence, 0.7)

    def test_unknown_operation(self):
        """Test fallback for unknown operations"""
        old = "int x = 5;"
        new = "int x = 10;"

        intent = self.adapter._extract_hunk_intent(old, new)

        # Should default to UNKNOWN or be classified as field
        self.assertIsNotNone(intent.operation_type)


class TestKeyIdentifierExtraction(unittest.TestCase):
    """Test extraction of key identifiers for searching"""

    def setUp(self):
        self.adapter = SemanticHunkAdapter()

    def test_method_name_extraction(self):
        """Test extraction of method names"""
        text = "builder.startObject(COMPILATIONS_HISTORY);"
        identifiers = self.adapter._extract_key_identifiers(text)

        self.assertIn("startObject", identifiers)
        self.assertIn("COMPILATIONS_HISTORY", identifiers)

    def test_class_name_extraction(self):
        """Test extraction of class names"""
        text = "ObjectBuilder ob = new ObjectBuilder();"
        identifiers = self.adapter._extract_key_identifiers(text)

        self.assertIn("ObjectBuilder", identifiers)

    def test_multiple_identifiers(self):
        """Test extraction of multiple identifiers"""
        text = "XContentBuilder xb = response.getBuilder();"
        identifiers = self.adapter._extract_key_identifiers(text)

        # Should extract multiple identifiers
        self.assertGreater(len(identifiers), 1)
        self.assertIn("XContentBuilder", identifiers)
        self.assertIn("getBuilder", identifiers)


class TestEquivalentLocationFinding(unittest.TestCase):
    """Test finding equivalent locations in target code"""

    def setUp(self):
        self.adapter = SemanticHunkAdapter()

    def test_identifier_search_finds_location(self):
        """Test finding location by identifier search"""
        intent = HunkIntent(
            operation_type=HunkOperationType.METHOD_CALL,
            target_entity="startObject",
            confidence=0.8,
            original_old_string="builder.startObject()",
            original_new_string="ob.xContentObject()",
        )

        target_content = """
        public void test() {
            // Some code
            builder.startObject(key);
            // More code
        }
        """

        location = self.adapter._find_equivalent_location(
            intent=intent,
            target_file_content=target_content,
        )

        self.assertIsNotNone(location)
        self.assertIn("startObject", location.get("location_text", ""))

    def test_entity_search_finds_location(self):
        """Test finding location by entity search"""
        intent = HunkIntent(
            operation_type=HunkOperationType.METHOD_DEFINITION,
            target_entity="setup",
            confidence=0.8,
            original_old_string="public void setup() {",
            original_new_string="public void setUp() throws Exception {",
        )

        target_content = """
        public class TestClass {
            public void setup() {
                // test code
            }
        }
        """

        location = self.adapter._find_equivalent_location(
            intent=intent,
            target_file_content=target_content,
        )

        self.assertIsNotNone(location)
        self.assertGreater(location.get("line_number", 0), 0)


class TestBracketBalance(unittest.TestCase):
    """Test bracket/paren balance checking"""

    def setUp(self):
        self.adapter = SemanticHunkAdapter()

    def test_balanced_brackets(self):
        """Test balanced brackets"""
        text = "method(arg1, arg2) { if (x > 0) { return [1, 2, 3]; } }"
        self.assertTrue(self.adapter._check_bracket_balance(text))

    def test_unbalanced_brackets(self):
        """Test unbalanced brackets"""
        text = "method(arg1, arg2 { return [1, 2, 3]; }"
        self.assertFalse(self.adapter._check_bracket_balance(text))

    def test_string_literal_handling(self):
        """Test correct handling of brackets in string literals"""
        text = 'String s = "method(args) {}";\nmethod(args) { return s; }'
        self.assertTrue(self.adapter._check_bracket_balance(text))

    def test_escaped_quotes(self):
        """Test handling of escaped quotes"""
        text = r'String s = "He said \"Hello\""; method() {}'
        self.assertTrue(self.adapter._check_bracket_balance(text))


class TestConfidenceScoring(unittest.TestCase):
    """Test confidence score calculation"""

    def setUp(self):
        self.adapter = SemanticHunkAdapter()

    def test_perfect_score(self):
        """Test perfect confidence score"""
        score = self.adapter._score_confidence(
            intent_confidence=1.0,
            equivalent_location_confidence=1.0,
            recomposition_confidence=1.0,
            validation_errors=0,
        )
        self.assertEqual(score, 1.0)

    def test_partial_score(self):
        """Test partial confidence score"""
        score = self.adapter._score_confidence(
            intent_confidence=0.8,
            equivalent_location_confidence=0.7,
            recomposition_confidence=0.8,
            validation_errors=0,
        )
        # Expected: 0.8 * 0.7 * 0.8 = 0.448
        self.assertAlmostEqual(score, 0.448, places=2)

    def test_validation_error_penalty(self):
        """Test penalty for validation errors"""
        score_no_error = self.adapter._score_confidence(
            intent_confidence=0.8,
            equivalent_location_confidence=0.8,
            recomposition_confidence=0.8,
            validation_errors=0,
        )

        score_with_error = self.adapter._score_confidence(
            intent_confidence=0.8,
            equivalent_location_confidence=0.8,
            recomposition_confidence=0.8,
            validation_errors=1,
        )

        # Error should reduce score
        self.assertGreater(score_no_error, score_with_error)

    def test_score_bounds(self):
        """Test that score is always between 0 and 1"""
        score = self.adapter._score_confidence(
            intent_confidence=1.5,  # Over 1.0
            equivalent_location_confidence=0.5,
            recomposition_confidence=0.5,
            validation_errors=100,  # Many errors
        )

        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestAdaptationFlow(unittest.TestCase):
    """Test full adaptation workflow"""

    def setUp(self):
        self.adapter = SemanticHunkAdapter()

    def test_exact_match_no_adaptation_needed(self):
        """Test that exact matches are detected"""
        old_string = "builder.startObject();"
        new_string = "ob.xContentObject();"
        target_content = "builder.startObject();\nob.xContentObject();"

        result = self.adapter.analyze_and_adapt(
            hunk_old_string=old_string,
            hunk_new_string=new_string,
            target_file_content=target_content,
            target_file_path="Test.java",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.strategy, AdaptationStrategy.EXACT_MATCH)
        self.assertEqual(result.confidence, 1.0)

    def test_low_intent_confidence_rejected(self):
        """Test that low confidence intents are rejected"""
        old_string = "x = y;"
        new_string = "a = b;"
        target_content = "some code here"

        result = self.adapter.analyze_and_adapt(
            hunk_old_string=old_string,
            hunk_new_string=new_string,
            target_file_content=target_content,
            target_file_path="Test.java",
        )

        # Should fail due to low intent confidence
        self.assertFalse(result.success)
        self.assertLess(result.confidence, 0.5)


if __name__ == "__main__":
    unittest.main()
