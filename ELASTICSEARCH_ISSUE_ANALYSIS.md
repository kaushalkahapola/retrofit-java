# Elasticsearch_88cf2487 Issue Analysis

## Current Architecture Overview

### The 7-Agent Pipeline

```
INPUT PATCH
    ↓
[Phase 0] → Fast Path (git apply) → SUCCESS ✓ or FAIL → continue
    ↓
[Agent 1] Context Analyzer (DETERMINISTIC, no LLM)
    INPUT: patch + files
    OUTPUT: SemanticBlueprint (root_cause, fix_logic, hunk_chain)
    ↓
[Agent 2] Structural Locator (DETERMINISTIC + LLM ReAct)
    Phase 2A: Deterministic blob hunting + line anchoring
    Phase 2B: LLM ReAct with 7 tools (if Phase 2A fails)
    OUTPUT: ConsistencyMap + MappedTargetContext (file locations with line numbers)
    ↓
[Agent 2.5] Planning Agent (LLM ReAct with 5 tools) ← KEY AGENT FOR THIS ISSUE
    INPUT: patch + MappedTargetContext + ConsistencyMap
    GOAL: For each hunk, verify old_string exists in target file
    OUTPUT: HunkGenerationPlan (edit_type + old_string + new_string with verified=bool)
    ↓
[Agent 2.5 Recovery] Semantic Hunk Adapter (Called from Planning Agent)
    TRIGGER: old_string verification fails + confidence > 60%
    INPUT: failed hunk + target code
    OUTPUT: adapted_old_string + adapted_new_string (if confidence ≥ 60%)
    ↓
[Agent 3] File Editor / Hunk Generator (LLM ReAct, generates code hunks)
    INPUT: HunkGenerationPlan + target file
    GOAL: Actually apply edits and capture diff
    OUTPUT: adapted_code_hunks + adapted_test_hunks
    ↓
[Agent 4] Validation (6-phase "Prove Red, Make Green" loop)
    INPUT: generated hunks
    GOAL: Prove vulnerability exists before fix, prove fix works after
    OUTPUT: validation_passed (bool) + failure_category (for retry routing)
    ↓
RETRY LOGIC: If validation fails, route back based on failure category
```

---

## What Each Agent Actually Does

### Agent 1: Context Analyzer (src/agents/context_analyzer.py)
**Purpose**: Understand the patch semantically WITHOUT applying it
**Type**: Deterministic (no LLM)
**Output**:
```json
{
  "root_cause_hypothesis": "Fixing serialization of ScriptStats cache_evictions_history",
  "fix_logic": "Add CACHE_EVICTIONS_HISTORY import and fix wrong constant usage",
  "dependent_apis": ["CACHE_EVICTIONS_HISTORY", "COMPILATIONS_HISTORY", ...],
  "hunk_chain": [
    { "hunk_index": 0, "role": "declaration", "summary": "Add import" },
    { "hunk_index": 1, "role": "core_fix", "summary": "Replace wrong constant" }
  ]
}
```

**Does it understand semantics?** YES, but only from the patch text itself
**Does it adapt?** NO, it's purely analysis

---

### Agent 2: Structural Locator (src/agents/structural_locator.py)
**Purpose**: Find WHERE in the target file each hunk should go
**Type**: Deterministic Phase 2A + LLM ReAct Phase 2B
**Process**:
1. **Phase 2A (Deterministic)**: Use raw diff context + git blob hunting
   - Read mainline file, extract git blob hash
   - Search target repo: `git rev-parse HEAD:<path>:<blob_hash>`
   - If found → line number is EXACT
2. **Phase 2B (LLM ReAct)**: If Phase 2A fails, use 7 tools
   - search_candidates, match_structure, git_pickaxe, grep_repo, etc.

**Output**:
```json
{
  "mapped_target_context": {
    "server/src/main/java/org/elasticsearch/script/ScriptStats.java": [
      {
        "hunk_index": 0,
        "mainline_method": "<import>",
        "target_file": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
        "target_method": "<import>",
        "start_line": 26,
        "end_line": 26,
        "code_snippet": "... surrounding code ...",
        "anchor_confidence": "high"
      },
      {
        "hunk_index": 1,
        "mainline_method": "hunk_2",
        "target_method": null,  ← FAILED TO MATCH METHOD
        "start_line": 215,
        "end_line": 215,
        "code_snippet": "... ob.xContentObject(COMPILATIONS_HISTORY, ...) ...",
        "anchor_confidence": "medium"
      }
    ]
  }
}
```

**Does it understand semantics?** NO, purely structural matching
**Does it use LLM?** YES (Phase 2B as fallback)
**Key limitation**: Maps hunk to a line number, but doesn't verify exact text

---

