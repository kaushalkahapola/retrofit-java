# Implementation Guide: Elasticsearch Test Case Fix

## Overview

This document provides **concrete code changes** to fix the elasticsearch_41f09bf1 failure. All changes are in `agents-backend/src/agents/` directory.

---

## Phase 4A: Quick Wins (Highest Impact)

### Change 1: Add Semantic Validation to `verify_guidelines()`

**File**: `agents-backend/src/agents/hunk_generator_tools.py` (line 634)

**Current Code** (lines 634-679):
```python
def verify_guidelines(self, diff_text: str) -> str:
    """
    Verify the generated git diff adheres to strict Java syntactic and structural guidelines.
    """
    issues = []
    
    # 1. Truncated structs
    added = [...]
    # ... existing checks ...
    
    if issues:
        return "GUIDELINE_FAILURES:\n- " + "\n- ".join(issues)
    
    return "ALL_GOOD"
```

**New Code**: Add these checks BEFORE the final `if issues:` block:

```python
    # 3. Duplicate annotations (NEW)
    duplicate_annotations = self._check_duplicate_annotations(diff_text)
    if duplicate_annotations:
        issues.extend(duplicate_annotations)
    
    # 4. Method brace balance (NEW)
    brace_issues = self._check_method_brace_balance(diff_text)
    if brace_issues:
        issues.extend(brace_issues)
    
    # 5. Import validity (NEW)
    import_issues = self._check_import_validity(diff_text)
    if import_issues:
        issues.extend(import_issues)
```

---

### Helper Methods: Add to HunkGeneratorTools class

**Location**: `agents-backend/src/agents/hunk_generator_tools.py` (after `verify_guidelines()`)

```python
def _check_duplicate_annotations(self, diff_text: str) -> list:
    """
    Detect duplicate annotations (e.g., @Inject appearing twice).
    
    Returns list of issues found.
    """
    issues = []
    lines = (diff_text or "").splitlines()
    
    # Track annotations in each section
    current_section_annotations = {}
    
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            current_section_annotations = {}
            continue
        
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].strip()
            # Match @Annotation pattern
            if stripped.startswith("@"):
                annotation = stripped.split("(")[0]  # Get @Name without params
                
                if annotation in current_section_annotations:
                    # Check if they're consecutive or in same block
                    prev_line_idx = current_section_annotations[annotation]
                    # If within 3 lines, likely a duplicate
                    if i - prev_line_idx <= 3:
                        issues.append(
                            f"semantic_guard_failed: duplicate annotation '{annotation}' "
                            f"at lines ~{prev_line_idx} and ~{i}"
                        )
                else:
                    current_section_annotations[annotation] = i
    
    return issues


def _check_method_brace_balance(self, diff_text: str) -> list:
    """
    Detect mismatched braces in method definitions.
    
    Returns list of issues found.
    """
    issues = []
    lines = (diff_text or "").splitlines()
    
    # For each hunk, check brace balance
    current_section = []
    for line in lines:
        if line.startswith("@@"):
            if current_section:
                issues.extend(self._validate_section_braces(current_section))
            current_section = []
            continue
        
        current_section.append(line)
    
    if current_section:
        issues.extend(self._validate_section_braces(current_section))
    
    return issues


def _validate_section_braces(self, lines: list) -> list:
    """
    Check that braces are balanced within a code section.
    """
    issues = []
    
    # Extract added/unchanged lines (ignore removed)
    code_lines = [
        line[1:] if line.startswith("+") or line.startswith(" ") else ""
        for line in lines
        if line.startswith("+") or line.startswith(" ")
    ]
    
    # Look for method definitions
    in_method = False
    method_name = None
    brace_stack = []
    line_num = 0
    
    for code_line in code_lines:
        line_num += 1
        stripped = code_line.strip()
        
        # Detect method signature
        if re.match(r"^\s*(public|private|protected)?\s+\w+.*\(.*\)\s*\{?\s*$", code_line):
            in_method = True
            method_name = stripped[:50]  # Short version for error message
        
        if in_method:
            # Count braces
            for char in code_line:
                if char == '{':
                    brace_stack.append((line_num, '{'))
                elif char == '}':
                    if not brace_stack:
                        issues.append(
                            f"semantic_guard_failed: unmatched closing brace in method '{method_name}' "
                            f"at line ~{line_num}"
                        )
                    else:
                        brace_stack.pop()
                        if not brace_stack:
                            in_method = False
                            method_name = None
    
    # Check for unclosed braces at end
    if brace_stack:
        issues.append(
            f"semantic_guard_failed: unclosed braces in method '{method_name}' "
            f"({len(brace_stack)} unclosed)"
        )
    
    return issues


def _check_import_validity(self, diff_text: str) -> list:
    """
    Check for duplicate imports and import order issues.
    
    Returns list of issues found.
    """
    issues = []
    lines = (diff_text or "").splitlines()
    
    seen_imports = {}
    
    for i, line in enumerate(lines):
        if line.startswith("+") and "import " in line and not line.startswith("+++"):
            import_stmt = line[1:].strip()
            if import_stmt.startswith("import "):
                # Extract import path
                match = re.match(r"import\s+([\w\.]+)", import_stmt)
                if match:
                    import_path = match.group(1)
                    
                    if import_path in seen_imports:
                        issues.append(
                            f"semantic_guard_failed: duplicate import '{import_path}' "
                            f"at lines ~{seen_imports[import_path]} and ~{i}"
                        )
                    else:
                        seen_imports[import_path] = i
    
    return issues
```

