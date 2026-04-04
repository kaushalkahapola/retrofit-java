# Transition Summary

- Source: phase_outputs
- Valid backport signal: False
- Reason: Invalid: No fail-to-pass or newly passing relevant tests were observed.
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests']
  - org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests#testDeduplicatesStatsComputations: baseline=failed, patched=failed
  - org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests#testReturnsOnlyRequestedStats: baseline=passed, patched=passed
