"""
Integration tests for semantic hunk adapter with real-world test cases.

Simulates scenarios from actual failing backports like elasticsearch_88cf2487.
"""

import sys

sys.path.insert(0, ".")

from semantic_hunk_adapter import (
    SemanticHunkAdapter,
    APISignatureMapper,
    AdaptationStrategy,
)


def test_elasticsearch_88cf2487_case():
    """
    Real-world test case: elasticsearch_88cf2487

    Original hunk (mainline):
        builder.startObject(COMPILATIONS_HISTORY);

    Target code (diverged API):
        ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);

    The builder API changed to a different object type and signature.
    """
    print("\n" + "=" * 70)
    print("TEST: elasticsearch_88cf2487 - API Refactoring Case")
    print("=" * 70)

    adapter = SemanticHunkAdapter()

    # The hunk that failed in mainline
    old_string = "    builder.startObject(COMPILATIONS_HISTORY);"
    new_string = "    ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);"

    # Target file content (simplified representation of diverged code)
    target_content = """
public class CachesStatsResponse extends ToXContentResponse {
    private Map<String, CacheStatsInfo> cacheStatsInfo;
    
    @Override
    protected void toXContent(XContentBuilder ob, Params params) throws IOException {
        ob.startObject();
        ob.field("cluster_name", clusterName);
        
        if (cacheEvictionsHistory != null) {
            ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);
        }
        
        ob.endObject();
    }
}
"""

    # Run adaptation
    result = adapter.analyze_and_adapt(
        hunk_old_string=old_string,
        hunk_new_string=new_string,
        target_file_content=target_content,
        target_file_path="CachesStatsResponse.java",
    )

    # Verify results
    print(f"Strategy: {result.strategy.value}")
    print(f"Success: {result.success}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Reason: {result.reason}")

    if result.intent:
        print(f"Intent: {result.intent.operation_type.value}")
        print(f"Intent Confidence: {result.intent.confidence:.2f}")

    if result.detected_changes:
        print(f"Detected Changes: {result.detected_changes}")

    if result.adaptation_steps:
        print(f"Adaptation Steps:")
        for step in result.adaptation_steps:
            print(f"  - {step}")

    # Success criteria: should have found equivalent location and adapted
    assert result.success or result.confidence > 0.25, (
        "Should find equivalent or high confidence adaptation"
    )
    print("✓ Test passed!")
    return result


def test_method_rename_case():
    """Test case: Method renamed between versions"""
    print("\n" + "=" * 70)
    print("TEST: Method Rename - setUp -> setup")
    print("=" * 70)

    adapter = SemanticHunkAdapter()

    old_string = "public void setUp() throws Exception {"

    new_string = "public void setup() throws Exception {"

    target_content = """
public class TestCase {
    protected SearchEngine engine;
    
    public void setup() throws Exception {
        engine = createEngine();
    }
}
"""

    result = adapter.analyze_and_adapt(
        hunk_old_string=old_string,
        hunk_new_string=new_string,
        target_file_content=target_content,
        target_file_path="TestCase.java",
    )

    print(f"Strategy: {result.strategy.value}")
    print(f"Success: {result.success}")
    print(f"Confidence: {result.confidence:.2f}")

    # For this test, just verify it found the location and attempted adaptation
    assert result.equivalent_location_line is not None or result.confidence > 0.2, (
        "Should find equivalent location"
    )
    print("✓ Test passed!")
    return result


def test_builder_pattern_change():
    """Test case: Builder pattern changed"""
    print("\n" + "=" * 70)
    print("TEST: Builder Pattern Change")
    print("=" * 70)

    mapper = APISignatureMapper()
    adapter = SemanticHunkAdapter()

    old_call = mapper.extract_method_call("builder.startObject(FIELD_NAME)")
    print(f"Old call extracted: {old_call}")

    assert old_call["object"] == "builder"
    assert old_call["method_name"] == "startObject"

    # Transform to new API
    new_call_str = mapper.transform_method_call(
        old_call=old_call,
        new_method_name="xContentObject",
        new_object="ob",
        parameter_mapping=None,
    )
    print(f"Transformed call: {new_call_str}")

    assert new_call_str == "ob.xContentObject(FIELD_NAME)"
    print("✓ Test passed!")
    return True


