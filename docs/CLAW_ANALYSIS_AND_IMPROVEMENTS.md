# CLAW Architecture Analysis & Application to H-MABS

## Executive Summary

After studying the CLAW code architecture, we've identified critical patterns that are **absent or underdeveloped** in our H-MABS (Heuristic Multi-Agent Backport System). CLAW uses sophisticated error propagation, structured tool response patterns, and hook-based validation that would significantly improve our patch generation robustness.

---

## Key CLAW Architectural Patterns

### 1. **Structured Error/Result Objects**

**CLAW's Approach:**
- `ToolError` (Rust): Simple wrapper with `message: String` (lines 40-59 in conversation.rs)
- `RuntimeError`: Similar structured error type
- `ToolResult`: Variant of `ContentBlock` with `is_error: bool` flag (session.rs lines 31-36)
- All tool outputs include an `is_error` boolean flag to distinguish success from failure

```rust
pub enum ContentBlock {
    ToolResult {
        tool_use_id: String,
        tool_name: String,
        output: String,
        is_error: bool,  // <-- Key: Explicit error flag
    },
}
```

**Our Current Approach:**
- Plain string outputs from tools (no structured error metadata)
- Validation tools return dict with `"success": bool` but inconsistent structure
- Dry-run validation failures are caught but not formally marked as error states
- Error context lost when hunks are passed between phases

**Gap:** We lack a unified error type that carries both the error message AND metadata (error code, source, suggestion).

---

### 2. **Hook-Based Validation Pipeline**

**CLAW's Approach:**
- `HookEvent::PreToolUse` - validates tool call BEFORE execution (hooks.rs lines 76-84)
- `HookEvent::PostToolUse` - validates tool result AFTER execution (hooks.rs lines 87-102)
- Hooks can **deny** execution (exit code 2), **allow** (exit code 0), or **warn** (other codes)
- Hooks are composable: multiple hooks can run in sequence, early denial stops chain
- Hook messages merge with tool output: `merge_hook_feedback()` (lines 346-362)
- Result status is always `(denied: bool, messages: Vec<String>)`

```rust
pub struct HookRunResult {
    denied: bool,
    messages: Vec<String>,
}
```

**Our Current Approach:**
- Single validation layer in Phase 4 (apply_adapted_hunks)
- No pre-validation hooks (could catch issues earlier)
- No formal post-validation hooks
- Validation failures are logged but not propagated back as structured errors

**Gap:** We have no hook system to intercept and enrich errors with context before the LLM sees them.

---

### 3. **Conversation Loop Error Handling**

**CLAW's Approach:**
- Central loop in `ConversationRuntime::run_turn()` (lines 153-262)
- For each tool use:
  1. Check permission (allow/deny/prompt)
  2. Run pre-tool hooks
  3. Execute tool
  4. Run post-tool hooks
  5. Merge all feedback into a single `ToolResult` message
  6. Push to session for LLM to see

```python
for (tool_use_id, tool_name, input) in pending_tool_uses:
    permission_outcome = self.permission_policy.authorize(...)
    
    match permission_outcome:
        Allow => 
            pre_hook_result = self.hook_runner.run_pre_tool_use(...)
            if pre_hook_result.is_denied(): return error
            
            (output, is_error) = self.tool_executor.execute(...)
            
            post_hook_result = self.hook_runner.run_post_tool_use(...)
            
            result_message = ConversationMessage.tool_result(
                output=output,
                is_error=is_error,  # Explicit flag
            )
        Deny => result_message = ConversationMessage.tool_result(reason, is_error=true)
    
    self.session.messages.push(result_message)
```

**Our Current Approach:**
- Each phase is separate; no central loop
- Phase 3 catches validation errors and continues
- Phase 4 tries to apply all hunks and fails on first error
- No opportunity for the LLM to see intermediate failures and retry

**Gap:** We don't have a "conversation loop" where tool failures are visible to the agent for correction.

