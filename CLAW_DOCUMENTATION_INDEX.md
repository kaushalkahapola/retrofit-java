# CLAW Codebase Exploration - Documentation Index

## Overview
Complete analysis of the CLAW Code agent harness system from the Rust implementation. These documents contain everything needed to understand and adapt CLAW's tool implementations, prompt systems, and error handling strategies.

## Documents Created

### 1. CLAW_EXPLORATION_FINDINGS.md (830 lines, 24KB)
**Most Comprehensive Reference**

Main findings organized by topic:
- Tool implementations (file_ops.rs analysis)
- Data structures (StructuredPatchHunk, TextFilePayload, etc.)
- Tool specifications with permission levels
- System prompt architecture and sections
- Error handling patterns and categories
- Line number and context management
- File editing strategies
- Permission system design
- Structured output examples
- Implementation insights and patterns
- Testing examples
- Adaptation checklist for Retrofit

**Best for**: Understanding the complete picture, deep dives into architecture

---

### 2. CLAW_QUICK_REFERENCE.md (183 lines, 5.6KB)
**Fast Lookup Guide**

Quick reference organized for rapid access:
- Source file locations
- Critical data structures
- File operation tools table
- Critical validations checklist
- Error handling pattern
- Line number conventions
- System prompt structure
- Instruction file discovery locations
- Permission tiers
- Best practices
- JSON output examples
- Testing patterns
- Implementation checklist

**Best for**: Quick lookups during implementation, refreshing key concepts

---

### 3. CLAW_CODE_EXAMPLES.md (614 lines, 19KB)
**Concrete Implementation Reference**

Actual code snippets from CLAW with annotations:
1. StructuredPatchHunk definition and usage
2. File reading with line numbers
3. String replacement with validation
4. Comprehensive grep implementation
5. System prompt builder pattern
6. Instruction file discovery algorithm
7. Error handling in conversation loop
8. Tool specifications with JSON schema
9. Path normalization strategies
10. Test examples from actual tests

**Best for**: Copy-paste reference, understanding actual implementation details

---

### 4. CLAW_ANALYSIS_AND_IMPROVEMENTS.md (349 lines, 12KB)
**Pre-existing analysis document**

Strategic analysis and improvement recommendations

---

## Key Findings Summary

### Core Concepts

#### 1. StructuredPatchHunk (Most Important)
The fundamental patch format CLAW uses:
```rust
pub struct StructuredPatchHunk {
    pub old_start: usize,      // 1-indexed
    pub old_lines: usize,      // Count of removed lines
    pub new_start: usize,      // 1-indexed
    pub new_lines: usize,      // Count of added lines
    pub lines: Vec<String>,    // Actual diff lines (+/- prefixed)
}
```

#### 2. File Operations
- `read_file(path, offset?, limit?)` - Pagination support, returns total_lines
- `write_file(path, content)` - Full replacement with patch
- `edit_file(path, old_str, new_str, replace_all?)` - String-based with validation
- `glob_search(pattern, path?)` - File finding with 100-file limit
- `grep_search(input)` - Regex with context and pagination

#### 3. Critical Validations
- `edit_file` checks: old_string != new_string AND old_string exists in file
- `read_file` always returns: total_lines, start_line (1-indexed), num_lines
- All bounds use saturating arithmetic to prevent panics

#### 4. Line Number Convention
- User-facing: 1-indexed (line 1 = first line)
- Internal: 0-indexed for arrays
- Conversion: `line_number = index + 1`

#### 5. Error Handling
- Tools return `Result<String, String>` (JSON or error message)
- Errors marked with `is_error=true` flag in conversation messages
- AI can read errors and reason about recovery

#### 6. System Prompt Structure
1. Introduction + Output Style
2. System (tool model, permissions)
3. Doing Tasks (guidelines)
4. Executing Actions (reversibility)
5. **SYSTEM_PROMPT_DYNAMIC_BOUNDARY** (cache marker)
6. Environment (cwd, date, platform)
7. Project Context (git status/diff)
8. Claw Instructions (discovered from ancestor chain)
9. Runtime Config

