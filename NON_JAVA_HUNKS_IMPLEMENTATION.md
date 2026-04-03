# Non-Java Hunks Implementation: Change Summary

**Date**: 2026-04-03
**File Modified**: `agents-backend/evaluate/full_run/evaluate_full_workflow.py`
**Status**: ✅ COMPLETED

---

## What Was Changed

### Problem
The evaluation workflow was sending **all hunks from .java files** to the agentic generation system, including non-code content like:
- SQL query strings
- YAML/JSON/XML configuration blocks  
- Test data literals
- Property key-value pairs

This was inefficient and risky - agents shouldn't regenerate non-code content.

### Solution
Implement **content-based detection** to identify non-Java code hunks within Java files and move them to "auxiliary hunks" that bypass agent generation and are applied directly during validation.

---

## Changes Made

### 1. New Function: `_is_non_java_hunk_in_java_file()` 
**Lines 167-235**

Content-based detector that identifies non-code patterns:
- SQL patterns: SELECT, INSERT, UPDATE, DELETE, CREATE, WHERE, JOIN, GROUP BY, ORDER BY
- YAML patterns: key: value, document markers, tags
- JSON patterns: object and array syntax
- XML patterns: declarations and attributes
- Properties patterns: key=value syntax
- Multi-line strings and block comments

```python
def _is_non_java_hunk_in_java_file(file_path: str, hunk_text: str) -> bool:
    # Only applies to .java files (not test files)
    # Returns True if hunk contains non-code patterns
    # Uses 13 regex patterns to detect various formats
```

### 2. Modified Function: `_build_auxiliary_hunks_from_developer_patch()`
**Lines 367-469**

Changed to:
- Process ALL files (not just non-Java files)
- Filter hunks per-file using new detection function
- Mark as auxiliary if: is test file OR is non-Java file OR contains non-code content

**Key change** (lines 431-438):
```python
is_auxiliary = (
    is_test_file_check or
    is_non_java_file or
    _is_non_java_hunk_in_java_file(file_path, hunk_text)
)
```

---

## Data Flow

### Before
```
Developer Patch
    ↓
All .java files → Agents (Phases 1-3)
Test files + Non-Java files → Auxiliary hunks
    ↓
Validation Phase: Agents hunks + Auxiliary hunks
```

### After
```
Developer Patch
    ↓
Pure Java Code Hunks → Agents (Phases 1-3)
Test files + Non-Java files + Non-code in .java files → Auxiliary hunks
    ↓
Validation Phase: Agents hunks + Auxiliary hunks
```

---

## Integration Points

✅ **Auxiliary hunks passed to graph** (line 1475)
- `"developer_auxiliary_hunks": developer_aux_hunks`

✅ **Validation applies all hunks** (lines 1754-1757)
- `final_adapted_code_hunks = latest_adapted_code_hunks + developer_aux_hunks`

✅ **Comparison correctly filters** (lines 871-876)
- Only Java code hunks compared to developer patch (non-code hunks applied but not compared)

---

## Verification

✅ Python syntax valid (`py_compile` successful)
✅ Backward compatible (additive only)
✅ Error handling for invalid regex patterns
✅ Conservative approach (false positive > false negative)
✅ No new dependencies (uses only `re` stdlib)

---

## Example Behavior

**Input patch modifying**:
```
src/main/java/Query.java:
  - "SELECT * FROM users"  ← SQL pattern detected
  
src/main/java/Config.java:
  - "key: value"  ← YAML pattern detected
  
src/main/java/Logic.java:
  - "int x = 10;"  ← Pure Java, no pattern match
```

**Result**:
```
Agent receives hunks for: Logic.java only
Auxiliary hunks: Query.java SQL hunk + Config.yaml YAML hunk
Final patch: Agent-generated Logic.java hunks + developer-provided auxiliary hunks
```

---

## Key Design Decisions

1. **Whole-hunk approach**: If a hunk contains ANY non-code content, skip entire hunk from agents
   - Reason: Conservative - avoid breaking non-code patterns

2. **Pattern-based detection**: Uses regex patterns, not file extensions
   - Reason: Detects non-code content WITHIN .java files

3. **Graceful degradation**: Invalid regex patterns are skipped, detection continues
   - Reason: Robustness against pattern errors

4. **Per-hunk filtering**: Tests each hunk individually
   - Reason: Same file can have mixed content hunks

---

## No Changes Needed To

- ✅ Phase 0-2 (agentic phases) - automatically don't receive non-code hunks
- ✅ Phase 3 (hunk_generator) - no changes needed
- ✅ Phase 4 (validation) - already handles auxiliary hunks correctly
- ✅ Comparison logic - correctly excludes non-code hunks from metrics
