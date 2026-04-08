# Retrofit-Java: Full Workflow Execution Flow

## Executive Summary

The evaluation workflow is an orchestrated, multi-phase patch backporting system that:
1. **Loads** security patches from a dataset
2. **Prepares** repository state and mainline patch analysis
3. **Orchestrates** a multi-agent LLM pipeline (Phases 0-4) to adapt patches
4. **Validates** results by comparing generated vs. developer patches
5. **Reports** metrics on success, regression, and patch fidelity

---

## 1. ENTRY POINT: `main()` - Orchestrating the Evaluation

```
main() [async]
├─ Parse CLI Arguments (--mode, --project, --patch-id, --force, etc.)
├─ Configure Logging
├─ Ensure Output Directories
├─ Load Dataset (all_projects_final.csv)
├─ Filter by Project & Patch ID
├─ Limit Patches (MAX_PATCHES_PER_PROJECT = 10 per project)
└─ For Each Patch:
   └─ Invoke run_full_pipeline() [async]
```

### 1.1 Execution Modes

The workflow supports three execution modes:

| Mode | Purpose |
|------|---------|
| `RUN_MODE_FULL` | Complete pipeline: Phase 0 (fast path) → Phases 1-4 (agent pipeline) |
| `RUN_MODE_PHASE1` | Context Analyzer only (semantic patch analysis) |
| `RUN_MODE_PHASE2` | Structural Locator only (symbol mapping) |

**Flow**:
1. CLI argument parser determines which mode to run
2. Dataset is loaded and filtered by project name and patch ID
3. For each selected patch, `run_full_pipeline()` is invoked
4. Results accumulate in `all_results` list
5. At completion, write summary JSON with aggregated metrics

### 1.2 Data Loading & Filtering

```python
# Load from CSV
data = []
with open(DATASET_PATH, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['Project'] in selected_projects:
            data.append(row)

# Each row contains:
# {
#   'Project': 'elasticsearch' | 'crate' | 'druid'
#   'Original Commit': mainline SHA (long)
#   'Backport Commit': target SHA (long)
# }
```

**Key filtering logic**:
- If `--project` specified: filter to that project only
- If `--patch-id` specified: filter to exact patch (e.g., `elasticsearch_734dd070`)
- Limit to `MAX_PATCHES_PER_PROJECT` per project (default 10)
- Skip already-processed patches unless `--force` flag set

---

## 2. PIPELINE INVOCATION: `run_full_pipeline()`

This is the main orchestrator for a single patch. It's an async function that:

```
run_full_pipeline(project, patch_id, mainline_commit, backport_commit, ...)
├─ Phase 0: Attempt Fast Path (direct git apply)
├─ Phase 1: Context Analyzer (semantic analysis)
├─ Phase 2: Structural Locator (symbol mapping)
├─ Phase 3: File Editor (apply edits)
├─ Phase 4: Validation (compile + test)
├─ Compare Results
└─ Generate Artifacts & Reports
```

### 2.1 State Management & Logging

The function maintains detailed state:

```python
results = {
    'project': project,
    'patch_id': patch_id,
    'mainline_commit': mainline_commit,
    'backport_commit': backport_commit,
    'run_mode': run_mode,
    'timestamp': datetime.now().isoformat(),
    'phases': {},  # Will hold outputs from each phase
}

# Token tracking for LLM usage
token_totals = {
    'input_tokens': 0,
    'output_tokens': 0,
    'total_tokens': 0,
    'by_node': {},  # Per-agent token usage
}

# Runtime logging (stdout + file)
runtime_log_path = os.path.join(patch_dir, 'log.txt')
runtime_tokens_path = os.path.join(patch_dir, 'tokens.txt')
```

### 2.2 Repository Setup & Patch Generation

```python
# Called via _prepare_pipeline_inputs()
```

#### Step 1: Checkout Repositories

```
Target State:
├─ Main repo:  checkout to mainline_commit
└─ Target repo: checkout to backport_commit^ (parent, pre-backport)
```

This ensures:
- Mainline patch is generated from the intended commit
- Target repo is in the state *before* the developer applied their backport

#### Step 2: Generate Mainline Patch

```python
git format-patch -1 mainline_commit --stdout
    ↓
patch_output (full unified diff)
```

This patch represents the *security fix* that needs to be backported.

#### Step 3: Capture Developer Backport Patch

```python
git show --format="" --no-color backport_commit
    ↓
developer_patch_diff (what the developer actually did)
```

This is the **ground truth** against which generated patches are compared.

#### Step 4: Analyze Patches & Prepare Agent-Eligible Content