### Agent 2.5: Planning Agent (src/agents/planning_agent.py) ← **THE ISSUE**
**Purpose**: Convert hunks into str_replace edit plans (old_string + new_string format)
**Type**: LLM ReAct with 5 tools
**Tools**:
- `find_method_definitions(file_path)` → Find method/class declarations
- `ripgrep_in_file(pattern, offset, limit)` → Paginated regex search
- `find_symbol_references(symbol, offset, limit)` → Find usage of a symbol
- `read_file_window(file_path, center_line, radius)` → Read code around a line
- `verify_context_at_line(file_path, line, expected_text)` → Confirm exact text

**Workflow for each hunk**:
1. **Extract** old_string from mainline diff (the `-` lines)
2. **Search** in target file using tools (grep_in_file, read_file_window, etc.)
3. **Verify** old_string exists in target file
4. **Build** new_string by adapting the `+` lines from mainline
5. **Output** HunkGenerationPlan with verified=true/false

**For elasticsearch_88cf2487**:
- Hunk 0 (import): ✓ Found and verified
- Hunk 1 (builder.startObject): ✗ **NOT FOUND** in target
  - Agent 2 mapped it to line 215
  - But line 215 in target is: `ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);`
  - Planning Agent looks for: `builder.startObject(COMPILATIONS_HISTORY);`
  - **RESULT**: verification_result = "sanitize_old_not_found:not_found_single"

**Current output**:
```json
{
  "hunk_index": 1,
  "target_file": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "edit_type": "replace",
  "old_string": "builder.startObject(COMPILATIONS_HISTORY);",
  "new_string": "builder.startObject(CACHE_EVICTIONS_HISTORY);",
  "verified": false,  ← FAILED VERIFICATION
  "verification_result": "sanitize_old_not_found:not_found_single"
}
```

**Does it understand semantics?** PARTIALLY
- It reads the target code
- It uses grep + read_file_window
- But it's looking for EXACT TEXT matching
- **It doesn't recognize**: "This is the same semantic change needed in different code"

**Does it use LLM?** YES (to guide tool usage and search strategy)

**Key weakness for this issue**:
- Planning Agent generated 3 hunks from the mainline patch
- 2 worked (import + one xContentObject call)
- 1 failed (builder.startObject)
- But **the semantic intent is the same**: "Fix COMPILATIONS_HISTORY → CACHE_EVICTIONS_HISTORY"
- **The target code already has the bug TWICE** in different locations:
  - Line 220: `ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);` ✓ FOUND & FIXED
  - Line 223: `ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);` ← NEEDS FIX (but NOT in mainline)
  - builder.startObject location: DOESN'T EXIST in target (different architecture)

---

### Agent 2.5 Recovery: Semantic Hunk Adapter (src/agents/semantic_hunk_adapter.py)
**Purpose**: Recover from verification failures by intelligently adapting hunks
**Type**: Rules-based (no LLM) + confidence scoring
**Trigger**: old_string not found in target + semantic_diagnosis confidence > 60%

**Workflow**:
1. **Extract Intent**: Analyze old_string/new_string to understand what's changing
   - "Replace COMPILATIONS_HISTORY with CACHE_EVICTIONS_HISTORY"
   - Operation type: METHOD_CALL (0.8 confidence base)
2. **Find Equivalent Location**: 3 strategies
   - Diagnosis: From planning agent's failure context
   - Identifier: Look for semantic tokens (COMPILATIONS_HISTORY, cacheEvictionsHistory)
   - Fuzzy: Similarity matching
3. **Recompose Hunk**: Adapt to target API
   - If original was: `builder.startObject(X);`
   - But target uses: `ob.xContentObject(X, Y);`
   - Transform to: `ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);`
4. **Validate**: Check bracket balance, keyword preservation
5. **Score Confidence**: base_score × validation_penalty

**Current behavior**:
- **NOT BEING CALLED** for elasticsearch_88cf2487
- Why? Because the planning agent's confidence < 60% OR
- The adapter isn't being invoked from planning_agent_node

**Key insight**: Semantic adapter is designed for API transformations
- Can handle: `method1(X)` → `method2(X)` (rename)
- Can handle: `obj.method(X)` → `obj.method(X, Y, Z)` (signature change)
- **CAN'T handle**: Finding the right location to apply the change to target code

---

### Agent 3: File Editor / Hunk Generator (src/agents/file_editor.py)
**Purpose**: Actually apply the edits and capture the resulting diff
**Type**: LLM ReAct with 6 tools
**Input**: HunkGenerationPlan from Planning Agent

