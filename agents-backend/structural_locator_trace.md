# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 10
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/execution/dml/upsert/ShardUpsertRequest.java`

**Hunks in this file**: 4

**Git Resolution**: Found `server/src/main/java/io/crate/execution/dml/upsert/ShardUpsertRequest.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | 50–50 |
| 2 | propagation | `hunk_2` | `None` | 317–317 |
| 3 | core_fix | `sizeEstimateForUpdate` | `sizeEstimateForUpdate` | 337–337 |
| 4 | propagation | `hunk_4` | `None` | 587–587 |
### `server/src/main/java/io/crate/execution/dsl/projection/ColumnIndexWriterProjection.java`

**Hunks in this file**: 8

**Git Resolution**: Found `server/src/main/java/io/crate/execution/dsl/projection/ColumnIndexWriterProjection.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<class_declaration>` | `<class_declaration>` | 20–20 |
| 2 | guard | `hunk_2` | `None` | 80–80 |
| 3 | propagation | `hunk_3` | `None` | 89–89 |
| 4 | guard | `outputs` | `outputs` | 139–139 |
| 5 | guard | `hunk_5` | `None` | 201–201 |
| 6 | guard | `hunk_6` | `None` | 210–210 |
| 7 | guard | `bind` | `bind` | 251–251 |
| 8 | guard | `hunk_8` | `None` | 279–279 |
### `server/src/main/java/io/crate/execution/dsl/projection/UpdateProjection.java`

**Hunks in this file**: 4

**Git Resolution**: Found `server/src/main/java/io/crate/execution/dsl/projection/UpdateProjection.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<class_declaration>` | `<class_declaration>` | 60–60 |
| 2 | propagation | `hunk_2` | `None` | 66–66 |
| 3 | guard | `uidSymbol` | `uidSymbol` | 102–102 |
| 4 | guard | `hunk_4` | `None` | 207–207 |
### `server/src/main/java/io/crate/execution/engine/indexing/ColumnIndexWriterProjector.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/indexing/ColumnIndexWriterProjector.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | 88–88 |
| 2 | guard | `hunk_2` | `None` | 119–119 |
### `server/src/main/java/io/crate/execution/engine/indexing/IndexWriterProjector.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/indexing/IndexWriterProjector.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | 126–126 |
### `server/src/main/java/io/crate/planner/consumer/InsertFromSubQueryPlanner.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/planner/consumer/InsertFromSubQueryPlanner.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 80–80 |
### `server/src/main/java/io/crate/planner/consumer/UpdatePlanner.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/planner/consumer/UpdatePlanner.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 279–279 |
### `server/src/main/java/io/crate/planner/operators/InsertFromValues.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/planner/operators/InsertFromValues.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | 480–480 |
### `server/src/main/java/io/crate/statistics/TableStats.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/statistics/TableStats.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 22–22 |
| 2 | guard | `statsEntries` | `statsEntries` | 62–62 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
