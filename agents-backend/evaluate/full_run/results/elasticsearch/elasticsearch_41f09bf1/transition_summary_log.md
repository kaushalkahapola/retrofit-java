# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: server/src/main/java/org/elasticsearch/action/admin/cluster/allocation/TransportGetAllocationStatsAction.java:69
error: server/src/main/java/org/elasticsearch/action/admin/cluster
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests']
  - org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests#testDeduplicatesStatsComputations: baseline=failed, patched=unknown
  - org.elasticsearch.action.admin.cluster.allocation.TransportGetAllocationStatsActionTests#testReturnsOnlyRequestedStats: baseline=passed, patched=unknown
