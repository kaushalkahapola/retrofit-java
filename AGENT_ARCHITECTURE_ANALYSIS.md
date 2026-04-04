# Java Backport System - Agent Architecture Analysis

## Executive Summary

This is a sophisticated 4-Agent LLM orchestration system designed to backport Java security patches from a mainline (newer) repository to a target (older) repository. The system uses a **H-MABS (Hybrid Multi-Agent Backport System)** approach with deterministic anchoring, semantic hunk adaptation, and iterative validation.

---

## 1. System Overview & Data Flow

### High-Level Pipeline

```
START
  ↓
[Phase 0: Optimistic Fast-Path] ← Attempts direct git apply
  ↓ (if failed)
[Agent 1: Context Analyzer] → SemanticBlueprint
  ↓
[Agent 2: Structural Locator] → ConsistencyMap + MappedTargetContext
  ↓
[Planning Agent (Phase 2.5)] → HunkGenerationPlan (str_replace edits)
  ↓
[Agent 3: File Editor (Hunk Generator)] → AdaptedHunks (git diff output)
  ↓
[Agent 4: Validation] → Verify via compilation & tests
  ↓ (if failed, retry with feedback)
[Retry Loop] ↻ (max 3 attempts)
  ↓ (if passed or exhausted)
END
```

### Data Flow Visualization

```
patch_diff (unified diff)
    ↓
Context Analyzer (Agent 1) → semantic_blueprint
    ↓
Structural Locator (Agent 2) → consistency_map + mapped_target_context
    ↓
Planning Agent → hunk_generation_plan (old_string → new_string mappings)
    ↓
File Editor (Agent 3) → adapted_code_hunks + adapted_test_hunks
    ↓
Validation Agent (Agent 4) → validation_results
    ↓
[If failed] → validation_error_context (feedback for retry)
    ↓
[Hunk Generator Retry Loop]
```

---

## 2. Detailed Agent Descriptions

### Agent 1: Context Analyzer (Deterministic)

**Purpose**: Build a semantic blueprint of the patch without LLM calls.

**Input**:
- `patch_diff`: Raw unified diff text
- `with_test_changes`: Boolean flag to include/exclude test files

**Output**:
```python
semantic_blueprint = {
    "root_cause_hypothesis": str,  # e.g., "Missing bounds check"
    "fix_logic": str,              # e.g., "Add if(size > MAX) check"
    "dependent_apis": list[str],   # e.g., ["alloc_buf", "MAX_SIZE"]
    "patch_intent_summary": str,   # One-sentence summary
    "hunk_chain": list[HunkRole]   # Ordered chain of hunks with roles
}
```

**Key Methods**:
- `_infer_role()`: Classify hunk as "declaration", "guard", "core_fix", "propagation"
- `_hunk_summary()`: Count added/removed lines
- Filters out test files if `with_test_changes=False`

**LLM Usage**: NONE (fully deterministic)

**Limitations**:
- Does not analyze semantic meaning deeply
- Relies on heuristics to infer roles
- No structural understanding of the target codebase

---

### Agent 2: Structural Locator (H-MABS Phase 2)

**Purpose**: Find exact insertion points in the target repository despite structural divergence (renames, splits, moves).

**Input**:
- `semantic_blueprint`: From Agent 1
- `patch_analysis`: List[FileChange] with file paths and hunks
- `target_repo_path`: Path to target (older) repo
- `mainline_repo_path`: Path to mainline (newer) repo

**Output**:
```python
consistency_map = {
    "mainline_symbol": "target_symbol",  # e.g., {"oldMethod": "legacyMethod"}
    ...
}

mapped_target_context = {
    "src/Foo.java": [
        {
            "hunk_index": 0,
            "mainline_method": "fooOld",
            "target_file": "src/Foo.java",
            "target_method": "legacyFoo",
            "start_line": 42,
            "end_line": 88,
            "code_snippet": "...",
            "anchor_confidence": "high",
            "anchor_reason": "line_and_method_resolved"
        }
    ]
}
```

**Two-Phase Strategy**:

1. **Deterministic Phase (PHASE2_DETERMINISTIC_FIRST=True)**:
   - Uses raw diff anchors (removed/context lines from hunks)
   - Calls `_realign_mapping_to_target()` to ground line numbers
   - NO LLM calls
   - Falls back to LLM if mapping fails

