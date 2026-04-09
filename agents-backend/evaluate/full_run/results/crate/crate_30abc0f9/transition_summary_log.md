run_id=20260409T101748701708

# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java:21
error: server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.ja
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.execution.engine.distribution.DistributingConsumerTest', 'io.crate.integrationtests.GroupByAggregateTest']
  - io.crate.execution.engine.distribution.DistributingConsumerTest: baseline=absent, patched=unknown
  - io.crate.integrationtests.GroupByAggregateTest: baseline=absent, patched=unknown
