# Fix Strategy for Structural Locator Phase 2 Failure

## The Core Problem
Phase 2 returns line numbers that don't match the target file because it doesn't handle **branch divergence** — when the mainline and target branches have different code structures.

---

## Root Cause Deep Dive

### What's Happening:
1. LLM receives hunk details and patch diff
2. LLM uses tools like `get_class_context()` to find methods
3. Tools return line numbers from the target file
4. **BUT**: The tools are returning line numbers based on partial context, not accounting for structural differences

### Why it Fails:
- **Import Section**: Target has extra imports earlier → all line numbers shift
- **Class Fields**: Target has different field order → inserts at wrong point
- **Method Bodies**: Target has different code in methods → context matching fails

---

## Solution 1: Extract Actual Line Numbers from Patch Headers

**Most Direct Fix:** Use the patch headers themselves!

### Current Problem:
```
mainline.patch: @@ -106,12 +123,39 @@
target.patch:   @@ -126,12 +142,39 @@
```

The target patch header tells us the hunk starts at line **142**, not line 106 or 123.

### Implementation:
```python
def extract_line_numbers_from_patch_header(patch_diff: str, file_path: str):
    """
    Extract the actual target insertion line from patch header.
    Patch format: @@ -old_start,old_len +new_start,new_len @@
    We want new_start (the target file line number).
    """
    lines = patch_diff.split('\n')
    for i, line in enumerate(lines):
        if f'diff --git a/{file_path}' in line or f'diff --git a' in line:
            # Found the diff for this file, look for the hunk header
            for j in range(i, min(i+20, len(lines))):
                match = re.search(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', lines[j])
                if match:
                    new_start = int(match.group(1))
                    new_len = int(match.group(2) or 1)
                    return new_start, new_start + new_len
    return None, None
```

**Why This Works:**
- The patch headers are **ground truth** — they come from git and reflect the actual file structure
- No guessing needed — the information is already there
- No LLM hallucination possible

---

## Solution 2: Context-Based Line Mapping with Verification

**More Robust Fix:** Find code anchors and map from there.

### Implementation:

```python
def find_anchor_point_in_target(target_file_path: str, 
                               anchor_code: str,
                               target_repo_path: str) -> int | None:
    """
    Find the actual line number where anchor_code appears in target_file.
    
    For imports: anchor_code = "import org.elasticsearch.cluster.node.DiscoveryNode;"
    For methods: anchor_code = method signature line
    """
    try:
        with open(os.path.join(target_repo_path, target_file_path), 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines, 1):
                # Normalize whitespace for matching
                if re.sub(r'\s+', ' ', line.strip()) == re.sub(r'\s+', ' ', anchor_code.strip()):
                    return i
    except FileNotFoundError:
        return None
    return None


def map_hunk_with_context_matching(
    target_repo_path: str,
    target_file_path: str,
    hunk_dict: dict,  # { "mainline_method", "role", "summary" }
) -> dict:
    """
    Map a hunk using code context matching instead of line number guessing.
    """
    role = hunk_dict.get("role")  # "declaration", "definition", etc.
    mainline_method = hunk_dict.get("mainline_method")
    
    if role == "declaration":
        # This is an import statement
        # Extract the import code from the hunk
        # Find where it should be inserted in the target file
        import_line = extract_import_statement(hunk_dict)
        
        # Find the right place in target file's import section
        anchor_line = find_import_insertion_point(target_file_path, import_line, target_repo_path)
        return {
            "target_file": target_file_path,
            "target_method": "<import>",
            "start_line": anchor_line,
            "end_line": anchor_line,
            "code_snippet": import_line,
        }
    
    else:
        # This is a method or code block
        # Find the method by searching for its signature
        method_sig = extract_method_signature(hunk_dict)
        method_line = find_method_in_target(target_file_path, method_sig, target_repo_path)
        
        if method_line:
            # Found it! Now extract the actual method boundaries
            start, end, signature = get_method_boundaries(
                target_file_path, method_sig, target_repo_path
            )
            return {
                "target_file": target_file_path,
                "target_method": mainline_method,
                "start_line": start,
                "end_line": end,
                "code_snippet": signature,
            }
    
    return None  # Could not map this hunk
```

---

## Solution 3: Pre-Compute Branch Divergence Offset

**Smart Fix:** Detect and account for structural differences upfront.

### Implementation:

```python
def compute_branch_divergence_offset(
    mainline_file_path: str,
    target_file_path: str,
    mainline_repo_path: str,
    target_repo_path: str,
) -> int:
    """
    Compute the cumulative line offset between mainline and target versions
    of the same file by comparing key anchor points.
    
    Returns: offset (target_line = mainline_line + offset)
    """
    offsets = []
    
    # Anchor 1: imports section
    mainline_last_import = find_last_import_line(
        os.path.join(mainline_repo_path, mainline_file_path)
    )
    target_last_import = find_last_import_line(
        os.path.join(target_repo_path, target_file_path)
    )
    if mainline_last_import and target_last_import:
        offsets.append(target_last_import - mainline_last_import)
    
    # Anchor 2: class declaration
    mainline_class_line = find_class_declaration_line(
        os.path.join(mainline_repo_path, mainline_file_path)
    )
    target_class_line = find_class_declaration_line(
        os.path.join(target_repo_path, target_file_path)
    )
    if mainline_class_line and target_class_line:
        offsets.append(target_class_line - mainline_class_line)
    
    # Return the average/most common offset
    if offsets:
        return int(sum(offsets) / len(offsets))
    return 0


def apply_divergence_offset(
    mainline_line: int, 
    divergence_offset: int,
) -> int:
    """
    Adjust a mainline line number to target file accounting for branch divergence.
    """
    return max(1, mainline_line + divergence_offset)
```