2. **LLM Phase (if deterministic fails)**:
   - Creates ReAct agent with tools:
     - `search_candidates()`: Find moved/renamed files
     - `match_structure()`: Compare AST fingerprints
     - `get_class_context()`: Read method signatures
     - `get_dependency_graph()`: Find architectural neighbors
     - `grep_repo()`: Search for specific code snippets
     - `git_pickaxe()`: Trace code history
   - Recursion limit: 18 (to prevent infinite loops)

**Key Tools**:
- `EnsembleRetriever`: Lazy-loads index on demand (git-first strategy)
- `_extract_line_range()`: Parses line numbers from tool outputs
- `_deterministic_map_hunks_for_file()`: Anchor-based line realignment

**LLM Calls**: 
- System prompt: `_AGENT_SYSTEM` (detailed investigation strategy)
- Fallback system prompt: `_DIRECT_MAPPING_SYSTEM` (no-tool JSON-only)

**Limitations**:
- Deterministic path fails on structural divergence
- LLM can be slow (2 retries with 30-second delays)
- Recursion limit of 18 can be insufficient
- Line numbers may be approximate

---

### Planning Agent (Phase 2.5)

**Purpose**: Create verified str_replace edit plans for each hunk before code generation.

**Input**:
- `patch_diff`: Raw diff
- `mapped_target_context`: From Agent 2
- `consistency_map`: From Agent 2
- `target_repo_path`: For reading actual target files

**Output**:
```python
hunk_generation_plan = {
    "src/Foo.java": [
        {
            "hunk_index": 0,
            "target_file": "src/Foo.java",
            "edit_type": "replace",  # or "insert_after", "insert_before", "delete"
            "old_string": "exact text from target file",  # VERIFIED to exist
            "new_string": "replacement text",
            "verified": True,
            "verification_result": "EXACT_MATCH at line 59",
            "notes": "Applied consistency map renames"
        }
    ]
}
```

**Key Methods**:

1. **Decompose hunks**:
   - `_decompose_hunk_to_required_entries()`: Split mixed hunks (replace+insert)
   - Extracts removed, added, context lines

2. **Verify anchors**:
   - `_resolve_old_in_content()`: Find exact old_string in target file
   - Strategies: exact match → line_trimmed → multiline_trimmed → anchor_reconstructed

3. **Semantic adaptation** (Retry hook):
   - `_attempt_semantic_adapt_entry()`: Calls SemanticHunkAdapter if verification fails
   - Only accepts adaptations with confidence ≥ 0.6

4. **Sanitization**:
   - `_sanitize_entry_against_target()`: Normalizes entries against real file content
   - Ensures old_string exists verbatim

**LLM Calls**:
- System prompt: `_PLANNER_SYSTEM` (workflow-heavy, ReAct style)
- ReAct agent with tools from `HunkGeneratorToolkit`:
  - `find_method_definitions()`
  - `ripgrep_in_file()`
  - `find_symbol_references()`
  - `read_file_window()`
  - `verify_context_at_line()`

**Limitations**:
- Relies on verification_result being accurate
- Fallback to deterministic decomposition if LLM fails
- Doesn't handle all API changes (delegates to SemanticHunkAdapter)

---

### SemanticHunkAdapter (Phase 3+ Recovery Strategy)

**Purpose**: Intelligently adapt hunks when structural differences exist (API refactoring, method renames, signature changes).

**Input**:
- `hunk_old_string`: The old_string that failed to find
- `hunk_new_string`: The new_string to apply
- `target_file_content`: Full content of target file
- `semantic_diagnosis`: Optional diagnosis from file_editor failure
- `mainline_context`: Optional context from mainline

**Output**:
```python
adaptation_result = {
    "strategy": AdaptationStrategy,  # EXACT_MATCH, METHOD_RENAME, SIGNATURE_ADAPT, etc.
    "success": bool,
    "confidence": float,  # 0.0-1.0
    "adapted_old_string": str,
    "adapted_new_string": str,
    "intent": HunkIntent,
    "equivalent_location_line": int,
    "detected_changes": list[str],
    "adaptation_steps": list[str],
    "validation_errors": list[str],
    "reason": str
}
```

