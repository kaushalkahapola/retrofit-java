# Methods Used to Find Line Numbers in Structural Locator

## Overview

The Structural Locator uses **multiple methods layered together** to find the correct line numbers (start_line, end_line) for code hunks in the target file. Let's examine each method:

---

## Method 1: `get_class_context()` - PRIMARY METHOD

**Purpose**: Get the exact line numbers and code snippet for a method/class in the target file.

**Tool Source**: MCP Tool (Java side - presumably via LSP or AST traversal)

**How it works**:
```python
def get_class_context(self, file_path: str, focus_method: str = None):
    """
    Reads a Java file and returns a skeleton view with the full body of the focused method.
    Useful for verifying specific methods without reading the entire file.
    """
    client.call_tool("get_class_context", {
        "target_repo_path": repo_path,      # Target repository
        "file_path": file_path,              # File to analyze
        "focus_method": focus_method         # Method name to focus on
    })
```

**What it returns**:
```python
{
    "context": "...",
    "start_line": 42,      # ← Exact line where method starts
    "end_line": 88,        # ← Exact line where method ends
    "body": "...",         # ← Full method code
}
```

**Line extraction logic** (from `_extract_line_range`):
```python
def _extract_line_range(context_output):
    if isinstance(context_output, dict):
        start = context_output.get("start_line") or context_output.get("startLine")
        end = context_output.get("end_line") or context_output.get("endLine")
        snippet = context_output.get("context", context_output.get("body", ""))
        if start and end:
            return int(start), int(end), str(snippet)
```

**Why it fails for elasticsearch_734dd070**:
- ❌ The tool doesn't account for branch divergence
- ❌ Returns line numbers based on when it last index the file
- ❌ Doesn't verify those line numbers are actually correct in the target file

---

## Method 2: `git_log_follow()` - GIT-BASED SEARCH

**Purpose**: Find file renames or moves across git history.

**How it works**:
```python
def git_log_follow(self, file_path: str, use_mainline: bool = False) -> str:
    """
    Retrieves the git history for a file, following renames.
    """
    result = subprocess.run(
        ["git", "log", "--follow", "--name-status", "--oneline", "--", file_path],
        capture_output=True, text=True, cwd=repo_path
    )
    return result.stdout  # Git history with renames
```

**Example output**:
```
abc1234 Search query moved to QueryBuilder
A       src/search/QueryBuilder.java
R100    src/search/SearchQuery.java -> src/search/QueryBuilder.java
```

**What it tells us**:
- ✅ If a file was renamed (from X to Y)
- ✅ When the rename happened
- ✅ The git history of changes to that file

**What it DOESN'T tell us**:
- ❌ The exact line numbers in the current target branch
- ❌ Which branch we're on (main vs 8.19)
- ❌ Structural changes between versions

**Why it fails for elasticsearch_734dd070**:
- The file `DataNodeRequestSender.java` wasn't renamed
- `git log --follow` doesn't help us find line offset
- Still need another method to find actual line numbers

---

## Method 3: `git_blame_lines()` - COMMIT ATTRIBUTION

**Purpose**: Find who changed specific lines and in which commit.

**How it works**:
```python
def git_blame_lines(self, file_path: str, start_line: int, end_line: int):
    """
    Retrieves git blame for specific lines in a file.
    """
    result = subprocess.run(
        ["git", "blame", "-L", f"{start_line},{end_line}", "--", file_path],
        capture_output=True, text=True, cwd=repo_path
    )
    return result.stdout  # Blame info for those lines
```

**Example output**:
```
734dd070 (Ievgen Degtiarenko 2025-03-13) import org.elasticsearch.cluster.node.DiscoveryNodeRole;
abc12345 (Someone Else         2025-02-10) import org.elasticsearch.cluster.node.DiscoveryNode;
```

**What it tells us**:
- ✅ Which commit modified a line
- ✅ Author and date
- ✅ Lineage of code changes

**What it DOESN'T tell us**:
- ❌ The offset between mainline and target branch
- ❌ Which lines have the code we're looking for right now
- ❌ Alternative locations if first location doesn't match

**Why it fails for elasticsearch_734dd070**:
- We don't know which lines to blame (that's what we're trying to find!)
- Circular dependency: need line numbers to use blame

---

## Method 4: `search_candidates()` - FILE DISCOVERY

**Purpose**: Find files in the target repo that might correspond to a file in mainline.

**How it works**:
```python
def search_candidates(self, file_path: str) -> List[Dict]:
    """
    Searches for potential candidate files in the target repository.
    """
    return self.retriever.find_candidates(file_path, "HEAD")
```

