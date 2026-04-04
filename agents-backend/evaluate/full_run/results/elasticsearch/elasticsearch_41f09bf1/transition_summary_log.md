# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (1): ['org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests#testDeduplicatesStatsComputations']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests']
  - org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests#testDeduplicatesStatsComputations: baseline=failed, patched=passed
  - org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests#testReturnsOnlyRequestedStats: baseline=passed, patched=passed