**Core Workflow**:

1. **Extract Intent** (`_extract_hunk_intent()`):
   - Analyzes old_string and new_string to determine operation type:
     - `IMPORT_ADDITION` (confidence 0.95)
     - `METHOD_CALL` (0.8)
     - `METHOD_DEFINITION` (0.85)
     - `FIELD_DECLARATION` (0.8)
     - `OBJECT_INITIALIZATION` (0.75)
     - `UNKNOWN` (0.4)
   - Extracts target entity, old/new signatures, rationale

2. **Find Equivalent Location** (`_find_equivalent_location()`):
   - Strategy 1: Use semantic diagnosis if available
   - Strategy 2: Search for key identifiers from original hunk
   - Strategy 3: Fuzzy match on method/class names
   - Returns: `{location_text, line_number, confidence, match_type}`

3. **Recompose Hunk** (`_recompose_hunk()`):
   - Routes by operation type:
     - **Imports**: Context adjustment (add adjacent import)
     - **Method Calls**: API transformation (adapt call syntax)
     - **Method Definitions**: Signature adaptation
     - **Object Initialization**: Parameter transformation
     - **Generic**: Context adjustment
   - Uses `APISignatureMapper` to extract and transform method signatures

4. **Validate Adaptation** (`_validate_adaptation()`):
   - Check 1: adapted_old_string exists in target (or 50% of identifiers found)
   - Check 2: Bracket/paren balance
   - Check 3: Critical keywords not lost (this, return, if, for, etc.)
   - Returns: `list[errors]` (empty if all pass)

5. **Score Confidence** (`_score_confidence()`):
   - Formula: `base_score * error_penalty`
   - `base_score = intent_conf × location_conf × recomposition_conf`
   - `error_penalty = 1.0 - (validation_errors × 0.1)` (10% per error)

**Key Classes**:

- `HunkOperationType`: Enum of operation types
- `AdaptationStrategy`: Enum of adaptation strategies
- `HunkIntent`: Parsed intent of hunk
- `APISignatureMapper`: Maps API signatures between versions
  - `extract_method_signature()`: Parse method declarations
  - `extract_method_call()`: Parse method calls
  - `transform_method_call()`: Adapt calls to new API

**When Called**:
- From `planning_agent_node()` when entry verification fails
- Trigger: `old_resolution_failed:not_found_single` + semantic diagnosis confidence > 60%
- Only accepts adaptations with confidence ≥ 0.6

**Limitations**:
- Requires semantic diagnosis from file_editor
- Limited to common API refactoring patterns
- Manual rules-based (not LLM-powered)
- May miss complex structural changes

---

### Agent 3: File Editor / Hunk Generator (Phase 3)

**Purpose**: Rewrite mainline patch hunks surgically to fit target repository structure.

**Input**:
- `semantic_blueprint`: From Agent 1
- `consistency_map`: From Agent 2
- `mapped_target_context`: From Agent 2
- `hunk_generation_plan`: From Planning Agent
- `validation_error_context`: Feedback if retrying
- `validation_attempts`: Retry counter

**Output**:
```python
adapted_code_hunks = [
    {
        "target_file": "src/Foo.java",
        "mainline_file": "src/Foo.java",
        "hunk_text": "@@-42,5 +42,7 @@\n context\n-old\n+new\n context",
        "insertion_line": 42,
        "intent_verified": True,
        "file_operation": "MODIFIED",
        ...
    }
]
adapted_test_hunks = [...]  # Similar structure
```

**Two Implementation Paths**:

1. **Without Tools** (faster):
   - LLM receives: semantic blueprint, consistency map, context lines
   - Outputs: Raw unified diff hunk text
   - Fast but less accurate

2. **With Tools** (recommended):
   - System prompt: `_HUNK_REWRITE_SYSTEM_TOOLS`
   - Mandatory workflow:
     1. **PLAN** (`manage_todo`): Add todos for context gathering
     2. **GATHER** (tools):
        - `read_file_window()`: Read surrounding code
        - `grep_in_file()`: Find key identifiers
        - `get_exact_lines()`: Get exact line content
        - `verify_context_at_line()`: Verify context line positions
     3. **GENERATE** (`build_unified_hunk`): Emit final diff
   - Higher accuracy due to real file content

