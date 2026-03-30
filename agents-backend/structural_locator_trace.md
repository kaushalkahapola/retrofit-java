# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Requests to data nodes were not ordered by node role priority, potentially leading to suboptimal query routing and performance.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plugin/DataNodeRequestSender.java`

**Hunks in this file**: 5

**Git Resolution**: Found `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plugin/DataNodeRequestSender.java`

**Agent Tool Steps:**


| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 21–21 |
| 2 | declaration | `<import>` | `<import>` | 41–42 |
| 3 | core_fix | `order/related static methods and NODE_QUERY_ORDER` | `DataNodeRequestSender (class static fields and private static methods)` | 58–91 |
| 4 | propagation | `sendRequestsForTargetShards` | `sendRequestsForTargetShards` | 127–127 |
| 5 | propagation | `selectNodeRequests` | `selectNodeRequests` | 327–327 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
