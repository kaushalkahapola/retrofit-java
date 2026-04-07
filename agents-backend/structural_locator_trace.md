# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 7
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/replication/logical/LogicalReplicationService.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/LogicalReplicationService.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 52–52 |
  - JavaStructureLocator recovered target_method for hunk 2: close (java_structure_locator:method)
| 2 | guard | `hunk_2` | `close` | 267–267 |
### `server/src/main/java/io/crate/replication/logical/LogicalReplicationSettings.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/LogicalReplicationSettings.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
  - JavaStructureLocator recovered target_method for hunk 1: LogicalReplicationSettings (java_structure_locator:class_signature)
| 1 | core_fix | `hunk_1` | `LogicalReplicationSettings` | 92–92 |
  - JavaStructureLocator recovered target_method for hunk 2: LogicalReplicationSettings (java_structure_locator:class_signature)
| 2 | propagation | `hunk_2` | `LogicalReplicationSettings` | 149–149 |
### `server/src/main/java/io/crate/replication/logical/MetadataTracker.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/MetadataTracker.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 24–24 |
  - JavaStructureLocator recovered target_method for hunk 2: AckMetadataUpdateRequest (java_structure_locator:class_signature)
| 2 | core_fix | `hunk_2` | `AckMetadataUpdateRequest` | 405–405 |
  - JavaStructureLocator recovered target_method for hunk 3: isEmpty (java_structure_locator:method)
| 3 | guard | `hunk_3` | `isEmpty` | 440–440 |
### `server/src/main/java/io/crate/replication/logical/action/PublicationsStateAction.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/action/PublicationsStateAction.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 39–39 |
| 2 | core_fix | `concreteIndices` | `concreteIndices` | 221–221 |
### `server/src/main/java/io/crate/replication/logical/metadata/Publication.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/metadata/Publication.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 30–30 |
  - JavaStructureLocator recovered target_method for hunk 2: toString (java_structure_locator:method)
| 2 | core_fix | `hunk_2` | `toString` | 124–124 |
| 3 | guard | `subscriberCanRead` | `subscriberCanRead` | 172–172 |
### `server/src/main/java/io/crate/replication/logical/metadata/RelationMetadata.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/metadata/RelationMetadata.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 27–27 |
| 2 | core_fix | `fromMetadata` | `fromMetadata` | 61–61 |
  - JavaStructureLocator recovered target_method for hunk 3: fromMetadata (java_structure_locator:method)
| 3 | guard | `hunk_3` | `fromMetadata` | 74–74 |
### `server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 22–22 |
  - JavaStructureLocator recovered target_method for hunk 2: getPublicationsState (java_structure_locator:method)
| 2 | core_fix | `hunk_2` | `getPublicationsState` | 152–152 |
  - JavaStructureLocator recovered target_method for hunk 3: getPublicationsState (java_structure_locator:method)
| 3 | core_fix | `hunk_3` | `getPublicationsState` | 199–199 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
