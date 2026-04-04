# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (1): ['io.crate.planner.PlannerTest#test_table_with_clustered_by_and_partition_filter_routing']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.planner.PlannerTest']
  - io.crate.planner.PlannerTest#testDeallocate: baseline=passed, patched=passed
  - io.crate.planner.PlannerTest#testExecutionPhaseIdSequence: baseline=passed, patched=passed
  - io.crate.planner.PlannerTest#testSetPlan: baseline=passed, patched=passed
  - io.crate.planner.PlannerTest#testSetSessionTransactionModeIsNoopPlan: baseline=passed, patched=passed
  - io.crate.planner.PlannerTest#testSetTimeZone: baseline=passed, patched=passed
  - io.crate.planner.PlannerTest#test_execution_exception_is_not_wrapped_in_logical_planner: baseline=passed, patched=passed
  - io.crate.planner.PlannerTest#test_invalid_any_param_leads_to_clear_error_message: baseline=passed, patched=passed
  - io.crate.planner.PlannerTest#test_table_with_clustered_by_and_partition_filter_routing: baseline=failed, patched=passed
