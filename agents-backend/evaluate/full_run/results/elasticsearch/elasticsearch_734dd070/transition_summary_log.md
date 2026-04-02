# Transition Summary

- Source: phase_outputs
- Valid backport signal: False
- Reason: Invalid: Some tests regressed from pass to fail.
- fail->pass (0): []
- newly passing (0): []
- pass->fail (14): ['org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testAllowPartialResults', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testDoNotRetryCircuitBreakerException', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testLimitConcurrentNodes', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testNonFatalErrorIsRetriedOnAnotherShard', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testOnePass', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryButFail', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryMovedShard', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryMultipleMovedShards', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryOnlyMovedShards', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryThenSuccess', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryUnassignedShardWithPartialResults', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryUnassignedShardWithoutPartialResults', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testSkipNodes', 'org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testSkipRemovesPriorNonFatalErrors']

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests']
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testAllowPartialResults: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testDoNotRetryCircuitBreakerException: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testDoNotRetryOnRequestLevelFailure: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testDoesNotRetryMovedShardIndefinitely: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testEmpty: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testLimitConcurrentNodes: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testMissingShards: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testNonFatalErrorIsRetriedOnAnotherShard: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testNonFatalFailedOnAllNodes: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testOnePass: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testQueryHotShardsFirst: baseline=failed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testQueryHotShardsFirstWhenIlmMovesShard: baseline=failed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryButFail: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryMovedShard: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryMultipleMovedShards: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryOnlyMovedShards: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryThenSuccess: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryUnassignedShardWithPartialResults: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testRetryUnassignedShardWithoutPartialResults: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testSkipNodes: baseline=passed, patched=absent
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests#testSkipRemovesPriorNonFatalErrors: baseline=passed, patched=absent
