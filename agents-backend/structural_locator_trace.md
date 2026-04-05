# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 7
- Test files: 0

## Code File Mappings

### `x-pack/plugin/core/src/main/java/org/elasticsearch/xpack/core/deprecation/DeprecatedIndexPredicate.java`

**Hunks in this file**: 2

**Git Resolution**: Found `x-pack/plugin/core/src/main/java/org/elasticsearch/xpack/core/deprecation/DeprecatedIndexPredicate.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `getReindexRequiredPredicate` | `getReindexRequiredPredicate` | 1–1 |
| 2 | declaration | `<class_declaration>` | `<class_declaration>` | 57–57 |
### `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/DataStreamDeprecationChecks.java`

**Hunks in this file**: 2

**Git Resolution**: Found `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/DataStreamDeprecationChecks.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `oldIndicesCheck` | `oldIndicesCheck` | 27–27 |
| 2 | declaration | `<class_declaration>` | `<class_declaration>` | 48–48 |
### `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/DeprecationChecks.java`

**Hunks in this file**: 2

**Git Resolution**: Found `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/DeprecationChecks.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | 96–96 |
| 2 | propagation | `hunk_2` | `None` | 106–106 |
### `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecks.java`

**Hunks in this file**: 2

**Git Resolution**: Found `x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecks.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `hunk_1` | `None` | 39–39 |
| 2 | guard | `isNotDataStreamIndex` | `isNotDataStreamIndex` | 49–49 |
### `x-pack/plugin/migrate/src/main/java/org/elasticsearch/xpack/migrate/action/ReindexDataStreamIndexTransportAction.java`

**Hunks in this file**: 1

**Git Resolution**: Found `x-pack/plugin/migrate/src/main/java/org/elasticsearch/xpack/migrate/action/ReindexDataStreamIndexTransportAction.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 121–121 |
### `x-pack/plugin/migrate/src/main/java/org/elasticsearch/xpack/migrate/action/ReindexDataStreamTransportAction.java`

**Hunks in this file**: 1

**Git Resolution**: Found `x-pack/plugin/migrate/src/main/java/org/elasticsearch/xpack/migrate/action/ReindexDataStreamTransportAction.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 71–71 |
### `x-pack/plugin/migrate/src/main/java/org/elasticsearch/xpack/migrate/task/ReindexDataStreamPersistentTaskExecutor.java`

**Hunks in this file**: 2

**Git Resolution**: Found `x-pack/plugin/migrate/src/main/java/org/elasticsearch/xpack/migrate/task/ReindexDataStreamPersistentTaskExecutor.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `hunk_1` | `None` | 113–113 |
| 2 | core_fix | `hunk_2` | `None` | 159–159 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
