# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (0): []
- newly passing (1): ['org.elasticsearch.cluster.metadata.MetadataTest#test_bwc_read_writes_with_6_1_0']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.cluster.metadata.MetadataTest']
  - org.elasticsearch.cluster.metadata.MetadataTest#test_bwc_read_writes_with_6_1_0: baseline=absent, patched=passed