---

### 4. **Tool Response Contract**

**CLAW's Pattern:**
- Every tool response includes:
  - `output: String` (the actual result)
  - `is_error: bool` (success/failure flag)
  - `tool_use_id: String` (for correlation)
  - `tool_name: String` (for logging)

- Error responses still go back to LLM (not dropped)
- LLM sees: "Tool X failed with: [reason]" → can retry or use alternative approach

**Our Current Pattern:**
- Phase 3 dry-run validation catches errors silently → hunk dropped
- Phase 4 applies patches but fails on first error → no opportunity to rewrite
- No error-resilience feedback loop

**Gap:** Errors that occur in validation are not fed back to the agent that could fix them.

---

### 5. **Structured Metadata in Tool Outputs**

**CLAW's Pattern:**
- While not explicit in the code shown, hooks allow passing structured context
- Hook payload includes:
  ```json
  {
    "hook_event_name": "PreToolUse"|"PostToolUse",
    "tool_name": "tool_name",
    "tool_input": "...",
    "tool_input_json": "{...}",
    "tool_output": "...",
    "tool_result_is_error": bool
  }
  ```
- This lets external validation services inspect and enrich errors

**Our Current Pattern:**
- Validation results are plain dicts
- No standardized structure for error context
- Difficult to trace where in the pipeline an error originated

**Gap:** We lack structured metadata that tracks error source, context, and recovery suggestions.

---

## Mapping to Our H-MABS Pipeline

### Phase 0 (Optimistic Expansion)
- ✅ Input: mainline patch
- ❌ No error handling (assumes success)

### Phase 1 (Context Analysis)
- ✅ Analyzes target repo structure
- ❌ No validation of analysis results

### Phase 2 (Reasoning Agent)
- ✅ Generates hunk rewrites
- ❌ No validation before passing to Phase 3

### Phase 3 (Hunk Generator) — CURRENT PROBLEM
- ✅ Calls dry-run validation
- ❌ **Silently drops hunks that fail** (line ~1290 in hunk_generator.py)
- ❌ No structured error type tracking which hunks failed and why
- ❌ No opportunity for LLM to fix failures

### Phase 4 (Validation) — CURRENT PROBLEM
- ✅ Applies hunks individually (fixed)
- ❌ First failure kills entire patch
- ❌ No "hook" to inspect failures and provide context to Phase 3

---

## Recommended Improvements (Based on CLAW Patterns)

### 1. Create Structured Error Types

```python
from dataclasses import dataclass
from enum import Enum

class HunkValidationError(Enum):
    DRY_RUN_FAILED = "dry_run_failed"
    CONTEXT_MISMATCH = "context_mismatch"
    APPLY_FAILED = "apply_failed"
    SYNTAX_ERROR = "syntax_error"
    UNKNOWN = "unknown"

@dataclass
class HunkValidationResult:
    hunk_id: str
    is_error: bool
    error_type: Optional[HunkValidationError]
    error_message: str
    context_lines: Optional[List[str]]  # Surrounding code for debugging
    suggestions: Optional[List[str]]    # How to fix
    
@dataclass
class PatchValidationResult:
    patch_id: str
    hunks: List[HunkValidationResult]
    all_passed: bool
    first_failed_hunk_id: Optional[str]
```

### 2. Implement Hook-Based Validation

```python
# ValidationTools with hooks similar to CLAW

class HunkValidationHook:
    """Base class for validation hooks (pre/post)"""
    
    def run_pre_hunk_validation(self, hunk_id: str, hunk_content: str) -> HookResult:
        """Run before attempting to apply hunk"""
        pass
    
    def run_post_hunk_validation(self, hunk_id: str, applied: bool, output: str) -> HookResult:
        """Run after attempting to apply hunk"""
        pass

class HookResult:
    def __init__(self, allowed: bool, messages: List[str]):
        self.allowed = allowed
        self.messages = messages
```

