# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: The vulnerability stems from inaccurate memory usage estimation for upsert operations, specifically underestimating the size of full documents when loaded from disk, which can lead to resource exhaustion or denial of service due to improper memory accounting.

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
  - JavaStructureLocator recovered target_method for hunk 2: usedBytes (java_structure_locator:field_declaration)
| 2 | propagation | `hunk_2` | `usedBytes` | 317–317 |
| 3 | core_fix | `sizeEstimateForUpdate` | `sizeEstimateForUpdate` | 337–337 |
  - JavaStructureLocator recovered target_method for hunk 4: newRequest (java_structure_locator:method)
| 4 | propagation | `hunk_4` | `newRequest` | 587–587 |
### `server/src/main/java/io/crate/execution/dsl/projection/ColumnIndexWriterProjection.java`

**Hunks in this file**: 8

**Git Resolution**: Found `server/src/main/java/io/crate/execution/dsl/projection/ColumnIndexWriterProjection.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<class_declaration>` | `<class_declaration>` | 20–20 |
  - JavaStructureLocator recovered target_method for hunk 2: returnValues (java_structure_locator:field_declaration)
| 2 | guard | `hunk_2` | `returnValues` | 80–80 |
  - JavaStructureLocator recovered target_method for hunk 3: returnValues (java_structure_locator:field_declaration)
| 3 | propagation | `hunk_3` | `returnValues` | 89–89 |
| 4 | guard | `outputs` | `outputs` | 139–139 |
  - JavaStructureLocator recovered target_method for hunk 5: equals (java_structure_locator:method)
| 5 | guard | `hunk_5` | `equals` | 201–201 |
  - JavaStructureLocator recovered target_method for hunk 6: hashCode (java_structure_locator:method)
| 6 | guard | `hunk_6` | `hashCode` | 210–210 |
| 7 | guard | `bind` | `bind` | 251–251 |
  - JavaStructureLocator recovered target_method for hunk 8: bind (java_structure_locator:method)
| 8 | guard | `hunk_8` | `bind` | 279–279 |
### `server/src/main/java/io/crate/execution/dsl/projection/UpdateProjection.java`

**Hunks in this file**: 4

**Git Resolution**: Found `server/src/main/java/io/crate/execution/dsl/projection/UpdateProjection.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<class_declaration>` | `<class_declaration>` | 60–60 |
  - JavaStructureLocator recovered target_method for hunk 2: requiredVersion (java_structure_locator:field_declaration)
| 2 | propagation | `hunk_2` | `requiredVersion` | 66–66 |
| 3 | guard | `uidSymbol` | `uidSymbol` | 102–102 |
  - JavaStructureLocator recovered target_method for hunk 4: writeTo (java_structure_locator:method)
| 4 | guard | `hunk_4` | `writeTo` | 207–207 |
### `server/src/main/java/io/crate/execution/engine/indexing/ColumnIndexWriterProjector.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/indexing/ColumnIndexWriterProjector.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
  - JavaStructureLocator recovered target_method for hunk 1: shardingUpsertExecutor (java_structure_locator:field_declaration)
| 1 | propagation | `hunk_1` | `shardingUpsertExecutor` | 88–88 |
  - JavaStructureLocator recovered target_method for hunk 2: shardingUpsertExecutor (java_structure_locator:field_declaration)
| 2 | guard | `hunk_2` | `shardingUpsertExecutor` | 119–119 |
### `server/src/main/java/io/crate/execution/engine/indexing/IndexWriterProjector.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/indexing/IndexWriterProjector.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
  - JavaStructureLocator recovered target_method for hunk 1: shardingUpsertExecutor (java_structure_locator:field_declaration)
| 1 | propagation | `hunk_1` | `shardingUpsertExecutor` | 126–126 |
### `server/src/main/java/io/crate/planner/consumer/InsertFromSubQueryPlanner.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/planner/consumer/InsertFromSubQueryPlanner.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
  - JavaStructureLocator recovered target_method for hunk 1: InsertFromSubQueryPlanner (java_structure_locator:class_signature)
| 1 | core_fix | `hunk_1` | `InsertFromSubQueryPlanner` | 80–80 |
### `server/src/main/java/io/crate/planner/consumer/UpdatePlanner.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/planner/consumer/UpdatePlanner.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
  - JavaStructureLocator recovered target_method for hunk 1: type (java_structure_locator:method)
| 1 | core_fix | `hunk_1` | `type` | 279–279 |
### `server/src/main/java/io/crate/planner/operators/InsertFromValues.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/planner/operators/InsertFromValues.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
  - JavaStructureLocator recovered target_method for hunk 1: assignmentSources (java_structure_locator:field_declaration)
| 1 | propagation | `hunk_1` | `assignmentSources` | 480–480 |
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
