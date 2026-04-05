# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (0): []
- newly passing (17): ['io.crate.metadata.doc.DocTableInfoTest#testGetColumnInfo', 'io.crate.metadata.doc.DocTableInfoTest#testGetColumnInfoStrictParent', 'io.crate.metadata.doc.DocTableInfoTest#test_add_column_fixes_inner_types_of_all_its_parents', 'io.crate.metadata.doc.DocTableInfoTest#test_can_add_column_to_table', 'io.crate.metadata.doc.DocTableInfoTest#test_can_retrieve_all_parents_of_nested_object_column', 'io.crate.metadata.doc.DocTableInfoTest#test_cannot_add_child_column_without_defining_parents', 'io.crate.metadata.doc.DocTableInfoTest#test_drop_column_after_drop_column_preserves_previous_dropped_columns', 'io.crate.metadata.doc.DocTableInfoTest#test_drop_column_fixes_inner_types_of_all_its_parents', 'io.crate.metadata.doc.DocTableInfoTest#test_drop_column_updates_type_of_parent_ref', 'io.crate.metadata.doc.DocTableInfoTest#test_get_child_references', 'io.crate.metadata.doc.DocTableInfoTest#test_lookup_name_by_source_returns_null_for_deleted_columns', 'io.crate.metadata.doc.DocTableInfoTest#test_lookup_name_by_source_with_columns_with_and_without_oids_added_to_table_created_before_5_5_0', 'io.crate.metadata.doc.DocTableInfoTest#test_rename_column_fixes_inner_types_of_all_its_parents', 'io.crate.metadata.doc.DocTableInfoTest#test_version_created_is_read_from_partitioned_template', 'io.crate.metadata.doc.DocTableInfoTest#test_version_created_is_set_to_current_version_if_unavailable_at_partitioned_template', 'io.crate.metadata.doc.DocTableInfoTest#test_write_to_preserves_indices', 'io.crate.metadata.doc.DocTableInfoTest#test_write_to_preserves_number_of_shards_of_partitions']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.metadata.doc.DocTableInfoTest']
  - io.crate.metadata.doc.DocTableInfoTest#testGetColumnInfo: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#testGetColumnInfoStrictParent: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_add_column_fixes_inner_types_of_all_its_parents: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_can_add_column_to_table: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_can_retrieve_all_parents_of_nested_object_column: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_cannot_add_child_column_without_defining_parents: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_drop_column_after_drop_column_preserves_previous_dropped_columns: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_drop_column_fixes_inner_types_of_all_its_parents: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_drop_column_updates_type_of_parent_ref: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_get_child_references: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_lookup_name_by_source_returns_null_for_deleted_columns: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_lookup_name_by_source_with_columns_with_and_without_oids_added_to_table_created_before_5_5_0: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_rename_column_fixes_inner_types_of_all_its_parents: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_version_created_is_read_from_partitioned_template: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_version_created_is_set_to_current_version_if_unavailable_at_partitioned_template: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_write_to_preserves_indices: baseline=absent, patched=passed
  - io.crate.metadata.doc.DocTableInfoTest#test_write_to_preserves_number_of_shards_of_partitions: baseline=absent, patched=passed
