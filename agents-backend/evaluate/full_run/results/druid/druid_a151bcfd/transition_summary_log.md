# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (2): ['org.apache.druid.msq.exec.MSQExportTest#testExport', 'org.apache.druid.msq.exec.MSQExportTest#testExport2']
- newly passing (1): ['org.apache.druid.msq.querykit.results.ExportResultsFrameProcessorFactoryTest#testSerde']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.apache.druid.msq.exec.MSQExportTest', 'org.apache.druid.msq.querykit.results.ExportResultsFrameProcessorFactoryTest']
  - org.apache.druid.msq.exec.MSQExportTest#testExport: baseline=failed, patched=passed
  - org.apache.druid.msq.exec.MSQExportTest#testExport2: baseline=failed, patched=passed
  - org.apache.druid.msq.exec.MSQExportTest#testNumberOfRowsPerFile: baseline=passed, patched=passed
  - org.apache.druid.msq.querykit.results.ExportResultsFrameProcessorFactoryTest#testSerde: baseline=absent, patched=passed
