# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (0): []
- newly passing (11): ['io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testCallWithInvalidPrecisionResultsInAnError', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testMurmur3HashCalculationsForAllTypes', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testReturnTypeIsAlwaysLong', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testStreaming', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testWithPrecision', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testWithoutPrecision', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_function_implements_doc_values_aggregator_for_string_based_types', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_random_type_random_values', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_terminate_partial_without_initialization_returns_0', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_without_precision_long', 'io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_without_precision_string']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest']
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testCallWithInvalidPrecisionResultsInAnError: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testMurmur3HashCalculationsForAllTypes: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testReturnTypeIsAlwaysLong: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testStreaming: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testWithPrecision: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#testWithoutPrecision: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_function_implements_doc_values_aggregator_for_string_based_types: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_random_type_random_values: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_terminate_partial_without_initialization_returns_0: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_without_precision_long: baseline=absent, patched=passed
  - io.crate.operation.aggregation.HyperLogLogDistinctAggregationTest#test_without_precision_string: baseline=absent, patched=passed
