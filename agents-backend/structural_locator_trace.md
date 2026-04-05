# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 6
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java`

**Hunks in this file**: 4

**Git Resolution**: Found `server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 35–35 |
| 2 | guard | `hunk_2` | `None` | 196–196 |
| 3 | guard | `hunk_3` | `None` | 211–211 |
| 4 | core_fix | `deleteTempIndices` | `deleteTempIndices` | 283–283 |
### `server/src/main/java/io/crate/execution/ddl/tables/GCDanglingArtifactsRequest.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/ddl/tables/GCDanglingArtifactsRequest.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<class_declaration>` | `<class_declaration>` | 31–31 |
### `server/src/main/java/io/crate/execution/ddl/tables/TransportGCDanglingArtifacts.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/ddl/tables/TransportGCDanglingArtifacts.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `hunk_1` | `None` | 95–95 |
### `server/src/main/java/io/crate/planner/GCDanglingArtifactsPlan.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/planner/GCDanglingArtifactsPlan.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 45–45 |
### `server/src/main/java/org/elasticsearch/Version.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/Version.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 206–206 |
### `server/src/main/java/org/elasticsearch/action/admin/indices/shrink/TransportResize.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/action/admin/indices/shrink/TransportResize.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 19–19 |
| 2 | guard | `hunk_2` | `None` | 123–123 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
