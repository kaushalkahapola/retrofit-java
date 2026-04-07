# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java:224
error: server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java: patch does not apply

- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.execution.ddl.tables.GCDanglingArtifactsRequestTest', 'io.crate.integrationtests.ResizeShardsITest', 'io.crate.planner.node.ddl.AlterTablePlanTest']
  - io.crate.execution.ddl.tables.GCDanglingArtifactsRequestTest: baseline=absent, patched=unknown
  - io.crate.integrationtests.ResizeShardsITest: baseline=absent, patched=unknown
  - io.crate.planner.node.ddl.AlterTablePlanTest: baseline=absent, patched=unknown
