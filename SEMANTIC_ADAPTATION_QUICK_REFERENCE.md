# Semantic Adaptation for Anchor Text Not Found - Quick Reference

## Problem
Phase 3 (File Editor) fails when "anchor text not found" during edit application, with no semantic understanding of *why* the anchor is missing.

## Current Behavior
```
Edit attempt: old_string anchor not found
  ↓
Try whitespace-agnostic matching (4 passes)
  ↓
Still failing? → Validation returns error
  ↓
Retry loop decides: remap vs. retry generation
  ↓
No integration with semantic analysis tools
```

## Root Causes NOT Addressed
1. **Method renamed** - old_string won't match but renamed version might
2. **Method refactored** - structure changed but semantics preserved
3. **Code moved to different file** - exists elsewhere in codebase
4. **Class split/merged** - method body moved to sibling class
5. **Method signature changed** - API evolution not detected

## Semantic Tools Available (Not Currently Used in Failure Recovery)

### 1. Method Fingerprinting
```python
from utils.method_fingerprinter import MethodFingerprinter

fp = MethodFingerprinter()
match = fp.find_match(
    old_method_name="processRequest",
    old_signature="void processRequest(Request r)",
    old_code="... method body ...",
    old_calls=["validate()", "execute()", "log()"],
    candidate_methods=[...]  # from target file
)
# Returns: {match, confidence, reason}
# Tiers: Exact Name → Signature → Name Sim → Call Graph
```

**Why it works**: Detects renamed/refactored methods via structure similarity

### 2. Structural Class Matching
```python
from utils.structural_matcher import RichNode, calculate_structure_score

mainline_node = RichNode(mainline_class_data)
target_node = RichNode(target_class_data)
score = calculate_structure_score(mainline_node, target_node)
# Returns: 0.0-1.0
# Score weights:
#   - Inheritance (superclass + interfaces): 0.3
#   - Outgoing calls ("Social Network"): 0.4
#   - Fields: 0.1
#   - Name similarity: 0.2
```

**Why it works**: Detects refactored classes by comparing structure, not just names

### 3. File Content APIs
```python
toolkit = HunkGeneratorToolkit(target_repo_path)

# Find where anchor text actually is
matches = toolkit.grep_in_file(
    file_path="MyClass.java",
    search_text="processRequest",
    is_regex=False
)
# Returns: line numbers where text appears

# See actual file content around insertion point
window = toolkit.read_file_window(
    file_path="MyClass.java",
    center_line=150,
    radius=15
)
# Returns: numbered lines (center-15 to center+15)

# Verify context before committing
result = toolkit.verify_context_at_line(
    file_path="MyClass.java",
    line_number=150,
    expected_text="private void processRequest() {"
)
# Returns: EXACT_MATCH | TRIMMED_MATCH | NEARBY_MATCH | NOT_FOUND
```

**Why it works**: Actual file inspection, no guessing

### 4. Full-Repo Search
```python
# From Phase 2 ReasoningToolkit (available in reasoning_tools.py)
toolkit.grep_repo(
    search_text="processRequest",
    is_regex=False
)
# Search entire codebase for snippet
# If found in different file → code moved!

toolkit.git_pickaxe(
    file_path="OldFile.java",
    snippet="processRequest"
)
# Trace history: was method renamed? refactored? deleted?
# Returns: git log output showing where code moved to
```

**Why it works**: Detects code movement and history

## Implementation Strategy (Phase 3 Failure Recovery)

### When Anchor Resolution Fails

```python
# Current location: file_editor.py:_apply_edit_deterministically()

if not resolved_old:  # Anchor not found after 4-pass matching
    # NEW: Before giving up, try semantic analysis
    
    # Step 1: Method fingerprinting
    target_methods = extract_methods_from_file(target_file)
    fp = MethodFingerprinter()
    for method in target_methods:
        score = fp.find_match(
            old_method_name=infer_method_name(old_string),
            old_signature=infer_signature(old_string),
            old_code=old_string,
            old_calls=infer_calls(old_string),
            candidate_methods=target_methods
        )
        if score.confidence > 0.75:
            # Found semantically equivalent method!
            # Update old_string to match target and retry
            resolved_old = score.match
            break
    
    # Step 2: Full-repo search (if fingerprinter fails)
    if not resolved_old:
        matches = grep_repo(old_string, is_regex=False)
        if matches:
            if len(matches) == 1:
                # Found elsewhere! Code moved!
                return semantic_failure("code_moved", matches[0])
            else:
                # Multiple matches - ambiguous
                return semantic_failure("code_ambiguous", matches)
    
    # Step 3: Git history (if search fails)
    if not resolved_old:
        history = git_pickaxe(target_file, old_string)
        if "renamed" in history or "deleted" in history:
            return semantic_failure("code_renamed_or_deleted", history)
```

