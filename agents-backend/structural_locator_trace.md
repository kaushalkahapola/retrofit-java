# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

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
  - `Agent calls grep_repo` with `{"search_text": "Condition expression needs to be boolean, found", "is_regex": false}`
  - `Tool: grep_repo` -> No matches found for 'checkConditionExpressionDataType'....
  - `Tool: grep_repo` -> Found 17 match(es):
  x-pack/plugin/eql/src/test/java/org/elasticsearch/xpack/eql/analysis/VerifierTests.java:81 :: assertEquals("1:11: Condition expression needs to be boolean, found [LONG]", error("...
  - `Agent calls git_pickaxe` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Verifier.java", "snippet": "checkConditionExpressionDataType"}`
  - `Agent calls git_pickaxe` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Verifier.java", "snippet": "Condition expression needs to be boolean, found"}`
  - `Tool: git_pickaxe` -> No git history hits for content 'checkConditionExpressionDataType' in x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Verifier.java....
  - `Tool: git_pickaxe` -> Git Pickaxe results for content 'Condition expression needs to be boolean, found' in history of x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Verifier.java:
c17de01dbf7 ESQL: ...
  - `Agent calls get_dependency_graph` with `{"file_paths": ["x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Verifier.java"], "explore_neighbors": true}`
  - `Tool: get_dependency_graph` -> {"edges": [{"details": "resolveAgainstList(org.elasticsearch.xpack.esql.core.expression.UnresolvedAttribute,java.util.Collection) -> maybeResolveAgainstList(org.elasticsearch.xpack.esql.core.expressio...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plan/logical/Filter.java"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/capabilities/PostAnalysisVerificationAware.java"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.plan.logical;\n\n// Line 32\npublic class Filter extends UnaryPlan implements PostAnalysisVerificationAware, TelemetryAware, SortAgnostic {\n    // Li...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.capabilities;\n\n// Line 19\npublic interface PostAnalysisVerificationAware {\n    // Line 45: public abstract void postAnalysisVerification(Failures ...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Analyzer.java"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/AnalyzerRules.java"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.analysis;\n\n// Line 145\npublic class Analyzer extends ParameterizedRuleExecutor {\n    // Line 148: // marker list of attributes for plans that do n...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.analysis;\n\n// Line 23\npublic class AnalyzerRules {\n    // Line 83: public static List maybeResolveAgainstList(Predicate matcher, Supplier unresolv...

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `checkFilterConditionType` | `checkFilterConditionDataType` | None–None |
| 2 | core_fix | `checkConditionExpressionDataType` | `None` | None–None |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
