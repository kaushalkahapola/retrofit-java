# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java:95
error: x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.xpack.deprecation.IndexDeprecationCheckerTests']
  - org.elasticsearch.xpack.deprecation.IndexDeprecationCheckerTests: baseline=absent, patched=unknown
