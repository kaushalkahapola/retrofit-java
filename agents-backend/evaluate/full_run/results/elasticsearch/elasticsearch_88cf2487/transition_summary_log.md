# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (1): ['org.elasticsearch.script.ScriptStatsTests#testXContentChunkedHistory']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.script.ScriptStatsTests']
  - org.elasticsearch.script.ScriptStatsTests#testMerge: baseline=passed, patched=passed
  - org.elasticsearch.script.ScriptStatsTests#testSerializeEmptyTimeSeries: baseline=passed, patched=passed
  - org.elasticsearch.script.ScriptStatsTests#testSerializeTimeSeries: baseline=passed, patched=passed
  - org.elasticsearch.script.ScriptStatsTests#testTimeSeriesIsEmpty: baseline=passed, patched=passed
  - org.elasticsearch.script.ScriptStatsTests#testTimeSeriesSerialization: baseline=passed, patched=passed
  - org.elasticsearch.script.ScriptStatsTests#testXContentChunked: baseline=passed, patched=passed
  - org.elasticsearch.script.ScriptStatsTests#testXContentChunkedHistory: baseline=failed, patched=passed
