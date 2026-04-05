# CLAW Codebase - Concrete Code Examples

## 1. StructuredPatchHunk - The Core Diff Format

### Definition (from file_ops.rs)
```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StructuredPatchHunk {
    #[serde(rename = "oldStart")]
    pub old_start: usize,
    #[serde(rename = "oldLines")]
    pub old_lines: usize,
    #[serde(rename = "newStart")]
    pub new_start: usize,
    #[serde(rename = "newLines")]
    pub new_lines: usize,
    pub lines: Vec<String>,
}
```

### Simple Patch Generation (from file_ops.rs lines 430-446)
```rust
fn make_patch(original: &str, updated: &str) -> Vec<StructuredPatchHunk> {
    let mut lines = Vec::new();
    for line in original.lines() {
        lines.push(format!("-{line}"));
    }
    for line in updated.lines() {
        lines.push(format!("+{line}"));
    }

    vec![StructuredPatchHunk {
        old_start: 1,                           // Always 1 for simple whole-file diff
        old_lines: original.lines().count(),
        new_start: 1,
        new_lines: updated.lines().count(),
        lines,
    }]
}
```

### JSON Serialization Example
```json
{
  "oldStart": 1,
  "oldLines": 3,
  "newStart": 1,
  "newLines": 4,
  "lines": [
    "-function add(a, b) {",
    "-  return a + b",
    "-}",
    "+function add(a, b) {",
    "+  console.log('Adding', a, 'and', b);",
    "+  return a + b;",
    "+}"
  ]
}
```

---

## 2. File Reading with Line Numbers

### Definition (from file_ops.rs lines 132-156)
```rust
pub fn read_file(
    path: &str,
    offset: Option<usize>,
    limit: Option<usize>,
) -> io::Result<ReadFileOutput> {
    let absolute_path = normalize_path(path)?;
    let content = fs::read_to_string(&absolute_path)?;
    let lines: Vec<&str> = content.lines().collect();
    
    let start_index = offset.unwrap_or(0).min(lines.len());
    let end_index = limit.map_or(lines.len(), |limit| {
        start_index.saturating_add(limit).min(lines.len())
    });
    let selected = lines[start_index..end_index].join("\n");

    Ok(ReadFileOutput {
        kind: String::from("text"),
        file: TextFilePayload {
            file_path: absolute_path.to_string_lossy().into_owned(),
            content: selected,
            num_lines: end_index.saturating_sub(start_index),  // Count in selection
            start_line: start_index.saturating_add(1),          // 1-indexed for user
            total_lines: lines.len(),                           // Context: total file size
        },
    })
}
```

### Example Call and Response
```
read_file("/path/to/file.txt", Some(5), Some(10))

Response:
{
  "type": "text",
  "file": {
    "filePath": "/absolute/path/to/file.txt",
    "content": "line 6\nline 7\nline 8\n...",  // 10 lines
    "numLines": 10,
    "startLine": 6,                // 1-indexed (offset 5 = line 6)
    "totalLines": 100              // File has 100 total lines
  }
}
```

---

## 3. String Replacement with Validation

### Definition (from file_ops.rs lines 180-218)
```rust
pub fn edit_file(
    path: &str,
    old_string: &str,
    new_string: &str,
    replace_all: bool,
) -> io::Result<EditFileOutput> {
    let absolute_path = normalize_path(path)?;
    let original_file = fs::read_to_string(&absolute_path)?;
    
    // CRITICAL: Prevent no-op edits
    if old_string == new_string {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "old_string and new_string must differ",
        ));
    }
    
    // CRITICAL: Validate old_string exists
    if !original_file.contains(old_string) {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "old_string not found in file",
        ));
    }

    let updated = if replace_all {
        original_file.replace(old_string, new_string)
    } else {
        original_file.replacen(old_string, new_string, 1)
    };
    fs::write(&absolute_path, &updated)?;

    Ok(EditFileOutput {
        file_path: absolute_path.to_string_lossy().into_owned(),
        old_string: old_string.to_owned(),
        new_string: new_string.to_owned(),
        original_file: original_file.clone(),
        structured_patch: make_patch(&original_file, &updated),
        user_modified: false,
        replace_all,
        git_diff: None,
    })
}
```

