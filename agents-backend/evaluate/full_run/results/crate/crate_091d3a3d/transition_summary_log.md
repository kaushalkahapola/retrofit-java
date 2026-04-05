# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (0): []
- newly passing (17): ['io.crate.execution.ddl.tables.GCDanglingArtifactsRequestTest#test_bwc_streaming', 'io.crate.integrationtests.ResizeShardsITest#testNumberOfShardsOfAPartitionCanBeIncreased', 'io.crate.integrationtests.ResizeShardsITest#testShrinkShardsOfPartition', 'io.crate.integrationtests.ResizeShardsITest#testShrinkShardsOfTable', 'io.crate.integrationtests.ResizeShardsITest#test_number_of_shards_of_a_table_can_be_increased_without_explicitly_setting_number_of_routing_shards', 'io.crate.integrationtests.ResizeShardsITest#test_number_of_shards_on_a_one_sharded_table_can_be_increased_without_explicitly_setting_number_of_routing_shards', 'io.crate.integrationtests.ResizeShardsITest#test_number_of_shards_on_tables_can_be_increased', 'io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableOpenClose', 'io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableOpenCloseWithExplicitSchema', 'io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableRenameTable', 'io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableRenameTableWithExplicitSchema', 'io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableWithInvalidProperty', 'io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableWithPath', 'io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableWithReplicas', 'io.crate.planner.node.ddl.AlterTablePlanTest#test_alter_allowed_settings_on_a_replicated_table', 'io.crate.planner.node.ddl.AlterTablePlanTest#test_alter_forbidden_settings_on_a_replicated_table', 'io.crate.planner.node.ddl.AlterTablePlanTest#test_alter_setting_block_read_only']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.execution.ddl.tables.GCDanglingArtifactsRequestTest', 'io.crate.integrationtests.ResizeShardsITest', 'io.crate.planner.node.ddl.AlterTablePlanTest']
  - io.crate.execution.ddl.tables.GCDanglingArtifactsRequestTest#test_bwc_streaming: baseline=absent, patched=passed
  - io.crate.integrationtests.ResizeShardsITest#testNumberOfShardsOfAPartitionCanBeIncreased: baseline=absent, patched=passed
  - io.crate.integrationtests.ResizeShardsITest#testShrinkShardsOfPartition: baseline=absent, patched=passed
  - io.crate.integrationtests.ResizeShardsITest#testShrinkShardsOfTable: baseline=absent, patched=passed
  - io.crate.integrationtests.ResizeShardsITest#test_number_of_shards_of_a_table_can_be_increased_without_explicitly_setting_number_of_routing_shards: baseline=absent, patched=passed
  - io.crate.integrationtests.ResizeShardsITest#test_number_of_shards_on_a_one_sharded_table_can_be_increased_without_explicitly_setting_number_of_routing_shards: baseline=absent, patched=passed
  - io.crate.integrationtests.ResizeShardsITest#test_number_of_shards_on_tables_can_be_increased: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableOpenClose: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableOpenCloseWithExplicitSchema: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableRenameTable: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableRenameTableWithExplicitSchema: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableWithInvalidProperty: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableWithPath: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#testAlterBlobTableWithReplicas: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#test_alter_allowed_settings_on_a_replicated_table: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#test_alter_forbidden_settings_on_a_replicated_table: baseline=absent, patched=passed
  - io.crate.planner.node.ddl.AlterTablePlanTest#test_alter_setting_block_read_only: baseline=absent, patched=passed
