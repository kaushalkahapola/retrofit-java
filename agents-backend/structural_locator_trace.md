# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 3
- Test files: 0

## Code File Mappings

### `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/DeprecationChecks.java`

**Hunks in this file**: 2

**Git Resolution**: Found `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/DeprecationChecks.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
  - JavaStructureLocator recovered target_method for hunk 1: DeprecationChecks (java_structure_locator:class_signature)
| 1 | propagation | `hunk_1` | `DeprecationChecks` | 92–92 |
  - JavaStructureLocator recovered target_method for hunk 2: DeprecationChecks (java_structure_locator:class_signature)
| 2 | propagation | `hunk_2` | `DeprecationChecks` | 101–101 |
### `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecks.java`

**Hunks in this file**: 2

**Git Resolution**: Found `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecks.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | 19–19 |
| 2 | core_fix | `checkSourceModeInMapping` | `checkSourceModeInMapping` | 207–207 |
### `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/NodeDeprecationChecks.java`

**Hunks in this file**: 2

**Git Resolution**: Found `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/NodeDeprecationChecks.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 10–10 |
  - JavaStructureLocator recovered target_method for hunk 2: MONITORING_SETTING_REMOVAL_TIME (java_structure_locator:field_declaration)
| 2 | guard | `hunk_2` | `MONITORING_SETTING_REMOVAL_TIME` | 1035–1035 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
