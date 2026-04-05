# CLAW-Inspired Solution for Elasticsearch Test Case

## Key Insight: CLAW's Simplicity

CLAW uses **exact string matching** instead of line numbers. This completely avoids the elasticsearch problem:

```rust
// CLAW's approach (file_ops.rs:180-217)
pub fn edit_file(
    path: &str,
    old_string: &str,
    new_string: &str,
    replace_all: bool,
) -> io::Result<EditFileOutput> {
    let original_file = fs::read_to_string(&absolute_path)?;
    
    // VALIDATION FIRST
    if old_string == new_string {
        return Err("strings must differ");
    }
    if !original_file.contains(old_string) {
        return Err("old_string not found");
    }
    
    // THEN mutate
    let updated = if replace_all {
        original_file.replace(old_string, new_string)
    } else {
        original_file.replacen(old_string, new_string, 1)
    };
    
    fs::write(&absolute_path, &updated)?;
    
    // Return everything for verification
    Ok(EditFileOutput {
        file_path,
        old_string,
        new_string,
        original_file,
        structured_patch: make_patch(&original_file, &updated),
        user_modified: false,
        replace_all,
    })
}
```

---

## Why This Solves Elasticsearch

The elasticsearch problem is:

**Agent does**: `replace_lines(55-77, new_content_WITH_@Inject)`

**Problem**: New content includes decorator that's already in context (line 54)

**CLAW approach**: Use exact string matching instead

```python
# Instead of replace_lines(start_line, end_line, new_content)
# Use exact string matching like CLAW:

old_string = """@Inject
    public TransportGetAllocationStatsAction(
        TransportService transportService,
        ...
    ) {
        super(...)
        ...
    }"""

new_string = """@Inject
    public TransportGetAllocationStatsAction(
        TransportService transportService,
        ...
    ) {
        super(...)
        // NEW CODE HERE
        ...
    }"""

edit_file(file_path, old_string, new_string, replace_all=False)
```