**LLM System Prompts**:
- `_HUNK_REWRITE_SYSTEM`: No-tools version
- `_HUNK_REWRITE_SYSTEM_TOOLS`: With tools version
- Emphasis on: exact context matching, symbol renames, minimal edits

**Key Methods**:
- `_extract_hunk_block()`: Extract diff block from LLM output
- `_repair_hunk_header()`: Recalculate @@ line counts
- Deterministic fallback composition if LLM fails

**Limitations**:
- LLM may hallucinate context lines
- Tool invocation adds latency
- Recursion limits can truncate tool loop (max 100)
- Symbol renames may not be complete

---

### Agent 4: Validation Agent (Phase 4 - "Prove Red, Make Green" Loop)

**Purpose**: Verify backport correctness through compilation, testing, and static analysis.

**Input**:
- `adapted_code_hunks`: From Agent 3
- `adapted_test_hunks`: From Agent 3
- `semantic_blueprint`: From Agent 1
- `validation_attempts`: Retry counter

**Output**:
```python
{
    "validation_passed": bool,
    "validation_attempts": int,
    "validation_error_context": str,  # For retry feedback
    "validation_results": {
        "hunk_application": {success, raw, diagnostics},
        "build": {success, raw, diagnostics},
        "tests": {success, raw, state_transition},
        "spotbugs": {success, raw, agent_evaluation}
    },
    "validation_failure_category": str,  # For routing
    "validation_retry_files": list[str],
    "validation_retry_hunks": list[int]
}
```

**6-Phase "Prove Red, Make Green" Loop**:

**Phase 1: Proof of Vulnerability** (Apply tests only)
- Apply test hunks only (no code hunks)
- Goal: Tests should be able to execute without code fix

**Phase 2: Failure Confirmation** (Run tests pre-fix)
- Run test classes
- Goal: Tests MUST FAIL (proves vulnerability exists)
- Failure is SUCCESS in this phase

**Phase 3: Patch Application** (Apply full fix)
- Apply code hunks + test hunks together
- Goal: Patch applies without merge conflicts

**Phase 4: Targeted Verification** (Run tests post-fix)
- Run test classes again
- Goal: Tests MUST PASS (proves fix works)

**Phase 5: Full Compilation** (Recompile everything)
- Compile all modified files + tests
- Goal: No syntax errors

**Phase 6: Static Analysis** (SpotBugs)
- Run SpotBugs on compiled classes
- Goal: No high-severity bugs

**Alternative Validation Modes**:

1. **Compile-Only** (`compile_only=True`):
   - Skip test synthesis, testing, and static analysis
   - Only: apply patch → compile → verify no syntax errors

2. **Apply-Only** (`apply_only_validation=True`):
   - Skip all checks after hunk application
   - Only verify: hunks apply without conflicts

3. **Full Evaluation** (`evaluation_full_workflow=True`):
   - Apply → Build → Run relevant tests
   - Evaluate test state transitions (fail→pass, pass→fail)

**Failure Classification**:
- `_classify_apply_failure()`: Categorizes patch application errors
- `_classify_build_failure()`: Routes build errors
- Uses regex patterns to extract file hints

**LLM Usage**:
- `_analyze_failure()`: LLM analyzes error and provides diagnosis
- Input: `_ANALYZE_FAILURE_SYSTEM` + error output
- Output: 3-sentence concise diagnosis

**Limitations**:
- Assumes Maven build system
- SpotBugs requires compiled classes
- Test synthesis may not cover all edge cases
- Fixed max retry attempts (3)

---

## 3. State Schema (AgentState)

### Core Input Fields
```python
patch_path: str              # Absolute path to patch file
patch_diff: str              # Raw unified diff text
commit_message: str          # Mainline commit message
target_repo_path: str        # Path to target (older) repo
mainline_repo_path: str      # Path to mainline (newer) repo
experiment_mode: bool        # If True, checkout parent commit
backport_commit: str         # Target commit hash
original_commit: str         # Mainline commit hash
```