### Error Cases
```rust
// Case 1: String doesn't change
edit_file("/path/file", "foo", "foo", false)
// Returns: InvalidInput("old_string and new_string must differ")

// Case 2: Text doesn't exist
edit_file("/path/file", "nonexistent", "new", false)
// Returns: NotFound("old_string not found in file")

// Case 3: Success
edit_file("/path/file", "old text", "new text", true)
// Returns: EditFileOutput with structured_patch showing changes
```

---

## 4. Comprehensive Grep Implementation

### Definition (from file_ops.rs lines 263-370)
```rust
pub fn grep_search(input: &GrepSearchInput) -> io::Result<GrepSearchOutput> {
    let base_path = input
        .path
        .as_deref()
        .map(normalize_path)
        .transpose()?
        .unwrap_or(std::env::current_dir()?);

    let regex = RegexBuilder::new(&input.pattern)
        .case_insensitive(input.case_insensitive.unwrap_or(false))
        .dot_matches_new_line(input.multiline.unwrap_or(false))
        .build()
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidInput, error.to_string()))?;

    // ... file collection and filtering ...

    let mut filenames = Vec::new();
    let mut content_lines = Vec::new();
    let mut total_matches = 0usize;

    for file_path in collect_search_files(&base_path)? {
        if !matches_optional_filters(&file_path, glob_filter.as_ref(), file_type) {
            continue;
        }

        let Ok(file_contents) = fs::read_to_string(&file_path) else {
            continue;  // Skip unreadable files
        };

        let lines: Vec<&str> = file_contents.lines().collect();
        let mut matched_lines = Vec::new();
        for (index, line) in lines.iter().enumerate() {
            if regex.is_match(line) {
                total_matches += 1;
                matched_lines.push(index);
            }
        }

        if matched_lines.is_empty() {
            continue;
        }

        filenames.push(file_path.to_string_lossy().into_owned());
        if output_mode == "content" {
            for index in matched_lines {
                let start = index.saturating_sub(input.before.unwrap_or(context));
                let end = (index + input.after.unwrap_or(context) + 1).min(lines.len());
                for (current, line) in lines.iter().enumerate().take(end).skip(start) {
                    let prefix = if input.line_numbers.unwrap_or(true) {
                        format!("{}:{}:", file_path.to_string_lossy(), current + 1)  // 1-indexed!
                    } else {
                        format!("{}:", file_path.to_string_lossy())
                    };
                    content_lines.push(format!("{prefix}{line}"));
                }
            }
        }
    }

    // Apply limit and offset for pagination
    let (filenames, applied_limit, applied_offset) =
        apply_limit(filenames, input.head_limit, input.offset);
    
    // Return response...
}
```

### Example grep_search Input
```json
{
  "pattern": "function",
  "path": "/project/src",
  "glob": "**/*.js",
  "output_mode": "content",
  "-B": 2,
  "-A": 3,
  "-n": true,
  "-i": false,
  "head_limit": 50,
  "offset": 0
}
```

### Example Response
```json
{
  "mode": "content",
  "numFiles": 3,
  "filenames": ["/project/src/file1.js", "/project/src/file2.js"],
  "content": "file1.js:8:const helper = () => {};\nfile1.js:9:function add(a, b) {\nfile1.js:10:  return a + b;\nfile1.js:11:}\n\nfile2.js:15:  function nested() {",
  "numLines": 6,
  "appliedLimit": 50,
  "appliedOffset": 0
}
```

---

## 5. System Prompt Builder

### Builder Pattern (from prompt.rs lines 86-200)
```rust
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SystemPromptBuilder {
    output_style_name: Option<String>,
    output_style_prompt: Option<String>,
    os_name: Option<String>,
    os_version: Option<String>,
    append_sections: Vec<String>,
    project_context: Option<ProjectContext>,
    config: Option<RuntimeConfig>,
}

impl SystemPromptBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_output_style(mut self, name: impl Into<String>, prompt: impl Into<String>) -> Self {
        self.output_style_name = Some(name.into());
        self.output_style_prompt = Some(prompt.into());
        self
    }

    pub fn with_os(mut self, os_name: impl Into<String>, os_version: impl Into<String>) -> Self {
        self.os_name = Some(os_name.into());
        self.os_version = Some(os_version.into());
        self
    }

    pub fn with_project_context(mut self, project_context: ProjectContext) -> Self {
        self.project_context = Some(project_context);
        self
    }

    pub fn build(&self) -> Vec<String> {
        let mut sections = Vec::new();
        sections.push(get_simple_intro_section(self.output_style_name.is_some()));
        if let (Some(name), Some(prompt)) = (&self.output_style_name, &self.output_style_prompt) {
            sections.push(format!("# Output Style: {name}\n{prompt}"));
        }
        sections.push(get_simple_system_section());
        sections.push(get_simple_doing_tasks_section());
        sections.push(get_actions_section());
        sections.push(SYSTEM_PROMPT_DYNAMIC_BOUNDARY.to_string());  // MARKER
        sections.push(self.environment_section());
        if let Some(project_context) = &self.project_context {
            sections.push(render_project_context(project_context));
            if !project_context.instruction_files.is_empty() {
                sections.push(render_instruction_files(&project_context.instruction_files));
            }
        }
        if let Some(config) = &self.config {
            sections.push(render_config_section(config));
        }
        sections.extend(self.append_sections.iter().cloned());
        sections
    }

    pub fn render(&self) -> String {
        self.build().join("\n\n")
    }
}
```

