# Applying CLAW File Operations to H-MABS: Complete Implementation Guide

## Executive Summary

CLAW has solved the exact problems we're facing:
1. **Line number management** (0-indexed internally, 1-indexed for display)
2. **File editing** (exact string matching, pre-validation before mutation)
3. **Patch generation and validation** (structured hunks with line tracking)
4. **Error handling** (errors as messages, not exceptions)

This guide shows how to directly apply CLAW's proven solutions to H-MABS.

---

## Problem vs CLAW Solution

### Problem 1: Line Number Offsets
**What we're facing:**
- Hunks applied top-to-bottom cause subsequent hunks to have wrong line numbers
- Multiple hunks on same file can't be applied because offsets aren't recalculated
- Line number tracking is error-prone

**CLAW's Solution:**
```python
# Internal: 0-indexed
start_index = offset.unwrap_or(0).min(lines.len())

# Output: 1-indexed
start_line: usize = start_index.saturating_add(1)
```
- Uses 0-indexed internally for array slicing
- Converts to 1-indexed only for display/output
- Separates concern: storage vs presentation

**For H-MABS:** Apply the same pattern in validation_tools.py

---

### Problem 2: File Editing with Context Matching
**What we're facing:**
- Hunks fail because context doesn't match exactly
- Fuzzy matching doesn't work reliably
- Line numbers shift during patching

**CLAW's Solution:**
```rust
// Validation BEFORE mutation
if !original_file.contains(old_string) {
    return Err("old_string not found in file");
}

// Only then mutate
fs::write(&absolute_path, &updated)?;
```
- Exact string matching only (no fuzzy)
- Pre-validation before file write
- Returns comprehensive output (original + patch)

**For H-MABS:** Replace fuzzy matching with exact matching in validation

---

### Problem 3: Patch Generation
**What we're facing:**
- Multiple hunks per file cause complex line number calculations
- Patch headers are error-prone
- No clear "before/after" view

**CLAW's Solution:**
```rust
fn make_patch(original: &str, updated: &str) -> Vec<StructuredPatchHunk> {
    let mut lines = Vec::new();
    for line in original.lines() {
        lines.push(format!("-{line}"));  // Removed lines
    }
    for line in updated.lines() {
        lines.push(format!("+{line}"));  // Added lines
    }
    
    vec![StructuredPatchHunk {
        old_start: 1,
        old_lines: original.lines().count(),
        new_start: 1,
        new_lines: updated.lines().count(),
        lines,
    }]
}
```
- Creates ONE hunk per file (not multi-hunk)
- Always uses old_start=1, new_start=1 (full file replacement)
- Stores line counts explicitly
- Lines prefixed with +/- for clarity

**For H-MABS:** Apply to our make_patch logic in validation_tools.py

---

## Step-by-Step Implementation for H-MABS

### Step 1: Create Python Versions of CLAW Data Structures

Add to `src/utils/file_operations_models.py`:

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class StructuredPatchHunk:
    """Exact Python equivalent of CLAW's StructuredPatchHunk"""
    old_start: int      # 1-indexed
    old_lines: int
    new_start: int      # 1-indexed
    new_lines: int
    lines: List[str]    # Lines with +/- prefixes
    
    def to_dict(self):
        """Convert to JSON-friendly dict with camelCase"""
        return {
            "oldStart": self.old_start,
            "oldLines": self.old_lines,
            "newStart": self.new_start,
            "newLines": self.new_lines,
            "lines": self.lines,
        }

@dataclass
class TextFilePayload:
    """Exact Python equivalent of CLAW's TextFilePayload"""
    file_path: str
    content: str
    num_lines: int      # Lines in this chunk
    start_line: int     # 1-indexed for display
    total_lines: int    # Total lines in file
    
    def to_dict(self):
        return {
            "filePath": self.file_path,
            "content": self.content,
            "numLines": self.num_lines,
            "startLine": self.start_line,
            "totalLines": self.total_lines,
        }

@dataclass
class EditFileOutput:
    """Exact Python equivalent of CLAW's EditFileOutput"""
    file_path: str
    old_string: str
    new_string: str
    original_file: str
    structured_patch: List[StructuredPatchHunk]
    user_modified: bool = False
    replace_all: bool = False
    git_diff: Optional[dict] = None
    
    def to_dict(self):
        return {
            "filePath": self.file_path,
            "oldString": self.old_string,
            "newString": self.new_string,
            "originalFile": self.original_file,
            "structuredPatch": [p.to_dict() for p in self.structured_patch],
            "userModified": self.user_modified,
            "replaceAll": self.replace_all,
            "gitDiff": self.git_diff,
        }
```

### Step 2: Implement CLAW's File Operations Pattern

Add to `src/utils/file_operations.py`:

```python
import os
from typing import Optional, Tuple
from file_operations_models import StructuredPatchHunk, TextFilePayload, EditFileOutput

