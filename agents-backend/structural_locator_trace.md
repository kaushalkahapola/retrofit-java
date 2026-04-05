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
| 2 | guard | `hunk_2` | `None` | 267–267 |
### `server/src/main/java/io/crate/replication/logical/LogicalReplicationSettings.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/LogicalReplicationSettings.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 92–92 |
| 2 | propagation | `hunk_2` | `None` | 149–149 |
### `server/src/main/java/io/crate/replication/logical/MetadataTracker.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/MetadataTracker.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 24–24 |
| 2 | core_fix | `hunk_2` | `None` | 405–405 |
| 3 | guard | `hunk_3` | `None` | 440–440 |
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
| 2 | core_fix | `hunk_2` | `None` | 124–124 |
| 3 | guard | `subscriberCanRead` | `subscriberCanRead` | 172–172 |
### `server/src/main/java/io/crate/replication/logical/metadata/RelationMetadata.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/metadata/RelationMetadata.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 27–27 |
| 2 | core_fix | `fromMetadata` | `fromMetadata` | 61–61 |
| 3 | guard | `hunk_3` | `None` | 74–74 |
### `server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 22–22 |
| 2 | core_fix | `hunk_2` | `None` | 152–152 |
| 3 | core_fix | `hunk_3` | `None` | 199–199 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
