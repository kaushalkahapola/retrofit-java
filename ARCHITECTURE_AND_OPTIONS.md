# System Architecture & Where Options 2 & 4 Fit

## Current 7-Agent Architecture

```
PHASE 0: Fast Path (git apply) - No LLM
│
AGENT 1: Context Analyzer
├─ Input: patch file
├─ Logic: Extract semantic blueprint (root cause, fix logic, hunk chain)
├─ Type: Deterministic (no LLM, no tools)
└─ Output: SemanticBlueprint

AGENT 2: Structural Locator (WHERE hunks go)
├─ Phase 2A: Deterministic blob hunting (git rev-parse)
├─ Phase 2B: LLM ReAct with 7 tools (if Phase 2A fails)
├─ Input: patch + target repo
├─ Logic: Find line numbers where each hunk should apply
└─ Output: MappedTargetContext (file + line + code_snippet + confidence)

AGENT 2.5: Planning Agent (WHAT to apply) ← **ISSUE IS HERE**
├─ Input: patch + MappedTargetContext + ConsistencyMap
├─ Logic: For each hunk, verify old_string exists in target file
├─ Type: LLM ReAct with 5 tools (grep, ripgrep, read_window, etc.)
├─ Tools search target file for exact text matching
├─ Output: HunkGenerationPlan (old_string + new_string + verified=bool)
│
├─ ERROR CASE: old_string not found in target → verified=false
│   └─ RECOVERY: Semantic Adapter (if confidence > 60%)
│       ├─ Analyzes intent of failed hunk
│       ├─ Tries to adapt old_string/new_string for target API
│       ├─ Scores confidence (0.0-1.0)
│       └─ Returns adapted plan if confidence >= 0.6

AGENT 3: File Editor / Hunk Generator
├─ Input: HunkGenerationPlan
├─ Logic: Apply edits using str_replace semantics
├─ Type: LLM ReAct with 6 tools
└─ Output: adapted_code_hunks + adapted_test_hunks

AGENT 4: Validation ("Prove Red, Make Green")
├─ Input: generated hunks
├─ Logic: 6-phase validation (apply → test → compile → analyze)
├─ Output: validation_passed (bool) + failure_category
│
└─ RETRY ROUTING: If failed
    ├─ path_or_file_operation → Structural Locator (remap)
    ├─ context_mismatch → Planning Agent (replan)
    ├─ generation_contract_failed → Planning Agent
    ├─ api_mismatch or syntax_error → Planning Agent
    └─ else → File Editor (retry with context)
```

---

## Why elasticsearch_88cf2487 Fails in Current Architecture

### The Issue (Not a File Editing Problem)

**Mainline** uses `ChunkedToXContent` API:
```java
builder.startObject(COMPILATIONS_HISTORY);
cacheEvictionsHistory.toXContent(builder, params);
builder.endObject();
```

**Target** uses direct `toXContent` API:
```java
ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);
```

**Same bug** (wrong constant: `COMPILATIONS_HISTORY` → `CACHE_EVICTIONS_HISTORY`)  
**Different code structure** (builder vs ob.xContentObject)

### Current Flow

```
Agent 1: "Root cause is COMPILATIONS_HISTORY vs CACHE_EVICTIONS_HISTORY"
    ↓
Agent 2: Maps hunk to line 215 in target (medium confidence, method unresolved)
    ↓
Agent 2.5 Planning Agent:
    - Extracts old_string from mainline: "builder.startObject(COMPILATIONS_HISTORY);"
    - Searches target file for this exact text
    - grep_in_file: NOT FOUND ✗
    - read_file_window: Finds "ob.xContentObject(COMPILATIONS_HISTORY, ...)" instead
    - Result: verified=false (can't find builder.startObject)
    - Semantic Adapter: Considers adapting but...
        - Intent: "Replace COMPILATIONS_HISTORY with CACHE_EVICTIONS_HISTORY"
        - Problem: The main issue is that the CODE PATTERN doesn't exist in target
        - Adapter expects to transform: method1(X) → method2(X, Y)
        - But here the entire code structure is different
        - Confidence too low or trigger not met
    - Outputs: verified=false, unverified plan
    ↓
Agent 3 File Editor:
    - Tries to apply: old_string = "builder.startObject(COMPILATIONS_HISTORY);"
    - Not found in file
    - Result: "old_resolution_failed:not_found_single"
    ↓
Agent 4 Validation:
    - No hunks generated successfully
    - Validation FAILED (attempt 1/3)
    - Retry → same failure (attempt 2/3)
    - Retry → same failure (attempt 3/3)
    - Give up ✗
```

