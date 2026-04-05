# Line Drift Bug Fix Roadmap

## Executive Summary

The file editor agent encountered a critical **line number staleness** bug during multi-edit sequences where:
1. An agent edited lines 67-82 with a delta of +10 lines
2. The agent did not track this delta and used stale line numbers from the original file state
3. Subsequent edits overlapped and corrupted the file structure

This document outlines the three-layer fix already implemented plus the long-term AST-based solution.

## Three-Layer Short-Term Fix (COMPLETED)

### Layer 1: Line Delta Reporting (COMPLETED ✓)
**File**: `agents-backend/src/agents/hunk_generator_tools.py:685-739`

Changed `replace_lines` to return explicit line delta:
```python
delta = new_line_count - old_line_count
sign = "+" if delta >= 0 else ""
return f"SUCCESS: lines {start_line} to {end_line} replaced. " \
       f"Line delta: {sign}{delta} (subsequent edits below line {end_line} must shift by {sign}{delta})."
```

**Impact**: Agent now sees "Line delta: +5" in tool response and can adjust subsequent line numbers.

### Layer 2: System Prompt Enhancement (COMPLETED ✓)
**File**: `agents-backend/src/agents/file_editor.py:58-98`

Added two critical sections:
1. **Line Number Drift Warning**: Explicit instruction to track deltas and adjust subsequent lines
2. **Bottom-to-Top Edit Ordering**: Plan all edits first, execute from end of file upward

```
## CRITICAL: Line Number Drift After Edits (Non-Negotiable)
After EVERY replace_lines or insert_after_line call:
1. Note the line delta from the tool's response (e.g., "Line delta: +5")
2. IMMEDIATELY adjust ALL subsequent line numbers for this file by that delta
3. Example: If you replace lines 67-82 with +10 net lines, any later edits 
   originally at lines 100+ must shift to 110+
```

**Impact**: Agent follows mandated protocol for tracking edits across multiple calls.

### Layer 3: Multi-Edit File Heuristic (COMPLETED ✓)
**File**: `agents-backend/src/agents/file_editor.py:1043-1050`

Added runtime detection for complex files:
```python
# Add heuristic for multi-edit files: prefer str_replace_in_file over line numbers
if len(plan_entries) >= 3:
    system_prompt += (
        "\n\n## IMPORTANT: Multi-Edit File Detection\n"
        "This file has 3+ distinct edits. Consider using str_replace_in_file "
        "(exact string matching) instead of line numbers to avoid line drift.\n"
        "Line numbers are inherently fragile across multiple sequential edits."
    )
```

**Impact**: Files with 3+ edits get explicit steering toward safer string-based replacement.

### Layer 4: Mid-Session Validation Gate (COMPLETED ✓)
**File**: `agents-backend/src/agents/file_editor.py:58-98` (updated system prompt)

Added mandatory verification step:
```
4. VERIFY your changes: After ALL edits are complete, call `git_diff_file` to see 
   the actual diff, then call `verify_guidelines` with the diff to catch syntax 
   errors before returning.
```

**Impact**: Agent uses validation tools as gates, catching corrupted state before commit.

---

## Long-Term Fix: AST-Based Method Replacement

### Problem with Line-Based Editing

Line numbers are inherently fragile because:
- They change with every edit that modifies line count
- Multiple edits in sequence suffer cumulative drift
- Overlapping edits can corrupt syntax before being caught
- No semantic understanding of code structure

### Solution: Replace by Method/Field AST Coordinates

Instead of "replace lines 67-82", use:
- "replace the body of method `TransportGetAllocationStatsAction(TransportService, ...)`"
- "replace the field declaration `private final EsExecutor executor`"
- "insert import `com.example.NewClass`"

The tool resolves exact byte ranges via tree-sitter AST parsing, making line drift impossible.

---

## Implementation Roadmap

### Phase 1: Python-Side AST Replacement Tool (Week 1)

**Objective**: Add Python tools for AST-based method/field replacement