---

### Change 2: Enhanced Error Messages

**File**: `agents-backend/src/agents/hunk_generator_tools.py` (line 676)

**Current Code**:
```python
if issues:
    return "GUIDELINE_FAILURES:\n- " + "\n- ".join(issues) + "\n\nFix these issues using `replace_lines` again."

return "ALL_GOOD"
```

**New Code**:
```python
if issues:
    # Parse issues to provide semantic guidance
    formatted_issues = []
    for issue in issues:
        if "duplicate annotation" in issue:
            formatted_issues.append(
                f"❌ {issue}\n"
                f"   → The annotation is already present in the context.\n"
                f"   → Remove it from the new_content parameter."
            )
        elif "unmatched" in issue or "unclosed" in issue:
            formatted_issues.append(
                f"❌ {issue}\n"
                f"   → Check that opening and closing braces match in method definition.\n"
                f"   → Count { and } carefully in your new_content."
            )
        elif "duplicate import" in issue:
            formatted_issues.append(
                f"❌ {issue}\n"
                f"   → Remove the duplicate import statement."
            )
        else:
            formatted_issues.append(f"❌ {issue}")
    
    error_msg = "GUIDELINE_FAILURES:\n" + "\n".join(formatted_issues)
    error_msg += (
        "\n\nFix these issues using `replace_lines` again.\n"
        "OR if replace_lines keeps failing, try replace_method_body() or get_method_boundaries() instead."
    )
    return error_msg

return "ALL_GOOD"
```

---

### Change 3: Update System Prompt with Tool Selection Strategy

**File**: `agents-backend/src/agents/file_editor.py` (find the `_FILE_EDITOR_AGENT_SYSTEM` constant)

**Add this section** to the system prompt (after existing guidelines):

