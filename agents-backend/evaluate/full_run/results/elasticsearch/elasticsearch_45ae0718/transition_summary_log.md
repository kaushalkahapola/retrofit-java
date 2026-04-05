# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (1): ['org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testOldIndicesIgnoredWarningCheck']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.xpack.deprecation.DataStreamDeprecationChecksTests', 'org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests']
  - org.elasticsearch.xpack.deprecation.DataStreamDeprecationChecksTests: baseline=absent, patched=absent
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testCamelCaseDeprecation: baseline=passed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testDefaultTranslogRetentionSettings: baseline=passed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testFrozenIndex: baseline=passed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testIndexDataPathSetting: baseline=passed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testOldIndicesCheck: baseline=passed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testOldIndicesCheckClosedIgnored: baseline=passed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testOldIndicesCheckDataStreamIndex: baseline=passed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testOldIndicesCheckSnapshotIgnored: baseline=passed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testOldIndicesIgnoredWarningCheck: baseline=failed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testSimpleFSSetting: baseline=passed, patched=passed
  - org.elasticsearch.xpack.deprecation.IndexDeprecationChecksTests#testTranslogRetentionSettings: baseline=passed, patched=passed
