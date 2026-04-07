# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecks.java:15
error: x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/d
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.xpack.deprecation.NodeDeprecationChecksTests', 'org.elasticsearch.xpack.logsdb.LogsIndexModeCustomSettingsIT']
  - org.elasticsearch.xpack.deprecation.NodeDeprecationChecksTests: baseline=absent, patched=unknown
  - org.elasticsearch.xpack.logsdb.LogsIndexModeCustomSettingsIT: baseline=absent, patched=unknown