### Example Usage
```rust
let project_context = ProjectContext::discover_with_git("/path/to/project", "2026-04-02")?;
let config = ConfigLoader::default_for("/path/to/project").load()?;

let prompt = SystemPromptBuilder::new()
    .with_output_style("Technical", "Prefer concise, code-focused responses.")
    .with_os("linux", "6.8")
    .with_project_context(project_context)
    .with_runtime_config(config)
    .render();
```

---

## 6. Instruction File Discovery

### Discovery Algorithm (from prompt.rs lines 202-223)
```rust
fn discover_instruction_files(cwd: &Path) -> std::io::Result<Vec<ContextFile>> {
    let mut directories = Vec::new();
    let mut cursor = Some(cwd);
    
    // Walk up ancestor chain
    while let Some(dir) = cursor {
        directories.push(dir.to_path_buf());
        cursor = dir.parent();
    }
    directories.reverse();  // Start from root

    let mut files = Vec::new();
    for dir in directories {
        for candidate in [
            dir.join("CLAW.md"),
            dir.join("CLAW.local.md"),
            dir.join(".claw").join("CLAW.md"),
            dir.join(".claw").join("instructions.md"),
        ] {
            push_context_file(&mut files, candidate)?;
        }
    }
    Ok(dedupe_instruction_files(files))
}

fn push_context_file(files: &mut Vec<ContextFile>, path: PathBuf) -> std::io::Result<()> {
    match fs::read_to_string(&path) {
        Ok(content) if !content.trim().is_empty() => {
            files.push(ContextFile { path, content });
            Ok(())
        }
        Ok(_) => Ok(()),  // Skip empty files
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(error),
    }
}
```

### Directory Structure Example
```
/workspace/
  CLAW.md                    <- Discovered first
  /apps/
    CLAW.md                  <- Discovered second
    .claw/
      instructions.md        <- Discovered third
  /apps/api/
    .claw/
      CLAW.md                <- Discovered fourth
      instructions.md        <- Discovered fifth
```

---

## 7. Error Handling in Conversation Loop

### Tool Execution with Error Handling (from conversation.rs lines 201-254)
```rust
for (tool_use_id, tool_name, input) in pending_tool_uses {
    let permission_outcome = self.permission_policy.authorize(&tool_name, &input, None);

    let result_message = match permission_outcome {
        PermissionOutcome::Allow => {
            // Pre-execution hook
            let pre_hook_result = self.hook_runner.run_pre_tool_use(&tool_name, &input);
            if pre_hook_result.is_denied() {
                let deny_message = format!("PreToolUse hook denied tool `{tool_name}`");
                ConversationMessage::tool_result(
                    tool_use_id,
                    tool_name,
                    format_hook_message(&pre_hook_result, &deny_message),
                    true,  // is_error
                )
            } else {
                // MAIN EXECUTION
                let (mut output, mut is_error) =
                    match self.tool_executor.execute(&tool_name, &input) {
                        Ok(output) => (output, false),              // Success
                        Err(error) => (error.to_string(), true),    // Marked as error
                    };
                output = merge_hook_feedback(pre_hook_result.messages(), output, false);

                // Post-execution hook
                let post_hook_result = self
                    .hook_runner
                    .run_post_tool_use(&tool_name, &input, &output, is_error);
                if post_hook_result.is_denied() {
                    is_error = true;  // Mark if post-hook denies
                }
                output = merge_hook_feedback(
                    post_hook_result.messages(),
                    output,
                    post_hook_result.is_denied(),
                );

                ConversationMessage::tool_result(
                    tool_use_id,
                    tool_name,
                    output,
                    is_error,  // Propagate error state
                )
            }
        }
        PermissionOutcome::Deny { reason } => {
            ConversationMessage::tool_result(tool_use_id, tool_name, reason, true)
        }
    };
    self.session.messages.push(result_message.clone());
    tool_results.push(result_message);
}
```