```
Full patch analysis:
├─ Parse all file changes
├─ Filter to Java code files only (exclude tests, non-Java, auto-generated)
└─ Build 'agent_eligible_patch' (agents will only modify this)

developer_aux_hunks (from developer patch):
├─ All test file hunks
├─ All non-Java file hunks
├─ All auto-generated Java file hunks
└─ These are NOT modified by agents; applied as-is during validation
```

**Filtering logic** (in `_is_auto_generated_java_file()`):

```
Auto-generated patterns detected:
├─ ANTLR: *Lexer.java, *Parser.java, *BaseListener.java, *BaseVisitor.java
├─ Protobuf: *OuterClass.java, *Pb.java, *PbOrBuilder.java
└─ gRPC: *Grpc.java
```

**Non-code detection** (in `_is_non_java_hunk_in_java_file()`):

```
Detects non-Java content like:
├─ SQL (SELECT, INSERT, WHERE, JOIN, etc.)
├─ YAML (key: value syntax, ---, tags)
├─ JSON ("key": value patterns)
├─ XML (<tag attr="value">)
└─ Regex patterns to identify these signatures
```

#### Step 5: Pair Consistency Check

```python
_compute_pair_consistency(mainline_patch, developer_patch, analyzer)
    ↓
{
    'mainline_java_files': [list of files touched by mainline patch],
    'developer_java_files': [list of files touched by developer patch],
    'overlap_java_files': [intersection],
    'overlap_ratio_mainline': ratio (0-1),
    'pair_mismatch': bool,
    'reason': 'mainline_backport_scope_mismatch' | 'scope_overlap_ok'
}
```

**Interpretation**:
- If `pair_mismatch = True`: mainline patch touches different files than developer patch
  - Suggests scope divergence (mainline may have refactored, simplified, or restructured code)
  - Pipeline should be cautious about fidelity claims

---

## 3. PHASE EXECUTION: The Agent Pipeline

### 3.1 Build Base Inputs for LangGraph

```python
base_inputs = {
    'messages': ['Start'],
    'patch_path': patch_path,
    'patch_diff': agent_eligible_patch,  # Only Java code, no tests/generated
    'patch_analysis': java_only_patch_analysis,
    'target_repo_path': target_repo_path,
    'mainline_repo_path': mainline_repo_path,
    'experiment_mode': True,
    'backport_commit': backport_commit,
    'original_commit': mainline_commit,
    'skip_phase_0': False,
    'compile_only': False,
    'apply_only_validation': False,
    'skip_compilation_checks': False,
    'evaluation_full_workflow': True,
    'with_test_changes': False,
    'developer_auxiliary_hunks': developer_aux_hunks,
    'pair_consistency': pair_consistency,
    'use_phase_0_cache': True,  # Reuse Phase 0 results if cached
}
```

### 3.2 Phase 0: Optimistic Fast Path

**Purpose**: Try applying the mainline patch directly to target repo before invoking any LLM agents.

```
Detection:
├─ Does agent_eligible_patch apply cleanly to target repo?
└─ Run: git apply --cached --recount agent_eligible_patch

Success Path:
├─ Parse generated patch
├─ Extract test transitions (fail→pass, newly passing, pass→fail)
├─ Run baseline & post-patch test suites
├─ Determine if patch is valid backport (test improvements?)
└─ Cache results for future runs (same commit pair)

Failure Path:
├─ Continue to Phase 1 (agentic adaptation)
```

**Caching** (in `_load_phase0_cache()` & `_is_phase0_cache_reusable()`):

```python
cache_file = "{project}_{backport[:12]}_{original[:12]}.json"
# Stored in: phase0_cache/
# Rejection criteria:
# - 'baseline_apply_failed': Phase 0 couldn't apply patch originally
# - 'empty_baseline_and_empty_transition': No baseline tests + no improvements
# - 'inconclusive_target_tests_not_observed': Couldn't identify relevant tests
```

### 3.3 Phase 1: Context Analyzer

**Node**: `context_analyzer_node()` in agents-backend

**Inputs**:
- `patch_diff`: Agent-eligible patch
- `patch_analysis`: Parsed hunks with file/line/content info
- `mainline_repo_path`: For reading contexts

**Process**:
```
1. Parse mainline patch into structured hunks
2. For each hunk, extract surrounding context (lines before/after)
3. Analyze semantic intent: what is this code change *doing*?
   - Is it adding a null check?
   - Refactoring a loop?
   - Replacing a deprecated API?
   - Adding error handling?
4. Build 'SemanticBlueprint': structured intent description
5. Store in state for Phase 2
```

**Output**: `SemanticBlueprint` object (in `state.py`)

### 3.4 Phase 2: Structural Locator

**Node**: `structural_locator_node()` in agents-backend