**What it receives for elasticsearch_88cf2487**:
```json
{
  "server/src/main/java/org/elasticsearch/script/ScriptStats.java": [
    {
      "hunk_index": 0,
      "old_string": "import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;",
      "new_string": "import static ... CACHE_EVICTIONS_HISTORY;\nimport static ... COMPILATIONS_HISTORY;",
      "verified": true
    },
    {
      "hunk_index": 1,
      "old_string": "ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);",
      "new_string": "ob.xContentObject(CACHE_EVICTIONS_HISTORY, compilationsHistory);",
      "verified": false  ← FROM PLANNING AGENT
    },
    {
      "hunk_index": 2,
      "old_string": "builder.startObject(COMPILATIONS_HISTORY);",
      "new_string": "builder.startObject(CACHE_EVICTIONS_HISTORY);",
      "verified": false  ← FROM PLANNING AGENT
    }
  ]
}
```

**Process**:
1. Read target file
2. For each edit, try to apply it
3. Hunk 1: ✓ Found and applied
4. Hunk 2: ✗ Not found → fails with "not_found_single"
5. Hunk 3: ✗ Not found → fails with "not_found_single"
6. Returns: adapted_code_hunks = [] (empty, because no edits worked)

**Agent 4 sees**: No hunks generated → Validation FAILED

---

## The Real Problem

### The Semantic Issue (NOT a file editing issue)

**Mainline code structure** (ChunkedToXContent):
```java
if (cacheEvictionsHistory != null && ...) {
    builder.startObject(COMPILATIONS_HISTORY);    // ← BUG (wrong constant)
    cacheEvictionsHistory.toXContent(builder, params);
    builder.endObject();
}
```

**Target code structure** (direct toXContent):
```java
if (cacheEvictionsHistory != null && ...) {
    ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);  // ← SAME BUG (wrong constant)
}
```

**The problem**: 
- Mainline and target use **DIFFERENT APIs** for the same logical operation
- Mainline: `builder.startObject(...)` → `toXContent()` → `endObject()`
- Target: `ob.xContentObject(..., ...)`
- **The bug is in both**, but in different code patterns
- Planning Agent generates hunks for mainline code patterns
- But target doesn't have those patterns!

**Current flow**:
1. Planning Agent looks for `builder.startObject(COMPILATIONS_HISTORY)`
2. Can't find it in target
3. Marks verified=false
4. File Editor tries to apply anyway → fails
5. Semantic Adapter not invoked (wrong trigger condition)
6. Agent 4 validation fails → retry
7. Loop repeats 3 times → gives up

---

## Why Current Components Fail

### Planning Agent's Limitation
**Design**: Designed to search for exact old_string text in target
**Assumption**: Target file is similar structure to mainline
**Reality for elasticsearch_88cf2487**: Target has fundamentally different API
**Result**: old_string verification fails → generates unverified plan → File Editor fails

### Semantic Hunk Adapter's Limitation
**Design**: Designed to adapt when old_string not found, using semantic analysis
**Current trigger**: Called from planning_agent when confidence > 60%
**Problem**: 
- It's designed to transform `method1(X)` → `method2(X)`
- NOT designed to say: "This code pattern doesn't exist in target, but the bug still exists here"
- It can't proactively search for WHERE the bug is in the target

---

## Where Option 2 and Option 4 Would Fit

### Option 4 (Multi-Path Hunk Extraction) - Phase 1
**Location**: In Context Analyzer or as post-processing after it

**How it works**:
```
Phase 1: Context Analyzer (EXISTING)
    Outputs: SemanticBlueprint (current behavior)
    
NEW Post-Phase-1: Variant Generation
    INPUT: mainline patch + mainline file content
    GOAL: Detect multiple code patterns that need the same fix
    
    For each hunk:
        Extract semantic intent: "Fix COMPILATIONS_HISTORY → CACHE_EVICTIONS_HISTORY in cacheEvictionsHistory context"
        
        Search mainline file for ALL code patterns matching this intent:
        - Pattern 1: builder.startObject(COMPILATIONS_HISTORY) ✓ Found at mainline line 208
        - Pattern 2: ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory)? [search mainline...]
        - Pattern 3: Any other similar pattern?
        
        Output variants:
        [
            {
                "hunk_index": 1,
                "pattern_type": "chunked_builder",
                "old_string": "builder.startObject(COMPILATIONS_HISTORY);",
                "new_string": "builder.startObject(CACHE_EVICTIONS_HISTORY);",
                "context": "in cacheEvictionsHistory block (ChunkedToXContent)"
            },
            {
                "hunk_index": 1,
                "pattern_type": "direct_xontent",
                "old_string": "ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);",
                "new_string": "ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);",
                "context": "in cacheEvictionsHistory block (direct toXContent)"
            }
        ]
    
    Output: Enhanced SemanticBlueprint with variants
    
Agent 2: Structural Locator (MODIFIED)
    For each hunk variant:
        Try to anchor it in target file
        Record which variant(s) match
    
    Output ConsistencyMap + MappedTargetContext
    But MARK which variant matched
    
Agent 2.5: Planning Agent (MODIFIED)
    Use only the variant(s) that Agent 2 found in target
    Generate plan using whichever variant matched
    
Result: For elasticsearch_88cf2487:
    - Variant "chunked_builder": NOT FOUND in target
    - Variant "direct_xontent": FOUND in target ✓
    - Plan uses "direct_xontent" variant → succeeds
```

