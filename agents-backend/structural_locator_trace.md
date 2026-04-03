# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Pair Consistency
- Pair mismatch: True
- Overlap ratio (mainline): 0.0
- Overlap Java files: []

## Locator Retry State
- Attempt: 1
- Previously failed paths: []

## Hunk Segregation
- Code files: 2
- Test files: 0

## Code File Mappings

### `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/parser/EsqlBaseLexer.java`

**Hunks in this file**: 9

**Deterministic Mode**: matched `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/parser/EsqlBaseLexer.java` with high confidence.

**Deterministic Mode**: 1 hunk(s) remained low confidence; using deterministic partial mapping without LLM escalation.

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | None–None |
| 2 | propagation | `hunk_2` | `None` | 97–97 |
| 3 | propagation | `hunk_3` | `None` | 133–133 |
| 4 | propagation | `hunk_4` | `None` | 142–142 |
| 5 | propagation | `hunk_5` | `None` | 167–167 |
| 6 | core_fix | `hunk_6` | `None` | 259–259 |
| 7 | core_fix | `NESTED_SORT_sempred` | `NESTED_SORT_sempred` | 264–264 |
| 8 | propagation | `hunk_8` | `None` | 379–379 |
| 9 | core_fix | `hunk_9` | `None` | 443–443 |
### `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/parser/EsqlBaseParser.java`

**Hunks in this file**: 16

**Deterministic Mode**: matched `x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/parser/EsqlBaseParser.java` with high confidence.

**Deterministic Mode**: 9 hunk(s) remained low confidence; using deterministic partial mapping without LLM escalation.

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | None–None |
| 2 | propagation | `hunk_2` | `None` | 109–109 |
| 3 | propagation | `hunk_3` | `None` | 134–134 |
| 4 | guard | `hunk_4` | `None` | 1569–1569 |
| 5 | propagation | `hunk_5` | `None` | 1876–1876 |
| 6 | propagation | `hunk_6` | `None` | 1882–1882 |
| 7 | guard | `hunk_7` | `None` | 968–968 |
| 8 | propagation | `hunk_8` | `None` | 6303–6303 |
| 9 | propagation | `hunk_9` | `None` | None–None |
| 10 | propagation | `hunk_10` | `None` | None–None |
| 11 | propagation | `hunk_11` | `None` | None–None |
| 12 | propagation | `hunk_12` | `None` | None–None |
| 13 | propagation | `hunk_13` | `None` | None–None |
| 14 | propagation | `hunk_14` | `None` | None–None |
| 15 | propagation | `hunk_15` | `None` | None–None |
| 16 | propagation | `hunk_16` | `None` | None–None |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