### 3. Refactor Phase 3 to NOT Drop Hunks

```python
# In hunk_generator.py, instead of:
if not dry_run_result["success"]:
    continue  # ❌ WRONG: drops hunk

# Do:
if not dry_run_result["success"]:
    hunk["validation_error"] = {
        "error_type": dry_run_result.get("error_code"),
        "message": dry_run_result.get("error_message"),
        "suggestions": generate_suggestions(dry_run_result)
    }
    # ✅ PASS HUNK TO PHASE 4 with error metadata
```

### 4. Implement Feedback Loop in Phase 4

```python
# After all hunks processed in Phase 4:

failed_hunks = [h for h in hunks if h.get("applied_error")]

if failed_hunks:
    # Instead of giving up, compile context and retry
    context = PatchRetryContext(
        failed_hunks=failed_hunks,
        target_file_content=get_file_content(target_path),
        line_offsets={h.id: h.offset_error for h in failed_hunks},
        suggestions=suggest_fixes(failed_hunks)
    )
    
    # Send back to Phase 3 for LLM rewrite
    phase3_retry_result = phase3_agent.retry_with_context(context)
```

### 5. Centralize Error Reporting

```python
# Create a ValidationObserver (similar to CLAW's hook system)

class ValidationObserver:
    def on_hunk_validation_started(self, hunk_id: str):
        pass
    
    def on_hunk_validation_error(self, result: HunkValidationResult):
        """Called when a hunk fails validation"""
        # Log structured error
        # Potentially trigger hooks
        pass
    
    def on_patch_validation_complete(self, result: PatchValidationResult):
        """Called when entire patch is validated"""
        pass
```

---

## Priority Implementation Order

1. **Phase 1 (Quick Win):** Create structured error types (HunkValidationResult, PatchValidationResult)
   - Low risk, high clarity improvement
   - Enables tracking which hunks failed and why

2. **Phase 2 (Core Fix):** Modify Phase 3 to NOT drop hunks
   - Attach validation errors to hunk objects
   - Pass everything to Phase 4

3. **Phase 3 (Feedback Loop):** Implement Phase 4 -> Phase 3 retry mechanism
   - When hunks fail in Phase 4, collect context (file content, line offsets)
   - Call Phase 3 with structured retry request
   - LLM rewrites failed hunks with full context

4. **Phase 4 (Advanced):** Add hook-based validation
   - Pre-hunk hooks to catch obvious issues early
   - Post-hunk hooks to enrich errors with suggestions
   - Merge hook feedback into Phase 3 retry messages

---

## Key Differences from CLAW

| Aspect | CLAW | H-MABS Current | H-MABS Target |
|--------|------|----------------|---------------|
| **Error Propagation** | Structured + hooks | Silent drops | Structured + feedback loop |
| **Tool Failures** | Visible to agent | Caught but not reported | Reported with context |
| **Validation** | Hook-based (pre/post) | Single point (Phase 4) | Hook-based + retry |
| **Error Context** | Metadata-rich | Generic strings | Structured objects |
| **Recovery** | LLM-driven retry | Manual | Automated feedback loop |
| **Session History** | Explicit (Session struct) | Implicit logs | Session-like trail |

---

## Testing Strategy

1. **Unit test:** HunkValidationResult structure
2. **Integration test:** Phase 3 passes failed hunks to Phase 4
3. **E2E test:** Phase 4 detects failure → sends feedback → Phase 3 retries → success
4. **Regression test:** elasticsearch_734dd070 (5 hunks) applies completely without dropping

---

## Next Steps

1. Implement structured error types (HunkValidationResult)
2. Modify Phase 3 to attach errors instead of dropping hunks
3. Verify Phase 4 processes hunks with embedded errors
4. Test with elasticsearch_734dd070 case
5. Implement Phase 4 -> Phase 3 feedback loop for failures
6. Add hook-based validation layer
