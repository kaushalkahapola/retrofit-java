# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (0): []
- newly passing (3): ['org.elasticsearch.search.query.RescoreKnnVectorQueryIT#testKnnQueryRescore', 'org.elasticsearch.search.query.RescoreKnnVectorQueryIT#testKnnRetriever', 'org.elasticsearch.search.query.RescoreKnnVectorQueryIT#testKnnSearchRescore']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.search.query.RescoreKnnVectorQueryIT', 'org.elasticsearch.search.vectors.RescoreKnnVectorQueryTests']
  - org.elasticsearch.search.query.RescoreKnnVectorQueryIT#testKnnQueryRescore: baseline=absent, patched=passed
  - org.elasticsearch.search.query.RescoreKnnVectorQueryIT#testKnnRetriever: baseline=absent, patched=passed
  - org.elasticsearch.search.query.RescoreKnnVectorQueryIT#testKnnSearchRescore: baseline=absent, patched=passed
  - org.elasticsearch.search.vectors.RescoreKnnVectorQueryTests#testProfiling: baseline=passed, patched=passed
  - org.elasticsearch.search.vectors.RescoreKnnVectorQueryTests#testRescoreDocs: baseline=passed, patched=passed
