# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/planner/operators/Collect.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/io/crate/planner/operators/Collect.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `withOutputs` | `withOutputs` | 123–123 |
| 2 | guard | `hunk_2` | `None` | 348–348 |
| 3 | guard | `hunk_3` | `None` | 385–385 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
