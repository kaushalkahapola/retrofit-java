# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java: No such file or directory

- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.integrationtests.AlterTableIntegrationTest']
  - io.crate.integrationtests.AlterTableIntegrationTest: baseline=absent, patched=unknown
