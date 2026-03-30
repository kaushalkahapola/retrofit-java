# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Lack of proper ordering of nodes based on their roles when sending requests, which could lead to inefficient query execution.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plugin/DataNodeRequestSender.java`

**Hunks in this file**: 5

**Git Resolution**: Found `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plugin/DataNodeRequestSender.java`

**Fallback Mode**: direct no-tool LLM mapping used after recursion limit.

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `DataNodeRequestSender` | `<import>` | 17–17 |
| 2 | declaration | `DataNodeRequestSender` | `<import>` | 37–37 |
| 3 | declaration | `DataNodeRequestSender` | `<import>` | 57–57 |
| 4 | core_fix | `DataNodeRequestSender` | `order` | 106–123 |
| 5 | cleanup | `DataNodeRequestSender` | `selectNodeRequests` | 279–323 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
