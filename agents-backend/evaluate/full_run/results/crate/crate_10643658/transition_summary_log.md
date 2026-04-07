# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: docs/appendices/release-notes/5.8.4.rst:81
error: docs/appendices/release-notes/5.8.4.rst: patch does not apply
error: patch failed: server/src/main/java/org/elasticsearch/search/
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.search.profile.query.QueryProfilerTest']
  - org.elasticsearch.search.profile.query.QueryProfilerTest#test_ensure_thread_safety: baseline=failed, patched=unknown
