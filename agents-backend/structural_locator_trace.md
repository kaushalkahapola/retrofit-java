# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: The original code did not properly validate that the condition expression's data type is boolean, potentially allowing non-boolean types to be processed.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Verifier.java`

**Hunks in this file**: 2

**Git Resolution**: Found `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Verifier.java`

**Fallback Mode**: direct no-tool LLM mapping used after recursion limit.

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `checkFilterConditionType` | `checkFilterConditionType` | 237–240 |
| 2 | propagation | `checkConditionExpressionDataType` | `checkConditionExpressionDataType` | 243–250 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