**Files to create**:
1. `agents-backend/src/agents/ast_tools.py` (new)
   - `ASTMethodReplacer` class wrapping tree-sitter Java parser
   - `replace_method_body(file_path, method_signature, new_body)` tool
   - `replace_field(file_path, field_name, new_declaration)` tool
   - `insert_import(file_path, import_statement)` tool
   - `get_method_bounds(file_path, method_signature) -> (line_start, line_end)` helper

**Dependencies to add**:
- `tree-sitter>=0.20.0`
- `tree-sitter-java>=0.20.0`

**Example implementation**:
```python
import tree_sitter
from tree_sitter import Language, Parser

class ASTMethodReplacer:
    def __init__(self, target_repo_path: str):
        self.repo = target_repo_path
        self.parser = Parser()
        self.parser.set_language(Language(lib_path, "java"))
    
    def replace_method_body(
        self, 
        file_path: str, 
        method_signature: str, 
        new_body: str
    ) -> str:
        """
        Locate method by signature (e.g., 'TransportGetAllocationStatsAction(TransportService, ...)')
        and replace its entire body. Handles line number drift automatically.
        """
        # Parse file
        with open(file_path) as f:
            code = f.read()
        tree = self.parser.parse(code.encode())
        
        # Find method node matching signature
        method_node = self._find_method(tree, method_signature)
        if not method_node:
            return f"ERROR: Method '{method_signature}' not found"
        
        # Extract method body bounds
        body_node = self._get_body_node(method_node)
        start_byte = body_node.start_byte
        end_byte = body_node.end_byte
        
        # Replace bytes
        new_code = (
            code[:start_byte] +
            new_body +
            code[end_byte:]
        )
        
        with open(file_path, 'w') as f:
            f.write(new_code)
        
        return f"SUCCESS: Replaced body of {method_signature}"
    
    def _find_method(self, tree, signature: str):
        # Traverse AST to find constructor/method matching signature
        # Handles parameter matching with wildcards
        pass
    
    def _get_body_node(self, method_node):
        # Return the block node that is the method body
        pass
```

**Testing**:
```python
# agents-backend/src/agents/test_ast_tools.py
def test_replace_constructor_body():
    repl = ASTMethodReplacer(".")
    result = repl.replace_method_body(
        "TestFile.java",
        "TestConstructor(Service svc, Config cfg)",
        "this.service = svc;\nthis.config = cfg;"
    )
    assert "SUCCESS" in result
```

---

### Phase 2: Integration into HunkGeneratorToolkit (Week 2)

**Objective**: Add AST tools to the existing toolkit so agents can use them

**Files to modify**:
1. `agents-backend/src/agents/hunk_generator_tools.py`
   - Add `from ast_tools import ASTMethodReplacer`
   - Add methods:
     - `replace_method_body(file_path, method_sig, new_body)`
     - `replace_field(file_path, field_name, new_declaration)`
     - `insert_import(file_path, import_statement)`

**Example**:
```python
def replace_method_body(
    self,
    file_path: str,
    method_signature: str,
    new_body: str,
) -> str:
    """
    Replace the body of a method by its signature (AST-based, immune to line drift).
    
    Args:
        file_path: Repo-relative path
        method_signature: e.g. "TransportGetAllocationStatsAction(TransportService, ClusterService, ...)"
        new_body: Complete method body code
    
    Returns:
        SUCCESS or ERROR message
    """
    try:
        return self._ast_replacer.replace_method_body(
            self._full_path(file_path),
            method_signature,
            new_body
        )
    except Exception as e:
        return f"ERROR: AST replacement failed: {e}"
```

---

### Phase 3: System Prompt Update (Week 2)

**Objective**: Guide agent to prefer AST-based replacement for complex changes

**Files to modify**:
1. `agents-backend/src/agents/file_editor.py:58-98`

Add section:
```
## Preferred: AST-Based Method Replacement (When Modifying Methods)
For constructors and method bodies, prefer:
- replace_method_body(file_path, method_signature, new_body)

Instead of:
- replace_lines(start_line, end_line, new_content)

Example:
PREFERRED:
  replace_method_body(
    "TransportGetAllocationStatsAction.java",
    "TransportGetAllocationStatsAction(TransportService, ClusterService, ...)",
    "    this.service = service;\n    this.cluster = cluster;\n    this.executor = EsExecutors.DIRECT_EXECUTOR;"
  )

NOT PREFERRED (line drift risk):
  replace_lines(67, 82, "new constructor body...")
  replace_lines(100, 110, "new field assignment...")
```