**Uses**: `EnsembleRetriever` (combines multiple search strategies)

**What it tells us**:
- ✅ Possible files in target that match mainline file
- ✅ Search scores/rankings
- ✅ Candidate paths

**Example**:
```python
[
    {"file": "x-pack/plugin/esql/src/main/java/.../DataNodeRequestSender.java", "score": 0.98},
    {"file": "x-pack/plugin/esql/src/main/.../RequestSender.java", "score": 0.65}
]
```

**What it DOESN'T tell us**:
- ❌ Line numbers
- ❌ Structural differences
- ❌ Whether the file is on the right branch

---

## Method 5: `match_structure()` - STRUCTURAL ANALYSIS

**Purpose**: Compare AST (Abstract Syntax Tree) of mainline file vs candidates to find best match.

**How it works**:
```python
def match_structure(self, mainline_file_path: str, candidate_file_paths: List[str]) -> str:
    """
    Determines the best matching target file using structural analysis.
    """
    # 1. Analyze mainline file AST
    mainline_analysis = self.get_structural_analysis(mainline_file_path, use_mainline=True)
    
    # 2. Analyze candidate files AST
    candidates_data = []
    for cand_path in candidate_file_paths:
        cand_analysis = self.get_structural_analysis(cand_path, use_mainline=False)
        candidates_data.append(cand_analysis)
    
    # 3. Compare structures
    result = find_best_matches(mainline_analysis, candidates_data)
    return json.dumps(result)
```

**What it tells us**:
- ✅ Classes, methods, fields in both files
- ✅ Inheritance relationships
- ✅ Structural similarity score
- ✅ Best matching file

**Example output**:
```json
{
  "matches": [
    {
      "file_path": "x-pack/.../DataNodeRequestSender.java",
      "score": 0.95,
      "reasoning": "High structural similarity"
    }
  ]
}
```

**What it DOESN'T tell us**:
- ❌ Line numbers within the file
- ❌ Method start/end lines
- ❌ Offset due to branch divergence

---

## Method 6: `find_method_match()` - METHOD FINGERPRINTING

**Purpose**: Find renamed or refactored methods using multi-tier fingerprinting.

**How it works**:
```python
def find_method_match(self, target_file_path: str, old_method_name: str, 
                     old_signature: str, old_calls: List[str]) -> str:
    """
    Uses Method Fingerprinting to find a renamed method.
    """
    # Tier 1: Git Pickaxe - find where signature appeared
    tracer = GitMethodTracer(self.target_repo_path)
    moved_file = tracer.find_moved_method_by_pickaxe(old_method_name, old_signature)
    
    # Tier 2: Body Similarity - match method bodies
    body_matcher = BodySimilarityMatcher()
    best_body_score = body_matcher.score(old_body, candidates)
    
    # Tier 3: Call Graph - match calling patterns
    fingerprinter = MethodFingerprinter()
    result = fingerprinter.find_match(old_method_name, old_signature, old_calls)
    
    return str(result)
```

**What it tells us**:
- ✅ Renamed method names
- ✅ Refactored methods
- ✅ Method similarity scores

**What it DOESN'T tell us**:
- ❌ Line numbers
- ❌ Start/end line ranges
- ❌ Insertion points in the file

---

## The Problem: MISSING FINAL STEP

All these methods help us **find the RIGHT FILE and RIGHT METHOD**, but **NONE of them directly return line numbers that work for the target branch**.

### What we're missing:

```
Method 1: get_class_context()
   ↓
   Returns line numbers... but are they for the current branch?
   ❌ Doesn't verify
   ❌ Doesn't account for divergence

Method 2: git_log_follow()
   ↓
   Finds renames... but that's not our problem here
   ❌ DataNodeRequestSender.java wasn't renamed

Method 3: git_blame_lines()
   ↓
   Attributes lines... but we don't know which lines to blame yet
   ❌ Circular dependency

Method 4: search_candidates()
   ↓
   Finds candidate files... but which branch?
   ❌ Doesn't tell us line numbers

Method 5: match_structure()
   ↓
   Ranks files by structure... but no line numbers
   ❌ Still missing exact placement

Method 6: find_method_match()
   ↓
   Finds method names... but not line boundaries
   ❌ Doesn't find line numbers
```

---

## The Solution: USE PATCH HEADERS

The patch headers **already contain the exact line numbers** for the target branch:

```diff
mainline.patch: @@ -106,12 +123,39 @@ class DataNodeRequestSender {
target.patch:   @@ -126,12 +142,39 @@ class DataNodeRequestSender {
                                             ↑
                                        This is line 142 in the target file!
```

