# CLAW Codebase Exploration - Detailed Findings

## Project Overview
- **Repository**: Claw Code (https://github.com/instructkr/claw-code)
- **Language**: Rust (active implementation, Python port also exists)
- **Architecture**: Agent harness system with runtime, tools, prompts, and orchestration

---

## 1. TOOL IMPLEMENTATIONS

### 1.1 File Operations Tools (file_ops.rs)
**Location**: `/rust/crates/runtime/src/file_ops.rs` (550 lines)

#### Core Data Structures:

```rust
// Text file payload for read operations
pub struct TextFilePayload {
    pub file_path: String,
    pub content: String,
    pub num_lines: usize,           // Number of lines in selected range
    pub start_line: usize,          // 1-indexed start line number
    pub total_lines: usize,         // Total lines in entire file
}

// Structured patch representation
pub struct StructuredPatchHunk {
    pub old_start: usize,           // Starting line in original file
    pub old_lines: usize,           // Number of lines removed
    pub new_start: usize,           // Starting line in new file
    pub new_lines: usize,           // Number of lines added
    pub lines: Vec<String>,         // Actual patch lines (prefixed with +/-)
}

// Write/edit output tracking changes
pub struct WriteFileOutput {
    pub kind: String,               // "create" or "update"
    pub file_path: String,
    pub content: String,
    pub structured_patch: Vec<StructuredPatchHunk>,  // Diff representation
    pub original_file: Option<String>,               // Previous content
    pub git_diff: Option<serde_json::Value>,         // Optional git format diff
}

pub struct EditFileOutput {
    pub file_path: String,
    pub old_string: String,
    pub new_string: String,
    pub original_file: String,
    pub structured_patch: Vec<StructuredPatchHunk>,
    pub user_modified: bool,        // Track if user modified output
    pub replace_all: bool,          // Whether replace_all flag was used
    pub git_diff: Option<serde_json::Value>,
}
```

#### Key File Operations:

1. **read_file(path, offset, limit)**
   - Normalizes path (handles relative and absolute)
   - Splits file into lines
   - Returns line range with 1-indexed start_line
   - Includes total_lines context (not just selected count)
   - Error: Returns io::Result with path not found errors

2. **write_file(path, content)**
   - Normalizes path (allows missing files)
   - Creates parent directories automatically
   - Generates structured patch comparing to original
   - Returns "create" or "update" type
   - Error: IO errors propagated

3. **edit_file(path, old_string, new_string, replace_all)**
   - **Critical validations**:
     - old_string != new_string (prevents no-op edits)
     - old_string must exist in file (returns NotFound error)
   - replace_all controls: single replacement vs. replace all occurrences
   - Generates structured patch
   - Error: InvalidInput for bad params, NotFound for string not found

4. **glob_search(pattern, path)**
   - Uses glob crate for pattern matching
   - Sorts results by modification time (reverse chronological)
   - Truncates at 100 results with truncation flag
   - Returns: filenames, count, duration_ms, truncation status

5. **grep_search(input)**
   - Regex-based search with multiline support
   - Output modes: "files_with_matches", "count", "content"
   - Context options: -B (before), -A (after), -C/-context (both)
   - Line number tracking with 1-indexed lines
   - Limit/offset support for pagination
   - Returns: matching files, line count, match count, optional content

#### Line Number Handling Strategy:
```
- 1-indexed throughout (user-facing)
- start_index (0-indexed) used internally
- Conversion: start_line = start_index.saturating_add(1)
- Range calculation: [start_index..end_index] then joined with newlines
- Patch hunks use 1-indexed old_start and new_start
```

#### Patch Generation (make_patch):
```rust
fn make_patch(original: &str, updated: &str) -> Vec<StructuredPatchHunk> {
    // Simple diff: all lines prefixed with - for original, + for new
    // Single hunk with:
    //   old_start: 1, old_lines: original.lines().count()
    //   new_start: 1, new_lines: updated.lines().count()
}
```

---

### 1.2 Tool Specifications (tools/src/lib.rs)
**Location**: `/rust/crates/tools/src/lib.rs` (1800+ lines)

#### Tool Spec Structure:
```rust
pub struct ToolSpec {
    pub name: &'static str,
    pub description: &'static str,
    pub input_schema: Value,              // JSON schema
    pub required_permission: PermissionMode,
}

// Permission levels
pub enum PermissionMode {
    ReadOnly,
    WorkspaceWrite,
    DangerFullAccess,
}
```

#### Core File Tools:

| Tool | Permission | Input Schema | Purpose |
|------|-----------|--------------|---------|
| `read_file` | ReadOnly | path, offset?, limit? | Read file content with pagination |
| `write_file` | WorkspaceWrite | path, content | Full file replacement |
| `edit_file` | WorkspaceWrite | path, old_string, new_string, replace_all? | String replacement in file |
| `glob_search` | ReadOnly | pattern, path? | Find files by glob pattern |
| `grep_search` | ReadOnly | pattern, path?, glob?, output_mode?, -B?, -A?, -C?, -n?, -i?, type?, head_limit?, offset?, multiline? | Regex search in files |
| `bash` | DangerFullAccess | command, timeout?, description?, run_in_background?, dangerouslyDisableSandbox? | Execute shell commands |

#### Tool Descriptions (Key):
- **read_file**: "Read a text file from the workspace."
- **write_file**: "Write a text file in the workspace."
- **edit_file**: "Replace text in a workspace file."
- **glob_search**: "Find files by glob pattern."
- **grep_search**: "Search file contents with a regex pattern."

---

## 2. PROMPTS AND INSTRUCTIONS

### 2.1 System Prompt Builder (prompt.rs)
**Location**: `/rust/crates/runtime/src/prompt.rs` (795 lines)

#### System Prompt Structure:
```rust
pub struct SystemPromptBuilder {
    output_style_name: Option<String>,
    output_style_prompt: Option<String>,
    os_name: Option<String>,
    os_version: Option<String>,
    append_sections: Vec<String>,
    project_context: Option<ProjectContext>,
    config: Option<RuntimeConfig>,
}

pub struct ProjectContext {
    pub cwd: PathBuf,
    pub current_date: String,
    pub git_status: Option<String>,
    pub git_diff: Option<String>,
    pub instruction_files: Vec<ContextFile>,
}

pub struct ContextFile {
    pub path: PathBuf,
    pub content: String,
}
```

#### Prompt Sections (in order):

1. **Introduction** (get_simple_intro_section)
   - Base: "You are an interactive agent that helps users with software engineering tasks."
   - With style: describes output style compliance

2. **Output Style** (optional)
   - User-provided formatting/tone guidelines
   - Format: `# Output Style: {name}\n{prompt}`

3. **System** (get_simple_system_section)
   - Tool execution model
   - Permission modes
   - System reminders and prompt injection warnings
   - Hook feedback model
   - Automatic message compression

4. **Doing Tasks** (get_simple_doing_tasks_section)
   - Read before changing code
   - Keep changes tightly scoped
   - Don't create unneeded files
   - Diagnose failures before switching tactics
   - Security vulnerability warnings (injection, XSS, SQL)
   - Faithful outcome reporting

5. **Executing Actions** (get_actions_section)
   - Reversibility considerations
   - Local reversible actions (editing, testing)
   - High blast radius actions need explicit authorization

6. **SYSTEM_PROMPT_DYNAMIC_BOUNDARY**
   - Marks boundary between static and dynamic content

7. **Environment Context** (environment_section)
   - Model family: "Opus 4.6"
   - Working directory
   - Date
   - Platform info

8. **Project Context** (render_project_context)
   - Current date
   - Working directory
   - Instruction file count
   - Git status snapshot (if available)
   - Git diff snapshot (if available)

9. **Claw Instructions** (render_instruction_files)
   - Discovers from ancestor chain: CLAW.md, CLAW.local.md, .claw/CLAW.md, .claw/instructions.md
   - Deduplicates identical content
   - Truncates to budget: MAX_INSTRUCTION_FILE_CHARS = 4000, MAX_TOTAL_INSTRUCTION_CHARS = 12000
   - Includes file scope information

10. **Runtime Config** (render_config_section)
    - Loaded settings files
    - Configuration values as JSON

#### Instruction File Discovery:
```
Search pattern (bottom-up from cwd):
  - {dir}/CLAW.md
  - {dir}/CLAW.local.md
  - {dir}/.claw/CLAW.md
  - {dir}/.claw/instructions.md
  
For each ancestor up to filesystem root
```

#### Git Integration:
```bash
# Git status
git --no-optional-locks status --short --branch

# Staged changes
git diff --cached

# Unstaged changes
git diff
```

---

## 3. ERROR HANDLING IN TOOLS

### 3.1 Error Types

```rust
// File operations return io::Result
pub enum io::ErrorKind {
    NotFound,
    InvalidInput,
    // ... others
}

// Tool execution returns Result<String, String>
pub fn execute_tool(name: &str, input: &Value) -> Result<String, String>

// Deserialization errors converted to String
fn from_value<T: for<'de> Deserialize<'de>>(input: &Value) -> Result<T, String> {
    serde_json::from_value(input.clone()).map_err(|error| error.to_string())
}
```

### 3.2 Error Handling Patterns

#### File Operations:
```
read_file:
  - Path not found -> io::Error(NotFound)
  - Line out of range -> saturating_sub/min to clamp gracefully

write_file:
  - Parent dir creation failure -> propagated io::Error
  - File write failure -> propagated io::Error

edit_file:
  - old_string == new_string -> io::Error(InvalidInput, "strings must differ")
  - old_string not found -> io::Error(NotFound, "old_string not found in file")
  - File read failure -> propagated io::Error

grep_search:
  - Invalid regex pattern -> io::Error(InvalidInput, regex_error.to_string())
  - Invalid glob pattern -> io::Error(InvalidInput, glob_error.to_string())
  - File read errors -> silently continue (skip unreadable files)
```

#### Tool Execution Layer:
```rust
fn run_read_file(input: ReadFileInput) -> Result<String, String> {
    to_pretty_json(read_file(&input.path, input.offset, input.limit).map_err(io_to_string)?)
}

fn io_to_string(error: std::io::Error) -> String {
    error.to_string()  // Convert IO error to string message
}

fn to_pretty_json<T: serde::Serialize>(value: T) -> Result<String, String> {
    serde_json::to_string_pretty(&value).map_err(|error| error.to_string())
}
```

### 3.3 Error Recovery in Conversation Loop

```rust
// From conversation.rs - Tool error handling
match self.tool_executor.execute(&tool_name, &input) {
    Ok(output) => (output, false),
    Err(error) => (error.to_string(), true),  // Tool errors marked as is_error=true
}

// Tool result message includes error flag
ConversationMessage::tool_result(
    tool_use_id,
    tool_name,
    output_string,
    is_error,  // true if execution failed
)
```

### 3.4 Error Categories:

1. **Validation Errors**
   - Invalid input parameters
   - Schema validation failures
   - Missing required fields

2. **File Not Found Errors**
   - File doesn't exist
   - Path is invalid
   - Permission denied

3. **Pattern Errors**
   - Invalid regex
   - Invalid glob pattern
   - Invalid JSON

4. **Execution Errors**
   - Tool execution failures
   - Subprocess failures (for bash)
   - Timeout errors

5. **State Errors**
   - Conversation loop max iterations exceeded
   - Assistant stream ended early
   - Missing required content blocks

---

## 4. LINE NUMBER AND CONTEXT MANAGEMENT

### 4.1 Line Number Conventions:

```
File Line Numbering:
- User-facing: 1-indexed (line 1 is first line)
- Internal: 0-indexed for array access
- Conversion: line_number = index + 1

Read Operation:
  Input: offset (0-indexed starting line), limit (number of lines)
  Processing:
    start_index = offset.unwrap_or(0).min(lines.len())
    end_index = (start_index + limit).min(lines.len())
  Output:
    start_line: start_index + 1  (1-indexed for user)
    num_lines: end_index - start_index
    total_lines: lines.len()

Grep Operation:
  Line tracking: 1-indexed in output
  Line prefix: "{file_path}:{line_number + 1}:{content}"
  Context: Calculated with saturating_sub/min for safety
```

### 4.2 Patch Line Number Management:

```
StructuredPatchHunk:
  old_start: 1          (1-indexed start in original file)
  old_lines: N          (number of consecutive lines removed)
  new_start: 1          (1-indexed start in new file)
  new_lines: M          (number of consecutive lines added)
  lines: Vec<String>    (actual diff lines, each prefixed with +/-)

Simple Patch Algorithm:
  - Create single hunk covering entire file change
  - All original lines prefixed with "-"
  - All new lines prefixed with "+"
  - No line continuity tracking (simple full-file diff)
```

### 4.3 Multiple Changes Strategy:

CLAW's approach for handling multiple edits to the same file:

1. **Single-change edits**: Use edit_file with old_string/new_string
   - Atomic replacement
   - Validates old_string exists first
   - All or nothing (replace_all controls scope)

2. **Write full file**: Use write_file with complete new content
   - Replaces entire file
   - Generates patch showing complete diff
   - Preserves original for comparison

3. **Multiple sequential edits**: Conversation loop handles this
   - Each edit returns StructuredPatchHunk
   - AI reads file after each change
   - Next edit works on updated content
   - No built-in conflict resolution (relies on AI state tracking)

---

## 5. FILE EDITING STRATEGIES THAT WORK

### 5.1 Simple String Replacement (Best for Small Changes)
```
Tool: edit_file
Input:
  path: "/path/to/file"
  old_string: "exact text to replace"  # Must match exactly
  new_string: "replacement text"
  replace_all: false  # or true for all occurrences
  
Output: StructuredPatchHunk, original_file content
Error: NotFound if old_string not in file
Strategy: Use when you know exact text to replace
```

### 5.2 Full File Replacement (Best for Large Changes)
```
Tool: write_file
Input:
  path: "/path/to/file"
  content: "complete new file content"
  
Output: StructuredPatchHunk (shows before/after), kind ("create"/"update")
Error: IO errors if parent dir doesn't exist (auto-created)
Strategy: Use when rewriting large sections or entire file
```

### 5.3 Read-Modify-Write Pattern
```
1. read_file(path, offset, limit)  # Get context
   Output: TextFilePayload with num_lines, start_line, total_lines
   
2. Analyze content in conversation
   
3. edit_file or write_file with updates
   Output: StructuredPatchHunk showing changes
   
4. read_file(path) to verify
   Output: Confirms changes applied
   
Strategy: Safest for multi-step changes
```

### 5.4 Search Before Edit Pattern
```
1. grep_search(pattern, path, output_mode="content")
   Output: line numbers and content with matches
   
2. Use returned line numbers to identify exact text
   
3. Use edit_file with exact matched string
   
4. verify with read_file or grep_search again
   
Strategy: Ensures you're editing correct location
```

### 5.5 Atomic Multi-Change Pattern
```
// DON'T: Sequential edits that might interfere
edit_file(path, old1, new1)
edit_file(path, old2, new2)  // Might fail if old1 changed search text

// DO: Collect all changes, write_file once
read_file(path)
<compute all needed changes in conversation>
write_file(path, complete_new_content)
```

---

## 6. PERMISSION SYSTEM

### 6.1 Permission Modes:

```rust
pub enum PermissionMode {
    ReadOnly,           // read_file, grep_search, glob_search
    WorkspaceWrite,     // write_file, edit_file
    DangerFullAccess,   // bash, PowerShell, REPL
}
```

### 6.2 Tool Permission Mapping:

| Tool | Mode | Risk |
|------|------|------|
| read_file | ReadOnly | Safe |
| glob_search | ReadOnly | Safe |
| grep_search | ReadOnly | Safe |
| write_file | WorkspaceWrite | Moderate |
| edit_file | WorkspaceWrite | Moderate |
| bash | DangerFullAccess | High |
| PowerShell | DangerFullAccess | High |
| REPL | DangerFullAccess | High |

---

## 7. STRUCTURED OUTPUT PATTERNS

### 7.1 Read File Response:
```json
{
  "type": "text",
  "file": {
    "filePath": "/absolute/path/to/file",
    "content": "selected lines joined with newlines",
    "numLines": 10,
    "startLine": 1,
    "totalLines": 100
  }
}
```

### 7.2 Write File Response:
```json
{
  "type": "create|update",
  "filePath": "/absolute/path/to/file",
  "content": "new file content",
  "structuredPatch": [
    {
      "oldStart": 1,
      "oldLines": 0,
      "newStart": 1,
      "newLines": 5,
      "lines": ["+line1", "+line2", "+line3", "+line4", "+line5"]
    }
  ],
  "originalFile": "previous content if update",
  "gitDiff": null
}
```

### 7.3 Edit File Response:
```json
{
  "filePath": "/absolute/path/to/file",
  "oldString": "text that was replaced",
  "newString": "new replacement text",
  "originalFile": "full original file content",
  "structuredPatch": [
    {
      "oldStart": 1,
      "oldLines": 2,
      "newStart": 1,
      "newLines": 2,
      "lines": ["-old line 1", "-old line 2", "+new line 1", "+new line 2"]
    }
  ],
  "userModified": false,
  "replaceAll": false,
  "gitDiff": null
}
```

### 7.4 Grep Search Response:
```json
{
  "mode": "content|count|files_with_matches",
  "numFiles": 3,
  "filenames": ["/path/to/file1", "/path/to/file2", "/path/to/file3"],
  "content": "file1:10:matching line\nfile2:15:another match",
  "numLines": 2,
  "numMatches": 2,
  "appliedLimit": 250,
  "appliedOffset": 0
}
```

---

## 8. KEY IMPLEMENTATION INSIGHTS

### 8.1 Strengths of CLAW's Approach:

1. **Simple Structured Patches**
   - Human-readable diff format
   - Always includes old and new line counts
   - Easy to verify and explain to users

2. **Graceful Line Number Handling**
   - saturating_sub/min prevents panics on out-of-bounds
   - Always returns total context (total_lines in read output)
   - User always knows file size

3. **Comprehensive Grep Support**
   - Regex with multiline support
   - Multiple context options (-B, -A, -C, context)
   - Line number tracking in output
   - Pagination with limit/offset

4. **Validation-First Edit Strategy**
   - edit_file checks old_string exists before applying
   - Prevents silent failures from missing text
   - replace_all parameter gives explicit control

5. **Path Safety**
   - normalize_path uses canonicalize for existing files
   - normalize_path_allow_missing for new files
   - Always returns absolute paths to users

### 8.2 Design Patterns to Adapt:

1. **Error Propagation Model**
   - Convert io::Error to String in tool boundary
   - Mark tool errors in conversation with is_error=true flag
   - Allow AI to reason about failures

2. **Patch Generation**
   - Single hunk approach is simple and works
   - Could be extended with multi-hunk for better context
   - Line numbers match semantic change locations

3. **Context Management**
   - Always include total_lines/total context
   - Use saturation arithmetic for safety
   - Return 1-indexed line numbers to users

4. **State Tracking**
   - original_file field in outputs allows verification
   - user_modified flag tracks if AI output was modified
   - git_diff field reserved for future integration

5. **Permission-Based Tool Access**
   - Clear three-tier system (ReadOnly, WorkspaceWrite, DangerFull)
   - Hooks can intercept pre/post execution
   - Tool names normalized for consistent access

---

## 9. TOOL EXECUTION FLOW

### 9.1 From Input to Output:

```
User Request
  ↓
ConversationRuntime.run_turn()
  ↓
API Client streams AssistantEvent
  ↓
build_assistant_message() constructs ContentBlock::ToolUse
  ↓
Permission check via PermissionPolicy.authorize()
  ↓
Pre-hook execution (HookRunner.run_pre_tool_use)
  ↓
Tool Executor.execute(tool_name, input_json)
  ├─ Deserialize JSON to typed input struct
  ├─ Call tool function (read_file, write_file, etc)
  ├─ Serialize result to JSON string
  └─ Return as String
  ↓
Post-hook execution (HookRunner.run_post_tool_use)
  ↓
ConversationMessage.tool_result(tool_use_id, tool_name, output, is_error)
  ↓
Response sent to AI for next iteration or end
```

### 9.2 Error Handling in Loop:

```rust
match self.tool_executor.execute(&tool_name, &input) {
    Ok(output) => (output, false),           // Mark as success
    Err(error) => (error.to_string(), true), // Mark as error
}
// Tool result always has is_error flag set
// AI sees both success and failure clearly
```

---

## 10. PROMPT ENGINEERING INSIGHTS

### 10.1 Key Prompt Directives:

1. **Code Change Practices**
   - "Read relevant code before changing it"
   - "Keep changes tightly scoped to the request"
   - "Do not add speculative abstractions"

2. **Validation and Diagnostics**
   - "If an approach fails, diagnose the failure before switching tactics"
   - "Report outcomes faithfully"
   - "If verification fails or was not run, say so explicitly"

3. **Security Consciousness**
   - "Be careful not to introduce security vulnerabilities"
   - Lists: command injection, XSS, SQL injection

4. **Reversibility Thinking**
   - "Carefully consider reversibility and blast radius"
   - "Local, reversible actions like editing files are usually fine"
   - "Actions affecting shared systems need explicit authorization"

5. **File Creation Caution**
   - "Do not create files unless they are required"

### 10.2 Boundary Markers:

```
SYSTEM_PROMPT_DYNAMIC_BOUNDARY separates:
  - Static instruction sections (before)
  - Dynamic context sections (after)
  
This allows systems to:
  - Cache static portions
  - Update dynamic portions per-request
  - Track what changed between turns
```

---

## 11. TESTING PATTERNS

### 11.1 File Operations Tests:

```rust
#[test]
fn reads_and_writes_files() {
    let path = temp_path("read-write.txt");
    let write_output = write_file(path, "one\ntwo\nthree");
    assert_eq!(write_output.kind, "create");
    
    let read_output = read_file(path, Some(1), Some(1));
    assert_eq!(read_output.file.content, "two");  // offset=1, limit=1 gets second line
}

#[test]
fn edits_file_contents() {
    write_file(path, "alpha beta alpha");
    let output = edit_file(path, "alpha", "omega", true);
    assert!(output.replace_all);  // Both occurrences replaced
}

#[test]
fn globs_and_greps_directory() {
    write_file(file, "fn main() {\n println!(\"hello\");\n}\n");
    
    let globbed = glob_search("**/*.rs", Some(dir));
    assert_eq!(globbed.num_files, 1);
    
    let grep_output = grep_search(&GrepSearchInput {
        pattern: String::from("hello"),
        output_mode: Some(String::from("content")),
        line_numbers: Some(true),
        // ...
    });
    assert!(grep_output.content.unwrap().contains("hello"));
}
```

---

## 12. SPECIFIC ADAPTATIONS FOR RETROFIT

### Key Patterns to Implement:

1. **StructuredPatchHunk** - Our core patch format
   - oldStart, oldLines, newStart, newLines + lines array
   - Simple single-hunk generation
   - Support for future multi-hunk

2. **Line Number Safety**
   - 1-indexed for users
   - saturating arithmetic internally
   - Always return total context

3. **Error as State**
   - Tools return Result<Output, String>
   - Errors marked in conversation with is_error=true
   - AI can reason about and recover from failures

4. **Read-Verify Pattern**
   - Always read file before editing
   - Always read file after editing
   - Validates state changes

5. **Tool Permission Tiers**
   - ReadOnly, WorkspaceWrite, DangerFull
   - Each tool specifies requirements
   - Conversation loop enforces permissions

6. **Prompt Context Sections**
   - Static instructions (before boundary)
   - Dynamic project context (after boundary)
   - Allows caching and efficient updates