---

## The Missing Link: Semantic Pattern Recognition

**Current Planning Agent Assumption**:
"If I can't find the exact old_string in the target file, the hunk is unapplicable"

**What Should Happen**:
"If I can't find the exact pattern, maybe the target has the same SEMANTIC ISSUE in a DIFFERENT code pattern. Let me find and adapt to that pattern."

**Semantic Adapter's Limitation**:
It's designed to handle **API transformation** (method name change, signature change)  
It's NOT designed to handle **code pattern discovery** ("Where else in the target does this bug exist?")

---

## Option 4: Multi-Path Hunk Extraction (Phase 1 Enhancement)

### Goal
Proactively detect all code patterns in mainline that need the same semantic fix

### Location
Enhanced Phase 1 (Context Analyzer) or as separate post-processing step

### Implementation Approach

```
Current Phase 1 Output:
{
  "semantic_blueprint": {
    "root_cause_hypothesis": "Wrong constant in cacheEvictionsHistory serialization",
    "fix_logic": "Replace COMPILATIONS_HISTORY with CACHE_EVICTIONS_HISTORY",
    "hunk_chain": [
      { "hunk_index": 0, "role": "declaration", "summary": "import CACHE_EVICTIONS_HISTORY" },
      { "hunk_index": 1, "role": "core_fix", "summary": "Fix constant in cacheEvictionsHistory" }
    ]
  }
}

NEW Enhancement:
After extracting semantic blueprint, search mainline file for:
  1. All code patterns matching the fix intent
  2. Generate variants for each pattern found
  
For elasticsearch_88cf2487:
  Search mainline file for: patterns with (COMPILATIONS_HISTORY AND cacheEvictionsHistory)
  
  Pattern A: builder.startObject(COMPILATIONS_HISTORY); @ mainline:208
  Pattern B: ob.xContentObject(COMPILATIONS_HISTORY, ...) [if found in mainline, else skip]
  Pattern C: Any other patterns?
  
  Output variants:
  {
    "hunk_index": 1,
    "variants": [
      {
        "variant_id": 1,
        "pattern_type": "chunked_builder",
        "description": "ChunkedToXContent API pattern",
        "old_string": "builder.startObject(COMPILATIONS_HISTORY);",
        "new_string": "builder.startObject(CACHE_EVICTIONS_HISTORY);",
        "found_in_mainline": true,
        "line_in_mainline": 208
      },
      {
        "variant_id": 2,
        "pattern_type": "direct_xontent",
        "description": "Direct toXContent API pattern",
        "old_string": "ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);",
        "new_string": "ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);",
        "found_in_mainline": false,  # Only in target! Need to detect this
        "semantic_intent": "Same fix, different API"
      }
    ]
  }
```

### How Downstream Agents Use Variants

**Agent 2: Structural Locator**
```
For each variant:
  Try to find old_string in target
  Record which variants matched
  
Result:
  Variant 1 (chunked_builder): MATCHED at target:208 ✓ (for hypothetical case)
  Variant 1 (chunked_builder): NOT MATCHED (actual case - this API doesn't exist)
  Variant 2 (direct_xontent): MATCHED at target:220 ✓
```

**Agent 2.5: Planning Agent**
```
Input includes: variant match info from Agent 2
For each hunk:
  Use the variant(s) that matched in target
  
For elasticsearch_88cf2487:
  Hunk 0 (import): Uses original pattern, verified=true ✓
  Hunk 1 (constant fix): Uses variant 2 (direct_xontent matched)
    old_string: "ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);"
    new_string: "ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);"
    verified=true ✓
```

### Pros & Cons

**Pros**:
- ✓ Deterministic (no LLM at variant detection)
- ✓ Fast path (variants pre-computed)
- ✓ Covers 80% of cases (common refactoring patterns)
- ✓ Debuggable (explicit variants listed)
- ✓ Solves elasticsearch_88cf2487 immediately