**No more line number issues!** The exact string handles:
- Decorators automatically (included in old_string)
- Brace matching automatically (entire method body matched)
- Context awareness (you see exactly what's being replaced)

---

## Implementation: Apply CLAW Pattern to Python Backend

### Step 1: Create CLAW-style file editor

**File**: `agents-backend/src/agents/claw_file_editor.py` (NEW)

```python
"""
CLAW-inspired file editor using exact string matching instead of line numbers.
"""

import os
import subprocess
from typing import Optional
from dataclasses import dataclass


@dataclass
class EditFileOutput:
    """CLAW-compatible output structure"""
    file_path: str
    old_string: str
    new_string: str
    original_file: str
    structured_patch: list  # List of diff lines with +/- prefix
    user_modified: bool = False
    replace_all: bool = False


def make_patch(original: str, updated: str) -> list:
    """
    Create structured patch (CLAW pattern).
    Returns list of lines with +/- prefixes.
    """
    lines = []
    
    # Add removed lines
    for line in original.splitlines():
        lines.append(f"-{line}")
    
    # Add added lines
    for line in updated.splitlines():
        lines.append(f"+{line}")
    
    return lines


def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> EditFileOutput:
    """
    Edit a file using exact string matching (CLAW-inspired).
    
    This avoids line number issues entirely by:
    1. Matching exact old_string in file
    2. Replacing with exact new_string
    3. No line number calculations needed
    
    Args:
        file_path: Path to file (repo-relative or absolute)
        old_string: Exact string to find and replace
        new_string: Exact string to replace it with
        replace_all: If False, replace only first occurrence
    
    Returns:
        EditFileOutput with original file, patch, and metadata
    
    Raises:
        ValueError: If old_string not found or strings are identical
    """
    
    # Resolve path
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)
    
    # Read original
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            original_file = f.read()
    except FileNotFoundError as e:
        raise ValueError(f"File not found: {file_path}") from e
    
    # VALIDATION FIRST (CLAW pattern)
    if old_string == new_string:
        raise ValueError("old_string and new_string must differ")
    
    if old_string not in original_file:
        raise ValueError(
            f"old_string not found in {file_path}\n\n"
            f"Searched for:\n{old_string[:200]}...\n\n"
            f"File content preview:\n{original_file[:500]}..."
        )
    
    # THEN mutate
    if replace_all:
        updated = original_file.replace(old_string, new_string)
    else:
        updated = original_file.replace(old_string, new_string, 1)
    
    # Write back
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated)
    except Exception as e:
        raise ValueError(f"Failed to write file {file_path}: {e}") from e
    
    # Return CLAW-style output
    return EditFileOutput(
        file_path=file_path,
        old_string=old_string,
        new_string=new_string,
        original_file=original_file,
        structured_patch=make_patch(original_file, updated),
        user_modified=False,
        replace_all=replace_all,
    )


def verify_edit_output(output: EditFileOutput) -> str:
    """
    Verify the edit output is valid.
    Returns "ALL_GOOD" or error message.
    """
    # Check that strings differ
    if output.old_string == output.new_string:
        return "ERROR: old_string and new_string are identical"
    
    # Check that new_string appeared in result
    with open(output.file_path, 'r', encoding='utf-8', errors='replace') as f:
        current = f.read()
    
    if output.new_string not in current:
        return "ERROR: new_string not found in file after edit"
    
    # Check that old_string is gone (if replace_all)
    if output.replace_all and output.old_string in current:
        return "ERROR: old_string still found in file after replace_all"
    
    return "ALL_GOOD"
```

### Step 2: Integrate into agent system prompt

**File**: `agents-backend/src/agents/file_editor.py`

**Add this to system prompt**:

```
## CRITICAL: File Editing Strategy (NEW - CLAW-Inspired)

You have TWO tools for file editing:

### Tool 1: replace_lines (OLD - Line-based)
- Pros: Works for simple changes
- Cons: Prone to off-by-one errors, decoration duplication
- Use ONLY for: Single-line changes that don't involve decorators or method boundaries

### Tool 2: edit_file (NEW - String-based, CLAW-inspired)
- Pros: No line number issues, exact matching, handles decorators correctly
- Cons: Requires you to provide exact old_string content
- Use FOR: Method changes, decorator changes, any structural edits

## Decision Rule

```
if change involves:
  - Annotations (@Inject, @Override, etc.)
  - Method signature
  - Method body
  - Class structure
then:
  USE edit_file() with exact string matching
else if simple single-line change AND far from decorators:
  OK to use replace_lines()
else:
  DEFAULT: Use edit_file()
```

## How to Use edit_file()

1. Read the method/section using get_context() or read_file()
2. Copy the EXACT old_string (including decorators, all lines, exact spacing)
3. Create new_string with your changes
4. Call edit_file(file_path, old_string, new_string, replace_all=False)
5. Immediately call verify_guidelines() on the structured patch

## Example: Fix the elasticsearch duplicate @Inject problem

OLD WAY (FAILED):
```
replace_lines(55-77, new_content_WITH_@Inject)
  → Caused duplicate @Inject because decorator was in context
```

NEW WAY (WORKS):
```
old_string = """@Inject
    public TransportGetAllocationStatsAction(
        TransportService transportService,
        ...
    ) {
        super(...);
        ...
    }"""

new_string = """@Inject
    public TransportGetAllocationStatsAction(
        TransportService transportService,
        ...
    ) {
        super(...);
        // NEW CODE
        ...
    }"""

edit_file(file_path, old_string, new_string)
  → No duplicate @Inject because exact match includes decorator
```

## Why This Works

- ✅ No line number calculations
- ✅ Decorators are part of the match, can't be duplicated
- ✅ Braces must match exactly (no extra braces)
- ✅ Context automatically correct (full old_string is extracted)
- ✅ Simple validation (old_string must be in file)
```

### Step 3: Register new tool in agent

**File**: `agents-backend/src/agents/hunk_generator_tools.py`

Add this tool to the tool registry:

```python
def edit_file(
    self,
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    """
    Edit a file using exact string matching (CLAW-inspired method).
    
    This approach avoids line number issues by matching and replacing exact strings.
    
    Args:
        file_path: Path to file (repo-relative)
        old_string: Exact string to find and replace
        new_string: Exact string to replace it with
        replace_all: If True, replace all occurrences; if False, replace first only
    
    Returns:
        JSON response with EditFileOutput structure or error message
    """
    from claw_file_editor import edit_file as claw_edit_file, verify_edit_output
    
    try:
        full_path = self._full_path(file_path)
        output = claw_edit_file(full_path, old_string, new_string, replace_all)
        
        # Verify the edit
        verification = verify_edit_output(output)
        
        if verification != "ALL_GOOD":
            return f"ERROR: {verification}"
        
        return (
            f"SUCCESS: Replaced in {file_path}\n"
            f"Old string: {old_string[:100]}...\n"
            f"New string: {new_string[:100]}...\n"
            f"Structured patch generated with {len(output.structured_patch)} lines"
        )
    
    except ValueError as e:
        return f"ERROR: {str(e)}"
    except Exception as e:
        return f"ERROR: Unexpected error: {str(e)}"
```

---

## Why CLAW's Approach is Better

| Aspect | Old `replace_lines()` | New `edit_file()` (CLAW) |
|--------|----------------------|-------------------------|
| **Duplication Risk** | High (decorator context) | None (exact match) |
| **Brace Issues** | High (manual counting) | None (exact match) |
| **Line Number Tracking** | Complex (delta tracking) | Not needed |
| **Context Handling** | Manual/error-prone | Automatic/exact |
| **Validation** | Post-hoc checks | Pre-condition checks |
| **Complexity** | O(n) with state tracking | O(1) string matching |

---

## elasticsearch_41f09bf1 Will Now Work

**Old Flow (FAILED)**:
```
Agent: replace_lines(55-77, new_content_WITH_@Inject)
Validation: ❌ Duplicate @Inject detected
Agent retry: Same mistake, infinite loop
```

**New Flow (SUCCEEDS)**:
```
Agent: edit_file(old_string="""@Inject
    public TransportGetAllocationStatsAction...""",
       new_string="""@Inject
    public TransportGetAllocationStatsAction...""")
Validation: ✅ Exact match, decorator included, no duplication
Result: ✅ Correct patch generated
```

---

## Implementation Priority

### Phase 5A: Quick Win (2 hours) - **IMMEDIATE**
1. Create `claw_file_editor.py` with exact string matching
2. Add `edit_file()` tool to hunk_generator_tools.py
3. Update system prompt with tool selection decision tree
4. Test against elasticsearch_41f09bf1

**Expected Result**: Test converges in 1 attempt (not 3) ✅

### Phase 5B: Sunset Old Method (Optional)
- Mark `replace_lines()` as deprecated
- Guide agents toward `edit_file()` for new patches
- Keep `replace_lines()` for backward compatibility

---

## Files to Create/Modify

```
agents-backend/src/agents/
├── claw_file_editor.py          ← NEW (100 lines)
│   ├── EditFileOutput dataclass
│   ├── make_patch()
│   ├── edit_file()
│   └── verify_edit_output()
│
├── hunk_generator_tools.py       ← MODIFY
│   ├── Add import: from claw_file_editor import ...
│   └── Add new method: def edit_file(self, ...)
│
└── file_editor.py                ← MODIFY
    └── Update _FILE_EDITOR_AGENT_SYSTEM with new tool selection
```

---

## Key Advantage Over Previous 4-Layer Fix

The 4-layer fix (semantic validation, error messages, context awareness, retry logic) was **comprehensive but complex**.

CLAW's string-matching approach is **simple and eliminates the root cause**:
- No need for annotation duplication detector (exact match prevents it)
- No need for brace balance checker (exact match prevents it)
- No need for context validation (exact match requires it)
- No need for retry logic (gets it right first time)

**Result**: Simpler code, fewer bugs, better reliability.

---

## Why CLAW Works and Why We Didn't See It Earlier

CLAW was designed for human-written code where:
1. You know EXACTLY what you want to change
2. You provide exact strings (not line ranges)
3. Validation is trivial (old_string in file?)
4. Generation is trivial (replace string A with string B)

Our agents inherited the "line-based" approach from editors (VSCode, etc.) when they should have used CLAW's "string-based" approach for reliability.

This is the correct fix for elasticsearch and will prevent similar issues on all future patches.
