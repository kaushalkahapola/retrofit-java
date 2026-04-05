# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 3
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/protocols/postgres/Portal.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/protocols/postgres/Portal.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 30–30 |
| 2 | propagation | `hunk_2` | `None` | 91–91 |
### `server/src/main/java/io/crate/session/RowConsumerToResultReceiver.java`

**Hunks in this file**: 5

**Git Resolution**: Found `server/src/main/java/io/crate/session/RowConsumerToResultReceiver.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 48–48 |
| 2 | guard | `hunk_2` | `None` | 84–84 |
| 3 | core_fix | `hunk_3` | `None` | 112–112 |
| 4 | guard | `closeAndFinishIfSuspended` | `closeAndFinishIfSuspended` | 138–138 |
| 5 | propagation | `hunk_5` | `None` | 174–174 |
### `server/src/main/java/io/crate/session/Session.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/session/Session.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 585–585 |
| 2 | core_fix | `triggerDeferredExecutions` | `triggerDeferredExecutions` | 663–663 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
