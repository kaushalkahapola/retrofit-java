# Transition Summary

- Source: phase0_cache
- Valid backport signal: False
- Reason: Invalid: git apply --check failed. error: patch failed: server/src/main/java/io/crate/role/Role.java:257
error: server/src/main/java/io/crate/role/Role.java: patch does not apply
error: patch failed: server/src/main/java/io/crate/role/
- fail->pass (0): []
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.role.TransportRoleActionTest', 'io.crate.role.metadata.RolesMetadataTest']
  - io.crate.role.TransportRoleActionTest: baseline=absent, patched=unknown
  - io.crate.role.metadata.RolesMetadataTest: baseline=absent, patched=unknown