### Control Flags
```python
skip_phase_0: bool           # Skip fast-path attempt
compile_only: bool           # Validation only compiles (no tests)
with_test_changes: bool      # Include test file hunks
apply_only_validation: bool  # Validation only checks application
skip_compilation_checks: bool # Compile-only mode skips compilation
evaluation_full_workflow: bool # Run full eval flow (apply+build+tests)
```

### Inter-Agent Artifacts
```python
# Agent 1 → 2
semantic_blueprint: SemanticBlueprint

# Agent 2 → 3
consistency_map: dict[str, str]
mapped_target_context: dict[str, list]
implementation_plan: dict  # Legacy

# Planning Agent → Agent 3
hunk_generation_plan: dict[str, list]

# Agent 3 → Agent 4
adapted_code_hunks: list[AdaptedHunk]
adapted_test_hunks: list[AdaptedHunk]
adapted_file_edits: list[FileEdit]
developer_auxiliary_hunks: list[AdaptedHunk]

# Agent 4 feedback
validation_attempts: int
validation_passed: bool
validation_error_context: str
validation_results: dict
validation_failure_category: str
validation_retry_files: list[str]
validation_retry_hunks: list[int]
```

---

## 4. LLM Integration Points

### Where LLM is Called

| Agent | Phase | System Prompt | Tools | Recursion Limit | Usage |
|-------|-------|---------------|-------|-----------------|-------|
| **Agent 1** | - | N/A | N/A | N/A | None (deterministic) |
| **Agent 2** | Phase 2 | `_AGENT_SYSTEM` | search_candidates, match_structure, get_class_context, git_pickaxe, grep_repo, find_symbol_locations, git_log_follow | 18 | ReAct agent for structural mapping |
| **Agent 2 Fallback** | Phase 2 | `_DIRECT_MAPPING_SYSTEM` | None | N/A | Direct LLM call (no tools) |
| **Planning Agent** | Phase 2.5 | `_PLANNER_SYSTEM` | find_method_definitions, ripgrep_in_file, find_symbol_references, read_file_window, verify_context_at_line | 100 | ReAct for anchor verification |
| **Agent 3** | Phase 3 | `_HUNK_REWRITE_SYSTEM` or `_HUNK_REWRITE_SYSTEM_TOOLS` | read_file_window, grep_in_file, get_exact_lines, verify_context_at_line, manage_todo, build_unified_hunk | 100 | Rewrite hunks to target structure |
| **Agent 4** | Phase 4 | `_ANALYZE_FAILURE_SYSTEM` | N/A | N/A | Analyze validation failures (not cached) |

### LLM Providers & Models
- Provider: `get_llm()` from `utils/llm_provider.py`
- Default: Gemini 2.0 Flash (configurable via `LLM_PROVIDER` env var)
- Temperature: 0 (deterministic)

### Token Counting
- Function: `count_text_tokens()` and `extract_usage_from_response()`
- Tracks: input_tokens, output_tokens, total_tokens
- Estimated flag when using tiktoken fallback

---

## 5. Retry Logic & Error Recovery

### Validation Failure Routing

```python
if validation_passed:
    END
elif attempts < 3:
    if failure_category == "path_or_file_operation":
        → structural_locator (remap files)
    elif failure_category == "context_mismatch":
        → planning_agent (replan anchors)
    elif failure_category == "generation_contract_failed":
        → planning_agent (structural fix)
    elif build_error in ["api_mismatch", "syntax_error"]:
        → planning_agent (regen with guardrails)
    elif failed_stage == "generation_incomplete":
        → planning_agent (retry generation)
    else:
        → hunk_generator (retry with error context)
else:
    END (give up, output failure)
```

### Identical Patch Guard
- Computes `plan_signature` (SHA256 of plan JSON) and `generated_patch_hash`
- If identical to previous attempt, forces replanning instead of identical retry

---

## 6. Key Components & Helper Functions

### PatchAnalyzer
```python
analyzer = PatchAnalyzer()
changes = analyzer.analyze(diff_text)  # List[FileChange]
hunks_by_file = analyzer.extract_raw_hunks(diff_text)  # dict[file] = list[hunks]
```

### EnsembleRetriever
```python
retriever = EnsembleRetriever(mainline_repo_path, target_repo_path)
retriever.build_index(commit)
candidates = retriever.find_candidates(file_path)  # Lazy-loads index
```