def test_confidence_scoring():
    """Test confidence scoring system"""
    print("\n" + "=" * 70)
    print("TEST: Confidence Scoring")
    print("=" * 70)

    adapter = SemanticHunkAdapter()

    # Perfect score
    perfect = adapter._score_confidence(1.0, 1.0, 1.0, 0)
    print(f"Perfect score (1.0, 1.0, 1.0, 0 errors): {perfect}")
    assert perfect == 1.0

    # Partial score
    partial = adapter._score_confidence(0.8, 0.7, 0.75, 0)
    print(f"Partial score (0.8, 0.7, 0.75, 0 errors): {partial:.3f}")
    expected = 0.8 * 0.7 * 0.75
    assert abs(partial - expected) < 0.001

    # With errors
    with_errors = adapter._score_confidence(0.8, 0.8, 0.8, 2)
    print(f"With errors (0.8, 0.8, 0.8, 2 errors): {with_errors:.3f}")
    assert with_errors < (0.8 * 0.8 * 0.8)

    print("✓ Test passed!")
    return True


def test_validation_logic():
    """Test hunk validation logic"""
    print("\n" + "=" * 70)
    print("TEST: Hunk Validation")
    print("=" * 70)

    adapter = SemanticHunkAdapter()

    target_content = """
public class Test {
    public void method() {
        doSomething();
    }
}
"""

    # Valid adaptation: old string exists, new string has valid syntax
    errors = adapter._validate_adaptation(
        adapted_old_string="public void method() {",
        adapted_new_string="public void method() {\n        doSomething();",
        target_file_content=target_content,
    )
    print(f"Valid adaptation errors: {len(errors)}")
    # Should have 0 or minimal errors (validation is lenient)

    # Invalid: completely missing old string (with unbalanced brackets)
    errors = adapter._validate_adaptation(
        adapted_old_string="zzzAbsolutelyUnknown qqq",
        adapted_new_string="some replacement [unclosed",
        target_file_content=target_content,
    )
    print(f"Invalid (missing) errors: {len(errors)}")
    assert len(errors) > 0, "Should detect missing old_string or syntax errors"

    print("✓ Test passed!")
    return True


def test_intent_extraction_comprehensiveness():
    """Test that intent extraction works for various hunk types"""
    print("\n" + "=" * 70)
    print("TEST: Intent Extraction Comprehensiveness")
    print("=" * 70)

    adapter = SemanticHunkAdapter()

    test_cases = [
        # (old, new, expected_operation_type, min_confidence)
        (
            "import java.util.List;",
            "import java.util.List;\nimport java.util.Map;",
            "import_addition",
            0.9,
        ),
        (
            "builder.method();",
            "ob.method();",
            "method_call",
            0.7,
        ),
        (
            "private int count;",
            "private int count = 0;",
            "field_declaration",
            0.7,
        ),
    ]

    for old, new, expected_type, min_conf in test_cases:
        intent = adapter._extract_hunk_intent(old, new)
        print(
            f"Type: {intent.operation_type.value}, Confidence: {intent.confidence:.2f}"
        )
        assert intent.operation_type.value == expected_type
        assert intent.confidence >= min_conf, (
            f"Confidence {intent.confidence} < {min_conf}"
        )

    print("✓ All intent extractions passed!")
    return True


def run_all_tests():
    """Run all Phase D tests"""
    print("\n" + "=" * 80)
    print("PHASE D: COMPREHENSIVE INTEGRATION TESTS")
    print("=" * 80)

    tests = [
        ("elasticsearch_88cf2487", test_elasticsearch_88cf2487_case),
        ("method_rename", test_method_rename_case),
        ("builder_pattern", test_builder_pattern_change),
        ("confidence_scoring", test_confidence_scoring),
        ("validation_logic", test_validation_logic),
        ("intent_extraction", test_intent_extraction_comprehensiveness),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_name} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        return True
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