```
## CRITICAL: Tool Selection by Change Type

Your choice of tool DIRECTLY AFFECTS SUCCESS. Follow these rules:

### Rule 1: ANNOTATION/DECORATOR CHANGES
- Use: get_method_boundaries() THEN replace_method_body()
- Never use replace_lines() alone for annotations
- Why: Decorators (@Inject, @Override, etc.) are easy to duplicate from context
- Example: To change a constructor's @Inject, first call get_method_boundaries("__init__" or method name)
  to get EXACT boundaries, then use replace_method_body() with the new body

### Rule 2: FULL METHOD SIGNATURE/BODY CHANGES
- Use: replace_method_body()
- Never use replace_lines() for multi-line methods
- Why: Handles braces, indentation, full signature automatically
- Example: Changing return type or entire method implementation → use replace_method_body()

### Rule 3: FIELD/VARIABLE CHANGES
- Use: replace_field()
- Never use replace_lines() for field declaration changes
- Why: Handles type, modifiers, initialization correctly

### Rule 4: IMPORT ADDITIONS
- Use: insert_import()
- Never manually add imports with replace_lines()
- Why: Automatic duplicate detection and proper ordering

### Rule 5: SIMPLE SINGLE-LINE CHANGES
- Use: replace_lines()
- ONLY if change is entirely within method body
- REQUIRED BEFORE EDIT: Call get_method_boundaries() to verify line is NOT:
  - At a decorator (@...)
  - At method signature boundary
  - In closing braces of method

### Default Rule: When in Doubt
- Call get_method_boundaries() FIRST to understand the exact structure
- Then choose the most specific tool (replace_method_body, replace_field, etc.)
- Use replace_lines() only as a last resort for trivial changes

## CRITICAL: After Using replace_lines()

MANDATORY VALIDATION SEQUENCE:
1. After each replace_lines() call, IMMEDIATELY call verify_guidelines()
2. If verify_guidelines() reports ANY semantic error, STOP and:
   a) Read the error message carefully
   b) Understand WHY the error occurred
   c) Do NOT retry with same strategy
   d) Use alternative tool (replace_method_body(), replace_field(), etc.)
3. DO NOT attempt the same replace_lines() call more than 2 times
   - If it fails twice, you're using the wrong tool
   - Switch to AST-based tool instead

## CRITICAL: Preventing Common Mistakes

### Mistake 1: Duplicate Annotations
- Problem: @Inject appears twice (once in context, once in replacement)
- Prevention: Before calling replace_lines(), check what's at line N-1
- If line N-1 has @Annotation, do NOT include @Annotation in new_content
- Use get_method_boundaries() to see full context

### Mistake 2: Extra/Missing Braces
- Problem: Method has extra closing brace or missing one
- Prevention: Count { and } in your new_content BEFORE calling replace_lines()
- If replacing a full method, count braces in old method = count in new method
- Example: Original has 1 opening, 1 closing → replacement must also have 1 + 1

### Mistake 3: Off-by-One Line Numbers
- Problem: start_line includes decorator, causing duplication
- Prevention: Use get_method_boundaries() to find where method actually starts
- Never guess: A method starts at @Decorator, not at "public"
```

---

## Phase 4B: Structural Fixes

### Change 4: Enhanced Context Validation in replace_lines()

**File**: `agents-backend/src/agents/hunk_generator_tools.py` (line 685-750, within `replace_lines()`)

**Add this validation** at the start of the function (after reading the file):

```python
def replace_lines(
    self,
    file_path: str,
    start_line: int,
    end_line: int,
    new_content: str,
) -> str:
    """
    Replace lines with enhanced context awareness.
    """
    full_path = self._full_path(file_path)
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
    except Exception as exc:
        return f"ERROR: Cannot read file '{file_path}': {exc}"

    lines = original.splitlines(keepends=True)
    total = len(lines)
    
    # NEW: Validate context awareness
    validation_warnings = []
    
    # Check if we're about to replace a decorator or its target
    if start_line > 1:
        prev_line = lines[start_line - 2].strip()  # -2 because 0-indexed
        if prev_line.startswith("@"):
            validation_warnings.append(
                f"WARNING: Line {start_line-1} has annotation '{prev_line}'. "
                f"Do NOT duplicate it in new_content. "
                f"The annotation stays as context."
            )
    
    # Check if new_content might cause brace imbalance
    opening_braces = new_content.count("{")
    closing_braces = new_content.count("}")
    if opening_braces != closing_braces:
        # This is a rough check - full validation in verify_guidelines()
        validation_warnings.append(
            f"WARNING: new_content has {opening_braces} opening braces but {closing_braces} closing braces. "
            f"This will likely fail validation. Ensure balanced braces."
        )
    
    # Continue with existing logic...
    if start_line < 1 or end_line > total or start_line > end_line + 1:
        return f"ERROR: Invalid range {start_line}-{end_line}. File has {total} lines."
    
    # ... rest of replace_lines() remains unchanged ...
```