**Inputs**:
- `SemanticBlueprint` (from Phase 1)
- `target_repo_path`: For AST analysis via MCP server

**Process**:
```
1. For each semantic change in blueprint:
   a. Identify Java symbols (classes, methods, variables) in mainline
   b. Query analysis-engine (Java AST service via MCP) to find equivalent symbols in target
   c. Map mainline line numbers to target line numbers
   d. Account for code drift (refactoring, deletions, additions)

2. Build 'MappedTargetContext':
   - Target file paths (may differ from mainline if files were moved)
   - Target line ranges for insertion/modification
   - Symbol consistency: are the same classes/methods present in target?

3. Build 'ConsistencyMap': how well do target symbols align with mainline?
```

**Key AST Queries**:
- `find_method_by_signature(class, method_name, param_types)`
- `find_field(class, field_name)`
- `find_class(fully_qualified_name)`
- `get_line_for_element(element_id)`

### 3.5 Phase 3: File Editor (Hunk Generation + Application)

**Two Sub-Phases**:

#### 3.5a: Planning Agent

**Input**: `MappedTargetContext` (from Phase 2)

**Process**:
```
1. For each hunk in mapped context:
   - Convert semantic intent + target location into concrete edit instructions
   - Generate str_replace edits: (old_text, new_text, target_file, insertion_line)

2. Build 'HunkGenerationPlan': array of edit instructions

3. Validate plan:
   - Can old_text string be found exactly in target file?
   - Is insertion line within file bounds?
   - Will edits overlap?
```

**Output**: `HunkGenerationPlan`

#### 3.5b: File Editor Agent

**Input**: `HunkGenerationPlan`

**Process**:
```
1. For each edit instruction:
   - Locate exact old_text string in target file
   - Replace with new_text
   - Record change

2. After all edits applied:
   - Run: git diff HEAD
   - Extract generated patch (full unified diff format)

3. Handle Edit Failures:
   - If old_text not found: try fuzzy matching (ignoring whitespace)
   - If fuzzy also fails: mark as unmodified or skip
```

**Output**: 
```python
{
    'hunk_text': 'diff --git a/file.java b/file.java\n... full patch ...',
    'target_file': 'path/to/file.java',
    'insertion_line': 42,
    'intent_verified': True/False,
    'file_operation': 'MODIFIED' | 'ADDED' | 'DELETED' | 'RENAMED'
}
```

**CLAW Approach** (str_replace exact matching):
- No fuzzy hunk offset matching
- All edits use exact string replacement
- Ensures reproducibility and clarity

---

## 4. PHASE 4: Validation

**Node**: `validation_agent_node()` in agents-backend

**Inputs**:
- Generated patch (from Phase 3)
- `developer_auxiliary_hunks` (test + non-Java + auto-generated files)
- Target repo path

**Process**:

#### 4.1 Combine Patches

```python
final_patch = [
    agent_generated_hunks (Java code files only) +
    developer_auxiliary_hunks (test, non-Java, auto-generated)
]
```

This ensures:
- Agents adapt Java code
- Tests/non-code changes are applied as-is from developer patch
- Result mimics real backport: code changes + auxiliary changes

#### 4.2 Apply Combined Patch

```
git apply final_patch to target_repo
```

#### 4.3 Run Compilation Check

```
mvn clean package (for Java projects)
```

**Outcomes**:
- ✅ Compilation succeeds → continue to tests
- ❌ Compilation fails → trigger Reasoning Architect (retry loop)

#### 4.4 Run Relevant Tests

```
Identify test classes touched by:
├─ Mainline patch
├─ Generated patch
└─ Developer patch

Run: mvn test -Dtest=<TestClass1>,<TestClass2>,...
```

**Collect Test States**:

```python
baseline_test_state = {
    'test_cases': {
        'ClassName#testMethod': 'PASS' | 'FAIL',
        ...
    },
    'classes': {
        'ClassName': 'PASS' | 'FAIL' | 'ERROR',
        ...
    },
    'summary': {
        'total': N,
        'passed': P,
        'failed': F,
        'error': E
    }
}

post_patch_test_state = {...}  # Same structure after applying patch
```

#### 4.5 Compute Test Transition

```python
transition = {
    'fail_to_pass': tests that went from FAIL → PASS,
    'newly_passing': tests that were skipped/error → PASS,
    'pass_to_fail': tests that went from PASS → FAIL (regression!),
    'valid_backport_signal': bool(fail_to_pass or newly_passing),
    'reason': diagnostic message
}
```

**Validation Success Criteria**:
1. ✅ Compilation succeeds
2. ✅ No regressions (pass_to_fail is empty)
3. ✅ Test improvements detected (fail_to_pass or newly_passing non-empty)

