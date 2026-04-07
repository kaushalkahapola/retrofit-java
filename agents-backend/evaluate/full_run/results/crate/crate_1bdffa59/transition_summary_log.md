# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: server/src/main/java/io/crate/replication/logical/MetadataTracker.java:23
error: server/src/main/java/io/crate/replication/logical/MetadataTracker.java: patch does not apply
error
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.integrationtests.LogicalReplicationITest', 'io.crate.integrationtests.MetadataTrackerITest', 'io.crate.replication.logical.MetadataTrackerTest', 'io.crate.replication.logical.action.PublicationsStateActionTest']
  - io.crate.integrationtests.LogicalReplicationITest: baseline=absent, patched=unknown
  - io.crate.integrationtests.MetadataTrackerITest: baseline=absent, patched=unknown
  - io.crate.replication.logical.MetadataTrackerTest: baseline=absent, patched=unknown
  - io.crate.replication.logical.action.PublicationsStateActionTest: baseline=absent, patched=unknown
