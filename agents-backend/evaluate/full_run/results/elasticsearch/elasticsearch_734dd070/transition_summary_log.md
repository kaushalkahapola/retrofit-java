# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plugin/DataNodeRequestSender.java:17
error: x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plugin/Data
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

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
