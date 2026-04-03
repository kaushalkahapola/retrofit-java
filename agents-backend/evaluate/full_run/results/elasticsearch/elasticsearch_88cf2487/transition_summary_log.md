# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: server/src/main/java/org/elasticsearch/script/ScriptStats.java:28
error: server/src/main/java/org/elasticsearch/script/ScriptStats.java: patch does not apply

- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.script.ScriptStatsTests']
  - org.elasticsearch.script.ScriptStatsTests#testMerge: baseline=passed, patched=unknown
  - org.elasticsearch.script.ScriptStatsTests#testSerializeEmptyTimeSeries: baseline=passed, patched=unknown
  - org.elasticsearch.script.ScriptStatsTests#testSerializeTimeSeries: baseline=passed, patched=unknown
  - org.elasticsearch.script.ScriptStatsTests#testTimeSeriesIsEmpty: baseline=passed, patched=unknown
  - org.elasticsearch.script.ScriptStatsTests#testTimeSeriesSerialization: baseline=passed, patched=unknown
  - org.elasticsearch.script.ScriptStatsTests#testXContentChunked: baseline=passed, patched=unknown
  - org.elasticsearch.script.ScriptStatsTests#testXContentChunkedHistory: baseline=failed, patched=unknown