**Pros of Option 4**:
- Proactive: Detects code structure differences during Phase 1
- Deterministic: No LLM at variant detection time
- Fast: Phase 2 just picks the right variant
- Debuggable: Explicit list of variants generated

**Cons of Option 4**:
- Complexity: Need to detect ALL code patterns in mainline
- False positives: Might generate irrelevant variants
- Overhead: Need to analyze mainline file content + search for patterns

---

### Option 2 (LLM-Based Adaptation) - Phase 2.5 Fallback
**Location**: After Planning Agent, before File Editor

**How it works**:
```
Planning Agent: Generates plan
    (Some hunks verified=true, some verified=false)
    
NEW: LLM Adaptation Layer
    For each hunk where verified=false:
        Extract semantic intent from (old_string, new_string)
        
        Query target code:
        "The mainline hunk tries to do: 'Replace COMPILATIONS_HISTORY with CACHE_EVICTIONS_HISTORY'
         But the old_string 'builder.startObject(COMPILATIONS_HISTORY)' doesn't exist in target.
         Here's the target code around the area where this bug should be fixed:
         [code snippet showing ob.xContentObject usage]
         
         Where should we apply this fix in the target code? Generate adapted (old_string, new_string)."
        
        LLM reads target code, recognizes:
            - Pattern: ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory)
            - Intent: Same bug (wrong constant)
            - Adaptation: Apply the same fix to this code pattern
            - Output: {
                "adapted_old_string": "ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);",
                "adapted_new_string": "ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);",
                "confidence": 0.92
              }
        
        If confidence >= 0.6:
            Use adapted plan instead of original
        Else:
            Mark as unrecoverable, skip hunk
    
File Editor: Gets adapted plan and applies successfully
```

**Pros of Option 2**:
- Smart: LLM understands semantic intent and code context
- Flexible: Works for ANY code structure variations
- Simple: Single fallback point in planning agent

**Cons of Option 2**:
- LLM call overhead: Extra call per failed hunk
- Latency: Adds delay to planning phase
- False positives: Might suggest wrong locations
- Cost: More LLM calls = more tokens

---

## Recommendation: Layered Approach (Option 4 + Option 2)

### Layer 1: Variant Detection (Option 4) - FAST PATH
**Timing**: Phase 1 (Context Analyzer) or early Phase 2 (Structural Locator)
**Goal**: Cover 80% of cases with deterministic pattern detection

```
For common refactoring patterns:
- Method rename: methodA → methodB
- Builder pattern change: builder.startObject() → ob.xContentObject()
- API signature change: method(X) → method(X, Y)
- Field name change: field1 → field2

Pre-generate variants for these patterns in mainline
Let Agent 2 find which variant exists in target
Agent 2.5 planning uses the matched variant
```

### Layer 2: LLM Adaptation (Option 2) - FALLBACK
**Timing**: After Planning Agent (Phase 2.5)
**Goal**: Handle remaining 20% of edge cases

```
If ANY hunk still has verified=false after planning:
    Use LLM to understand semantic intent
    Search target code for semantically equivalent location
    Generate adapted old_string + new_string
    If confidence >= 0.6: use adapted plan
    Else: mark as unrecoverable
```

### For elasticsearch_88cf2487 Specifically

**Layer 1 Would Help**:
- Detect during Phase 1: "builder.startObject(X)" in cacheEvictionsHistory context
- Detect during Phase 1: "ob.xContentObject(X, Y)" in cacheEvictionsHistory context
- Generate both as variants
- Agent 2 tries both patterns
- Pattern 2 matches in target
- Planning Agent uses pattern 2
- Success!

**Layer 2 Would Help**:
- Planning Agent can't find builder.startObject
- Asks LLM: "Where's the analogous code pattern in target?"
- LLM finds and adapts to ob.xContentObject pattern
- Success!

---

## Next Steps (If You Choose to Implement)

1. **Decide**: Do you want Option 4 (proactive), Option 2 (fallback), or both?
2. **If Option 4**: Implement variant detection in Phase 1
3. **If Option 2**: Implement LLM fallback in planning_agent_node
4. **Test**: Run elasticsearch_88cf2487 again
5. **Iterate**: Refine based on what works
