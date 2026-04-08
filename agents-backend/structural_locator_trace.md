# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: The QueryProfiler class is not thread-safe, leading to potential data races and inconsistent profiling results when accessed concurrently.

## Hunk Segregation
- Code files: 1
- Test files: 0

## Code File Mappings

### `server/src/main/java/org/elasticsearch/search/profile/query/QueryProfiler.java`

**Hunks in this file**: 5

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/search/profile/query/QueryProfiler.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `getProfileBreakdown` | `getProfileBreakdown` | 18–18 |
| 2 | refactor | `createProfileBreakdown` | `createProfileBreakdown` | 41–41 |
| 3 | guard | `getTree` | `getTree` | 9–9 |
| 4 | refactor | `getTypeFromElement` | `getTypeFromElement` | 41–41 |
| 5 | refactor | `getDescriptionFromElement` | `getDescriptionFromElement` | 41–41 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
