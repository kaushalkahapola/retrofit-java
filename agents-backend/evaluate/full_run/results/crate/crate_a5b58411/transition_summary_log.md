# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (4): ['io.crate.integrationtests.ExplainAnalyzeIntegrationTest#testExplainAnalyzeReportsExecutionTimesOnBothNodesInclQueryBreakdown', 'io.crate.integrationtests.ExplainAnalyzeIntegrationTest#testExplainSelectWithoutJobExecutionContexts', 'io.crate.integrationtests.ExplainAnalyzeIntegrationTest#test_explain_analyze_on_statement_with_subquery', 'io.crate.integrationtests.ExplainAnalyzeIntegrationTest#test_explain_analyze_with_all_values_sub_query_does_not_leak_memory']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.integrationtests.ExplainAnalyzeIntegrationTest']
  - io.crate.integrationtests.ExplainAnalyzeIntegrationTest#testExplainAnalyzeReportsExecutionTimesOnBothNodesInclQueryBreakdown: baseline=failed, patched=passed
  - io.crate.integrationtests.ExplainAnalyzeIntegrationTest#testExplainSelectWithoutJobExecutionContexts: baseline=failed, patched=passed
  - io.crate.integrationtests.ExplainAnalyzeIntegrationTest#test_explain_analyze_on_statement_with_subquery: baseline=failed, patched=passed
  - io.crate.integrationtests.ExplainAnalyzeIntegrationTest#test_explain_analyze_query_execution_contains_shard_and_partition_information: baseline=passed, patched=passed
  - io.crate.integrationtests.ExplainAnalyzeIntegrationTest#test_explain_analyze_query_execution_contains_shard_information: baseline=passed, patched=passed
  - io.crate.integrationtests.ExplainAnalyzeIntegrationTest#test_explain_analyze_with_all_values_sub_query_does_not_leak_memory: baseline=failed, patched=passed
  - io.crate.integrationtests.ExplainAnalyzeIntegrationTest#test_explain_analyze_with_nested_subquery: baseline=passed, patched=passed