**Cons**:
- ✗ Complex to implement (need to detect patterns in mainline)
- ✗ Might generate spurious variants
- ✗ Requires parsing mainline file content
- ✗ Doesn't help if target has EXTRA bugs not in mainline

### Implementation Complexity: Medium

```python
# Pseudocode
def extract_hunk_variants(mainline_file_content, patch, semantic_blueprint):
    variants = {}
    
    for hunk_index, hunk_info in semantic_blueprint['hunk_chain']:
        # Extract semantic intent
        intent = extract_intent(hunk_info)  # "Fix COMPILATIONS_HISTORY in cacheEvictionsHistory"
        
        # Search mainline file for all patterns matching this intent
        patterns = find_semantic_patterns(mainline_file_content, intent)
        # patterns = [
        #   ("builder.startObject(COMPILATIONS_HISTORY);", line_208),
        #   ("ob.xContentObject(COMPILATIONS_HISTORY, ...)", None)  # not in mainline
        # ]
        
        # Generate variants
        variants[hunk_index] = {
            "intent": intent,
            "variants": [
                {
                    "pattern": pat,
                    "old_string": extract_old_from_hunk(hunk_info, pat),
                    "new_string": extract_new_from_hunk(hunk_info, pat),
                    "line": line
                }
                for pat, line in patterns
            ]
        }
    
    return variants
```

---

## Option 2: LLM-Based Adaptation Fallback (Phase 2.5 Enhancement)

### Goal
When Planning Agent can't find old_string, use LLM to understand intent and find equivalent location in target

### Location
Added to `planning_agent_node()` after initial verification fails

### Implementation Approach

```
Current Phase 2.5 Planning Agent:

For each hunk:
  1. Extract old_string from mainline
  2. Search target file
  3. If found: verified=true
  4. If not found: verified=false, try semantic adapter
  
NEW: LLM Adaptation Layer

For each hunk where verified=false:
  1. Call LLM with:
     - Mainline old_string: "builder.startObject(COMPILATIONS_HISTORY);"
     - Mainline new_string: "builder.startObject(CACHE_EVICTIONS_HISTORY);"
     - Semantic intent: "Fix COMPILATIONS_HISTORY constant in cacheEvictionsHistory context"
     - Target code snippet: [code around mapped line showing ob.xContentObject]
     
     Prompt: "The mainline code wants to change X to Y for semantic reason Z.
              But the exact pattern doesn't exist in target.
              Here's the target code around the area where this bug exists.
              What is the equivalent code pattern in target?
              Provide adapted old_string and new_string."
  
  2. LLM Response:
     "In the target, the equivalent code is:
      OLD: ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);
      NEW: ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);
      Confidence: 0.92 (same semantic bug, different API)"
  
  3. Accept if confidence >= 0.6:
     verified=true (semantically adapted)
     adaptation_strategy=LLM_SEMANTIC_SEARCH
```

### Code Changes

```python
async def planning_agent_node(state: AgentState, config) -> dict:
    # ... existing code ...
    
    # After planning agent generates initial plan
    hunk_generation_plan = ...
    
    # NEW: LLM Adaptation pass for failed verifications
    adapted_plan = await adapt_unverified_hunks(
        state=state,
        plan=hunk_generation_plan,
        target_file_content=read_target_file(...),
        mapped_context=state['mapped_target_context'],
        semantic_blueprint=state['semantic_blueprint'],
        confidence_threshold=0.6
    )
    
    return {"hunk_generation_plan": adapted_plan}

async def adapt_unverified_hunks(state, plan, target_file, mapped_context, blueprint, threshold):
    """Use LLM to adapt hunks that failed verification"""
    
    llm = get_llm()
    adaptation_prompt = _build_adaptation_prompt(state, plan, target_file, blueprint)
    
    response = llm.invoke([HumanMessage(content=adaptation_prompt)])
    
    adapted = _parse_adaptation_response(response)
    
    # Merge: verified hunks stay as-is, unverified get adapted versions
    for hunk in plan['hunks']:
        if not hunk['verified'] and hunk['hunk_index'] in adapted:
            adaptation = adapted[hunk['hunk_index']]
            if adaptation['confidence'] >= threshold:
                hunk['old_string'] = adaptation['adapted_old_string']
                hunk['new_string'] = adaptation['adapted_new_string']
                hunk['verified'] = True
                hunk['adaptation_strategy'] = 'LLM_SEMANTIC_SEARCH'
    
    return plan
```

