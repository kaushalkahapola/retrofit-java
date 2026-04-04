# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (1): ['org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testFollowLinks']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests']
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testEmpty: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testFollowLinks: baseline=failed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testForwardSlashes: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testJdkAccess: baseline=failed, patched=failed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testMultipleDataDirs: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testNormalizePath: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testNormalizeTrailingSlashes: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testPathAndFileWithSamePrefix: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testPrunedPaths: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testRead: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testReadWithRelativePath: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testReadWriteUnderRead: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testTempDirAccess: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testTwoPaths: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testWrite: baseline=passed, patched=passed
  - org.elasticsearch.entitlement.runtime.policy.FileAccessTreeTests#testWriteWithRelativePath: baseline=passed, patched=passed