---

## 8. Tool Specifications with JSON Schema

### Tool Definition (from tools/src/lib.rs lines 264-278)
```rust
ToolSpec {
    name: "edit_file",
    description: "Replace text in a workspace file.",
    input_schema: json!({
        "type": "object",
        "properties": {
            "path": { "type": "string" },
            "old_string": { "type": "string" },
            "new_string": { "type": "string" },
            "replace_all": { "type": "boolean" }
        },
        "required": ["path", "old_string", "new_string"],
        "additionalProperties": false
    }),
    required_permission: PermissionMode::WorkspaceWrite,
},
```

### Tool Execution Wrapper (from tools/src/lib.rs lines 585-595)
```rust
fn run_edit_file(input: EditFileInput) -> Result<String, String> {
    to_pretty_json(
        edit_file(
            &input.path,
            &input.old_string,
            &input.new_string,
            input.replace_all.unwrap_or(false),
        )
        .map_err(io_to_string)?,  // Convert io::Error to String
    )
}

fn io_to_string(error: std::io::Error) -> String {
    error.to_string()
}

fn to_pretty_json<T: serde::Serialize>(value: T) -> Result<String, String> {
    serde_json::to_string_pretty(&value).map_err(|error| error.to_string())
}
```

---

## 9. Path Normalization

### Safe Path Handling (from file_ops.rs lines 448-478)
```rust
fn normalize_path(path: &str) -> io::Result<PathBuf> {
    let candidate = if Path::new(path).is_absolute() {
        PathBuf::from(path)
    } else {
        std::env::current_dir()?.join(path)
    };
    candidate.canonicalize()  // Resolve all symlinks
}

fn normalize_path_allow_missing(path: &str) -> io::Result<PathBuf> {
    let candidate = if Path::new(path).is_absolute() {
        PathBuf::from(path)
    } else {
        std::env::current_dir()?.join(path)
    };

    // Try to canonicalize existing path
    if let Ok(canonical) = candidate.canonicalize() {
        return Ok(canonical);
    }

    // For missing files, construct path from canonicalized parent
    if let Some(parent) = candidate.parent() {
        let canonical_parent = parent
            .canonicalize()
            .unwrap_or_else(|_| parent.to_path_buf());
        if let Some(name) = candidate.file_name() {
            return Ok(canonical_parent.join(name));
        }
    }

    Ok(candidate)
}
```

---

## 10. Test Examples

### File Operations Test (from file_ops.rs lines 494-504)
```rust
#[test]
fn reads_and_writes_files() {
    let path = temp_path("read-write.txt");
    let write_output = write_file(path.to_string_lossy().as_ref(), "one\ntwo\nthree")
        .expect("write should succeed");
    assert_eq!(write_output.kind, "create");

    let read_output = read_file(path.to_string_lossy().as_ref(), Some(1), Some(1))
        .expect("read should succeed");
    assert_eq!(read_output.file.content, "two");  // offset=1 (0-indexed) = line 2 (1-indexed)
}
```

### Edit File Test (from file_ops.rs lines 506-514)
```rust
#[test]
fn edits_file_contents() {
    let path = temp_path("edit.txt");
    write_file(path.to_string_lossy().as_ref(), "alpha beta alpha")
        .expect("initial write should succeed");
    let output = edit_file(path.to_string_lossy().as_ref(), "alpha", "omega", true)
        .expect("edit should succeed");
    assert!(output.replace_all);
}
```

---

## Key Takeaways for Implementation

1. **StructuredPatchHunk** is the universal patch format
2. **Always validate** before modifying (old_string exists check)
3. **Line numbers are 1-indexed** for users, 0-indexed internally
4. **Always include context** (total_lines, original_file)
5. **Saturating arithmetic** prevents panics on bounds
6. **Error messages propagate** to AI for reasoning
7. **Prompts have boundaries** for static/dynamic content
8. **Permission checks** happen before execution
9. **Hooks run** pre and post execution
10. **Paths are normalized** to absolute canonical forms

