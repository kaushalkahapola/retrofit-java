# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/execution/ddl/tables/AlterTableOperation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 64–64 |
| 2 | guard | `addColumn` | `addColumn` | 395–395 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
