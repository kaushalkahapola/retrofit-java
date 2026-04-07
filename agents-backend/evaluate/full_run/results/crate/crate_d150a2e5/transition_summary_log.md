# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (0): []
- newly passing (15): ['io.crate.integrationtests.AlterTableIntegrationTest#test_alter_partitioned_table_drop_column_can_add_again', 'io.crate.integrationtests.AlterTableIntegrationTest#test_alter_partitioned_table_drop_simple_column', 'io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_can_add_column_after_dropping_column_with_max_known_position', 'io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_column_can_add_again', 'io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_column_dropped_meanwhile', 'io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_leaf_subcolumn', 'io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_leaf_subcolumn_with_parent_object_array', 'io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_simple_column', 'io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_simple_column_view_updated', 'io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_subcolumn_with_children', 'io.crate.integrationtests.AlterTableIntegrationTest#test_can_add_sub_column_to_ignored_parent_if_table_is_empty', 'io.crate.integrationtests.AlterTableIntegrationTest#test_cannot_add_sub_column_to_ignored_parent_if_table_is_not_empty', 'io.crate.integrationtests.AlterTableIntegrationTest#test_create_soft_delete_setting_for_partitioned_tables', 'io.crate.integrationtests.AlterTableIntegrationTest#test_drop_sub_column_readd_and_update', 'io.crate.integrationtests.AlterTableIntegrationTest#test_rename_columns']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.integrationtests.AlterTableIntegrationTest']
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_partitioned_table_drop_column_can_add_again: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_partitioned_table_drop_simple_column: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_can_add_column_after_dropping_column_with_max_known_position: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_column_can_add_again: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_column_dropped_meanwhile: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_leaf_subcolumn: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_leaf_subcolumn_with_parent_object_array: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_simple_column: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_simple_column_view_updated: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_alter_table_drop_subcolumn_with_children: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_can_add_sub_column_to_ignored_parent_if_table_is_empty: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_cannot_add_sub_column_to_ignored_parent_if_table_is_not_empty: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_create_soft_delete_setting_for_partitioned_tables: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_drop_sub_column_readd_and_update: baseline=absent, patched=passed
  - io.crate.integrationtests.AlterTableIntegrationTest#test_rename_columns: baseline=absent, patched=passed
