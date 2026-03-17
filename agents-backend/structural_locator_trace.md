# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Documentation missing description of the 'lagAggregate' configuration option for supervisor scaling. | The computeLagForAutoScaler method is exposed as a public API but is not intended for external use, potentially leading to misuse or unintended access. | The code previously used a single lag value from supervisor.computeLagForAutoScaler(), which did not support flexible aggregation or robust handling of missing lag stats, potentially leading to incorrect scaling decisions or failures. | Lack of configurability for the lag aggregation function in LagBasedAutoScalerConfig, preventing users from specifying how lag should be aggregated for autoscaling decisions. | The computeLagForAutoScaler() default method may provide misleading or unsafe lag values if not properly overridden by implementing classes, potentially leading to incorrect autoscaling decisions. | Missing definition of the AggregateFunction enum, which is required for code that needs to reference aggregate operations (MAX, SUM, AVERAGE) in the autoscaler logic. | The LagStats class lacked support for specifying and retrieving the preferred aggregate function for scaling, making it inflexible and potentially error-prone when different scaling metrics are needed.

## Hunk Segregation
- Code files: 7
- Test files: 0

## Code File Mappings

### `docs/ingestion/supervisor.md`

**Hunks in this file**: 1

**Git Resolution**: Found `docs/ingestion/supervisor.md`

**Agent Tool Steps:**


| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `None` | `None` | 99–99 |
### `extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java`

**Hunks in this file**: 1

**Git Resolution**: Found `extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java`

**Agent Tool Steps:**

  - `Agent calls get_class_context` with `{"file_path": "extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java"}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.indexing.kinesis.supervisor;\n\n// Line 77\npublic class KinesisSupervisor extends SeekableStreamSupervisor {\n    // Line 79: private static final org.apache.dru...
  - `Agent calls get_class_context` with `{"file_path": "extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java", "focus_method": "computeLagForAutoScaler"}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.indexing.kinesis.supervisor;\n\n// Line 77\npublic class KinesisSupervisor extends SeekableStreamSupervisor {\n    // Line 79: private static final org.apache.dru...

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `computeLagForAutoScaler` | `computeLagForAutoScaler` | 431–435 |
### `indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java`

**Hunks in this file**: 2

**Git Resolution**: Found `indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java`

**Agent Tool Steps:**

  - `Agent calls get_class_context` with `{"file_path": "indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java"}`
  - `Agent calls read_file` with `{"file_path": "indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java"}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.indexing.seekablestream.supervisor.autoscaler;\n\n// Line 40\npublic class LagBasedAutoScaler implements SupervisorTaskAutoScaler {\n    // Line 42: private stati...
  - `Tool: read_file` -> package org.apache.druid.indexing.seekablestream.supervisor.autoscaler;
import org.apache.commons.collections4.queue.CircularFifoQueue;
import org.apache.druid.indexing.overlord.supervisor.SupervisorS...

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 4–4 |
| 2 | core_fix | `computeAndCollectLag` | `computeAndCollectLag` | 151–183 |
### `indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java`

**Hunks in this file**: 6

**Git Resolution**: Found `indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java`

**Agent Tool Steps:**


| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 24–27 |
| 2 | declaration | `LagBasedAutoScalerConfig` | `LagBasedAutoScalerConfig` | 47–56 |
| 3 | propagation | `LagBasedAutoScalerConfig` | `LagBasedAutoScalerConfig` | 63–75 |
| 4 | core_fix | `LagBasedAutoScalerConfig` | `LagBasedAutoScalerConfig` | 78–81 |
| 5 | propagation | `getLagAggregate` | `getLagAggregate` | 193–200 |
| 6 | cleanup | `toString` | `toString` | 218–229 |
### `server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java`

**Hunks in this file**: 1

**Git Resolution**: Found `server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java`

**Agent Tool Steps:**


| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `computeLagForAutoScaler` | `computeLagForAutoScaler` | 95–103 |
### `server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/AggregateFunction.java`

**Hunks in this file**: 1

**Agent Tool Steps:**


| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `AggregateFunction` | `AggregateFunction` | 19–27 |
### `server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java`

**Hunks in this file**: 2

**Git Resolution**: Found `server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java`

**Agent Tool Steps:**

  - `Agent calls get_class_context` with `{"file_path": "server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java"}`
  - `Agent calls read_file` with `{"file_path": "server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java"}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.indexing.overlord.supervisor.autoscaler;\n\n// Line 22\npublic class LagStats {\n    // Line 24: private final long maxLag;\n    // Line 25: private final long to...
  - `Tool: read_file` -> package org.apache.druid.indexing.overlord.supervisor.autoscaler;
public class LagStats
{
  private final long maxLag;
  private final long totalLag;
  private final long avgLag;
  public LagStats(lon...

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `LagStats (constructor)` | `LagStats` | 7–13 |
| 2 | core_fix | `getAggregateForScaling / getMetric` | `None` | None–None |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