### MethodFingerprinter
```python
fingerprinter.match_files(mainline_file, candidates)
fingerprinter.match_methods(mainline_method, target_file)
```

### ValidationToolkit
```python
toolkit = ValidationToolkit(target_repo_path)
toolkit.apply_adapted_hunks(code_hunks, test_hunks)
toolkit.run_build_script()
toolkit.run_targeted_tests(test_classes)
toolkit.run_spotbugs()
```

### HunkGeneratorToolkit
```python
toolkit = HunkGeneratorToolkit(target_repo_path)
toolkit.find_method_definitions(file_path)
toolkit.ripgrep_in_file(file_path, pattern, offset, limit)
toolkit.verify_context_at_line(file_path, line_num, expected_text)
toolkit.read_file_window(file_path, center_line, radius)
```

---

## 7. Current Limitations & Edge Cases

### Major Limitations

1. **Deterministic Path**: Only works if target file has same path and basic structure
2. **Semantic Adapter**: Limited to common API patterns, misses complex refactoring
3. **Method Matching**: 4-tier fingerprinting may fail on heavily obfuscated/minified code
4. **Test Synthesis**: Generic vulnerability test may not trigger actual issue
5. **Line Number Stability**: Realigned lines may drift if file changes between phases
6. **Recursion Limits**: Agent tool loops can hit limits (18 for locator, 100 for others)
7. **Single Commit**: Assumes monolithic patch, not multi-commit backports
8. **Language**: Java-specific (hardcoded regex, Maven assumptions)

### Known Failure Modes

1. **File Moved or Renamed**:
   - Fix: Structural locator should find it, but git resolution attempts first
   - Fallback: EnsembleRetriever + match_structure

2. **Method Signature Changed**:
   - Fix: SemanticHunkAdapter detects and adapts
   - Limitation: May hallucinate parameter transformations

3. **Circular Dependencies in Patch**:
   - Fix: None (would need dependency analysis)
   - Symptom: Hunk application fails with "depends on old contents"

4. **Test Doesn't Fail Pre-Fix**:
   - Fix: Manual test synthesis OR re-use existing test from suite
   - Symptom: Phase 2 validation fails ("tests passed unexpectedly")

5. **Symbol Rename Not in ConsistencyMap**:
   - Fix: Consistency map extraction from LLM mapping result
   - Limitation: May miss dynamic/implicit renames

---

## 8. Diagram: Data Flow with LLM Checkpoints

```
┌─────────────────────────────────────────────────────────────────┐
│ Input: patch_diff, target_repo_path, mainline_repo_path        │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │ Phase 0: Optimistic Path   │
                    │ (git apply --check)        │
                    │ [No LLM]                   │
                    └──────┬──────────┬──────────┘
                           │          │
                  SUCCESS──┤          └──FAILED
                           │
                        END │         ┌────────────────────────────┐
                            │         │ Agent 1: Context Analyzer  │
                            │         │ [No LLM - Deterministic]   │
                            │         │ OUTPUT: semantic_blueprint │
                            │         └──────┬─────────────────────┘
                            │                │
                            │         ┌──────▼─────────────────────┐
                            │         │ Agent 2: Structural Locator│
                            │         │ LLM: ReAct (if needed)     │
                            │         │ Fallback: Direct LLM       │
                            │         │ OUTPUT: consistency_map +  │
                            │         │         mapped_target_ctx  │
                            │         └──────┬─────────────────────┘
                            │                │
                            │         ┌──────▼──────────────────────┐
                            │         │ Planning Agent (Phase 2.5)   │
                            │         │ LLM: ReAct (verify anchors)  │
                            │         │ Fallback: Deterministic      │
                            │         │ OUTPUT: hunk_generation_plan │
                            │         └──────┬──────────────────────┘
                            │                │
                            │         ┌──────▼──────────────────────┐
                            │         │ Agent 3: File Editor         │
                            │         │ LLM: ReAct (with tools) OR   │
                            │         │      Direct (no tools)       │
                            │         │ OUTPUT: adapted_code_hunks + │
                            │         │         adapted_test_hunks   │
                            │         └──────┬──────────────────────┘
                            │                │
                            │         ┌──────▼──────────────────────┐
                            │         │ Agent 4: Validation          │
                            │         │ Phase 1-6: Apply, Build, Test│
                            │         │ LLM: Failure Analysis        │
                            │         │ OUTPUT: validation_results   │
                            │         └──────┬────┬──────────────────┘
                            │                │    │
                            │          SUCCESS    FAILED
                            │                │    │
                            │             END    ┌▼──────────────────┐
                            │                    │ Retry Loop?       │
                            │                    │ (attempts < 3)    │
                            │                    └──┬────────────────┘
                            │                       │
                            └──LOOP BACK────────────┘
```

