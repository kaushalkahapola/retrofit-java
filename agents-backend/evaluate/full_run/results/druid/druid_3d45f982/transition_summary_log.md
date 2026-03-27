# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (6): ['org.apache.druid.frame.allocation.ArenaMemoryAllocatorTest#testAllocationInMultiplePasses', 'org.apache.druid.frame.allocation.ArenaMemoryAllocatorTest#testAllocationInSinglePass', 'org.apache.druid.frame.allocation.ArenaMemoryAllocatorTest#testReleaseAllocationTwice', 'org.apache.druid.frame.allocation.ArenaMemoryAllocatorTest#testReleaseLastAllocationFirst', 'org.apache.druid.frame.allocation.HeapMemoryAllocatorTest#testReleaseAllocationTwice', 'org.apache.druid.frame.write.RowBasedFrameWriterTest#test_addSelection_singleLargeRow']
- newly passing (0): []
- pass->fail (0): []
