# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: server/src/main/java/io/crate/execution/dml/upsert/ShardUpsertRequest.java:334
error: server/src/main/java/io/crate/execution/dml/upsert/ShardUpsertRequest.java: patch does not ap
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.execution.dml.upsert.ShardUpsertRequestTest', 'io.crate.execution.dml.upsert.TransportShardUpsertActionTest', 'io.crate.execution.dsl.projection.ColumnIndexWriterProjectionTest', 'io.crate.execution.dsl.projection.UpdateProjectionTest', 'io.crate.planner.InsertPlannerTest', 'io.crate.planner.UpdatePlannerTest', 'io.crate.statistics.TableStatsTest']
  - io.crate.execution.dml.upsert.ShardUpsertRequestTest: baseline=absent, patched=unknown
  - io.crate.execution.dml.upsert.TransportShardUpsertActionTest: baseline=absent, patched=unknown
  - io.crate.execution.dsl.projection.ColumnIndexWriterProjectionTest: baseline=absent, patched=unknown
  - io.crate.execution.dsl.projection.UpdateProjectionTest: baseline=absent, patched=unknown
  - io.crate.planner.InsertPlannerTest: baseline=absent, patched=unknown
  - io.crate.planner.UpdatePlannerTest: baseline=absent, patched=unknown
  - io.crate.statistics.TableStatsTest: baseline=absent, patched=unknown
