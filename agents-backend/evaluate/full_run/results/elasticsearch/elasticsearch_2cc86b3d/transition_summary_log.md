# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: x-pack/plugin/migrate/src/internalClusterTest/java/org/elasticsearch/xpack/migrate/action/ReindexDatastreamIndexTransportActionIT.java:7
error: x-pack/plugin/migrate/src/internalC
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.upgrades.DataStreamsUpgradeIT', 'org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT']
  - org.elasticsearch.upgrades.DataStreamsUpgradeIT: baseline=absent, patched=unknown
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT: baseline=absent, patched=unknown
