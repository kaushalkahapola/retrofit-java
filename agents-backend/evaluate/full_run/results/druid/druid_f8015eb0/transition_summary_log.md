# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (0): []
- newly passing (1): ['org.apache.druid.indexing.overlord.supervisor.LagStatsTest#testAutoScalerLagComputation']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.apache.druid.indexing.overlord.supervisor.LagStatsTest']
  - org.apache.druid.indexing.overlord.supervisor.LagStatsTest#testAutoScalerLagComputation: baseline=absent, patched=passed