---

## 9. Example Data Flow for Single Hunk

### Hunk Input: Add bounds check
```diff
@@ -42,3 +42,5 @@
 public void processBuffer(byte[] data) {
+    if (data.length > MAX_SIZE) return;
     validateHeader(data);
```

### Agent 1 Output
```python
{
    "root_cause_hypothesis": "Missing bounds check before buffer processing",
    "fix_logic": "Add length check (data.length > MAX_SIZE) before processing",
    "dependent_apis": ["validateHeader", "MAX_SIZE"],
    "hunk_chain": [
        {"hunk_index": 1, "role": "core_fix", "summary": "Adds bounds check..."}
    ]
}
```

### Agent 2 Output
```python
consistency_map = {}  # No renames

mapped_target_context = {
    "src/Buffer.java": [
        {
            "hunk_index": 0,
            "target_file": "src/Buffer.java",
            "target_method": "processBuffer",
            "start_line": 42,
            "end_line": 44,
            "code_snippet": "public void processBuffer(byte[] data) {"
        }
    ]
}
```

### Planning Agent Output
```python
hunk_generation_plan = {
    "src/Buffer.java": [
        {
            "hunk_index": 0,
            "edit_type": "insert_after",
            "old_string": "public void processBuffer(byte[] data) {",
            "new_string": "public void processBuffer(byte[] data) {\n    if (data.length > MAX_SIZE) return;",
            "verified": True,
            "verification_result": "EXACT_MATCH at line 42"
        }
    ]
}
```

### Agent 3 Output
```python
{
    "target_file": "src/Buffer.java",
    "mainline_file": "src/Buffer.java",
    "hunk_text": "@@ -42,2 +42,4 @@\n public void processBuffer(byte[] data) {\n+    if (data.length > MAX_SIZE) return;\n     validateHeader(data);",
    "insertion_line": 42,
    "intent_verified": True
}
```

### Agent 4 Validation
- **Phase 1**: Apply test hunk (vulnerable test)
- **Phase 2**: Run test → FAILS (before fix)
- **Phase 3**: Apply code hunk
- **Phase 4**: Run test → PASSES (after fix)
- **Phase 5**: Compile → SUCCESS
- **Phase 6**: SpotBugs → NO BUGS

---

## 10. Summary Table: Agent Responsibilities

| Agent | Input | Output | LLM Type | Retry On | Key Files |
|-------|-------|--------|----------|----------|-----------|
| **1** | patch_diff | semantic_blueprint | None | N/A | context_analyzer.py |
| **2** | patch_analysis | consistency_map, mapped_context | ReAct + Direct Fallback | File not found, LLM fail | structural_locator.py |
| **Planning** | patch_diff, mapped_context | hunk_generation_plan | ReAct | Verification fail | planning_agent.py |
| **3** | semantic_blueprint, consistency_map, mapped_context | adapted_code_hunks, adapted_test_hunks | ReAct ± Tools | Validation fail | hunk_generator.py |
| **4** | adapted_hunks | validation_results | Failure Analysis | Validation fail | validation_agent.py |

---

## Conclusion

This is a sophisticated multi-agent system designed to solve the hard problem of backporting security patches across software versions with structural divergence. It combines:

- **Deterministic components** for efficiency (Agent 1, early phases of Agent 2, Planning)
- **LLM ReAct loops** for complex structural matching (Agents 2, 3)
- **Semantic adaptation** for API compatibility (SemanticHunkAdapter)
- **Validation-driven iteration** for correctness (Agent 4 + retry routing)

The system is production-grade with comprehensive error handling, but has known limitations on complex refactoring scenarios and may require tuning for non-Maven Java projects.