**After the replacement is successful**, add this in the return message:

```python
# Calculate line delta: how many lines the file grows or shrinks
old_line_count = max(1, end_line - start_line + 1)
new_line_count = new_content.count('\n')
line_delta = old_line_count - new_line_count

success_msg = f"SUCCESS: Replaced lines {start_line}-{end_line}"
if validation_warnings:
    success_msg += "\n" + "\n".join(validation_warnings)

# Include line delta for downstream tracking
success_msg += f"\nLine delta: {'+' if line_delta > 0 else ''}{line_delta}"

return success_msg
```

---

### Change 5: Implement Edit Attempt History

**File**: Create new file `agents-backend/src/agents/edit_attempt_history.py`

```python
"""
Track editing attempts to detect when a tool isn't working and suggest alternatives.
"""

from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime
import hashlib


@dataclass
class EditAttempt:
    """Record of a single edit attempt"""
    file_path: str
    tool_name: str  # 'replace_lines', 'replace_method_body', etc.
    start_line: int
    end_line: int
    content_hash: str
    error: str  # Error message, or "" if successful
    timestamp: datetime = field(default_factory=datetime.now)
    
    def key(self) -> str:
        """Create key for deduplication"""
        return f"{self.file_path}:{self.start_line}-{self.end_line}"


class EditAttemptHistory:
    """Track edit attempts and suggest strategies when stuck"""
    
    def __init__(self, max_history: int = 50):
        self.attempts: List[EditAttempt] = []
        self.max_history = max_history
    
    def record(self, file_path: str, tool_name: str, start_line: int, 
               end_line: int, content: str, error: str = ""):
        """Record an edit attempt"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        attempt = EditAttempt(
            file_path=file_path,
            tool_name=tool_name,
            start_line=start_line,
            end_line=end_line,
            content_hash=content_hash,
            error=error
        )
        self.attempts.append(attempt)
        
        # Keep history bounded
        if len(self.attempts) > self.max_history:
            self.attempts = self.attempts[-self.max_history:]
    
    def get_failed_attempts(self, file_path: str) -> List[EditAttempt]:
        """Get all failed attempts for a file"""
        return [a for a in self.attempts if a.file_path == file_path and a.error]
    
    def get_repeated_failures(self, file_path: str, tool_name: str, 
                              max_repeats: int = 2) -> bool:
        """Check if same edit with same tool failed multiple times"""
        failed = self.get_failed_attempts(file_path)
        same_tool_failures = [a for a in failed if a.tool_name == tool_name]
        return len(same_tool_failures) >= max_repeats
    
    def suggest_alternative_strategy(self, file_path: str, 
                                     tool_name: str) -> Dict:
        """Suggest alternative strategy if current one is stuck"""
        failed = self.get_failed_attempts(file_path)
        
        if not failed:
            return {"strategy": "CONTINUE", "suggestion": None}
        
        # If replace_lines failed 2+ times, suggest AST tools
        if tool_name == "replace_lines":
            replace_lines_failures = [a for a in failed if a.tool_name == "replace_lines"]
            if len(replace_lines_failures) >= 2:
                return {
                    "strategy": "SWITCH_TOOLS",
                    "suggestion": "replace_lines() failed twice with semantic errors. "
                                  "Try replace_method_body(), replace_field(), or insert_import() instead.",
                    "recommended_tools": ["replace_method_body", "replace_field", "insert_import"]
                }
        
        return {"strategy": "CONTINUE", "suggestion": None}


# Global history instance (used by agent)
_global_history = EditAttemptHistory()


def track_edit(file_path: str, tool_name: str, start_line: int, 
               end_line: int, content: str, error: str = ""):
    """Record an edit attempt globally"""
    _global_history.record(file_path, tool_name, start_line, end_line, content, error)


def check_stuck_condition(file_path: str, tool_name: str) -> Dict:
    """Check if we're stuck with current strategy"""
    return _global_history.suggest_alternative_strategy(file_path, tool_name)


def get_history_summary(file_path: str) -> str:
    """Get summary of attempts for this file"""
    attempts = _global_history.get_failed_attempts(file_path)
    if not attempts:
        return f"No failed attempts recorded for {file_path}"
    
    summary = f"Failed attempts for {file_path}:\n"
    for attempt in attempts:
        summary += f"  - {attempt.tool_name} (lines {attempt.start_line}-{attempt.end_line}): {attempt.error[:60]}\n"
    
    return summary
```