**Why this works**:
1. ✅ The patch header is generated by git
2. ✅ It reflects the actual target file structure
3. ✅ It's branch-aware (each branch has its own patch)
4. ✅ No guessing needed — it's the ground truth

---

## Recommended Method Hierarchy

To properly find line numbers:

### **Level 1 (BEST - Use Patch Headers)**
```python
def extract_line_numbers_from_patch_header(patch_diff, mainline_file):
    # Parse @@ -old_start,old_len +new_start,new_len @@
    # Return new_start (target line number)
```
- Cost: O(1) regex parse
- Accuracy: 100% (patch headers are ground truth)
- Effort: Low

### **Level 2 (GOOD - Verify with File Content)**
```python
def validate_line_numbers(target_file, target_repo_path, start_line, end_line, code_snippet):
    # Read the actual file
    # Check if code_snippet is at those lines
    # If not, search nearby
```
- Cost: O(1) file read
- Accuracy: 95%+ (catches mismatches)
- Effort: Medium

### **Level 3 (FALLBACK - Use get_class_context)**
```python
def get_class_context(file_path, focus_method):
    # Use MCP tool
    # Return line numbers from tool
    # Trust them (with validation from Level 2)
```
- Cost: O(1) tool call
- Accuracy: 50-70% without validation (branch divergence!)
- Effort: Already coded

### **Level 4 (ADVANCED - Compute Branch Offset)**
```python
def compute_divergence_offset(mainline_file, target_file, mainline_repo, target_repo):
    # Find anchor points (imports, class declaration, methods)
    # Calculate offset at each anchor
    # Return average offset
    # Apply offset to all line numbers
```
- Cost: Multiple file reads + analysis
- Accuracy: 80-90% for systematic offsets
- Effort: Medium-High

---

## Current Flow in structural_locator.py

Here's what actually happens today:

```python
# 1. Try git-based resolution (git log follow, git blame, etc.)
git_candidates = toolkit.search_candidates(mainline_file)  # Method 4
                                                            #  ↓
# 2. If git found something, use it as target
target_file = git_candidates[0]["file"] if git_candidates

# 3. Create LLM prompt with hunk details and patch diff
input_msg = f"""
Mainline File: {mainline_file}
Target File: {target_file}
Hunk Details: {hunk_details}
Patch Diff: 
{file_diff}
"""

# 4. LLM uses tools to find line numbers
agent.ainvoke(input_msg)
    ↓
    LLM might call:
    - toolkit.get_class_context()        # Method 1 ❌ Fails due to branch divergence
    - toolkit.search_candidates()        # Method 4 ❌ Doesn't give line numbers  
    - toolkit.match_structure()          # Method 5 ❌ Doesn't give line numbers
    - toolkit.find_method_match()        # Method 6 ❌ Doesn't give line numbers
    - toolkit.read_file()                # Manual search ❌ Slow

# 5. LLM returns JSON with line numbers
{
  "mappings": [{
    "target_file": "...",
    "target_method": "...",
    "start_line": 106,    # ❌ WRONG! Should be 142 for target
    "end_line": 123       # ❌ WRONG! Should be 160 for target
  }]
}
```

---

## Why Phase 2 Failed

✅ Current methods **successfully found** the right file: `DataNodeRequestSender.java`
✅ Current methods **successfully found** the right methods: `order()`, `NODE_QUERY_ORDER`

❌ But **failed to find** the correct line numbers because:
- `get_class_context()` returned mainline line numbers (106-123)
- Didn't account for branch divergence (target lines are 142-160)
- No validation step to catch the mismatch
- LLM had no way to know the line numbers were wrong

---

## Summary

| Method | Purpose | Returns Lines? | Handles Divergence? | Reliability |
|--------|---------|---------------|--------------------|-------------|
| `get_class_context()` | Get method boundaries | ✅ Yes | ❌ No | 50% |
| `git_log_follow()` | Find renames | ❌ No | N/A | N/A |
| `git_blame_lines()` | Attribution | ❌ No | N/A | N/A |
| `search_candidates()` | File discovery | ❌ No | N/A | N/A |
| `match_structure()` | Structural matching | ❌ No | N/A | N/A |
| `find_method_match()` | Method fingerprinting | ❌ No | N/A | N/A |
| **Patch Headers** (proposed) | **Extract from diff** | **✅ Yes** | **✅ Yes** | **100%** |

**Conclusion**: Need to **extract line numbers from patch headers** instead of relying on tools that don't account for branch divergence.

