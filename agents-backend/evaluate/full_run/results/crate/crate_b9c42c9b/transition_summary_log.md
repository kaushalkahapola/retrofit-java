# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: docs/appendices/release-notes/6.0.1.rst: No such file or directory
error: patch failed: server/src/test/java/io/crate/session/SessionTest.java:43
error: server/src/test/java/io/crate/session/Se
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.integrationtests.PostgresITest', 'io.crate.session.RowConsumerToResultReceiverTest', 'io.crate.session.SessionTest']
  - io.crate.integrationtests.PostgresITest: baseline=absent, patched=unknown
  - io.crate.session.RowConsumerToResultReceiverTest: baseline=absent, patched=unknown
  - io.crate.session.SessionTest: baseline=absent, patched=unknown
