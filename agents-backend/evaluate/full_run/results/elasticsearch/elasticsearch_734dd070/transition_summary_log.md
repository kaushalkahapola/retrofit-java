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
  - org.elasticsearch.xpack.esql.plugin.DataNodeRequestSenderTests: baseline=absent, patched=absent