**Heuristic**:
```python
# If patch contains constructor/method changes and 3+ edits, strongly recommend AST
if has_constructor_changes(plan_entries) and len(plan_entries) >= 3:
    system_prompt += (
        "\n\n## Strongly Recommended: AST Method Replacement\n"
        "This patch modifies constructors/methods with multiple edits.\n"
        "Use replace_method_body() instead of replace_lines() for these changes.\n"
        "It eliminates line drift entirely."
    )
```

---

### Phase 4: Optional - Java MCP Server Enhancement (Week 3+)

**Objective**: Move AST parsing to Java side for better integration with existing infrastructure

**Files to modify** (in java-mcp-server repository):
1. Add MCP endpoint: `POST /replace-method-body`
   ```java
   @PostMapping("/replace-method-body")
   public Map<String, Object> replaceMethodBody(
       @RequestParam String filePath,
       @RequestParam String methodSignature,
       @RequestBody String newBody
   ) {
       // Use existing tree-sitter infrastructure
       // Return { success: true, message: "..." }
   }
   ```

2. Add endpoint: `POST /get-method-boundaries`
   ```java
   @PostMapping("/get-method-boundaries")
   public Map<String, Object> getMethodBoundaries(
       @RequestParam String filePath,
       @RequestParam String methodSignature
   ) {
       // Return { lineStart, lineEnd, byteStart, byteEnd }
   }
   ```

**Benefit**: Leverage existing `get_class_context` infrastructure and tree-sitter Java integration already present in the Java MCP server.

---

## Risk Mitigation

### What Happens If AST Parsing Fails?

The system has graceful degradation:
1. If `replace_method_body` fails (e.g., method not found), it returns ERROR
2. Agent falls back to `replace_lines` with explicit line tracking
3. System prompt's layer 2 (bottom-to-top + delta tracking) prevents most corruption
4. Layer 4 (verify_guidelines gate) catches remaining issues

### Testing Strategy

```python
# Unit tests
test_replace_constructor_body()
test_replace_field_declaration()
test_insert_import()
test_overlapping_edits_still_work()  # Ensures backward compat

# Integration tests
test_elasticsearch_patch_with_ast_replacement()  # Original failing case
test_multi_method_file_patch()
test_mixed_ast_and_line_replacement()  # Both tools in one file
```

---

## Execution Timeline

| Phase | Task | Timeline | Owner |
|-------|------|----------|-------|
| ✓ 0 | Short-term fixes (layers 1-4) | COMPLETED | Engineering |
| 1 | Python AST tool implementation + tests | Week 1 | Backend Team |
| 2 | Integration into HunkGeneratorToolkit | Week 2 | Backend Team |
| 3 | System prompt enhancement + heuristics | Week 2 | Agent Team |
| 4 | (Optional) Java MCP server enhancement | Week 3+ | Backend Team |

---

## Success Criteria

**Short-term (now)**: 
- [x] Line delta reporting working
- [x] Agent instructed on bottom-to-top ordering
- [x] Multi-edit file detection active
- [x] Validation gates in place

**Medium-term (week 2)**:
- [ ] AST method replacement tools available
- [ ] Agent can use them via HunkGeneratorToolkit
- [ ] System prompt guides toward AST for complex patches
- [ ] Original failing patch (Elasticsearch) passes with AST approach

**Long-term (week 3+)**:
- [ ] Java MCP server provides method boundary resolution
- [ ] File editor agent primarily uses AST-based approach
- [ ] Line-based editing reserved for simple insertions only
- [ ] Zero line-drift-related failures in test suite

---

## References

- **Original Bug Analysis**: See root cause analysis in git commit message
- **Elasticsearch Test Case**: `agents-backend/evaluate/full_run/results/elasticsearch/elasticsearch_41f09bf1`
- **System Prompt**: `agents-backend/src/agents/file_editor.py` line 58
- **Tool Implementation**: `agents-backend/src/agents/hunk_generator_tools.py` line 685