### Routing to Correct Retry Path

```python
# Current location: graph.py:route_validation()

# After validation failure with anchor error:
semantic_diagnosis = get_semantic_failure_reason(error_context)

if semantic_diagnosis == "code_moved":
    # Method exists but in different file
    return "structural_locator"  # Remap to correct file

elif semantic_diagnosis == "code_renamed_or_deleted":
    # History shows it changed
    return "structural_locator"  # Remap with rename hints

elif semantic_diagnosis == "semantically_equivalent_found":
    # Fingerprinter found match with high confidence
    # Retry with updated anchor
    return "hunk_generator"  # Retry with semantic context

else:
    # Standard retry
    return "hunk_generator"
```

## Error Information to Capture

### Enhanced Validation Error
```python
@dataclass
class HunkValidationError:
    # ... existing fields ...
    
    # NEW: Semantic analysis results
    semantic_analysis: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "method_fingerprints": [
    #         {"match": candidate, "confidence": 0.85, "reason": "Call Graph Match"}
    #     ],
    #     "grep_results": [
    #         {"file": "OtherFile.java", "line": 42}
    #     ],
    #     "git_history": "... history output ...",
    #     "diagnosis": "code_moved" | "code_renamed" | "semantically_equivalent"
    # }
```

## Integration Checklist

- [ ] Phase 2 (Structural Locator) computes and returns `anchor_confidence` + `anchor_reason`
- [ ] Phase 2 confidence propagated to Phase 3 via `mapped_target_context`
- [ ] Phase 3 checks confidence before applying edits
- [ ] Phase 3 calls MethodFingerprinter on anchor failure
- [ ] Phase 3 calls grep_repo on fingerprint failure
- [ ] Phase 3 records semantic diagnosis in validation error
- [ ] Phase 4 (Validation) enhances error with semantic context
- [ ] graph.py routes based on semantic diagnosis
- [ ] Testing: validate with intentionally refactored code samples

## Key Files to Modify

| File | Change | Reason |
|------|--------|--------|
| `file_editor.py` | Add semantic analysis in `_apply_edit_deterministically()` + `_retry_with_file_check()` | Anchor failure recovery |
| `validation_models.py` | Add `semantic_analysis` field to `HunkValidationError` | Error enrichment |
| `graph.py` | Add semantic-based routing in `route_validation()` | Smart rerouting |
| `structural_locator.py` | Ensure `anchor_confidence` + `anchor_reason` in output | Phase 2→3 signal |

## Low-Hanging Fruit (Start Here)

1. **Integrate MethodFingerprinter call** (5-10 lines)
   - Location: file_editor.py:_retry_with_file_check()
   - After grep fails, try fingerprinting

2. **Propagate Phase 2 confidence** (2-3 lines)
   - Location: file_editor.py check before applying edits
   - Route low-confidence files differently

3. **Enhanced error context** (10-15 lines)
   - Location: validation_tools.py error extraction
   - Add semantic_analysis field to error

4. **Smart routing** (20-30 lines)
   - Location: graph.py:route_validation()
   - Add check for semantic_diagnosis

## Expected Impact

**Before**: 
- Anchor not found → random retry or fail
- 3+ attempts to same file
- No semantic insight into divergence

**After**:
- Anchor not found → semantic analysis in <100ms
- Detect renamed/refactored methods
- Route to correct retry path (remap vs. retry-with-context)
- Reduce redundant retries
- Better error diagnostics for debugging

## References

- MethodFingerprinter: `agents-backend/src/utils/method_fingerprinter.py`
- StructuralMatcher: `agents-backend/src/utils/structural_matcher.py`
- HunkGeneratorToolkit: `agents-backend/src/agents/hunk_generator_tools.py`
- ReasoningToolkit: `agents-backend/src/agents/reasoning_tools.py` (for grep_repo, git_pickaxe)
- Validation Models: `agents-backend/src/utils/validation_models.py`
- File Editor: `agents-backend/src/agents/file_editor.py`
- Graph Router: `agents-backend/src/graph.py`