---

### Change 6: Agent Loop Integration

**File**: `agents-backend/src/agents/file_editor.py` (update the file_editor_node() function)

**Add this check after verify_guidelines() fails**:

```python
from edit_attempt_history import track_edit, check_stuck_condition

async def file_editor_node(state: AgentState) -> AgentState:
    """File editing node with enhanced error tracking"""
    
    # ... existing logic ...
    
    # After calling verify_guidelines()
    validation_result = tool_handler.verify_guidelines(diff_text)
    
    if validation_result != "ALL_GOOD":
        # Track the failure
        track_edit(
            file_path=current_file,
            tool_name="replace_lines",
            start_line=start_line,
            end_line=end_line,
            content=new_content,
            error=validation_result
        )
        
        # Check if we're stuck
        strategy = check_stuck_condition(current_file, "replace_lines")
        if strategy["strategy"] == "SWITCH_TOOLS":
            # Add to plan to use alternative tools
            plan.append({
                "file": current_file,
                "action": "SWITCH_STRATEGY",
                "message": strategy["suggestion"],
                "recommended_tools": strategy.get("recommended_tools", [])
            })
        
        # Re-add validation failure to context for next iteration
        state.chat_history.append({
            "role": "user",
            "content": (
                f"Validation failed: {validation_result}\n\n"
                f"{strategy.get('suggestion', '')}"
            )
        })
    
    return state
```

---

## Summary Table: All Changes

| Change | File | Lines | Impact | Effort |
|--------|------|-------|--------|--------|
| 1. Add semantic validation methods | hunk_generator_tools.py | 634-750 | HIGH | 2 hrs |
| 2. Enhance error messages | hunk_generator_tools.py | 676-720 | HIGH | 1 hr |
| 3. Update system prompt | file_editor.py | ~150 lines new | CRITICAL | 2 hrs |
| 4. Context validation in replace_lines | hunk_generator_tools.py | 708-730 | MEDIUM | 1 hr |
| 5. Edit attempt history tracker | edit_attempt_history.py | NEW (150 lines) | MEDIUM | 1.5 hrs |
| 6. Agent loop integration | file_editor.py | ~30 lines | MEDIUM | 1 hr |

**Total Effort**: ~8.5 hours
**Expected Improvement**: elasticsearch_41f09bf1 will pass within 2-3 agent iterations instead of failing

---

## Validation Strategy

After implementing changes:

1. **Unit test** each helper method in isolation
2. **Test verify_guidelines()** against known bad diffs
3. **Run elasticsearch_41f09bf1** test case and verify:
   - Detects duplicate @Inject on first attempt
   - Detects extra brace on first attempt
   - Agent self-corrects on second attempt
   - Converges to correct solution by attempt 3

---

## Next Steps (If Approved)

1. Implement Phase 4A changes (1-3 above)
2. Test elasticsearch_41f09bf1 with new validation
3. Implement Phase 4B changes (4-6) if needed
4. Run full test suite
5. Document lessons learned for next patches
