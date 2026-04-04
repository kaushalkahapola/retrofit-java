# H-MABS Pipeline Execution Flow

**Document Date**: April 3, 2026  
**Status**: Complete Pipeline Reference  
**Focus**: End-to-end execution flow with examples

---

## Table of Contents

1. [Pipeline Overview](#pipeline-overview)
2. [Phase 0: Optimistic Fast-Path](#phase-0-optimistic-fast-path)
3. [Phase 1: Context Analysis](#phase-1-context-analysis)
4. [Phase 2: Structural Localization](#phase-2-structural-localization)
5. [Phase 2.5: Planning & Adaptation](#phase-25-planning--adaptation)
6. [Phase 3: File Editing](#phase-3-file-editing)
7. [Phase 4: Validation Loop](#phase-4-validation-loop)
8. [Retry Logic & Routing](#retry-logic--routing)
9. [State Flow Diagram](#state-flow-diagram)
10. [Example: CVE Backport Trace](#example-cve-backport-trace)

---

## Pipeline Overview

```
START (user provides: mainline_diff, target_repo, mainline_repo)
  |
  v
Route: skip_phase_0 or use fast-path?
  |
  +---> NO  --> Phase 0 (git apply --check + test)
  |              |
  |              +---> SUCCESS --> END (skip all LLM)
  |              |
  |              +---> FAIL
  |
  +---> YES or Phase 0 FAIL
         |
         v
       Phase 1: ContextAnalyzer (Agent 1)
         - Deterministic semantic blueprint extraction
         - Output: semantic_blueprint (intent, critical APIs, affected imports)
         - LLM: None (purely heuristic)
         |
         v
       Phase 2: StructuralLocator (Agent 2)
         - File mapping (mainline files -> target files)
         - Symbol consistency mapping (renames, refactors)
         - Output: consistency_map, mapped_target_context
         - LLM: ReAct (max 18 recursions) with 7 tools
         |
         v
       Phase 2.5: PlanningAgent
         - Anchor verification (4-pass algorithm)
         - SemanticHunkAdapter fallback for API mismatches
         - str_replace edit plan generation
         - Output: hunk_generation_plan
         - LLM: ReAct (max 100 recursions) with 5 tools
         |
         v
       Phase 3: FileEditor (Agent 3)
         - Apply str_replace edits directly to target files
         - Generate git diffs (mechanically correct)
         - Output: adapted_code_hunks, adapted_test_hunks
         - LLM: ReAct (max 100 recursions) with 6 tools
         |
         v
       Phase 4: ValidationAgent (Agent 4)
         - 6-phase validation loop
         - Output: validation_results
         - LLM: Direct call (failure analysis only)
         |
         +---> PASS --> END
         |
         +---> FAIL (attempts < MAX_VALIDATION_ATTEMPTS=3)
                |
                v
             Smart Retry Routing
                |
                +---> path_or_file_operation   --> Phase 2 (StructuralLocator)
                +---> context_mismatch         --> Phase 2.5 (PlanningAgent)
                +---> api_mismatch             --> Phase 2.5 (PlanningAgent)
                +---> generation_contract      --> Phase 2.5 (PlanningAgent)
                +---> other                    --> Phase 3 (FileEditor)
                |
                v
             [Repeat Phase 2/2.5/3/4 with error context]
         |
         +---> FAIL (attempts >= MAX_VALIDATION_ATTEMPTS) --> END
```

---

## Phase 0: Optimistic Fast-Path

**File**: `/agents/phase0_optimistic.py`  
**Purpose**: Attempt direct `git apply` before spinning up expensive LLM pipeline

### Algorithm

```python
def phase_0_optimistic(state: AgentState, config) -> dict:
    # 1. Check cache first
    cached = load_phase0_cache(project, backport_commit, original_commit)
    if cached and is_phase0_cache_reusable(cached):
        return {"fast_path_success": True, "phase_0_baseline_test_result": cached, ...}
    
    # 2. Try direct git apply
    result = git.apply(patch_diff, target_repo, check=True)
    if result.failed:
        return {"fast_path_success": False}
    
    # 3. Run baseline tests (prove red)
    baseline_result = run_tests(target_repo, test_classes)
    if baseline_result.all_pass:
        # No vulnerability found! Patch may not be needed.
        return {"fast_path_success": False}
    
    # 4. Check if patch applies
    apply_result = git.apply(patch_diff, target_repo, check=False)
    if apply_result.failed:
        return {"fast_path_success": False}
    
    # 5. Run tests again (make green)
    fixed_result = run_tests(target_repo, test_classes)
    
    # 6. Evaluate transition
    transition = evaluate_transition(baseline_result, fixed_result)
    
    # Cache and return
    save_phase0_cache(project, backport_commit, original_commit, {
        "phase_0_baseline_test_result": baseline_result,
        "phase_0_transition_evaluation": transition,
    })
    
    return {
        "fast_path_success": True,
        "phase_0_baseline_test_result": baseline_result,
        "phase_0_transition_evaluation": transition,
        ...
    }
```

### Cache Reusability Check

```python
def is_phase0_cache_reusable(cached: dict) -> (bool, str):
    baseline = cached.get("phase_0_baseline_test_result", {})
    transition = cached.get("phase_0_transition_evaluation", {})
    
    # NOT reusable if:
    # - baseline mode = "baseline-apply-failed"
    # - baseline has 0 tests AND no transitions observed
    # - transition reason = "inconclusive: target tests not observed"
    
    return is_ok, reason
```

### Success Criteria

**Phase 0 succeeds if ALL of**:
1. `git apply --check` succeeds (patch applies cleanly)
2. Baseline tests show failure(s) (vulnerability exists)
3. `git apply` (actual) succeeds
4. Post-apply tests pass (fix works)
5. Transition evaluation shows `fail_to_pass` or `newly_passing` tests

---

## Phase 1: Context Analysis

**File**: `/agents/context_analyzer.py`  
**Purpose**: Extract semantic blueprint (fix intent, critical APIs)  
**LLM**: None (deterministic heuristic)  
**Determinism**: 100%

### Algorithm

```python
def context_analyzer(state: AgentState, config) -> dict:
    patch_analysis = PatchAnalyzer().analyze(patch_diff, with_test_changes=True)
    
    # 1. Identify test changes
    test_changes = [fc for fc in patch_analysis if fc.is_test_file]
    code_changes = [fc for fc in patch_analysis if not fc.is_test_file]
    
    # 2. Extract vulnerability intent
    vulnerability_intent = extract_intent_from_test_changes(test_changes)
    
    # 3. Extract critical APIs
    critical_apis = extract_apis_from_code_changes(code_changes)
    
    # 4. Identify affected modules and imports
    affected_imports = extract_imports(code_changes)
    affected_classes = extract_classes(code_changes)
    
    # 5. Create semantic blueprint
    blueprint = SemanticBlueprint(
        vulnerability_intent=vulnerability_intent,
        critical_apis=critical_apis,
        affected_imports=affected_imports,
        affected_classes=affected_classes,
        patch_scope="localized|moderate|wide",  # based on file count
        complexity_estimate=estimate_complexity(code_changes),
    )
    
    return {"semantic_blueprint": blueprint}
```

### Output Structure

```python
@dataclass
class SemanticBlueprint:
    vulnerability_intent: str  # e.g., "Prevent XXE attacks via XML parsing"
    critical_apis: List[str]   # e.g., ["SAXParserFactory.setFeature()", ...]
    affected_imports: List[str]  # e.g., ["javax.xml.parsers.SAXParserFactory"]
    affected_classes: List[str]  # e.g., ["XMLParser", "SecurityUtil"]
    patch_scope: str  # "localized" (1-2 files), "moderate" (3-5), "wide" (5+)
    complexity_estimate: str  # "simple", "moderate", "complex"
    test_synthesis_hints: List[str]  # Suggested test cases
```

---

## Phase 2: Structural Localization

**File**: `/agents/structural_locator.py`  
**Purpose**: Map mainline files to target files, track renames/refactors  
**LLM**: ReAct (max 18 recursions, 7 tools)  
**Fallback Strategy**: Deterministic first, then LLM

### Two-Phase Algorithm

#### Phase 2A: Deterministic (No LLM)

```python
def structural_locator_phase_2a(state: AgentState):
    # For each file in patch_analysis:
    for file_change in patch_analysis:
        mainline_file = file_change.file_path
        
        # Strategy 1: Direct path match
        if target_repo.has_file(mainline_file):
            map[mainline_file] = mainline_file
            confidence = 1.0
            continue
        
        # Strategy 2: Find by blob hash (exact content match)
        blob_hash = git.hash_object(mainline_file, mainline_repo)
        target_match = search_by_blob_hash(target_repo, blob_hash)
        if target_match:
            map[mainline_file] = target_match
            confidence = 0.95
            continue
        
        # Strategy 3: Package-level path normalization
        # e.g., "src/main/java/com/foo/Bar.java" exists
        normalized_path = normalize_package_path(mainline_file)
        if target_repo.has_file(normalized_path):
            map[mainline_file] = normalized_path
            confidence = 0.85
            continue
        
        # If deterministic fails, mark for LLM phase
        unmapped.append(mainline_file)
```

#### Phase 2B: LLM ReAct (Fallback)

```python
def structural_locator_phase_2b(state: AgentState):
    # For unmapped files, use LLM with tools:
    # 1. search_candidates(file_path)
    # 2. read_file(path)
    # 3. list_files(directory)
    # 4. get_dependency_graph(file_paths)
    # 5. search_by_patterns(patterns)
    # 6. get_method_info(file_path, method_name)
    # 7. search_class_by_outline(class_name)
    
    llm_prompt = f"""
    Map these unmapped files to target repo:
    {unmapped_files}
    
    Tools available:
    - search_candidates(file): Find candidate files
    - read_file(path): Read file content
    - get_dependency_graph(files): Analyze imports
    - search_by_patterns(patterns): Find by regex
    
    Your goal: For each unmapped file, find the exact path in target repo.
    If exact path doesn't exist, find the best match and explain why.
    """
    
    result = llm.invoke_react(llm_prompt, tools, max_recursions=18)
    
    # Extract mapping from result
    for mapping in result.mappings:
        map[mapping.source] = mapping.target
        confidence_map[mapping.source] = mapping.confidence
```

### Symbol Consistency Mapping

```python
def extract_consistency_map(state: AgentState):
    # For each mapped file pair:
    for source_file, target_file in file_mappings.items():
        source_content = read(source_file, mainline_repo)
        target_content = read(target_file, target_repo)
        
        # Extract classes, methods
        source_syms = extract_symbols(source_content)
        target_syms = extract_symbols(target_content)
        
        # Match symbols (exact or fuzzy)
        for src_sym in source_syms:
            # Tier 1: Exact match
            if src_sym in target_syms:
                consistency_map[src_sym] = src_sym
                confidence = 1.0
            
            # Tier 2: Fuzzy match (Levenshtein)
            else:
                best_match = find_fuzzy_match(src_sym, target_syms)
                if best_match.distance < 3:  # Allow 2 char differences
                    consistency_map[src_sym] = best_match
                    confidence = 0.8
                else:
                    # Method might be missing (deleted/refactored)
                    consistency_map[src_sym] = None
```

### Output

```python
return {
    "file_mappings": {
        "src/main/java/Security.java": "src/main/java/security/Validator.java",
        ...
    },
    "consistency_map": {
        "validateXML": "validateXMLInput",
        "parseDocument": "parseDocument",
        ...
    },
    "mapped_target_context": {
        "src/main/java/security/Validator.java": {
            "content": "...",
            "symbols": {"validateXMLInput", "parseDocument", ...},
            "imports": [...],
        },
        ...
    },
    "phase2_confidence": 0.92,
    "unmapped_files": []
}
```

---

## Phase 2.5: Planning & Adaptation

**File**: `/agents/planning_agent.py`  
**Purpose**: Verify anchors and create str_replace edit plans  
**LLM**: ReAct (max 100 recursions, 5 tools)  
**Special**: SemanticHunkAdapter fallback for API mismatches

### Anchor Verification (4-Pass Algorithm)

```python
def verify_anchor(anchor_text, target_file_content):
    # Pass 1: Exact match
    if anchor_text in target_file_content:
        return {
            "found": True,
            "method": "exact_match",
            "confidence": 1.0,
            "line_number": line_of(anchor_text, target_file_content)
        }
    
    # Pass 2: Line trimmed (ignore leading/trailing whitespace)
    trimmed_anchor = trim_lines(anchor_text)
    if trimmed_anchor in target_file_content:
        return {
            "found": True,
            "method": "line_trimmed",
            "confidence": 0.95,
            "line_number": line_of(trimmed_anchor, target_file_content)
        }
    
    # Pass 3: Multiline context aggregation
    # e.g., anchor is:
    # "public void foo() {" + "    return null;" + "}"
    # Search for "foo()" + later "return null" even if on different lines
    multiline_pattern = create_pattern(anchor_text)
    matches = regex_search(multiline_pattern, target_file_content)
    if matches:
        return {
            "found": True,
            "method": "multiline_trimmed",
            "confidence": 0.85,
            "line_number": matches[0].start_line
        }
    
    # Pass 4: Anchor reconstruction (use consistency_map)
    reconstructed_anchor = apply_consistency_map(anchor_text, consistency_map)
    if reconstructed_anchor in target_file_content:
        return {
            "found": True,
            "method": "anchor_reconstructed",
            "confidence": 0.75,
            "line_number": line_of(reconstructed_anchor, target_file_content),
            "reconstructed": True
        }
    
    # All passes failed
    return {"found": False, "confidence": 0.0}
```

### SemanticHunkAdapter Invocation

```python
def planning_agent_with_adapter(state: AgentState):
    for hunk in patch_hunks:
        anchor = extract_anchor_context(hunk)
        target_file = file_mappings[hunk.source_file]
        target_content = read(target_file)
        
        # Try anchor verification
        result = verify_anchor(anchor, target_content)
        
        if result.found:
            # Create str_replace plan
            plan = create_str_replace_plan(hunk, result.line_number)
        else:
            # Anchor failed - try semantic adaptation
            print(f"Anchor verification failed for {hunk.id}")
            adapter_result = semantic_hunk_adapter(
                hunk=hunk,
                target_file_content=target_content,
                target_file_path=target_file,
                consistency_map=consistency_map,
                semantic_blueprint=semantic_blueprint,
            )
            
            if adapter_result.confidence >= 0.6:  # Threshold
                # Use adapted anchor + plan
                plan = adapter_result.str_replace_plan
            else:
                # Adaptation failed - mark for Phase 3 LLM
                plan = create_fallback_plan(hunk, confidence=0.0)
```

### str_replace Plan Structure

```python
@dataclass
class StrReplaceEditPlan:
    file_path: str
    old_string: str  # Exact text to find and replace
    new_string: str  # Exact text to insert
    description: str  # "Add null check", "Fix SQL injection", etc.
    line_hint: int  # Approximate line number for validation
    confidence: float  # 0.0-1.0
    requires_llm_verification: bool  # If False, can auto-apply
```

---

## Phase 3: File Editing

**File**: `/agents/file_editor.py`  
**Purpose**: Apply str_replace edits and generate diffs  
**LLM**: ReAct (max 100 recursions, 6 tools)  
**Output**: Machine-generated diffs (git diff)

### Algorithm

```python
def file_editor(state: AgentState):
    # For each file with edits
    for target_file in hunk_generation_plan.keys():
        # 1. Checkout fresh copy
        git_reset(target_file, target_repo)
        
        # 2. Apply edits in sequence
        edits = hunk_generation_plan[target_file]
        applied_edits = []
        
        for edit in edits:
            # Pre-validation: Does old_string exist?
            if not edit.old_string in read(target_file):
                # Try to find it with tools
                result = search_for_anchor(
                    target_file=target_file,
                    search_pattern=edit.description,
                    tools=HunkGeneratorToolkit(target_repo)
                )
                
                if result.found:
                    # Adjust old_string
                    edit.old_string = result.actual_text
                else:
                    # Cannot apply - mark as failed
                    applied_edits.append({
                        "status": "FAILED",
                        "edit": edit,
                        "reason": "Anchor not found"
                    })
                    continue
            
            # Apply edit (atomic)
            success = str_replace_in_file(
                target_file,
                edit.old_string,
                edit.new_string
            )
            
            applied_edits.append({
                "status": "SUCCESS" if success else "FAILED",
                "edit": edit,
            })
        
        # 3. Generate diff (mechanically correct)
        if any(e["status"] == "SUCCESS" for e in applied_edits):
            diff = git_diff(target_file, target_repo)
            adapted_hunk = AdaptedHunk(
                hunk_id=f"adapted_{target_file}",
                hunk_text=diff,
                source_file=None,  # N/A for file editor
                applied_edits=applied_edits,
                confidence=calculate_confidence(applied_edits),
            )
            adapted_code_hunks.append(adapted_hunk)
        
        # 4. Reset file for next iteration
        git_reset(target_file, target_repo)
    
    return {
        "adapted_code_hunks": adapted_code_hunks,
        "adapted_test_hunks": [],  # Tests handled separately
        "adapted_file_edits": all_edits
    }
```

### Intent Check

```python
def verify_intent(generated_diff, semantic_blueprint):
    # LLM check: Does the diff match the intent?
    prompt = f"""
    ## Expected Intent
    {semantic_blueprint.vulnerability_intent}
    
    ## Critical APIs Required
    {semantic_blueprint.critical_apis}
    
    ## Generated Diff
    {generated_diff}
    
    Does the diff correctly implement the fix? Answer YES or NO.
    """
    
    response = llm.invoke(prompt, system_message=INTENT_CHECK_SYSTEM)
    
    if "NO" in response:
        # Regenerate or escalate
        print(f"Intent check failed: {response}")
        return False
    
    return True
```

---

## Phase 4: Validation Loop

**File**: `/agents/validation_agent.py`  
**Purpose**: 6-phase validation of patch correctness  
**LLM**: Direct call (failure analysis)  
**Recursion Limit**: N/A (not ReAct)

### Validation Phases

```
Phase 4.1: Proof of Vulnerability (Apply Tests Only)
  - Goal: Show that vulnerability exists in target (baseline broken)
  - Commands:
    * Checkout target repo
    * Apply only the test cases (if they exist)
    * Run tests -> Should FAIL (vulnerability present)
  - Outcome: "fail_to_pass" list (tests that need to pass after fix)

       |
       v

Phase 4.2: Failure Confirmation
  - Goal: Confirm tests actually fail before patch
  - Commands:
    * Apply full patch (code + tests)
    * Run tests -> Should FAIL
  - Outcome: Baseline test state

       |
       v

Phase 4.3: Patch Application
  - Goal: Apply code changes (no tests yet)
  - Commands:
    * git apply code_hunks (only code, not tests)
    * Check syntax (javac --check)
    * Compilation (mvn compile)
  - Outcome: Patch application success/failure

       |
       v

Phase 4.4: Targeted Verification
  - Goal: Confirm fix works for identified vulnerability
  - Commands:
    * Apply test hunks
    * Run only vulnerability tests (from Phase 4.1)
    * Run tests -> Should PASS
  - Outcome: "fail_to_pass" test results (all should pass)

       |
       v

Phase 4.5: Full Compilation
  - Goal: Ensure no regressions
  - Commands:
    * Full Maven build (mvn clean compile)
    * Check for warnings/errors
  - Outcome: Build success/failure, diagnostics

       |
       v

Phase 4.6: Static Analysis
  - Goal: Ensure patch doesn't introduce new vulnerabilities
  - Commands:
    * SpotBugs analysis
    * Optional: Infer, Checkstyle, other tools
  - Outcome: Bug findings (should not include new bugs)
```

### Validation Result Structure

```python
@dataclass
class ValidationResults:
    passed: bool  # All 6 phases succeeded
    phases: Dict[str, PhaseResult]  # "vulnerability_proof", "failure_confirmation", etc.
    
    # Quick access to failure info
    failure_category: str  # "path_or_file_operation", "context_mismatch", etc.
    failed_stage: str  # Which phase failed
    build: Dict  # Maven diagnostics
    hunk_application: Dict  # Hunk apply results
    test_results: Dict  # JUnit results
```

### Smart Routing (After Phase 4 Failure)

```python
def determine_retry_route(validation_results):
    failure_category = validation_results.failure_category
    failed_stage = validation_results.failed_stage
    
    # Category 1: File/path operation issues
    if failed_stage in ["hunk_apply_failed", "file_not_found"]:
        if "file not found" in validation_results.raw_output.lower():
            return "structural_locator"  # Re-map files
        elif "context mismatch" in validation_results.raw_output.lower():
            return "planning_agent"  # Re-plan anchors
    
    # Category 2: Context mismatch
    if failure_category == "context_mismatch":
        return "planning_agent"  # Re-verify anchors
    
    # Category 3: API/signature issues
    build_issues = validation_results.build.diagnostics.issues
    if any(issue.error_type == "api_or_signature_mismatch" for issue in build_issues):
        return "planning_agent"  # Re-plan with semantic adapter
    
    # Category 4: Generation contract failed
    if failed_stage == "generation_contract_failed":
        return "planning_agent"  # Structural fix needed
    
    # Category 5: Empty generation
    if validation_results.generation_output == "":
        return "planning_agent"  # Need to re-plan
    
    # Default: Retry Agent 3
    return "hunk_generator"
```

---

## Retry Logic & Routing

**File**: `/graph.py` (routes), `/agents/validation_agent.py` (determines category)

### Retry Budget

```python
MAX_VALIDATION_ATTEMPTS = 3

# Attempt 1: Initial run
# Attempt 2: First retry (smart route)
# Attempt 3: Second retry (different route or same if loop)
# Attempt 4+: Give up
```

### Identical Patch Guard

```python
def check_identical_patch_guard(state: AgentState):
    # If validation fails but generated patch is identical to last iteration
    last_patch_hash = state.get("last_patch_sha256")
    current_patch_hash = sha256(state.adapted_code_hunks)
    
    if last_patch_hash == current_patch_hash:
        # Infinite loop detected! Don't retry.
        return {
            "validation_passed": False,
            "infinite_loop_detected": True
        }
    
    # Continue with retry
    return {"last_patch_sha256": current_patch_hash}
```

### Retry Routing Table

| Failure Category | Source | Route | Purpose |
|------------------|--------|-------|---------|
| `path_or_file_operation` | Agent 4 | Phase 2 (StructuralLocator) | Re-map files |
| `context_mismatch` | Agent 4 | Phase 2.5 (PlanningAgent) | Re-verify anchors |
| `api_mismatch` | Agent 4 Build | Phase 2.5 (PlanningAgent) | Semantic adaptation |
| `generation_contract_failed` | Agent 4 | Phase 2.5 (PlanningAgent) | Structural fix |
| `empty_generation` | Agent 4 | Phase 2.5 (PlanningAgent) | Regenerate plan |
| `hunk_application_failed` | Agent 4 | Phase 3 (FileEditor) | Retry editing |
| Others | Agent 4 | Phase 3 (FileEditor) | Default retry |

---

## State Flow Diagram

```
AgentState (LangGraph StateGraph)
{
  # Input
  patch_diff: str                           # Raw unified diff
  mainline_repo_path: str                   # Path to mainline (source)
  target_repo_path: str                     # Path to target (dest)
  skip_phase_0: bool                        # Skip fast-path?
  
  # Phase 0 Output
  fast_path_success: bool                   # Did git apply work?
  phase_0_baseline_test_result: dict        # Before-patch test state
  phase_0_transition_evaluation: dict       # Fail->Pass analysis
  
  # Phase 1 Output
  semantic_blueprint: SemanticBlueprint     # Intent + critical APIs
  patch_analysis: List[FileChange]          # Structured patch data
  
  # Phase 2 Output
  file_mappings: Dict[str, str]             # mainline_file -> target_file
  consistency_map: Dict[str, str]           # symbol renames
  mapped_target_context: Dict               # target file content
  phase2_confidence: float                  # 0.0-1.0
  
  # Phase 2.5 Output
  hunk_generation_plan: Dict[str, List[StrReplaceEditPlan]]
  
  # Phase 3 Output
  adapted_code_hunks: List[AdaptedHunk]     # Generated diffs
  adapted_test_hunks: List[AdaptedHunk]     # Test diffs (usually empty)
  adapted_file_edits: List[FileEdit]        # Edit records
  
  # Phase 4 Output
  validation_results: ValidationResults
  validation_passed: bool
  validation_failure_category: str          # For routing
  validation_failed_stage: str              # Which phase
  validation_attempts: int                  # Retry counter
  
  # Retry Context
  last_patch_sha256: str                    # For identical patch guard
  validation_error_context: str             # Feedback for retry
  validation_retry_history: List[dict]      # All attempt records
}
```

---

## Example: CVE Backport Trace

### Scenario
Backporting a CVE fix from Elasticsearch mainline (latest) to target (older version)  
CVE: XML External Entity (XXE) injection vulnerability

### Trace

```
INPUT:
  patch_diff = """
    --- a/src/main/java/org/elasticsearch/common/xcontent/XmlUtils.java
    +++ b/src/main/java/org/elasticsearch/common/xcontent/XmlUtils.java
    @@ -25,6 +25,8 @@ public class XmlUtils {
         SAXParserFactory factory = SAXParserFactory.newInstance();
    +    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
    +    factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
         SAXParser parser = factory.newParser();
  """
  mainline_repo_path = "/path/to/elasticsearch/mainline"
  target_repo_path = "/path/to/elasticsearch/target"

PHASE 0: Optimistic Fast-Path
  [1] Try: git apply --check
    -> FAIL: File moved in target branch
  [2] Result: fast_path_success = False
  [3] Continue to Phase 1

PHASE 1: Context Analysis
  [1] Extract test changes (if any)
    -> Found: XmlUtilsTest.testXXEPrevention()
  [2] Extract vulnerability intent
    -> "Prevent XXE attacks by disabling external entity parsing"
  [3] Extract critical APIs
    -> ["SAXParserFactory.setFeature()", "XMLConstants.ACCESS_EXTERNAL_DTD"]
  [4] Create semantic blueprint
    -> semantic_blueprint = {
         vulnerability_intent: "Prevent XXE attacks...",
         critical_apis: ["SAXParserFactory.setFeature()", ...],
         affected_imports: ["javax.xml.parsers.SAXParserFactory"],
         affected_classes: ["XmlUtils"],
         patch_scope: "localized",
         complexity_estimate: "simple"
       }
  [5] Result: Output semantic_blueprint

PHASE 2: Structural Localization
  [1] Deterministic file mapping:
    -> Check if "src/main/java/org/elasticsearch/common/xcontent/XmlUtils.java" exists
    -> NOT found in target
  [2] LLM ReAct Phase (fallback):
    -> Use search_candidates("src/main/java/org/elasticsearch/common/xcontent/XmlUtils.java")
    -> Find: "src/main/java/elasticsearch/xcontent/XmlUtils.java" (package moved)
    -> Confidence: 0.92
  [3] Symbol consistency mapping:
    -> Extract symbols from both versions
    -> SAXParserFactory -> SAXParserFactory (exact match)
    -> newParser() -> newParser() (exact match)
  [4] Extract mapped context
    -> Read full XmlUtils.java from target
  [5] Result: Output file_mappings, consistency_map, mapped_target_context

PHASE 2.5: Planning & Adaptation
  [1] Extract hunk from patch:
    -> old_string = """    SAXParserFactory factory = SAXParserFactory.newInstance();
        SAXParser parser = factory.newParser();"""
    -> new_string = """    SAXParserFactory factory = SAXParserFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        SAXParser parser = factory.newParser();"""
  
  [2] Verify anchor in target:
    -> Search for "SAXParserFactory factory = SAXParserFactory.newInstance();"
    -> Pass 1 (exact match): FOUND at line 28
    -> Confidence: 1.0
  
  [3] Create str_replace plan:
    -> StrReplaceEditPlan {
         file_path: "src/main/java/elasticsearch/xcontent/XmlUtils.java",
         old_string: "    SAXParserFactory factory = SAXParserFactory.newInstance();",
         new_string: "    SAXParserFactory factory = SAXParserFactory.newInstance();\n    factory.setFeature(...)",
         line_hint: 28,
         confidence: 1.0,
         requires_llm_verification: False
       }
  
  [4] Result: Output hunk_generation_plan

PHASE 3: File Editing
  [1] Read target file
    -> src/main/java/elasticsearch/xcontent/XmlUtils.java
  
  [2] Apply str_replace edit:
    -> Find: "    SAXParserFactory factory = SAXParserFactory.newInstance();"
    -> Replace with: [3 lines with setFeature calls]
    -> Result: SUCCESS
  
  [3] Generate diff:
    -> git diff HEAD -- src/main/java/elasticsearch/xcontent/XmlUtils.java
    -> Produces mechanically correct unified diff
  
  [4] Reset file to HEAD
    -> git checkout HEAD -- src/main/java/elasticsearch/xcontent/XmlUtils.java
  
  [5] Result: Output adapted_code_hunks

PHASE 4: Validation Loop (Attempt 1/3)
  [4.1] Proof of Vulnerability:
    -> Apply test changes only (XmlUtilsTest.testXXEPrevention)
    -> Run: mvn test -Dtest=XmlUtilsTest#testXXEPrevention
    -> Result: FAIL (as expected - vulnerability present)
  
  [4.2] Failure Confirmation:
    -> Apply full patch (code + test)
    -> Run: mvn test -Dtest=XmlUtilsTest#testXXEPrevention
    -> Result: FAIL (baseline confirmed)
  
  [4.3] Patch Application:
    -> Apply code_hunks only (no tests)
    -> Run: mvn compile
    -> Result: SUCCESS
  
  [4.4] Targeted Verification:
    -> Apply test changes
    -> Run: mvn test -Dtest=XmlUtilsTest#testXXEPrevention
    -> Result: PASS (fix works!)
    -> fail_to_pass = ["testXXEPrevention"]
  
  [4.5] Full Compilation:
    -> Run: mvn clean compile
    -> Result: SUCCESS
    -> No warnings
  
  [4.6] Static Analysis:
    -> Run: spotbugs -effort:max
    -> Result: No XXE-related bugs found
  
  [5] Validation Result:
    -> validation_passed = True
    -> failure_category = N/A
    -> failed_stage = N/A
  
  [6] Routing decision:
    -> Route to: END (success!)

FINAL OUTPUT:
  {
    "fast_path_success": False,
    "semantic_blueprint": {...},
    "file_mappings": {
      "src/main/java/org/elasticsearch/common/xcontent/XmlUtils.java": 
      "src/main/java/elasticsearch/xcontent/XmlUtils.java"
    },
    "consistency_map": {"SAXParserFactory": "SAXParserFactory", ...},
    "adapted_code_hunks": [{
      "hunk_id": "adapted_XmlUtils",
      "hunk_text": "[git diff output]",
      "confidence": 1.0
    }],
    "validation_results": {
      "passed": True,
      "phases": {
        "vulnerability_proof": {"result": "FAIL"},
        "failure_confirmation": {"result": "FAIL"},
        "patch_application": {"result": "SUCCESS"},
        "targeted_verification": {"result": "PASS"},
        "full_compilation": {"result": "SUCCESS"},
        "static_analysis": {"result": "PASS"}
      }
    },
    "validation_attempts": 1
  }
```

---

## Key Design Patterns

### 1. **Deterministic-First, LLM-as-Fallback**
- Phase 0: Pure git (no LLM)
- Phase 1: Heuristics (no LLM)
- Phase 2A: Deterministic (no LLM)
- Phase 2B: LLM only if Phase 2A fails
- Similar pattern in other phases

### 2. **Smart Retry Routing**
- Don't just retry the same agent
- Analyze failure category
- Route to most likely fixing agent
- Example: `context_mismatch` -> `planning_agent` (re-verify anchors)

### 3. **Pre-Validation Before Mutation**
```python
# CORRECT pattern (used throughout)
if old_string not in file_content:
    return error  # Fail before mutation
actual_change = replace(old_string, new_string)  # NOW mutate

# WRONG pattern (avoided)
actual_change = replace(old_string, new_string)  # Mutate first
if old_string not in file_content:
    rollback()  # Try to fix after
```

### 4. **Session State Management**
- Each toolkit maintains state (HunkGeneratorToolkit._todos)
- Per-session (not global)
- Enables agent to track progress

### 5. **Confidence Scores**
- All major operations produce confidence: 0.0-1.0
- Phase 2: Uses for file mapping decisions
- Phase 2.5: Decides if LLM verification needed
- Phase 4: Determines retry routing

---

## Summary

The H-MABS pipeline is a carefully orchestrated sequence of deterministic analysis → intelligent mapping → planning → execution → validation, with smart retry logic that routes failures to the most likely fixing agent.

The key innovation is **hybrid determinism**: maximizing correctness by using LLM only when deterministic approaches fail, and using detailed error categorization to guide retries to the right agent.

---

