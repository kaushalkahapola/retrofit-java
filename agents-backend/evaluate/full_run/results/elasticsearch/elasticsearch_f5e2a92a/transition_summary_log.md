# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java:17
error: server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java: patch does not a
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.search.query.RescoreKnnVectorQueryIT', 'org.elasticsearch.search.vectors.RescoreKnnVectorQueryTests']
  - org.elasticsearch.search.query.RescoreKnnVectorQueryIT: baseline=absent, patched=unknown
  - org.elasticsearch.search.vectors.RescoreKnnVectorQueryTests#testProfiling: baseline=passed, patched=unknown
  - org.elasticsearch.search.vectors.RescoreKnnVectorQueryTests#testRescoreDocs: baseline=passed, patched=unknown
