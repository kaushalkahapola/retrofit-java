# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (2): ['org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testQueryHotShardsFirst', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testQueryHotShardsFirstWhenIlmMovesShard']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests']
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testAllowPartialResults: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testDoNotRetryCircuitBreakerException: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testDoNotRetryOnRequestLevelFailure: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testDoesNotRetryMovedShardIndefinitely: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testEmpty: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testLimitConcurrentNodes: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testMissingShards: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testNonFatalErrorIsRetriedOnAnotherShard: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testNonFatalFailedOnAllNodes: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testOnePass: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testQueryHotShardsFirst: baseline=failed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testQueryHotShardsFirstWhenIlmMovesShard: baseline=failed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryButFail: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryMovedShard: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryMultipleMovedShards: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryOnlyMovedShards: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryThenSuccess: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryUnassignedShardWithPartialResults: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryUnassignedShardWithoutPartialResults: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testSkipNodes: baseline=passed, patched=passed
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testSkipRemovesPriorNonFatalErrors: baseline=passed, patched=passed
