# Transition Summary

- Source: phase0_cache
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (1): ['org.elasticsearch.ingest.IngestStatsTests#testProcessorNameAndTypeIdentitySerialization']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.ingest.IngestServiceTests', 'org.elasticsearch.ingest.IngestStatsTests']
  - org.elasticsearch.ingest.IngestServiceTests: baseline=absent, patched=absent
  - org.elasticsearch.ingest.IngestStatsTests#testIdentitySerialization: baseline=passed, patched=passed
  - org.elasticsearch.ingest.IngestStatsTests#testPipelineStatsMerge: baseline=passed, patched=passed
  - org.elasticsearch.ingest.IngestStatsTests#testProcessorNameAndTypeIdentitySerialization: baseline=failed, patched=passed
  - org.elasticsearch.ingest.IngestStatsTests#testProcessorStatsMerge: baseline=passed, patched=passed
  - org.elasticsearch.ingest.IngestStatsTests#testProcessorStatsMergeHeterogeneous: baseline=passed, patched=passed
  - org.elasticsearch.ingest.IngestStatsTests#testProcessorStatsMergeZeroCounts: baseline=passed, patched=passed
  - org.elasticsearch.ingest.IngestStatsTests#testSerialization: baseline=passed, patched=passed
  - org.elasticsearch.ingest.IngestStatsTests#testStatsMerge: baseline=passed, patched=passed
