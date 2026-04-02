# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Lack of proper ordering of nodes based on their roles when sending requests to data nodes.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plugin/DataNodeRequestSender.java`

**Hunks in this file**: 5

**Git Resolution**: Found `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plugin/DataNodeRequestSender.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 17–17 |
| 2 | declaration | `<import>` | `<import>` | 39–39 |
| 3 | declaration | `<class_declaration>` | `<class_declaration>` | 59–59 |
| 4 | core_fix | `trySendingRequestsForPendingShards` | `trySendingRequestsForPendingShards` | 129–129 |
| 5 | cleanup | `selectNodeRequests` | `selectNodeRequests` | 341–341 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
