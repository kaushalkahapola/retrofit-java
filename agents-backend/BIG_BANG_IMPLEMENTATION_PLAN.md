# Big-Bang Implementation Plan

## Goals
- Add confidence-gated routing (`TRIVIAL`, `STRUCTURAL`, `REWRITE`) to avoid full-pipeline cost on easy patches.
- Collapse the planning+editing hot path for non-rewrite patches by allowing File Editor to run deterministic fallback plans directly.
- Distinguish infrastructure/test-runner failures from code failures, auto-fix test-runner config once, and avoid regeneration retries for infra failures.
- Enforce bounded tool usage in edit loops and clamp oversized file-window reads.

## Scope of Change
- `src/utils/patch_complexity.py`: deterministic complexity classifier.
- `src/state.py`: state fields for patch complexity and infra inconclusive metadata.
- `src/agents/phase0_optimistic.py`: compute and persist complexity classification.
- `src/graph.py`: complexity-based path routing and infra-aware validation routing.
- `src/agents/file_editor.py`: deterministic fallback planning path + tool-budget enforcement.
- `src/agents/hunk_generator_tools.py`: `read_file_window` radius clamp.
- `src/agents/validation_tools.py`: test-runner/infra failure classification helper.
- `src/agents/validation_agent.py`: classify test failures, mark infra failures, stop wrong retries.
- `evaluate/helpers/elasticsearch/run_tests.sh`: task-resolution hardening + one auto-fix rerun for ambiguous/missing Gradle tasks.
- tests: add routing/classifier tests and extend validation-tool tests.

## Implementation Steps
1. Create classifier utility and state fields.
2. Integrate classifier in Phase 0 and graph routing.
3. Allow File Editor to build deterministic fallback entries when planner is skipped.
4. Add validation/test infra classification and adjust retry routing behavior.
5. Fix Elasticsearch helper script to resolve QA tasks and rerun once on task errors.
6. Add tool budgets and radius clamping.
7. Add/adjust tests.
8. Run focused test suite and report outcomes.

## Acceptance Criteria
- Fast-path/near-fast-path patches avoid unnecessary planning node.
- Infra/test-runner failures do not trigger generation retries.
- Elasticsearch helper retries once with remapped tasks on ambiguous/missing-task failures.
- ReAct edit loops are bounded by complexity budget.
- `read_file_window` cannot request oversized windows.