---

## Solution 4: Fallback Validation Chain

**Defensive Fix:** Verify that returned line numbers are actually correct.

### Implementation:

```python
def validate_line_number_mapping(
    target_file_path: str,
    target_repo_path: str,
    start_line: int,
    end_line: int,
    expected_code_snippet: str,
) -> bool:
    """
    Verify that the code at [start_line, end_line] in target file
    actually contains the expected code snippet.
    
    Returns True if mapping is valid, False otherwise.
    """
    try:
        with open(os.path.join(target_repo_path, target_file_path), 'r') as f:
            lines = f.readlines()
            
            # Check bounds
            if start_line < 1 or end_line > len(lines) or start_line > end_line:
                return False
            
            # Extract actual code at those lines
            actual_code = ''.join(lines[start_line-1:end_line])
            
            # Normalize and compare
            actual_norm = re.sub(r'\s+', ' ', actual_code.strip())
            expected_norm = re.sub(r'\s+', ' ', expected_code_snippet.strip())
            
            return expected_norm in actual_norm or expected_norm[:50] in actual_norm
    except (FileNotFoundError, IndexError):
        return False


def validate_and_correct_mapping(
    hunk_mapping: dict,
    target_repo_path: str,
) -> dict:
    """
    If mapping validation fails, attempt automatic correction.
    """
    target_file = hunk_mapping.get("target_file")
    start_line = hunk_mapping.get("start_line")
    end_line = hunk_mapping.get("end_line")
    code_snippet = hunk_mapping.get("code_snippet")
    
    # Try validation
    if validate_line_number_mapping(target_file, target_repo_path, start_line, end_line, code_snippet):
        return hunk_mapping  # Valid!
    
    # Validation failed — try to find the code nearby (±10 lines)
    for offset in range(-10, 11):
        corrected_start = start_line + offset
        corrected_end = end_line + offset
        if validate_line_number_mapping(target_file, target_repo_path, corrected_start, corrected_end, code_snippet):
            # Found it! Correct the mapping
            hunk_mapping["start_line"] = corrected_start
            hunk_mapping["end_line"] = corrected_end
            return hunk_mapping
    
    # Still invalid — mark as needing manual review
    hunk_mapping["validation_status"] = "FAILED"
    hunk_mapping["needs_manual_review"] = True
    return hunk_mapping
```

---

## Recommended Implementation Order

### **Priority 1 (CRITICAL - Fix Immediately):**
1. **Extract line numbers from patch headers** (Solution 1)
   - This is the most direct and reliable fix
   - Requires minimal code changes
   - Solves the problem completely for non-import hunks

### **Priority 2 (HIGH - Fix Next):**
2. **Add validation layer** (Solution 4)
   - Verify that returned line numbers are correct
   - Flag problematic mappings for review
   - Provide fallback search when validation fails

### **Priority 3 (MEDIUM - Enhance):**
3. **Detect branch divergence offset** (Solution 3)
   - Account for systematic line shifts across the file
   - Makes hunk generation more accurate

### **Priority 4 (LOW - Polish):**
4. **Context-based matching** (Solution 2)
   - More sophisticated but also more complex
   - Good for truly problematic cases where simple fixes don't work

---

## What NOT to Do

❌ **Don't rely solely on LLM line number guessing**
- LLMs can hallucinate line numbers
- No way to verify correctness without checking actual file

❌ **Don't assume identical structure across branches**
- Different branches = different code structures
- Must detect and account for differences

❌ **Don't ignore import statements**
- Imports need special handling (insertion point calculation)
- Can't use method boundary extraction for imports

---

## Testing the Fix

After implementing:

```python
# Test 1: Verify patch header extraction
mainline_start, mainline_end = extract_line_numbers_from_patch_header(mainline_patch, "DataNodeRequestSender.java")
target_start, target_end = extract_line_numbers_from_patch_header(target_patch, "DataNodeRequestSender.java")
assert mainline_start == 106  # From patch header
assert target_start == 126    # From patch header

# Test 2: Verify offsets match actual changes
offset = target_start - mainline_start  # Should be ~20
assert offset > 0  # Target has more code before this hunk

# Test 3: Validate all mapped lines
for file_path, hunk_list in mapped_target_context.items():
    for hunk in hunk_list:
        result = validate_line_number_mapping(
            hunk.get("target_file"),
            target_repo_path,
            hunk.get("start_line"),
            hunk.get("end_line"),
            hunk.get("code_snippet"),
        )
        assert result, f"Mapping invalid for {file_path} hunk {hunk.get('hunk_index')}"
```