def make_patch(original: str, updated: str) -> list[StructuredPatchHunk]:
    """
    CLAW's approach: Create a SINGLE hunk for the entire file.
    This avoids line number offset issues entirely.
    """
    lines = []
    
    # Add removed lines
    for line in original.splitlines():
        lines.append(f"-{line}")
    
    # Add added lines
    for line in updated.splitlines():
        lines.append(f"+{line}")
    
    # Single hunk for entire file
    return [StructuredPatchHunk(
        old_start=1,  # Always 1 (full file)
        old_lines=len(original.splitlines()),
        new_start=1,  # Always 1 (full file)
        new_lines=len(updated.splitlines()),
        lines=lines,
    )]

def read_file(
    path: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict:
    """
    Read file with CLAW's line number handling:
    - Internal: 0-indexed
    - Output: 1-indexed
    """
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    lines = content.splitlines()
    
    # 0-indexed internally
    start_index = min(offset or 0, len(lines))
    end_index = min(
        start_index + (limit or len(lines)),
        len(lines)
    )
    
    selected_lines = lines[start_index:end_index]
    selected_content = '\n'.join(selected_lines)
    
    # Return payload with 1-indexed start_line
    payload = TextFilePayload(
        file_path=os.path.abspath(path),
        content=selected_content,
        num_lines=max(0, end_index - start_index),
        start_line=start_index + 1,  # Convert to 1-indexed
        total_lines=len(lines),
    )
    
    return {
        "type": "text",
        "file": payload.to_dict(),
    }

def edit_file(
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> EditFileOutput:
    """
    CLAW's file editing pattern:
    1. Pre-validation before mutation
    2. Exact string matching (no fuzzy)
    3. Return comprehensive output
    """
    
    # Read original
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        original_file = f.read()
    
    # Pre-validation (BEFORE mutation)
    if old_string == new_string:
        raise ValueError("old_string and new_string must differ")
    
    if old_string not in original_file:
        raise ValueError(f"old_string not found in file: {path}")
    
    # Perform replacement (exact, no fuzzy)
    if replace_all:
        updated = original_file.replace(old_string, new_string)
    else:
        # Replace only first occurrence
        updated = original_file.replace(old_string, new_string, 1)
    
    # Write to disk
    with open(path, 'w', encoding='utf-8') as f:
        f.write(updated)
    
    # Return comprehensive output
    return EditFileOutput(
        file_path=os.path.abspath(path),
        old_string=old_string,
        new_string=new_string,
        original_file=original_file,
        structured_patch=make_patch(original_file, updated),
        user_modified=False,
        replace_all=replace_all,
    )
```

### Step 3: Integrate CLAW Patterns into Validation Tools

Modify `src/agents/validation_tools.py`:

```python
def apply_hunk_with_claw_approach(
    self,
    target_file_path: str,
    hunk_text: str,
) -> Dict:
    """
    Apply CLAW's approach to hunk application:
    - Validate BEFORE mutation
    - Use exact string matching
    - Return structured patch for verification
    """
    
    # Step 1: Read the file
    with open(os.path.join(self.target_repo_path, target_file_path), 'r') as f:
        original_content = f.read()
    
    # Step 2: Parse the hunk to extract old/new strings
    # (this requires extracting context from hunk_text)
    old_string, new_string = self._extract_strings_from_hunk(hunk_text)
    
    # Step 3: Pre-validate (CLAW approach)
    if old_string not in original_content:
        return {
            "success": False,
            "error": "context_not_found",
            "message": f"Could not find context in {target_file_path}",
            "suggestions": [
                "Context lines may have changed",
                "Try running git diff to see current state",
                "Verify file line numbers match target repo",
            ]
        }
    
    # Step 4: Apply change
    updated_content = original_content.replace(old_string, new_string, 1)
    
    # Step 5: Write to disk
    with open(os.path.join(self.target_repo_path, target_file_path), 'w') as f:
        f.write(updated_content)
    
    # Step 6: Return comprehensive output (CLAW pattern)
    patch = make_patch(original_content, updated_content)
    
    return {
        "success": True,
        "file_path": target_file_path,
        "original_content": original_content,
        "updated_content": updated_content,
        "structured_patch": [p.to_dict() for p in patch],
        "message": "Hunk applied successfully",
    }
```

### Step 4: Update Phase 4 to Use CLAW Approach

Replace the current `apply_adapted_hunks` method to use exact string matching:

```python
def apply_adapted_hunks_claw_style(self, code_hunks: list, test_hunks: list) -> Dict:
    """
    Apply hunks using CLAW's proven approach:
    - Extract exact strings from hunk context
    - Pre-validate before mutation
    - Apply one hunk at a time
    - Return structured output with patches
    """
    
    all_hunks = list(code_hunks) + list(test_hunks)
    results = []
    applied_files = []
    
    for hunk in all_hunks:
        target_file = hunk.get("target_file")
        hunk_text = hunk.get("hunk_text")
        
        # Extract context from hunk
        old_context, new_context = self._extract_hunk_context(hunk_text)
        
        try:
            # Apply using CLAW approach
            result = self.apply_hunk_with_claw_approach(target_file, old_context, new_context)
            
            if result["success"]:
                results.append({
                    "hunk_id": hunk.get("hunk_id"),
                    "file": target_file,
                    "status": "applied",
                })
                if target_file not in applied_files:
                    applied_files.append(target_file)
            else:
                # Hunk failed - attach error metadata
                results.append({
                    "hunk_id": hunk.get("hunk_id"),
                    "file": target_file,
                    "status": "failed",
                    "error": result.get("error"),
                    "suggestions": result.get("suggestions", []),
                })
        except Exception as e:
            results.append({
                "hunk_id": hunk.get("hunk_id"),
                "file": target_file,
                "status": "error",
                "error_message": str(e),
            })
    
    # Check results
    failed_hunks = [r for r in results if r["status"] != "applied"]
    
    if failed_hunks:
        return {
            "success": False,
            "applied_files": applied_files,
            "results": results,
            "failed_count": len(failed_hunks),
            "message": f"{len(failed_hunks)} hunks failed to apply",
        }
    
    return {
        "success": True,
        "applied_files": applied_files,
        "results": results,
        "message": "All hunks applied successfully",
    }
```

---

## Key CLAW Principles to Apply

### 1. **Line Number Convention**
- **Internal processing**: Use 0-indexed (for slicing, array operations)
- **Output/Display**: Convert to 1-indexed (for human readability)
- **Always explicitly convert**: `display_line = internal_index + 1`

### 2. **Exact String Matching**
- No fuzzy matching or context inference
- Match the EXACT old_string from hunk
- If not found, report clearly (don't guess)
- Use Python's `replace(old, new, 1)` for single occurrence

### 3. **Pre-Mutation Validation**
```python
# BEFORE writing to disk:
if old_string not in file_content:
    return error

# ONLY THEN write
file.write(new_content)
```

### 4. **Comprehensive Output**
Always return:
- Original file content (for verification)
- New file content (what was written)
- Structured patch (how it changed)
- Metadata (line counts, file path)
- Error details (if applicable)

### 5. **Error Handling as Messages**
- Convert errors to structured messages
- Include suggestions for fixing
- Don't raise exceptions in tool layer
- Return error details to agent for retry

---

## Testing CLAW Approach with elasticsearch_734dd070

When you test with the new approach:

1. **Phase 3** extracts exact context from each hunk
2. **Phase 4** does exact string matching (no fuzzy)
3. For each hunk:
   - Read file (returns TextFilePayload)
   - Check if old_string exists (pre-validation)
   - Apply change (write to disk)
   - Return structured patch (for verification)
4. **No line number tracking needed** - single hunk per file handles it
5. **All failures visible** - agent sees exact error

### Expected Results:
- ✅ All 5 hunks attempt application
- ✅ Exact string match or clear error message
- ✅ Structured patches for verification
- ✅ No "magic" line number calculations
- ✅ Ready for agent-driven retry if needed

---

## Files to Create/Modify

1. **NEW**: `src/utils/file_operations_models.py`
   - CLAW data structures in Python
   - ~100 lines

2. **NEW**: `src/utils/file_operations.py`
   - CLAW functions in Python (read_file, edit_file, etc)
   - ~200 lines

3. **MODIFY**: `src/agents/validation_tools.py`
   - Add `apply_hunk_with_claw_approach()`
   - Update Phase 4 logic
   - ~150 lines of new/modified code

4. **MODIFY**: `src/agents/hunk_generator.py`
   - Extract exact context from hunks
   - Add `_extract_hunk_context()` method
   - ~50 lines

---

## Advantages of CLAW Approach

| Aspect | Current | CLAW |
|--------|---------|------|
| **Line numbers** | Complex offset tracking | Simple 0/1 indexed pattern |
| **String matching** | Fuzzy, error-prone | Exact, clear failures |
| **Mutation safety** | Write first, validate | Validate first, then write |
| **Output clarity** | Generic success/fail | Structured patch + metadata |
| **Error messages** | Vague | Specific + suggestions |
| **Multi-hunk files** | Complex calculations | One hunk per file (simple) |
| **Agent retry** | Difficult | Easy (has full context) |

---

## Next Steps

1. Create file_operations_models.py with CLAW data structures
2. Create file_operations.py with CLAW functions
3. Integrate into validation_tools.py Phase 4
4. Test with elasticsearch_734dd070
5. Verify all 5 hunks apply (or clear error messages)
6. Enable Phase 4→Phase 3 retry loop with full context

This approach directly solves our line number and patching issues by using CLAW's proven patterns!
