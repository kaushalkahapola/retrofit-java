# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 7
- Test files: 0

## Code File Mappings

### `server/src/main/java/io/crate/protocols/postgres/PgClient.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/protocols/postgres/PgClient.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | 600–600 |
### `server/src/main/java/org/elasticsearch/Version.java`

**Hunks in this file**: 5

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/Version.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 220–220 |
| 2 | propagation | `hunk_2` | `None` | 424–424 |
| 3 | propagation | `hunk_3` | `None` | 494–494 |
| 4 | guard | `minimumCompatibilityVersion` | `minimumCompatibilityVersion` | 503–503 |
| 5 | guard | `isCompatible` | `isCompatible` | 524–524 |
### `server/src/main/java/org/elasticsearch/transport/InboundDecoder.java`

**Hunks in this file**: 4

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/transport/InboundDecoder.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 22–22 |
| 2 | core_fix | `hunk_2` | `None` | 76–76 |
| 3 | guard | `hunk_3` | `None` | 171–171 |
| 4 | core_fix | `ensureVersionCompatibility` | `ensureVersionCompatibility` | 202–202 |
### `server/src/main/java/org/elasticsearch/transport/OutboundHandler.java`

**Hunks in this file**: 3

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/transport/OutboundHandler.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 92–92 |
| 2 | core_fix | `hunk_2` | `None` | 113–113 |
| 3 | core_fix | `hunk_3` | `None` | 135–135 |
### `server/src/main/java/org/elasticsearch/transport/TcpTransport.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/transport/TcpTransport.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | propagation | `hunk_1` | `None` | 148–148 |
| 2 | core_fix | `hunk_2` | `None` | 249–249 |
### `server/src/main/java/org/elasticsearch/transport/TcpTransportChannel.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/transport/TcpTransportChannel.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 62–62 |
| 2 | core_fix | `hunk_2` | `None` | 71–71 |
### `server/src/main/java/org/elasticsearch/transport/TransportHandshaker.java`

**Hunks in this file**: 8

**Git Resolution**: Found `server/src/main/java/org/elasticsearch/transport/TransportHandshaker.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 35–35 |
| 2 | core_fix | `hunk_2` | `None` | 69–69 |
| 3 | guard | `hunk_3` | `None` | 92–92 |
| 4 | guard | `handleResponse` | `handleResponse` | 136–136 |
| 5 | declaration | `<class_declaration>` | `<class_declaration>` | 51–51 |
| 6 | core_fix | `hunk_6` | `None` | 183–183 |
| 7 | guard | `hunk_7` | `None` | 194–194 |
| 8 | declaration | `<class_declaration>` | `<class_declaration>` | 211–211 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