#### 4.6 Failure & Retry Loop

If validation fails:

```
Reasoning Architect:
├─ Analyze compilation error or test failure
├─ Diagnose root cause:
│  ├─ Missing import?
│  ├─ Type mismatch?
│  ├─ Wrong line number (drift)?
│  └─ Incompatible API?
│
└─ Generate diagnostic report

Planning Agent Re-plans:
├─ Revise HunkGenerationPlan based on diagnosis
├─ Attempt new edits

File Editor Re-applies:
└─ Execute revised edits

Validation Re-runs (up to MAX_VALIDATION_ATTEMPTS=3)
```

**Retry Limits**:
- Max 3 validation attempts per patch
- If all fail: mark patch as failed

---

## 5. POST-PIPELINE: Artifact Generation & Comparison

### 5.1 Extract Adapted Code Hunks

```python
latest_adapted_code_hunks = [
    hunks from phase_outputs['phase3']['file_editor']['outputs']
]
```

### 5.2 Build Final Patch

```python
final_adapted_code_hunks = (
    latest_adapted_code_hunks (agent-generated Java code) +
    developer_auxiliary_hunks (test + non-Java + auto-generated)
)

final_generated_patch_diff = _build_generated_patch_from_hunks(
    final_adapted_code_hunks
)
```

This is what agents produced.

### 5.3 Compare with Developer Patch

**Function**: `compare_generated_with_developer_patch()`

**Process**:

#### Step 1: Prepare Temporary Index

```bash
GIT_INDEX_FILE=temp.index git read-tree backport_commit^
# Seed index to pre-backport state
```

#### Step 2: Apply Generated Patch to Index

```bash
GIT_INDEX_FILE=temp.index git apply agent_eligible_patch
```

#### Step 3: Compare File States

For each Java code file:
```python
developer_blob = git rev-parse backport_commit:file.java
generated_blob = git hash-object pre-generated-index:file.java

if developer_blob == generated_blob:
    # Content is identical
    aligned ✓
else:
    # Content differs
    mismatched ✗
```

#### Step 4: Whitespace-Insensitive Comparison (fallback)

```python
developer_normalized = [re.sub(r'\s+', '', line) for line in developer_lines]
generated_normalized = [re.sub(r'\s+', '', line) for line in generated_lines]

if developer_normalized == generated_normalized:
    # Semantically identical, only whitespace differs
    aligned ✓ (with caveat)
```

### 5.4 Compute Fidelity Metrics

```python
comparison = {
    'exact_developer_patch': bool(len(mismatched_files) == 0),
    'comparison_method': 'file_state',
    'compared_files': [all files compared],
    'mismatched_files': [files that differ],
    'developer_files': [files touched by developer],
    'generated_files': [files touched by agents],
    'developer_patch_comparison': {...},
    'error': error_message if comparison failed
}
```

**Interpretation**:
- `exact_developer_patch = True`: Generated patch is semantically identical to developer patch
- `exact_developer_patch = False` + `mismatched_files`: Generated patch differs from developer
  - Possible reasons:
    - Agent chose different approach (but still valid)
    - Agent missed some edge cases
    - Agent added unnecessary changes

---

## 6. RESULTS AGGREGATION & REPORTING

### 6.1 Save Artifacts

```python
_save_generated_patch_artifacts(
    project=project,
    patch_id=patch_id,
    agent_only_patch_diff=agent_only_patch_diff,
    final_effective_patch_diff=final_effective_patch_diff,
)

# Files created:
├─ results/{project}/{patch_id}/generated_patch_agent_only.patch
├─ results/{project}/{patch_id}/generated_patch_final_effective.patch
├─ results/{project}/{patch_id}/mainline.patch
├─ results/{project}/{patch_id}/pipeline_results.json
├─ results/{project}/{patch_id}/log.txt (runtime log)
├─ results/{project}/{patch_id}/tokens.txt (token usage)
└─ results/{project}/{patch_id}/*_log.md (phase logs)
```

### 6.2 Generate Markdown Reports

#### Report 1: Phase Inputs

```markdown
# Phase 0 Inputs

- Mainline commit: ...
- Backport commit: ...
- Java-only files for agentic phases: N
- Developer auxiliary hunks (test + non-Java): M

## Commit Pair Consistency

- Pair mismatch: True/False
- Reason: ...
- Mainline Java files: [...]
- Developer Java files: [...]
- Overlap Java files: [...]

## Mainline Patch

```diff
... full patch ...
```
```

#### Report 2: Developer Patch Comparison

