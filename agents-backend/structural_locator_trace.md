# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Pair Consistency
- Pair mismatch: True
- Overlap ratio (mainline): 0.0
- Overlap Java files: []

## Locator Retry State
- Attempt: 1
- Previously failed paths: []

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Verifier.java`

**Hunks in this file**: 2

**Agent Tool Steps:**

  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Verifier.java"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.analysis;\n\n// Line 55\npublic class Verifier {\n    // Line 57: private final org.elasticsearch.xpack.esql.telemetry.Metrics metrics;\n    // Line 5...
  - `Agent calls grep_repo` with `{"search_text": "checkConditionExpressionDataType", "is_regex": false}`
  - `Agent calls grep_repo` with `{"search_text": "Condition expression needs to be boolean, found [{}]", "is_regex": false}`
  - `Tool: grep_repo` -> No matches found for 'checkConditionExpressionDataType'....
  - `Tool: grep_repo` -> Found 3 match(es):
  x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/capabilities/PostAnalysisVerificationAware.java:37 :: *              failures.add(fail(condition, "Condition expressi...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/capabilities/PostAnalysisVerificationAware.java", "focus_method": "checkConditionExpressionDataType"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plan/logical/Filter.java", "focus_method": "checkConditionExpressionDataType"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/ql/src/main/java/org/elasticsearch/xpack/ql/analyzer/VerifierChecks.java", "focus_method": "checkConditionExpressionDataType"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.capabilities;\n\n// Line 19\npublic interface PostAnalysisVerificationAware {\n    // Line 45: public abstract void postAnalysisVerification(Failures ...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.plan.logical;\n\n// Line 32\npublic class Filter extends UnaryPlan implements PostAnalysisVerificationAware, TelemetryAware, SortAgnostic {\n    // Li...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.ql.analyzer;\n\n// Line 20\npublic class VerifierChecks {\n    // Line 22: public static void checkFilterConditionType(LogicalPlan p, Set localFailures) { ...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plan/logical/Filter.java", "focus_method": "checkFilterConditionDataType"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/ql/src/main/java/org/elasticsearch/xpack/ql/analyzer/VerifierChecks.java", "focus_method": "checkFilterConditionType"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.plan.logical;\n\n// Line 32\npublic class Filter extends UnaryPlan implements PostAnalysisVerificationAware, TelemetryAware, SortAgnostic {\n    // Li...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.ql.analyzer;\n\n// Line 20\npublic class VerifierChecks {\n    // [FOCUS] Full Body (Lines 22-29)\n  22:     public static void checkFilterConditionType(Lo...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plan/logical/Filter.java", "focus_method": "checkFilterConditionType"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/ql/src/main/java/org/elasticsearch/xpack/ql/analyzer/VerifierChecks.java", "focus_method": "checkFilterConditionType"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.plan.logical;\n\n// Line 32\npublic class Filter extends UnaryPlan implements PostAnalysisVerificationAware, TelemetryAware, SortAgnostic {\n    // Li...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.ql.analyzer;\n\n// Line 20\npublic class VerifierChecks {\n    // [FOCUS] Full Body (Lines 22-29)\n  22:     public static void checkFilterConditionType(Lo...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plan/logical/Filter.java", "focus_method": "checkFilterConditionType"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/ql/src/main/java/org/elasticsearch/xpack/ql/analyzer/VerifierChecks.java", "focus_method": "checkFilterConditionType"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.plan.logical;\n\n// Line 32\npublic class Filter extends UnaryPlan implements PostAnalysisVerificationAware, TelemetryAware, SortAgnostic {\n    // Li...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.ql.analyzer;\n\n// Line 20\npublic class VerifierChecks {\n    // [FOCUS] Full Body (Lines 22-29)\n  22:     public static void checkFilterConditionType(Lo...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plan/logical/Filter.java", "focus_method": "checkFilterConditionDataType"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/ql/src/main/java/org/elasticsearch/xpack/ql/analyzer/VerifierChecks.java", "focus_method": "checkFilterConditionType"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.plan.logical;\n\n// Line 32\npublic class Filter extends UnaryPlan implements PostAnalysisVerificationAware, TelemetryAware, SortAgnostic {\n    // Li...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.ql.analyzer;\n\n// Line 20\npublic class VerifierChecks {\n    // [FOCUS] Full Body (Lines 22-29)\n  22:     public static void checkFilterConditionType(Lo...

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `checkFilterConditionType` | `checkFilterConditionType` | 25–32 |
| 2 | core_fix | `checkConditionExpressionDataType` | `checkFilterConditionDataType` | 114–118 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