#### 7. Instruction File Discovery
Searches from cwd upward through ancestors:
- {dir}/CLAW.md
- {dir}/CLAW.local.md
- {dir}/.claw/CLAW.md
- {dir}/.claw/instructions.md

Deduplicates and truncates to budget (4000 per file, 12000 total)

### Permission Tiers
```
ReadOnly:           read_file, grep_search, glob_search
WorkspaceWrite:     write_file, edit_file
DangerFullAccess:   bash, PowerShell, REPL
```

## Implementation Patterns to Adapt

1. **Validation Before Modification**
   - Always check preconditions (old_string exists)
   - Return specific error types (InvalidInput, NotFound)

2. **Context in Responses**
   - Always include total_lines
   - Always include original_file for comparisons
   - Return absolute canonical paths

3. **Graceful Bounds Handling**
   - Use saturating_sub/min
   - Clamp values instead of panicking
   - Provide pagination with limit/offset

4. **Error as Opportunity**
   - Mark tool failures with is_error flag
   - Provide clear error messages
   - Let AI reason about recovery

5. **Line Number Consistency**
   - 1-indexed externally, 0-indexed internally
   - Convert at boundaries
   - Document in output which convention is used

## File Locations

All original CLAW source files are located at:
```
/media/kaushal/FDrive/retrofit-java/references/claw-code-main/rust/crates/

Key files:
- runtime/src/file_ops.rs       (550 lines) - File operations
- runtime/src/prompt.rs         (795 lines) - Prompt building
- runtime/src/bash.rs           (283 lines) - Shell execution
- runtime/src/conversation.rs   (801 lines) - Agent loop & errors
- tools/src/lib.rs              (1800+ lines) - Tool definitions
```

## How to Use These Documents

### For Quick Implementation
1. Start with CLAW_QUICK_REFERENCE.md
2. Reference CLAW_CODE_EXAMPLES.md for specific implementations
3. Consult CLAW_EXPLORATION_FINDINGS.md for detailed context

### For Deep Understanding
1. Read CLAW_EXPLORATION_FINDINGS.md sections in order
2. Review CLAW_CODE_EXAMPLES.md for concrete implementations
3. Check CLAW_ANALYSIS_AND_IMPROVEMENTS.md for strategic thinking

### For Problem-Solving
1. Check Implementation Checklist in CLAW_QUICK_REFERENCE.md
2. Look up specific error handling in CLAW_EXPLORATION_FINDINGS.md (Section 3)
3. Reference error patterns in CLAW_CODE_EXAMPLES.md (Section 7)

## Key Insights for Retrofit

1. **Patch format is universal** - All changes reported as StructuredPatchHunk
2. **Always include context** - Users need to know total file size
3. **Validation prevents failures** - Check before modifying
4. **Errors are informative** - Mark failures so AI can reason about them
5. **Prompts need boundaries** - Static content can be cached
6. **Instruction discovery is hierarchical** - Walk up the tree
7. **Permission checks matter** - Three-tier system provides clear boundaries
8. **Hooks enable extensibility** - Pre/post execution points
9. **Testing is comprehensive** - All edge cases covered in tests
10. **Paths are always absolute** - Canonicalized for safety

## Statistics

- **Total Documentation**: 1,976 lines across 4 files
- **Source Code Analyzed**: 4,000+ lines from CLAW Rust implementation
- **Core Structures Documented**: 12+ data types with examples
- **Implementation Patterns**: 10+ patterns extracted and documented
- **Tool Operations**: 5 main file tools fully analyzed
- **Code Examples**: 10 concrete implementation examples

## Next Steps

1. Review CLAW_QUICK_REFERENCE.md for key concepts
2. Study CLAW_CODE_EXAMPLES.md for implementation patterns
3. Reference CLAW_EXPLORATION_FINDINGS.md for design decisions
4. Implement StructuredPatchHunk as primary output format
5. Follow validation patterns from edit_file
6. Implement permission tier system
7. Add prompt boundary markers for caching
8. Test all edge cases documented

---

**Last Updated**: April 2, 2026
**Source Repository**: https://github.com/instructkr/claw-code
**Language**: Rust (active implementation)
**Focus**: File operations, prompts, error handling, and tool execution

