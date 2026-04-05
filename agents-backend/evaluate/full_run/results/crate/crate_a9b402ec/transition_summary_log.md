# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (0): []
- newly passing (3): ['io.crate.expression.reference.sys.snapshot.SysSnapshotsTest#testUnavailableSnapshotsAreFilteredOut', 'io.crate.expression.reference.sys.snapshot.SysSnapshotsTest#test_current_snapshot_does_not_fail_if_get_repository_data_returns_failed_future', 'io.crate.expression.reference.sys.snapshot.SysSnapshotsTest#test_snapshot_in_progress_shown_in_sys_snapshots']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.expression.reference.sys.snapshot.SysSnapshotsTest']
  - io.crate.expression.reference.sys.snapshot.SysSnapshotsTest#testUnavailableSnapshotsAreFilteredOut: baseline=absent, patched=passed
  - io.crate.expression.reference.sys.snapshot.SysSnapshotsTest#test_current_snapshot_does_not_fail_if_get_repository_data_returns_failed_future: baseline=absent, patched=passed
  - io.crate.expression.reference.sys.snapshot.SysSnapshotsTest#test_snapshot_in_progress_shown_in_sys_snapshots: baseline=absent, patched=passed
