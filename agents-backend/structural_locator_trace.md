# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: Insufficient check for available memory in the last allocated block could allow an allocation request to succeed even when the allocator cannot satisfy it, potentially leading to buffer overflows or logic errors.

## Hunk Segregation
- Code files: 1
- Test files: 4

## Code File Mappings

### `processing/src/main/java/org/apache/druid/frame/allocation/AppendableMemory.java`

**Agent Tool Steps:**

  - `Agent calls search_candidates` with `{"file_path": "processing/src/main/java/org/apache/druid/frame/allocation/AppendableMemory.java"}`
  - `Tool: search_candidates` -> [{"file": "processing/src/main/java/org/apache/druid/frame/allocation/AppendableMemory.java", "score": 1.0, "method": "GIT_EXACT", "reason": "Exact path match"}]...
  - `Agent calls get_class_context` with `{"file_path": "processing/src/main/java/org/apache/druid/frame/allocation/AppendableMemory.java"}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.frame.allocation;\n\n// Line 40\npublic class AppendableMemory implements Closeable {\n    // Line 42: private static final int NO_BLOCK = -1;\n    // Line 46: //...
  - `Agent calls get_class_context` with `{"file_path": "processing/src/main/java/org/apache/druid/frame/allocation/AppendableMemory.java", "focus_method": "reserveAdditional"}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.frame.allocation;\n\n// Line 40\npublic class AppendableMemory implements Closeable {\n    // Line 42: private static final int NO_BLOCK = -1;\n    // Line 46: //...
  - `Agent calls git_log_follow` with `{"file_path": "processing/src/main/java/org/apache/druid/frame/allocation/AppendableMemory.java"}`
  - `Tool: git_log_follow` -> 4a8008aebb Use the whole frame when writing rows. (#17094) (#17195)
M	processing/src/main/java/org/apache/druid/frame/allocation/AppendableMemory.java
5f588fa45c Fix bug while materializing scan's res...
  - `Agent calls get_class_context` with `{"file_path": "processing/src/main/java/org/apache/druid/frame/allocation/AppendableMemory.java", "focus_method": "reserveAdditional"}`
  - `Agent calls get_class_context` with `{"file_path": "processing/src/main/java/org/apache/druid/frame/allocation/AppendableMemory.java", "focus_method": "currentBlockNumber"}`
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.frame.allocation;\n\n// Line 40\npublic class AppendableMemory implements Closeable {\n    // Line 42: private static final int NO_BLOCK = -1;\n    // Line 46: //...
  - `Tool: get_class_context` -> {"context": "package org.apache.druid.frame.allocation;\n\n// Line 40\npublic class AppendableMemory implements Closeable {\n    // Line 42: private static final int NO_BLOCK = -1;\n    // Line 46: //...

| Mainline Method | Target Method | Lines |
|---|---|---|
| `reserveAdditional` | `reserveAdditional` | 149–195 |

## Test File Mappings

- `extensions-core/multi-stage-query/src/test/java/org/apache/druid/msq/exec/MSQWindowTest.java` → `extensions-core/multi-stage-query/src/test/java/org/apache/druid/msq/exec/MSQWindowTest.java` ✅
- `extensions-core/multi-stage-query/src/test/java/org/apache/druid/msq/test/MSQTestBase.java` → `extensions-core/multi-stage-query/src/test/java/org/apache/druid/msq/test/MSQTestBase.java` ✅
- `processing/src/test/java/org/apache/druid/frame/allocation/AppendableMemoryTest.java` → **null** (test synthesis required by Agent 4) ⚠️
- `processing/src/test/java/org/apache/druid/frame/write/FrameWriterTest.java` → `processing/src/test/java/org/apache/druid/frame/write/FrameWriterTest.java` ✅

## Consistency Map

_No renames detected — identity mapping assumed._
