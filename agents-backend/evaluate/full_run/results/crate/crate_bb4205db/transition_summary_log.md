# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (1): ['io.crate.execution.engine.collect.DocValuesAggregatesTest#test_create_aggregators_for_partitioned_col_returns_null']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.execution.engine.collect.DocValuesAggregatesTest']
  - io.crate.execution.engine.collect.DocValuesAggregatesTest#test_create_aggregators_for_cast_reference_returns_aggregator_only_if_it_is_cast_to_numeric: baseline=passed, patched=passed
  - io.crate.execution.engine.collect.DocValuesAggregatesTest#test_create_aggregators_for_literal_aggregation_input_returns_null: baseline=passed, patched=passed
  - io.crate.execution.engine.collect.DocValuesAggregatesTest#test_create_aggregators_for_multiple_aggregations: baseline=passed, patched=passed
  - io.crate.execution.engine.collect.DocValuesAggregatesTest#test_create_aggregators_for_partitioned_col_returns_null: baseline=failed, patched=passed
  - io.crate.execution.engine.collect.DocValuesAggregatesTest#test_create_aggregators_for_reference_and_doc_value_field_for_the_correct_field_type: baseline=passed, patched=passed
  - io.crate.execution.engine.collect.DocValuesAggregatesTest#test_create_aggregators_for_reference_and_without_doc_value_field_returns_null: baseline=passed, patched=passed
  - io.crate.execution.engine.collect.DocValuesAggregatesTest#test_create_aggregators_for_reference_not_mapped_to_field_returns_null: baseline=passed, patched=passed
