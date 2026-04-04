# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (1): ['org.elasticsearch.ingest.PipelineConfigurationTests#testMapKeyOrderingRoundTrip']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.ingest.PipelineConfigurationTests']
  - org.elasticsearch.ingest.PipelineConfigurationTests#testConfigInvariants: baseline=passed, patched=passed
  - org.elasticsearch.ingest.PipelineConfigurationTests#testFromXContent: baseline=passed, patched=passed
  - org.elasticsearch.ingest.PipelineConfigurationTests#testGetVersion: baseline=passed, patched=passed
  - org.elasticsearch.ingest.PipelineConfigurationTests#testMapKeyOrderingRoundTrip: baseline=failed, patched=passed
  - org.elasticsearch.ingest.PipelineConfigurationTests#testMetaSerialization: baseline=passed, patched=passed
  - org.elasticsearch.ingest.PipelineConfigurationTests#testParser: baseline=passed, patched=passed
  - org.elasticsearch.ingest.PipelineConfigurationTests#testSerialization: baseline=passed, patched=passed
