# CLAW Implementation Patterns - Quick Reference

## Critical Design Decisions

### 1. Line Number Indexing
- **Internal**: 0-indexed (for slicing and iteration)
- **Output**: 1-indexed (for human display)
- **Conversion**: Always use `index + 1` when returning to user

```rust
// Internal
let start_index = offset.unwrap_or(0).min(lines.len());
let selected = lines[start_index..end_index].join("\n");

// Output
start_line: start_index.saturating_add(1),
```

### 2. File Editing Strategy
CLAW uses **exact string matching** - NO fuzzy matching
- Use `replace()` for replace-all
- Use `replacen(..., 1)` for first-match-only
- Validate before mutation (pre-condition checks)

```rust
// Validation FIRST
if old_string == new_string {
    return Err("strings must differ");
}
if !original_file.contains(old_string) {
    return Err("old_string not found");
}
// THEN mutate
let updated = original_file.replace(old_string, new_string);
```

### 3. Patch Generation
- Single hunk for entire file
- `oldStart` and `newStart` always = 1
- Lines prefixed with `-` (removed) or `+` (added)
- For visualization only, not application

```rust
fn make_patch(original: &str, updated: &str) -> Vec<StructuredPatchHunk> {
    let lines = vec![
        original.lines().map(|l| format!("-{l}")).collect(),
        updated.lines().map(|l| format!("+{l}")).collect(),
    ].concat();
    
    vec![StructuredPatchHunk {
        old_start: 1,
        old_lines: original.lines().count(),
        new_start: 1,
        new_lines: updated.lines().count(),
        lines,
    }]
}
```

### 4. Boundary Safety
Always use safe arithmetic:
```rust
let start = index.saturating_sub(context);
let end = (index + context + 1).min(lines.len());
let remaining = start_index.saturating_add(limit).min(lines.len());
```

### 5. Error Handling Pattern
Errors → Messages (not exceptions)
```rust
match self.tool_executor.execute(&tool_name, &input) {
    Ok(output) => (output, false),
    Err(error) => (error.to_string(), true),  // Convert to message
}
```

### 6. Output Comprehensiveness
Return everything needed for verification:
```rust
EditFileOutput {
    file_path,              // Where it was
    old_string,             // What was searched
    new_string,             // What was inserted
    original_file,          // Full file before
    structured_patch,       // Visualizable diff
    user_modified: false,   // Provenance
    replace_all,            // Parameter echo
}
```

---

## Data Structures to Implement

### StructuredPatchHunk
```rust
pub struct StructuredPatchHunk {
    pub old_start: usize,    // 1-indexed
    pub old_lines: usize,
    pub new_start: usize,    // 1-indexed
    pub new_lines: usize,
    pub lines: Vec<String>,  // With +/- prefix
}
```

### TextFilePayload
```rust
pub struct TextFilePayload {
    pub file_path: String,
    pub content: String,
    pub num_lines: usize,      // Lines in this chunk
    pub start_line: usize,     // 1-indexed
    pub total_lines: usize,    // Lines in whole file
}
```

---

## Tool Specifications

### edit_file
```json
{
  "name": "edit_file",
  "description": "Replace text in a workspace file.",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": { "type": "string" },
      "old_string": { "type": "string" },
      "new_string": { "type": "string" },
      "replace_all": { "type": "boolean" }
    },
    "required": ["path", "old_string", "new_string"]
  },
  "required_permission": "workspace-write"
}
```

### read_file
```json
{
  "name": "read_file",
  "description": "Read a text file from the workspace.",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": { "type": "string" },
      "offset": { "type": "integer", "minimum": 0 },
      "limit": { "type": "integer", "minimum": 1 }
    },
    "required": ["path"]
  },
  "required_permission": "read-only"
}
```

### write_file
```json
{
  "name": "write_file",
  "description": "Write a text file in the workspace.",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": { "type": "string" },
      "content": { "type": "string" }
    },
    "required": ["path", "content"]
  },
  "required_permission": "workspace-write"
}
```

---

## System Prompt Structure

Static sections (before boundary):
1. Introduction
2. Output Style (optional)
3. System rules
4. Doing tasks guidelines
5. Executing actions with care
6. **DYNAMIC BOUNDARY** marker

Dynamic sections (after boundary):
7. Environment context (cwd, date, platform)
8. Project context (git status, instruction files)
9. Runtime configuration
10. Additional instructions (appended)

---

## Key Design Principles

1. **Deterministic**: No fuzzy matching, no guessing
2. **Auditable**: Return full context for verification
3. **Reversible**: File changes are clear and undoable
4. **Safe**: Boundary checks prevent panics
5. **Simple**: Straightforward algorithms over optimization
6. **Comprehensive**: Include metadata in all responses

---

## What's Intentionally NOT Implemented

- No fuzzy/context matching for edits
- No patch application (only generation)
- No file locking or transactions
- No rollback mechanism
- No merge conflict resolution
- No automatic retry on failure
- No line-based patching

These are design choices for simplicity and auditability.

---

## Testing Patterns from CLAW

```rust
#[test]
fn reads_and_writes_files() {
    let path = temp_path("read-write.txt");
    let write_output = write_file(path, "one\ntwo\nthree")?;
    assert_eq!(write_output.kind, "create");
    
    let read_output = read_file(&path, Some(1), Some(1))?;
    assert_eq!(read_output.file.content, "two");  // Second line
}

#[test]
fn edits_file_contents() {
    let path = temp_path("edit.txt");
    write_file(&path, "alpha beta alpha")?;
    let output = edit_file(&path, "alpha", "omega", true)?;
    assert!(output.replace_all);
}
```

---

## Absolute Path Handling

```rust
// For files that must exist
fn normalize_path(path: &str) -> Result<PathBuf> {
    let candidate = if Path::new(path).is_absolute() {
        PathBuf::from(path)
    } else {
        std::env::current_dir()?.join(path)
    };
    candidate.canonicalize()  // Fails if not found
}

// For files being created
fn normalize_path_allow_missing(path: &str) -> Result<PathBuf> {
    let candidate = if Path::new(path).is_absolute() {
        PathBuf::from(path)
    } else {
        std::env::current_dir()?.join(path)
    };
    
    if let Ok(canonical) = candidate.canonicalize() {
        return Ok(canonical);
    }
    
    // Canonicalize parent, then append filename
    if let Some(parent) = candidate.parent() {
        let canonical_parent = parent.canonicalize()?;
        if let Some(name) = candidate.file_name() {
            return Ok(canonical_parent.join(name));
        }
    }
    Ok(candidate)
}
```

