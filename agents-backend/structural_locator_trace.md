# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 4
- Test files: 0

## Code File Mappings

### `server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<class_declaration>` | `<class_declaration>` | 1231–1231 |
### `server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java`

**Hunks in this file**: 4

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 17–17 |
| 2 | declaration | `<import>` | `<import>` | 24–24 |
| 3 | propagation | `hunk_3` | `None` | 33–33 |
| 4 | core_fix | `hunk_4` | `None` | 52–52 |
### `server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `hunk_1` | `None` | 144–144 |
### `server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | 19–19 |
| 2 | guard | `innerQuery` | `innerQuery` | 63–63 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
