# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 2
- Test files: 0

## Code File Mappings

### `server/src/main/java/org/elasticsearch/action/admin/cluster/allocation/TransportGetAllocationStatsAction.java`

**Hunks in this file**: 5

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/action/admin/cluster/allocation/TransportGetAllocationStatsAction.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 13–13 |
| 2 | declaration | `<import>` | `<import>` | 28–28 |
| 3 | declaration | `<class_declaration>` | `<class_declaration>` | 50–50 |
  - JavaStructureLocator recovered target_method for hunk 4: featureService (java_structure_locator:field_declaration)
| 4 | guard | `hunk_4` | `featureService` | 73–73 |
  - JavaStructureLocator recovered target_method for hunk 5: masterOperation (java_structure_locator:method)
| 5 | core_fix | `hunk_5` | `masterOperation` | 92–92 |
### `server/src/main/java/org/elasticsearch/cluster/routing/allocation/AllocationStatsService.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/cluster/routing/allocation/AllocationStatsService.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 18–18 |
| 2 | guard | `stats` | `stats` | 95–95 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
