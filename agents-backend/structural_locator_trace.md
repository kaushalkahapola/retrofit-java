# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/expression/reference/sys/snapshot/SysSnapshots.java`

**Hunks in this file**: 6

**Git Resolution**: Found `server/src/main/java/io/crate/expression/reference/sys/snapshot/SysSnapshots.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 31–31 |
| 2 | declaration | `<import>` | `<import>` | 40–40 |
| 3 | declaration | `<class_declaration>` | `<class_declaration>` | 58–58 |
  - JavaStructureLocator recovered target_method for hunk 4: currentSnapshots (java_structure_locator:method)
| 4 | core_fix | `hunk_4` | `currentSnapshots` | 77–77 |
| 5 | declaration | `<class_declaration>` | `<class_declaration>` | 105–105 |
  - JavaStructureLocator recovered target_method for hunk 6: createSysSnapshot (java_structure_locator:method)
| 6 | guard | `hunk_6` | `createSysSnapshot` | 135–135 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
