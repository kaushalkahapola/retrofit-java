# CLAW-Inspired Improvements to H-MABS: Implementation Summary

## What We Did

We studied the CLAW (industry-standard agentic code tool) architecture and applied its proven patterns to significantly improve the robustness of our H-MABS (Heuristic Multi-Agent Backport System) pipeline. The improvements focus on **structured error handling**, **agent-to-agent feedback loops**, and **preventing silent failures**.

---

## Key CLAW Patterns We Applied

### 1. **Structured Error Types** (inspiration from conversation.rs, session.rs)
CLAW uses explicit error types with metadata instead of plain string errors:
- `ToolError`, `RuntimeError`: Structured error objects
- `ToolResult` with `is_error: bool` flag
- Hook system for error validation/enrichment

**What we built:**
- Created `src/utils/validation_models.py` with CLAW-inspired types:
  - `HunkValidationError`: Rich error with type, message, suggestions, context
  - `HunkValidationResult`: Complete validation result for a single hunk
  - `PatchValidationResult`: Aggregated results for entire patch
  - `PatchRetryContext`: Context for feeding failures back to Phase 3
  - `ValidationObserver`: Hook-based observation pattern

### 2. **Agent Communication Pattern** (inspiration from hooks.rs)
CLAW implements hooks at pre/post tool execution to validate and enrich errors:
```rust
pub fn run_pre_tool_use(&self, tool_name: &str, tool_input: &str) -> HookRunResult
pub fn run_post_tool_use(&self, tool_name: &str, output: &str, is_error: bool) -> HookRunResult
```

**What we added:**
- `apply_hunk_dry_run_structured()`: Wrapper around dry-run that returns structured HunkValidationResult
- `_categorize_validation_error()`: Analyzes error output and provides targeted suggestions
- `create_patch_retry_context()`: Collects failure context for Phase 4→Phase 3 feedback

### 3. **No Silent Failures** (inspiration from conversation loop)
CLAW's `ConversationRuntime::run_turn()` never drops tool failures; they're visible to the LLM for retry.

**What we changed:**
- Phase 3 (hunk_generator.py): NO LONGER drops hunks on dry-run failure
  - Previously: `if not dry_run_ok: continue` ❌
  - Now: Attach error metadata and pass to Phase 4 ✅
- Hunks now carry optional `dry_run_error` and `dry_run_error_message` fields
- Phase 4 can see which hunks failed in Phase 3 and why

### 4. **Structured Metadata in Hunk Objects** (inspired by session.rs ContentBlock)
CLAW tracks metadata across conversation turns. We do the same with hunks:

**Modified `AdaptedHunk` (state.py)**:
```python
class AdaptedHunk(TypedDict):
    # ... existing fields ...
    dry_run_error: NotRequired[Optional[Dict[str, Any]]]  # NEW: Error metadata
    dry_run_error_message: NotRequired[Optional[str]]      # NEW: Human-readable error
```

This allows Phase 4 to inspect what went wrong in Phase 3 validation.

---

## Files Modified

### 1. **`agents-backend/src/utils/validation_models.py`** (NEW)
Implements structured error types following CLAW patterns:
- `HunkValidationErrorType` enum: Categorizes validation errors
- `HookResult`: Hook execution result (allowed/denied + messages)
- `HunkValidationError`: Detailed error with suggestions
- `HunkValidationResult`: Result for single hunk validation
- `PatchValidationResult`: Aggregated patch validation
- `PatchRetryContext`: Retry context for Phase 3
- `ValidationObserver`: Hook pattern for observability

**Purpose**: Enable rich error reporting across the pipeline instead of silent failures

### 2. **`agents-backend/src/agents/validation_tools.py`** (MODIFIED)
Added new structured validation methods:
- **`apply_hunk_dry_run_structured()`**: Returns HunkValidationResult instead of dict
  - Categorizes errors automatically
  - Provides suggestions
  - Includes context for debugging
  
- **`_categorize_validation_error()`**: Analyzes error output
  - Pattern matching for common errors (malformed patch, context mismatch, etc)
  - Generates targeted fix suggestions
  
- **`create_patch_retry_context()`**: Creates retry context
  - Reads target file content for Phase 3
  - Includes assembly errors and suggestions
  - Ready for Phase 3 LLM retry

**Purpose**: Transform plain error strings into actionable structured data

### 3. **`agents-backend/src/state.py`** (MODIFIED)
Enhanced `AdaptedHunk` TypedDict:
- Added `dry_run_error: NotRequired[Optional[Dict[str, Any]]]`
- Added `dry_run_error_message: NotRequired[Optional[str]]`
- Imported `Dict`, `Any` for type hints

**Purpose**: Allow hunks to carry validation error metadata between phases

### 4. **`agents-backend/src/agents/hunk_generator.py`** (MODIFIED)
Updated code hunk AND test hunk processing to use error metadata:
- Collect `dry_run_error_info` from failed dry-run validations
- Attach error info to hunk objects: `hunk["dry_run_error"] = dry_run_error_info`
- **No longer drop hunks on failure** - pass through to Phase 4
- Phase 4 can now see what failed in Phase 3 and why

**Before**:
```python
if not dry_run_ok:
    continue  # ❌ SILENT FAILURE: hunk disappears
```

