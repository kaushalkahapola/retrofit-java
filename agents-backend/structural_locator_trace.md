# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Incorrect condition for checking if pushable sorts are available, which could lead to failing to push down sorts when they are present.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/optimizer/rules/physical/local/PushTopNToSource.java`

**Hunks in this file**: 1

**Git Resolution**: Found `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/optimizer/rules/physical/local/PushTopNToSource.java`

**Agent Tool Steps:**

  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/optimizer/rules/physical/local/PushTopNToSource.java"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.optimizer.rules.physical.local;\n\n// Line 62\npublic class PushTopNToSource extends ParameterizedOptimizerRule {\n    // Line 79: private static fina...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/optimizer/rules/physical/local/PushTopNToSource.java", "focus_method": "rule"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/optimizer/rules/physical/local/PushTopNToSource.java", "focus_method": "rewrite"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.optimizer.rules.physical.local;\n\n// Line 62\npublic class PushTopNToSource extends ParameterizedOptimizerRule {\n    // Line 79: private static fina...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.optimizer.rules.physical.local;\n\n// Line 62\npublic class PushTopNToSource extends ParameterizedOptimizerRule {\n    // Line 79: private static fina...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/optimizer/rules/physical/local/PushTopNToSource.java", "focus_method": "PushableCompoundExec"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/optimizer/rules/physical/local/PushTopNToSource.java", "focus_method": "PushableQueryExec"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.optimizer.rules.physical.local;\n\n// Line 62\npublic class PushTopNToSource extends ParameterizedOptimizerRule {\n    // Line 79: private static fina...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.optimizer.rules.physical.local;\n\n// Line 62\npublic class PushTopNToSource extends ParameterizedOptimizerRule {\n    // Line 79: private static fina...
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/optimizer/rules/physical/local/PushTopNToSource.java", "focus_method": "evaluatePushable"}`
  - `Agent calls get_class_context` with `{"file_path": "x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/optimizer/rules/physical/local/PushTopNToSource.java", "focus_method": "canPushDownOrders"}`
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.optimizer.rules.physical.local;\n\n// Line 62\npublic class PushTopNToSource extends ParameterizedOptimizerRule {\n    // Line 79: private static fina...
  - `Tool: get_class_context` -> {"context": "package org.elasticsearch.xpack.esql.optimizer.rules.physical.local;\n\n// Line 62\npublic class PushTopNToSource extends ParameterizedOptimizerRule {\n    // Line 79: private static fina...

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `rule` | `rule` | 65–68 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
