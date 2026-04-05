# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.

## Hunk Segregation
- Code files: 14
- Test files: 0

## Code File Mappings

### `extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java`

**Hunks in this file**: 7

**Git Resolution**: Found `extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `hunk_1` | `None` | 189–189 |
| 2 | core_fix | `hunk_2` | `None` | 200–200 |
| 3 | core_fix | `hunk_3` | `None` | 200–200 |
| 4 | core_fix | `hunk_4` | `None` | 200–200 |
| 5 | guard | `hunk_5` | `None` | 246–246 |
| 6 | guard | `hunk_6` | `None` | 246–246 |
| 7 | core_fix | `partialResult` | `partialResult` | 123–123 |
### `server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 34–34 |
| 2 | guard | `getAggReference` | `getAggReference` | 137–137 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `hunk_1` | `None` | 164–164 |
| 2 | guard | `hunk_2` | `None` | 180–180 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 48–48 |
| 2 | guard | `hunk_2` | `None` | 168–168 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java`

**Hunks in this file**: 4

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 48–48 |
| 2 | guard | `getDocValueAggregator` | `getDocValueAggregator` | 260–260 |
| 3 | guard | `hunk_3` | `None` | 307–307 |
| 4 | core_fix | `hunk_4` | `None` | 329–329 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 311–311 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `hunk_1` | `None` | 225–225 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | guard | `hunk_1` | `None` | 259–259 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 186–186 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 234–234 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 199–199 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 225–225 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 233–233 |
### `server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java`

**Deterministic Mode**: raw-diff anchor mapping succeeded (no LLM call).

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `hunk_1` | `None` | 315–315 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
