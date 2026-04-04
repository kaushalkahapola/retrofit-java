# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `x-pack/plugin/migrate/src/main/java/org/elasticsearch/xpack/migrate/action/ReindexDataStreamIndexTransportAction.java`

**Hunks in this file**: 6

**Git Resolution**: Found `x-pack/plugin/migrate/src/main/java/org/elasticsearch/xpack/migrate/action/ReindexDataStreamIndexTransportAction.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 24–24 |
| 2 | declaration | `<import>` | `<import>` | 66–66 |
| 3 | core_fix | `hunk_3` | `None` | 152–152 |
| 4 | core_fix | `hunk_4` | `None` | 171–171 |
| 5 | core_fix | `setBlockWrites` | `setBlockWrites` | 225–225 |
| 6 | core_fix | `getIndexDocCount` | `getIndexDocCount` | 420–420 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
