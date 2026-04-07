# Transition Summary

- Source: phase0_cache
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (1): ['io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_all_operator_cast_on_left_reference_is_moved_to_cast_on_literal']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest']
  - io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_all_operator_cast_on_left_reference_is_moved_to_cast_on_literal: baseline=failed, patched=passed
  - io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_all_operator_cast_on_right_reference_is_moved_to_cast_on_literal: baseline=passed, patched=passed
  - io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_any_operator_cast_on_left_reference_is_moved_to_cast_on_literal: baseline=passed, patched=passed
  - io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_any_operator_cast_on_nested_array_reference_is_moved_to_cast_on_literal: baseline=passed, patched=passed
  - io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_any_operator_cast_on_right_reference_is_moved_to_cast_on_literal: baseline=passed, patched=passed
  - io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_any_operator_does_not_move_explicit_reference_cast_to_literal_cast: baseline=passed, patched=passed
  - io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_operator_cast_on_array_length_with_reference_is_moved_to_literal_cast: baseline=passed, patched=passed
  - io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_operator_cast_on_reference_is_moved_to_cast_on_literal: baseline=passed, patched=passed
  - io.crate.planner.optimizer.symbol.CollectQueryCastRulesTest#test_operator_subscript_on_reference_cast_is_moved_to_literal_cast: baseline=passed, patched=passed