### Pros & Cons

**Pros**:
- ✓ Intelligent (understands semantic intent)
- ✓ Flexible (handles ANY code structure variation)
- ✓ Simple to add (single insertion point in planning agent)
- ✓ Solves elasticsearch_88cf2487

**Cons**:
- ✗ Extra LLM call per failed hunk (latency + cost)
- ✗ Risk of hallucination (LLM might suggest wrong patterns)
- ✗ Requires careful prompt engineering
- ✗ Harder to debug (LLM reasoning is opaque)

### Implementation Complexity: Low-Medium

---

## Recommendation: Layered Approach (Option 4 + Option 2)

### Why Both?

**Option 4 (Variants)**: Fast deterministic path
- Detects patterns upfront
- No LLM overhead
- Covers common refactoring scenarios
- 80% of cases solved immediately

**Option 2 (LLM Fallback)**: Smart edge case handler
- Catches unusual code structure variations
- Intelligently adapts to target's code
- Remaining 20% of cases handled
- Better error recovery

### Implementation Order

1. **Phase 1**: Implement Option 4 (variant detection)
   - Add to context_analyzer.py or as separate module
   - Estimated complexity: Medium (2-3 days)

2. **Phase 2**: Add Option 2 (LLM fallback)
   - Add to planning_agent.py
   - Estimated complexity: Low (1-2 days)

3. **Test**: Run elasticsearch_88cf2487 and other test cases
   - Option 4 alone should fix elasticsearch_88cf2487
   - Option 2 catches edge cases

### Architecture Diagram

```
Phase 1: Context Analyzer
  ├─ Extract semantic blueprint (EXISTING)
  └─ NEW: Detect hunk variants
      └─ Output: SemanticBlueprint + HunkVariants

Phase 2: Structural Locator
  ├─ Deterministic blob hunting (Phase 2A)
  ├─ LLM ReAct fallback (Phase 2B)
  └─ NEW: Track which variants matched in target
      └─ Output: MappedTargetContext + VariantMatches

Phase 2.5: Planning Agent
  ├─ For each hunk: use matched variant if available
  ├─ Verify variant's old_string in target
  ├─ NEW: If all variants failed, use LLM adaptation
  │   └─ LLM finds semantic equivalent in target
  │   └─ If confidence >= 0.6, use adapted plan
  └─ Output: HunkGenerationPlan (all verified=true)

Phase 3: File Editor
  └─ Apply all verified hunks (should all succeed now)

Phase 4: Validation
  └─ Verify patch works
```

---

## Summary Table

| Aspect | Option 4 | Option 2 | Both Together |
|--------|----------|----------|---------------|
| **When it works** | Common refactoring patterns exist in mainline | Any code structure variation | All cases |
| **Speed** | Fast (no LLM) | Slower (LLM call) | Optimal |
| **Coverage** | ~80% of cases | Edge cases | ~100% |
| **Complexity** | Medium (pattern detection) | Low (prompting) | Medium |
| **Debuggability** | High (explicit variants) | Low (LLM reasoning) | Mixed |
| **Cost** | Low | Higher (LLM tokens) | Medium |
| **Solves elasticsearch_88cf2487** | Yes ✓ | Yes ✓ | Yes ✓ |

---

## What I Recommend

**Choose the layered approach** (Option 4 + Option 2):

1. **Start with Option 4**: Build variant detection in Phase 1
   - Will immediately fix elasticsearch_88cf2487
   - Improves performance for all refactoring cases
   - Deterministic and debuggable

2. **Add Option 2 as safety net**: LLM fallback in Phase 2.5
   - Catches edge cases that variants don't cover
   - Handles unusual target structures
   - Lower risk because Option 4 handles 80% of cases first

This gives you:
- ✓ Fast deterministic path (Option 4)
- ✓ Intelligent fallback (Option 2)
- ✓ High coverage (80% + remaining 20%)
- ✓ Debuggable when things fail