```markdown
# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: True/False

**Comparison Method**: file_state

## Commit Pair Consistency

... (same as inputs)

## File State Comparison

- Compared files: [...]
- Mismatched files: [...]
- Error: ...

## Hunk-by-Hunk Comparison

For each file touched by both patches:
- Developer hunks count
- Generated hunks count
- Diff between developer and generated (unified diff of diffs)

## Full Generated Patch (Agent-Only, code-only)

```diff
... only Java code, no tests/auxiliary ...
```

## Full Generated Patch (Final Effective, code-only)

```diff
... including test/auxiliary hunks ...
```

## Full Developer Backport Patch

```diff
... ground truth from developer ...
```
```

#### Report 3: Transition Summary

```markdown
# Transition Summary

- Source: phase_outputs | phase0_cache
- Valid backport signal: True/False
- Reason: ...
- fail->pass count: N
- newly passing count: M
- pass->fail (regressions): K

## Touched Test States

For each test class modified by patch:
- ClassName: baseline=PASS, patched=PASS (no regression)
- ClassName: baseline=FAIL, patched=PASS (fix!)
- ClassName: baseline=PASS, patched=FAIL (regression!)
```

#### Report 4: Full Agentic File Edit Trace

```markdown
# Full Trace of Agentic File Edits

For each retry attempt (if any):
- Retry #0 (initial plan)
  - Planning Agent output
  - File Editor edits applied
  - Validation result
  
- Retry #1 (after first failure)
  - Reasoning Architect diagnosis
  - Planning Agent revised plan
  - File Editor edits applied
  - Validation result
  
... etc (up to 3 retries) ...
```

### 6.3 Compute Token Usage

```python
token_totals = {
    'input_tokens': SUM(all LLM inputs),
    'output_tokens': SUM(all LLM outputs),
    'total_tokens': input + output,
    'messages_with_usage': count of calls with exact token counts,
    'estimated_messages': count of calls with estimated tokens,
    'by_node': {
        'context_analyzer': {...token breakdown...},
        'structural_locator': {...},
        'planning_agent': {...},
        'file_editor': {...},
        'validation_agent': {...},
        'reasoning_architect': {...}
    },
    'tokenizer': {
        'model': resolved_model_name,
        'library': 'tiktoken',
        'available': True/False
    }
}
```

### 6.4 Build Final Results Dict

```python
results = {
    'project': project,
    'patch_id': patch_id,
    'mainline_commit': mainline_commit,
    'backport_commit': backport_commit,
    'run_mode': 'full' | 'phase1' | 'phase2',
    'timestamp': ISO8601,
    'status': 'completed' | 'failed' | 'skipped',
    'phases': {
        'phase0': {...outputs...},
        'phase1': {...outputs...},
        'phase2': {...outputs...},
        'phase3': {...outputs...},
        'phase4_validation': {...outputs...}
    },
    'pair_consistency': {...},
    'exact_developer_patch': True/False,
    'developer_patch_comparison': {...},
    'generated_patch_files': {
        'agent_only': path,
        'final_effective': path
    },
    'error': error_message if failed
}
```

### 6.5 Save Results & Summary

```python
# Per-patch results
results_file = results/{project}/{patch_id}/pipeline_results.json
json.dump(results, results_file)

# Aggregate summary
summary_file = results/pipeline_summary_{mode}.json
json.dump(all_results, summary_file)

# Print summary statistics
print(f"Total Patches: {len(data)}")
print(f"Skipped: {len(skipped_patches)}")
print(f"Newly Processed: {len(all_results)}")
print(f"Completed: {sum(1 for r in all_results if r['status'] == 'completed')}")
print(f"Failed: {sum(1 for r in all_results if r['status'] == 'failed')}")
```

---

## 7. HELPER FUNCTIONS & UTILITIES

### 7.1 Patch Analysis Utilities

**`_is_test_file(file_path)`**: Detects if path contains "test" or ends with "test.java"

**`_is_java_code_file(file_path)`**: Checks if file is `.java` and not a test file

**`_is_auto_generated_java_file(file_path)`**: Detects ANTLR/Protobuf/gRPC generated files

**`_is_non_java_hunk_in_java_file(file_path, hunk_text)`**: Detects if .java file contains non-code (SQL, YAML, JSON, XML)

### 7.2 Patch Filtering

