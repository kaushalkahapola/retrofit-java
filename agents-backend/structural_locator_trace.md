# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: The ExportResultsFrameProcessorFactory was not being provided with columnMappings, potentially leading to incorrect or missing column mapping during export operations. | Exported result columns could be mismatched or inconsistent due to reliance on input row signature and lack of explicit column mapping, especially across upgrades or schema changes. | The class did not support passing or serializing column mappings, which are necessary for correct export and downstream processing of query results.

## Hunk Segregation
- Code files: 3
- Test files: 0

## Code File Mappings

### `extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/exec/ControllerImpl.java`

**Hunks in this file**: 1

**Git Resolution**: Found `extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/exec/ControllerImpl.java`

**Agent Tool Steps:**

  - `Agent calls get_class_context` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/exec/ControllerImpl.java", "focus_method": "processorFactory", "use_mainline": false}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.msq.exec;\n\n// Line 245\npublic class ControllerImpl implements Controller {\n    // Line 247: private static final org.apache.druid.java.util.common.logger.Logg...
  - `Agent calls read_file` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/exec/ControllerImpl.java"}`
  - `Tool: read_file` -> package org.apache.druid.msq.exec;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Preconditions;
import co...
  - `Agent calls get_class_context` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/exec/ControllerImpl.java", "focus_method": "makeQueryDefinition", "use_mainline": false}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.msq.exec;\n\n// Line 245\npublic class ControllerImpl implements Controller {\n    // Line 247: private static final org.apache.druid.java.util.common.logger.Logg...
  - `Agent calls git_blame_lines` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/exec/ControllerImpl.java", "start_line": 1905, "end_line": 1917, "use_mainline": false}`
  - `Tool: git_blame_lines` -> bf8b9818bec (Adarsh Sanjeev 2024-02-08 14:38:01 +0530 1905)       final ResultFormat resultFormat = exportMSQDestination.getResultFormat();
bf8b9818bec (Adarsh Sanjeev 2024-02-08 14:38:01 +0530 1906) ...
  - `Agent calls get_class_context` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/exec/ControllerImpl.java", "focus_method": "ExportResultsFrameProcessorFactory", "use_mainline": false}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.msq.exec;\n\n// Line 245\npublic class ControllerImpl implements Controller {\n    // Line 247: private static final org.apache.druid.java.util.common.logger.Logg...

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `makeQueryDefinition` | `makeQueryDefinition` | 1754–1923 |
### `extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessor.java`

**Hunks in this file**: 9

**Git Resolution**: Found `extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessor.java`

**Agent Tool Steps:**

  - `Agent calls get_class_context` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessor.java", "focus_method": "ExportResultsFrameProcessor", "use_mainline": false}`
  - `Agent calls get_class_context` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessor.java", "focus_method": "exportFrame", "use_mainline": false}`
  - `Agent calls get_class_context` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessor.java", "focus_method": "createRowSignatureForExport", "use_mainline": false}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.msq.querykit.results;\n\n// Line 54\npublic class ExportResultsFrameProcessor implements FrameProcessor {\n    // Line 56: private final org.apache.druid.frame.ch...
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.msq.querykit.results;\n\n// Line 54\npublic class ExportResultsFrameProcessor implements FrameProcessor {\n    // Line 56: private final org.apache.druid.frame.ch...
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.msq.querykit.results;\n\n// Line 54\npublic class ExportResultsFrameProcessor implements FrameProcessor {\n    // Line 56: private final org.apache.druid.frame.ch...
  - `Agent calls read_file` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessor.java"}`
  - `Tool: read_file` -> package org.apache.druid.msq.querykit.results;
import com.fasterxml.jackson.databind.ObjectMapper;
import it.unimi.dsi.fastutil.ints.IntSet;
import org.apache.druid.error.DruidException;
import org.ap...

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 2–25 |
| 2 | declaration | `<import>` | `<import>` | 17–18 |
| 3 | declaration | `ExportResultsFrameProcessor` | `ExportResultsFrameProcessor` | 62–62 |
| 4 | propagation | `ExportResultsFrameProcessor` | `ExportResultsFrameProcessor` | 64–78 |
| 5 | core_fix | `ExportResultsFrameProcessor` | `ExportResultsFrameProcessor` | 79–79 |
| 6 | cleanup | `exportFrame` | `exportFrame` | 112–112 |
| 7 | refactor | `exportFrame` | `exportFrame` | 138–142 |
| 8 | core_fix | `exportFrame` | `exportFrame` | 146–148 |
| 9 | cleanup | `createRowSignatureForExport` | `createRowSignatureForExport` | 165–173 |
### `extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessorFactory.java`

**Hunks in this file**: 5

**Git Resolution**: Found `extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessorFactory.java`

**Agent Tool Steps:**

  - `Agent calls get_class_context` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessorFactory.java", "focus_method": "ExportResultsFrameProcessorFactory", "use_mainline": false}`
  - `Agent calls get_class_context` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessorFactory.java", "focus_method": "getColumnMappings", "use_mainline": false}`
  - `Agent calls get_class_context` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessorFactory.java", "focus_method": "makeProcessors", "use_mainline": false}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.msq.querykit.results;\n\n@com.fasterxml.jackson.annotation.JsonTypeName(\"exportResults\")\n// Line 53\npublic class ExportResultsFrameProcessorFactory extends Ba...
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.msq.querykit.results;\n\n@com.fasterxml.jackson.annotation.JsonTypeName(\"exportResults\")\n// Line 53\npublic class ExportResultsFrameProcessorFactory extends Ba...
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.msq.querykit.results;\n\n@com.fasterxml.jackson.annotation.JsonTypeName(\"exportResults\")\n// Line 53\npublic class ExportResultsFrameProcessorFactory extends Ba...
  - `Agent calls read_file` with `{"file_path": "extensions-core/multi-stage-query/src/main/java/org/apache/druid/msq/querykit/results/ExportResultsFrameProcessorFactory.java"}`
  - `Tool: read_file` -> package org.apache.druid.msq.querykit.results;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonTy...

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `<import>` | `<import>` | 2–2 |
| 2 | declaration | `<import>` | `<import>` | 24–24 |
| 3 | declaration | `ExportResultsFrameProcessorFactory` | `ExportResultsFrameProcessorFactory` | 41–54 |
| 4 | propagation | `getColumnMappings` | `None` | None–None |
| 5 | propagation | `makeProcessors` | `makeProcessors` | 91–133 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
