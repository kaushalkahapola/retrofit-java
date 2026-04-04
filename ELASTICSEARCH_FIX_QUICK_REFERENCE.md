# Quick Reference: Elasticsearch Failure Fix Checklist

## What's Wrong
- ❌ Duplicate `@Inject` annotation in TransportGetAllocationStatsAction.java
- ❌ Extra closing brace in AllocationStatsService.java  
- ❌ Agent retries same mistake instead of learning from errors

## Root Cause
Not line drift. Agent generates malformed code because it doesn't validate *structural correctness*, only basic syntax.

## The Fix (4 Components)

### 1️⃣ Semantic Validation Checkers
**File**: `agents-backend/src/agents/hunk_generator_tools.py` (line 634)

Add to `verify_guidelines()`:
```python
# Check for duplicate annotations
# Check for brace imbalance  
# Check for duplicate imports
```

**Why**: Catch errors before agent tries to compile them

---

### 2️⃣ Enhanced Error Messages
**File**: `agents-backend/src/agents/hunk_generator_tools.py` (line 676)

Change error output from:
```
GUIDELINE_FAILURES: duplicate annotation '@Inject'
```

To:
```
❌ duplicate annotation '@Inject' at lines ~54 and ~74
   → The annotation is already present in the context
   → Remove it from the new_content parameter
```

**Why**: Agent understands the problem and can fix it

---

### 3️⃣ Updated System Prompt
**File**: `agents-backend/src/agents/file_editor.py`

Add section explaining **when to use each tool**:
- Annotations → use get_method_boundaries() + replace_method_body()
- Methods → use replace_method_body()
- Fields → use replace_field()
- Imports → use insert_import()
- Simple lines → use replace_lines() (only if safe)

**Why**: Agent chooses better tools for complex edits

---

### 4️⃣ Smart Retry Logic (Optional)
**File**: Create `agents-backend/src/agents/edit_attempt_history.py`

Track failed edits and suggest tool switching after 2 failures:
```python
If replace_lines() fails twice with semantic errors:
  → Suggest replace_method_body() instead
  → Provide reasoning in error message
```

**Why**: Agent escapes infinite retry loops

---

## Expected Results

| Without Fix | With Fix |
|------------|----------|
| Attempt 1: Fails (duplicate @Inject) | Attempt 1: Fails, identifies problem |
| Attempt 2: Fails again (same mistake) | Attempt 2: Succeeds, fixed problem |
| Attempt 3: Fails again | Attempt 3: Succeeds with AllocationStatsService |
| ... Infinite retries ... | ✅ CONVERGED |

---

## Implementation Timeline

| Phase | Components | Time | Impact |
|-------|-----------|------|--------|
| 4A | Validators + Error messages + Prompt | 5 hrs | ⭐⭐⭐ High |
| 4B | Context validation + History tracker | 3.5 hrs | ⭐⭐ Medium |
| Total | Complete fix | 8.5 hrs | ✅ elasticsearch passes |

---

## Files to Read First

In order of importance:
1. `ELASTICSEARCH_FAILURE_ROOT_CAUSE_ANALYSIS.md` - Understand the problem
2. `ELASTICSEARCH_FAILURE_FIX_PROPOSAL.md` - Understand the solution  
3. `ELASTICSEARCH_FAILURE_FIX_IMPLEMENTATION.md` - Implement the fix

---

## Code Changes Summary

```
agents-backend/src/agents/
├── hunk_generator_tools.py
│   ├── verify_guidelines() - Add 3 helper methods (150 lines)
│   ├── _check_duplicate_annotations() - NEW
│   ├── _check_method_brace_balance() - NEW  
│   └── _check_import_validity() - NEW
│
├── file_editor.py
│   └── _FILE_EDITOR_AGENT_SYSTEM - Add tool selection rules (150 lines)
│
├── edit_attempt_history.py - NEW FILE (150 lines)
│   ├── EditAttempt - dataclass
│   ├── EditAttemptHistory - class
│   └── Global tracking functions
│
└── No other files need changes
```

---

## Success Criteria

✅ elasticsearch_41f09bf1 produces correct patch  
✅ No duplicate annotations  
✅ No extra braces  
✅ Converges within 3 agent attempts  
✅ Builds successfully  

---

## Questions?

- **Why not use AST tools?** Elasticsearch test uses Java code transformations that are complex. Phase 4A is faster and proves the approach.
- **Will this fix other tests?** Yes. Any test with annotation/brace issues will benefit.
- **How long to implement?** 8.5 hours estimated, can be done incrementally (Phase 4A first = 5 hours)
- **Is the fix complete?** Phase 4A completes the fix. Phase 4B adds robustness.

---

## Start Here

1. Read the root cause analysis
2. Review the fix proposal
3. Choose to implement Phase 4A first (quick wins)
4. Follow the detailed implementation guide
5. Test against elasticsearch_41f09bf1
6. Validate with `git diff` comparison

**Recommended**: Start with Phase 4A. It will immediately improve the test case success rate.