**After**:
```python
if not dry_run_ok:
    dry_run_error_info = {...}
    # ... hunk is added with error metadata ...
    hunk["dry_run_error"] = dry_run_error_info  # ✅ VISIBLE TO PHASE 4
```

---

## Architecture Changes Summary

```
BEFORE (Silent Failures):
Phase 3 Dry-Run Fails → continue → Hunk Dropped → Phase 4 Never Sees It
                                                     ❌ Lost opportunity to retry

AFTER (CLAW-Inspired Structured Errors):
Phase 3 Dry-Run Fails → Attach Error Metadata → Hunk Passes to Phase 4
                          ✅ With context, suggestions, categorization
                          
Phase 4 Detects Failure → Create PatchRetryContext → Could Retry Phase 3
                          ✅ Feed back richer context for LLM rewrite
```

---

## Immediate Benefits

1. **No More Silent Failures**: Every validation error is tracked in hunk metadata
2. **Better Observability**: Detailed error types and suggestions in phase outputs
3. **Retry-Ready**: Phase 4 can detect failures and create context for Phase 3 retry
4. **CLAW-Compatible**: Uses proven patterns from industry-standard tool
5. **Backward Compatible**: Enhanced optional fields don't break existing code

---

## Next Steps (For Future Sessions)

### Phase 1: Test Current Improvements
- Run elasticsearch_734dd070 patch evaluation
- Verify all 5 hunks make it to Phase 4 (none dropped)
- Verify Phase 4 sees dry-run error metadata
- Check error categorization and suggestions

### Phase 2: Implement Phase 4→Phase 3 Retry Loop
Once we verify hunks are preserved, we can:
- In Phase 4, when hunks fail: create `PatchRetryContext`
- Pass context back to Phase 3 with instructions to retry
- Phase 3 LLM gets: actual file content, line numbers, error details
- Automate retry with max iterations

### Phase 3: Add Hook-Based Validation
- Implement `ValidationObserver` hooks
- Pre-hunk-validation: Catch obvious issues early
- Post-hunk-validation: Enrich errors with suggestions
- Merge hook feedback into retry messages

### Phase 4: Structured Validation Throughout Pipeline
- Convert all tool outputs to structured types
- Add observability/logging to each validation event
- Create session-like audit trail of validation attempts

---

## Key Differences: H-MABS Before vs After CLAW Patterns

| Aspect | Before | After |
|--------|--------|-------|
| **Error Propagation** | String errors, sometimes dropped | Structured `HunkValidationError` with context |
| **Hunk Fate** | Fails dry-run → deleted | Fails dry-run → metadata attached, passed forward |
| **Error Visibility** | Phase 3 failures invisible to Phase 4 | Phase 4 sees Phase 3 failures + details |
| **Retry Capability** | Manual investigation required | `PatchRetryContext` ready for LLM |
| **Suggestion Support** | Generic "try again" | Targeted suggestions based on error type |
| **Observer Pattern** | None | `ValidationObserver` hooks available |

---

## Code References

- **New validation models**: `agents-backend/src/utils/validation_models.py`
- **Structured validation methods**: `agents-backend/src/agents/validation_tools.py:1404-1503`
- **Hunk error metadata**: `agents-backend/src/state.py:69-91`
- **Phase 3 error attachment**: `agents-backend/src/agents/hunk_generator.py:1286-1329` (code hunks)
- **Phase 3 error attachment**: `agents-backend/src/agents/hunk_generator.py:1427-1452` (test hunks)
- **Architecture analysis**: `/CLAW_ANALYSIS_AND_IMPROVEMENTS.md`

---

## How These Changes Solve Original Problems

### Problem 1: "Hunks dropped silently in Phase 3"
**Solution**: Hunks now carry `dry_run_error` metadata. Phase 4 can see which hunks failed validation and why.

### Problem 2: "Phase 4 fails on first error without feedback"
**Solution**: `create_patch_retry_context()` method collects failure details for Phase 3 retry.

### Problem 3: "Line number offset issues"
**Solution**: `_categorize_validation_error()` detects offset errors and suggests solutions.

### Problem 4: "Weak retry mechanism without context"
**Solution**: `PatchRetryContext` includes actual file content, error messages, and targeted suggestions.

---

## Testing Checklist

When we test the elasticsearch_734dd070 patch:
- [ ] All 5 code hunks appear in Phase 3 output (not dropped)
- [ ] Each hunk has either `dry_run_error=None` (success) or error metadata (failure)
- [ ] Phase 4 receives all hunks from Phase 3
- [ ] Phase 4 error messages are more specific (error type + suggestions)
- [ ] Could create PatchRetryContext from failed hunks (shows retry is possible)
- [ ] JSON output includes error categorization for each hunk

---

## Acknowledgments

This implementation follows architectural patterns from:
- CLAW (https://github.com/instructkr/claw-code) - Hook system, error handling, conversation loops
- CLAW's Rust crate:
  - `crates/runtime/src/conversation.rs`: Error handling, tool execution
  - `crates/runtime/src/hooks.rs`: Hook pattern for validation
  - `crates/runtime/src/session.rs`: Structured message/result types

The improvements maintain backward compatibility while adding observability and enabling future retry mechanisms.
