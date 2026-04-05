# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (2): ['org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testDestIndexContainsDocs', 'org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testSettingsAddedBeforeReindex']
- newly passing (0): []
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT']
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testCustomReindexPipeline: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testDestIndexContainsDocs: baseline=failed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testDestIndexDeletedIfExists: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testDestIndexNameSet_noDotPrefix: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testDestIndexNameSet_withDotPrefix: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testIndexLifecycleSettingNotCopied: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testIndexUnfrozen: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testMappingsAddedToDestIndex: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testMissingSourceIndex: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testReadOnlyBlocksNotAddedBack: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testSettingsAddedBeforeReindex: baseline=failed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testSettingsAndMappingsFromTemplate: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testTimestamp0AddedIfMissing: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testTimestampNotAddedIfExists: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testTsdbStartEndSet: baseline=passed, patched=passed
  - org.elasticsearch.xpack.migrate.action.ReindexDatastreamIndexTransportActionIT#testUpdateSettingsDefaultsRestored: baseline=passed, patched=passed
