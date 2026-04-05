# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/metadata/doc/DocTableInfo.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/metadata/doc/DocTableInfo.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 22–22 |
| 2 | core_fix | `hunk_2` | `None` | 263–263 |
| 3 | guard | `lookupNameBySourceKey` | `lookupNameBySourceKey` | 120–120 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
