# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 3
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java`

**Hunks in this file**: 6

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 22–22 |
| 2 | declaration | `<import>` | `<import>` | 40–40 |
| 3 | declaration | `<class_declaration>` | `<class_declaration>` | 76–76 |
| 4 | propagation | `hunk_4` | `None` | 83–83 |
| 5 | propagation | `hunk_5` | `None` | 92–92 |
| 6 | core_fix | `hunk_6` | `None` | 222–222 |
### `server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java`

**Hunks in this file**: 4

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 37–37 |
| 2 | declaration | `<class_declaration>` | `<class_declaration>` | 49–49 |
| 3 | core_fix | `hunk_3` | `None` | 57–57 |
| 4 | core_fix | `hunk_4` | `None` | 110–110 |
### `server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 25–25 |
| 2 | core_fix | `hunk_2` | `None` | 113–113 |
| 3 | guard | `hunk_3` | `None` | 207–207 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