**`_build_auxiliary_hunks_from_developer_patch(patch_diff)`**:
- Extracts hunks from test files, non-Java files, auto-generated files
- These hunks will be applied as-is during validation (agents don't touch them)
- Preserves pure file operations (add/delete/rename) with no hunks

**`_build_agent_eligible_patch(patch_diff)`**:
- Filters patch to include ONLY Java code hunks (not tool-generated)
- This is what agents will attempt to adapt
- Removes test hunks, non-Java hunks, auto-generated hunks

### 7.3 File Operation Detection

**`_normalize_hunk_header_for_operation(hunk_text, file_operation)`**:
- Adjusts hunk header `@@ -old_start,old_len +new_start,new_len @@` based on operation
- ADDED files: old_start=0, old_len=0
- DELETED files: new_start=0, new_len=0
- MODIFIED files: both preserved

### 7.4 Patch Generation

**`_build_generated_patch_from_hunks(adapted_code_hunks)`**:
- Takes array of hunk dicts (from file editor)
- Handles two hunk_text formats:
  1. Full git diff (starts with `diff --git ...`) - used as-is
  2. Bare hunk (starts with `@@`) - wrapped with diff/---/+++ headers
- Reconstructs unified diff file structure
- Handles RENAMED, ADDED, DELETED, MODIFIED operations

### 7.5 Hunk Comparison

**`_build_hunk_comparison_markdown(developer_patch, generated_patch, analyzer)`**:
- Extracts hunks by file from both patches
- For each file, compares hunk-by-hunk
- Generates unified diff of the diffs (shows what changed in the hunks themselves)
- Useful for understanding how agents adapted hunks

### 7.6 Test State Analysis

**`_extract_touched_test_classes(phase_outputs, phase0_cache)`**:
- Extracts list of test classes modified by patch
- Tries phase_outputs first, falls back to cached results

**`_extract_baseline_and_patched_test_results(phase_outputs, phase0_cache)`**:
- Gets test state before patch (baseline)
- Gets test state after patch (patched)
- Handles both phase 0 and phase 4 sources

**`_build_touched_test_state_markdown(touched_classes, baseline, patched)`**:
- For each touched test class, shows transition:
  - `ClassName: baseline=PASS, patched=PASS` (preserved)
  - `ClassName: baseline=FAIL, patched=PASS` (fixed!)
  - `ClassName: baseline=PASS, patched=FAIL` (regression!)

### 7.7 Phase Control

**`is_phase_processed(project, patch_id, phase_name, agent_name)`**:
- Checks if phase output already exists
- If `--force` flag passed, forces rerun even if output exists

---

## 8. DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                          ENTRY: main()                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  Parse CLI args, load dataset CSV     │
        │  Filter by project, --patch-id, limit│
        └──────────────────┬───────────────────┘
                           │
                    For each patch row:
                           │
                           ▼
        ┌──────────────────────────────────────────────────────────┐
        │    run_full_pipeline(project, patch_id, ...)   [async]   │
        └──────────────────┬──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  _prepare_pipeline_inputs()          │
        │  ├─ git checkout mainline, target^   │
        │  ├─ generate mainline patch (Phase-0 input)
        │  ├─ generate developer patch (ground truth)
        │  ├─ filter to agent-eligible hunks   │
        │  ├─ identify test/non-Java hunks     │
        │  └─ pair consistency check           │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │         Try Phase 0 Fast Path        │
        │  git apply agent_eligible_patch      │
        ├────────────────────────────────────┤
        │ Success?          Fail?             │
        │ ├─ Extract        └─ Continue to    │
        │ │  transitions       Phase 1        │
        │ ├─ Run tests                        │
        │ └─ Cache results                    │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  invoke app.astream(inputs)  [async] │
        │  (LangGraph orchestration)           │
        └──────────────────┬───────────────────┘
                           │
        ┌──────────────────┴──────────────────────────┬──────────────────────────────────────────────────────┐
        │                                             │                                                      │
        ▼                                             ▼                                                      ▼
    Phase 1:                                    Phase 2:                                             Phase 3+4:
    Context Analyzer                            Structural Locator                                   File Editor +
    ├─ SemanticBlueprint                       ├─ Map mainline symbols                              Validation
    │  (intent of changes)                     │  to target repo                                    (with retries)
    └─ Output: semantic understanding           ├─ ConsistencyMap                                    └─ Output:
       stored in state                          │  (how well aligned?)                                 adapted_code_hunks
                                                └─ MappedTargetContext
                                                   (where to apply in target)
        ┌────────────────────────────────────────────────────────────────────────────────────────┐
        │                                                                                        │
        │  Phase 3.5a: Planning Agent (HunkGenerationPlan)                                      │
        │  ├─ Convert intent + mapped location into str_replace edits                          │
        │  ├─ Validate edits (old_text exists? line in bounds? no overlap?)                    │
        │  └─ Output: HunkGenerationPlan                                                      │
        │                                                                                        │
        │  Phase 3.5b: File Editor (apply edits, extract patch)                                │
        │  ├─ For each edit in plan: string replacement                                        │
        │  ├─ Track successes/failures                                                        │
        │  ├─ git diff HEAD to extract patch                                                  │
        │  └─ Output: adapted_code_hunks                                                       │
        │                                                                                        │
        │  Phase 4: Validation Agent (compile + test)                                          │
        │  ├─ Combine: agent hunks + developer auxiliary hunks                                 │
        │  ├─ git apply combined patch                                                        │
        │  ├─ mvn clean package                                                               │
        │  │  ├─ Success? ✓ Continue                                                          │
        │  │  └─ Fail? → Reasoning Architect → re-plan → retry (up to 3 times)               │
        │  ├─ Identify relevant tests from patch                                              │
        │  ├─ Run tests, collect baseline vs. patched test states                             │
        │  ├─ Extract transitions: fail→pass, pass→fail, newly passing                       │
        │  └─ Output: validation_results with test transitions                               │
        │                                                                                        │
        │  Retry Loop (if validation fails):                                                  │
        │  ├─ Reasoning Architect: diagnose error                                             │
        │  ├─ Planning Agent: revise plan based on diagnosis                                  │
        │  ├─ File Editor: re-apply revised edits                                             │
        │  └─ Validation Agent: re-run tests (max 3 total attempts)                           │
        │                                                                                        │
        └────────────────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
        ┌────────────────────────────────────────────────────────┐
        │  compare_generated_with_developer_patch()             │
        │  ├─ temp index: git read-tree backport_commit^        │
        │  ├─ apply generated patch to temp index               │
        │  ├─ compare blob IDs (backport_commit vs. index)      │
        │  ├─ whitespace-insensitive fallback comparison       │
        │  └─ Output: exact_developer_patch, mismatched_files  │
        └────────────────────┬─────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────┐
        │  Generate & Save Artifacts                            │
        │  ├─ Save generated patch files                        │
        │  ├─ Build hunk comparison markdown                    │
        │  ├─ Build transition summary markdown                 │
        │  ├─ Build full edit trace markdown                    │
        │  ├─ Collect token usage from LLM calls                │
        │  └─ Save pipeline_results.json + logs                │
        └────────────────────┬─────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────┐
        │  Return: results dict (status, phases, metrics, etc.)  │
        └────────────────────┬─────────────────────────────────┘
                             │
        ┌────────────────────┴─────────────────────────────────┐
        │         Accumulate all_results list                 │
        └────────────────────┬─────────────────────────────────┘
                             │
                             ▼
        (After all patches processed)
        ┌────────────────────────────────────────────────────────┐
        │  Save: results/pipeline_summary_{mode}.json           │
        │  Print: completion statistics                         │
        └────────────────────────────────────────────────────────┘
```

---

## 9. KEY STATE TRANSITIONS

### Per-Patch Execution State

```python
AgentState (from src/state.py):
{
    'messages': [...],                      # Conversation history
    'patch_path': str,                      # File path to mainline patch
    'patch_diff': str,                      # Full patch content
    'patch_analysis': [FileChange],         # Parsed hunks
    'target_repo_path': str,
    'mainline_repo_path': str,
    'semantic_blueprint': SemanticBlueprint,  # Phase 1 output
    'mapped_target_context': MappedTargetContext,  # Phase 2 output
    'consistency_map': ConsistencyMap,      # Phase 2 consistency info
    'hunk_generation_plan': HunkGenerationPlan,  # Phase 3a output
    'adapted_code_hunks': [dict],          # Phase 3b output
    'validation_results': ValidationResult, # Phase 4 output
    'phase_0_baseline_test_result': dict,  # Phase 0 baseline
    'phase_0_post_patch_test_result': dict, # Phase 0 after patch
    'phase_0_transition_evaluation': dict,  # Phase 0 tests transition
}
```

### Error Handling

When validation fails:

```python
validation_results = {
    'compiled': False,
    'compile_error': error_message,
    'reason_for_failure': diagnostic_report
}

# Reasoning Architect analyzes & produces:
reasoning_output = {
    'diagnosis': str (what went wrong),
    'suggested_fixes': [str] (how to fix),
    'confidence': float (0-1)
}

# Planning Agent re-plans with reasoning as context
# File Editor re-applies with revised plan
# Validation re-runs
```

---

## 10. CRITICAL DECISION POINTS

### 1. Agent Eligibility Filter

```
Does agent touch this file?
├─ NO if: test file, non-Java, auto-generated
├─ NO if: non-code content in Java file (SQL, YAML, etc.)
└─ YES if: pure Java code file
```

**Rationale**: Agents should not regenerate tests or auto-generated files; they should only adapt business logic code.

### 2. Phase 0 Caching

```
Can we reuse Phase 0 results?
├─ NO if: baseline apply failed, or
├─ NO if: empty baseline + zero improvements, or
├─ NO if: no relevant target tests observed
└─ YES if: reusable cache exists
```

**Rationale**: Avoid re-running expensive fast paths if we already have conclusive results.

### 3. Pair Mismatch Detection

```
Does mainline patch scope differ from developer patch?
├─ YES if: < 50% file overlap
│  └─ Flag as pair_mismatch; be cautious about fidelity
└─ NO if: >= 50% file overlap
   └─ Proceed normally
```

**Rationale**: If patches touch different files, scope may have shifted; agent may not find equivalent code in target.

### 4. Validation Retry Decision

```
If compilation/tests fail:
├─ Reason: identify root cause (missing import? type? API?)
├─ Attempt: revise plan and re-apply (max 3 times total)
├─ Success (on any retry): mark as validated ✓
└─ Fail (all retries exhausted): mark as failed ✗
```

**Rationale**: Give agents multiple chances to fix common issues (scope drift, missing APIs, etc.).

### 5. Developer Patch Fidelity Assessment

```
Is generated patch "exact match" to developer?
├─ YES if: all Java code files match (bit-identical or whitespace-insensitive)
│  └─ → Agent perfectly replicated developer's logic
├─ NO if: mismatches exist
│  ├─ Possible: Agent chose valid alternative
│  ├─ Possible: Agent missed edge cases
│  └─ Requires manual review to assess quality
```

**Rationale**: Exact match = high confidence. Mismatch = requires inspection.

---

## 11. FAILURE MODES & RECOVERY

| Mode | Trigger | Recovery |
|------|---------|----------|
| **Phase 0 Fast Path Fails** | `git apply` doesn't apply cleanly | Continue to Phase 1 (agentic) |
| **Phase 1 Fails** | Semantic analysis fails | Abort patch, mark as failed |
| **Phase 2 Fails** | Cannot find symbols in target | Abort patch, mark as failed |
| **Phase 3 Compilation Fails** | Generated patch doesn't compile | Reasoning Architect → re-plan → retry (×3) |
| **Phase 4 Tests Fail** | Regressions detected | Same retry loop as compilation |
| **Phase 4 All Retries Exhausted** | Still failing after 3 attempts | Mark as failed, save diagnostics |
| **Comparison Fails** | Cannot compare with developer patch | Report error, save what we can |

---

## 12. METRICS & OUTPUTS

### Per-Patch Results

```python
{
    'patch_id': 'elasticsearch_734dd070',
    'status': 'completed' | 'failed' | 'skipped',
    'exact_developer_patch': True/False,
    'phases': {
        'phase0': {...},
        'phase1': {...},
        'phase2': {...},
        'phase3': {...},
        'phase4_validation': {...}
    },
    'pair_consistency': {...},
    'developer_patch_comparison': {...},
    'generated_patch_files': {...},
}
```

### Aggregate Summary

```python
[
    {patch_1_results},
    {patch_2_results},
    ...
]

# Written to: results/pipeline_summary_{mode}.json
```

### Generated Files (per patch)

```
results/{project}/{patch_id}/
├─ mainline.patch                           # Mainline patch (input)
├─ generated_patch_agent_only.patch         # Agent output (Java code only)
├─ generated_patch_final_effective.patch    # Agent + auxiliary (full)
├─ pipeline_results.json                    # Full results
├─ log.txt                                  # Runtime log
├─ tokens.txt                               # Token usage breakdown
├─ phase0_log.md                            # Phase 0 details
├─ phase1_context_analyzer.json             # Phase 1 state
├─ phase2_structural_locator.json           # Phase 2 state
├─ phase3_file_editor.json                  # Phase 3 state
├─ phase4_validation_agent.json             # Phase 4 state
├─ post_pipeline_developer_patch_compare.md # Comparison report
├─ full_trace.md                            # Edit trace (with retries)
└─ transition_summary.md                    # Test transitions
```

---

## Summary

The evaluate_full_workflow.py orchestrates an end-to-end patch backporting pipeline:

1. **Load** dataset and iterate over patches
2. **Setup** repos and generate mainline & developer patches
3. **Prepare** agent-eligible content (filter tests, auto-generated)
4. **Execute** Phase 0 fast path (direct git apply)
5. **If Phase 0 fails**: Invoke multi-agent LLM pipeline (Phases 1-4) to adapt patch
   - Context Analyzer: semantic intent
   - Structural Locator: symbol mapping
   - Planning Agent: edit instructions
   - File Editor: apply edits
   - Validation Agent: compilation + tests (with retry loop)
6. **Compare** generated patch to ground truth developer patch
7. **Report** metrics, artifacts, and diagnostics

The system prioritizes **fidelity** (how close to developer patch) and **validation** (compilation + tests pass), with built-in retry logic for failure recovery and detailed logging for analysis.

