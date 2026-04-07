# H-MABS: Hybrid Multi-Agent Backporting System — Complete Technical Overview

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Patch Type Taxonomy](#2-patch-type-taxonomy)
3. [System Architecture](#3-system-architecture)
4. [Pipeline: Phase by Phase](#4-pipeline-phase-by-phase)
   - [Phase 0 — Optimistic Fast-Path](#phase-0--optimistic-fast-path)
   - [Phase 1 — Context Analyzer](#phase-1--context-analyzer-agent-1)
   - [Phase 2 — Structural Locator](#phase-2--structural-locator-agent-2)
   - [Phase 2.5 — Planning Agent](#phase-25--planning-agent)
   - [Phase 3 — File Editor](#phase-3--file-editor-agent-3)
   - [Phase 4 — Validation Agent](#phase-4--validation-agent-agent-4)
   - [Retry — Reasoning Architect](#retry--reasoning-architect)
5. [Analysis Engine (Java MCP Tools)](#5-analysis-engine-java-mcp-tools)
6. [Key Data Structures](#6-key-data-structures)
7. [Evaluation Harness](#7-evaluation-harness)
8. [Configuration & Setup](#8-configuration--setup)
9. [Key File Reference](#9-key-file-reference)

---

## 1. Problem Statement

**Patch backporting** is the process of taking a fix (bug fix, security patch) applied to a newer version of a Java project and adapting it to apply to an older maintained version. This is extremely common in open-source Java projects (Elasticsearch, Druid, Crate, JDK) where multiple major versions are supported simultaneously.

### Why Backporting Java Is Hard

Simple `git cherry-pick` or `git apply` fails in practice because the target codebase (older version) has diverged:

| Divergence Type | Example |
|----------------|---------|
| Method renamed | `allocBuffer()` → `Legacy_allocBuffer()` in older version |
| Method moved to different class | Fixed in `TransportService`, lives in `LegacyTransport` in target |
| Method moved to different file | Split across modules differently |
| API signature changed | Extra parameter added, return type changed |
| Logic refactored | Entire block restructured; no direct equivalent code |
| Package/import renames | Different package hierarchy in target |

### The H-MABS Solution

H-MABS (Hybrid Multi-Agent Backporting System) combines:
- **Deterministic pre-checks** (git apply, anchor overlap scoring) to skip LLM work when unnecessary
- **Semantic understanding** (LLM agents) to understand *why* a patch exists
- **Structural mapping** (AST tools + vector retrieval) to find exact insertion points in the target
- **CLAW-inspired exact string replacement** (not brittle LLM-generated unified diffs)
- **Compile + test validation** with a bounded retry loop

---

## 2. Patch Type Taxonomy

Every backport challenge falls into one of five types. The classification is used by the **Planning Agent** (Phase 2.5) to decide how to adapt each hunk, and by the **complexity classifier** (Phase 0) for routing.

### TYPE I — Direct Apply (Trivial)
> Same location, same edits. The patch applies directly.

- `git apply --check` succeeds on the target repo
- Context lines match; no symbol renames needed
- **Pipeline**: Phase 0 fast-path exits immediately — no LLM agents invoked
- **Complexity classifier output**: `TRIVIAL`
- **Frequency**: ~30% of real-world backports

**Example**: A comment change, a constant value update, or a test-only fix that didn't touch any refactored code.

---

### TYPE II — Location Change, Same Edits
> The code change is identical, but the code lives in a different file or method in the target.

- `git apply --check` fails because context lines don't match
- No API/symbol renames needed — the edit itself is the same
- **Pipeline**: Phase 2 (Structural Locator) finds the new location; Planning Agent wraps edit in correct anchors
- **Complexity classifier output**: `STRUCTURAL`
- **Example**: Method moved to a parent class, or refactored into a utility file

**What changes**: Only the `target_file`, `target_method`, `start_line` / `end_line` in `MappedTargetContext`. The `old_string` and `new_string` are taken directly from the mainline patch with no symbol substitution.

---

### TYPE III — Same Location, Namespace Changes
> Code is in the same place, but symbols/APIs have different names in the target.

- File path is the same; method is the same
- Symbol names differ: renamed methods, renamed constants, different import paths
- **Pipeline**: Phase 2 detects renames and builds `ConsistencyMap`; Planning Agent applies symbol substitutions to produce `new_string`
- **Complexity classifier output**: `STRUCTURAL`
- **Example**: `alloc_buf()` was renamed `legacy_alloc_buf()` in the older version

**What changes**: `new_string` has symbols substituted per `ConsistencyMap`. Location (`target_file`, `start_line`) is the same as mainline.

---

### TYPE IV — Location Change + Namespace Changes
> Both location and symbol names differ between mainline and target.

- Combination of TYPE II + TYPE III challenges
- **Pipeline**: Structural Locator finds the new location AND builds ConsistencyMap; Planning Agent applies both
- **Complexity classifier output**: `STRUCTURAL` or `REWRITE`
- **Example**: A security check was added to `NetworkService.handleRequest()` in mainline, but in the target it was refactored into `LegacyNetworkHandler.processInbound()` which also uses `LegacySocketPool` instead of `SocketPool`

**What changes**: Both `target_file`/`target_method` and the symbols in `new_string`.

---

### TYPE V — Structural Rewrite
> Logic has been significantly refactored; no direct code equivalent exists.

- Anchor match ratio is low (< 40%); `old_string` from mainline patch won't be found anywhere in target
- Equivalent logic might be spread across multiple methods/classes, or implemented differently
- **Pipeline**: Reasoning Architect diagnoses structural mismatch; Planning Agent in TYPE_V mode writes entirely new code based on semantic intent
- **Complexity classifier output**: `REWRITE`
- **Example**: A null-check guard was added to a method in mainline, but in the target that method was refactored into a template method pattern — the equivalent logic must be placed in an overridden hook method

**What changes**: Entire `old_string`/`new_string` is derived from semantic understanding, not from mainline diff text.

### TYPE Mapping Summary

| TYPE | Location Same? | Namespace Same? | Complexity | Phase 0 | Key Pipeline Work |
|------|---------------|-----------------|------------|---------|-------------------|
| I    | Yes           | Yes             | TRIVIAL    | Exits   | None              |
| II   | No            | Yes             | STRUCTURAL | Fails   | Structural Locator |
| III  | Yes           | No              | STRUCTURAL | Fails   | ConsistencyMap    |
| IV   | No            | No              | STRUCTURAL/REWRITE | Fails | Both  |
| V    | N/A           | N/A             | REWRITE    | Fails   | Reasoning Architect |

---

## 3. System Architecture

### Two-Service Design

```
┌─────────────────────────────────────────────┐
│           agents-backend (Python)           │
│                                             │
│   LangGraph StateGraph                      │
│   ┌──────────────────────────────────────┐  │
│   │  Phase 0 → Agent1 → Agent2 → Agent3  │  │
│   │       ↑     ↓          (retry loop)  │  │
│   │  Agent4 (Validation) ─────────────→  │  │
│   └──────────────────────────────────────┘  │
│                    │ MCP calls               │
└────────────────────┼────────────────────────┘
                     │ HTTP/SSE
┌────────────────────┼────────────────────────┐
│        analysis-engine (Java)               │
│                                             │
│  Spring Boot + Spoon AST + SpotBugs         │
│  Endpoint: http://localhost:8080/mcp/sse    │
│                                             │
│  Tools: CompileTool, GetClassContextTool,   │
│         ReplaceMethodBodyTool, ...          │
└─────────────────────────────────────────────┘
```

### LangGraph State Graph

```
START
  │
  ├─[skip_phase_0=True]──────────────────────────┐
  │                                               ↓
  └─[default]──→ phase_0_optimistic         context_analyzer (Agent 1)
                      │                           │
           [success]  │  [failed]                 ↓
               END ←──┘             structural_locator (Agent 2)
                                          │
                                 [always: initial pass]
                                          ↓
                                    hunk_generator (Agent 3)
                                          │
                                          ↓
                                     validation (Agent 4)
                                          │
              ┌───────────────────────────┤
         [passed]                    [failed]
              │               ┌──────────┴──────────────────────┐
             END    [target_file_missing]  [generic] [max_attempts]
                              │                │           │
                    structural_locator    planning_agent  END
                                               │
                                      reasoning_architect
                                               │
                                         hunk_generator
                                               │
                                          validation ...
```

**MAX_VALIDATION_ATTEMPTS = 3** (defined in `src/graph.py`)

### Data Artifacts Flow

```
patch_diff ──→ [Phase 0] ──→ patch_complexity, fast_path_success
                          ↓
               [Agent 1] ──→ SemanticBlueprint
                          ↓
               [Agent 2] ──→ ConsistencyMap, MappedTargetContext
                          ↓
               [Planning] ──→ HunkGenerationPlan (per-hunk old_string/new_string)
                          ↓
               [Agent 3] ──→ AdaptedHunk[] (hunk_text = git diff output)
                          ↓
               [Agent 4] ──→ validation_passed, validation_results
```

---

## 4. Pipeline: Phase by Phase

---

### Phase 0 — Optimistic Fast-Path

**File**: `agents-backend/src/agents/phase0_optimistic.py`

**Goal**: Attempt direct `git apply` before invoking any LLM. Skip the entire pipeline if the patch applies cleanly and tests pass.

#### Complexity Classifier

Before the fast-path attempt, `patch_complexity.classify_patch_complexity()` deterministically classifies the patch:

| Output | Condition |
|--------|-----------|
| `TRIVIAL` | No Java changes, OR `git apply --check` passes |
| `STRUCTURAL` | Files exist in target + no ADD/DELETE/RENAME ops + anchor overlap ≥ threshold |
| `REWRITE` | Low anchor overlap OR structural ops (ADD/DELETE/RENAME) |

**Anchor overlap thresholds** (from `patch_complexity.py`):
```
avg_ratio >= 0.45           → STRUCTURAL (general case)
avg_ratio >= 0.38 (1 file)  → STRUCTURAL (single-file leniency)
avg_ratio >= 0.40 (≤3 files)→ STRUCTURAL
< threshold or struct ops   → REWRITE
```

*Anchor ratio* = fraction of hunk context lines (unchanged `-` lines and context ` ` lines) that appear verbatim in the target file.

#### Fast-Path Execution

```
1. Parse patch → List[FileChange]
2. If experiment_mode: checkout parent of backport_commit^ in target repo
3. git apply --check <patch>
   → FAIL: return fast_path_success=False
4. git apply <patch> (actual apply)
5. run_build_script()
   → FAIL: restore repo, return fast_path_success=False
6. run_relevant_tests()
7. evaluate_test_state_transition()
   → valid signal (fail→pass, no regressions): fast_path_success=True
```

**Caching**: In experiment mode, Phase 0 results are cached to `evaluate/full_run/phase0_cache/` to avoid re-running expensive builds. Cache is invalidated if baseline apply fails or tests are inconclusive.

**Outputs**:
- `fast_path_success`: bool
- `patch_analysis`: `List[FileChange]`
- `patch_complexity`: `TRIVIAL | STRUCTURAL | REWRITE`
- `phase_0_baseline_test_result`, `phase_0_post_patch_test_result`
- `phase_0_transition_evaluation`: `{fail_to_pass, newly_passing, pass_to_fail, valid_backport_signal}`

---

### Phase 1 — Context Analyzer (Agent 1)

**File**: `agents-backend/src/agents/context_analyzer.py`

**Goal**: Build a `SemanticBlueprint` explaining *why* the patch exists and *how* the fix works — without looking at the target repo at all.

#### Deterministic Analysis (Always Runs)

For every non-test `.java` hunk, infer:

| Role | Detection Pattern |
|------|------------------|
| `declaration` | Import statements, field declarations |
| `guard` | Lines with `if`, `throw`, `assert`, `return` (safety checks) |
| `core_fix` | Method calls, assignments (the actual fix) |
| `propagation` | Other changes that propagate the fix |

Dependent APIs are extracted from added lines by capturing identifiers that appear before parentheses (method calls).

#### LLM Phase (REWRITE complexity only)

When `patch_complexity == "REWRITE"`, an LLM call produces:
- `root_cause_hypothesis` — technical explanation of the vulnerability/bug
- `fix_logic` — the core algorithm/logic change
- `dependent_apis` — critical methods, constants, types the fix depends on
- `patch_intent_summary` — one-sentence goal of the entire patch
- `hunk_chain` — role annotations updated with semantic understanding

Patch diff is capped at 10,000 characters to avoid context overflow. Falls back to deterministic analysis on LLM failure.

**Outputs** → `semantic_blueprint: SemanticBlueprint`

```python
class SemanticBlueprint(TypedDict):
    root_cause_hypothesis: str  # "Missing bounds check on buffer_size"
    fix_logic: str              # "Add guard before reallocation"
    dependent_apis: list        # ["MAX_SIZE", "reallocate"]
    patch_intent_summary: str   # "Prevent buffer overflow"
    hunk_chain: list            # Ordered List[HunkRole]
```

---

### Phase 2 — Structural Locator (Agent 2)

**File**: `agents-backend/src/agents/structural_locator.py`

**Goal**: Find exact insertion points in the target repo. Produces `ConsistencyMap` (symbol renames) and `MappedTargetContext` (exact target file/line/method for each hunk).

#### Two-Phase Strategy

**Phase A — Deterministic Path Check**:
1. Check if `mainline_file_path` exists at the same relative path in target repo
2. If yes: verify logic is present via `get_class_context()` or `read_file()`
3. If no: escalate to Phase B

**Phase B — ReAct Tool Loop** (recursion limit: 18):

Available tools:

| Tool | Purpose |
|------|---------|
| `search_candidates(file_path)` | EnsembleRetriever: symbol + TF-IDF candidate search |
| `match_structure(mainline_file, candidates)` | Structural similarity scoring via AST |
| `get_class_context(file_path, method_name)` | Get method boundaries (start/end line, code) |
| `get_dependency_graph(file_paths)` | Find architectural neighbors |
| `read_file(file_path)` | Read target repo file |
| `grep_repo(search_text, is_regex)` | Full-repo text/regex search |
| `find_symbol_locations(symbol)` | Where a symbol is declared in target |
| `git_pickaxe(file_path, snippet)` | Trace snippet through git history |
| `git_log_follow(file_path)` | Check git history for renames |

#### EnsembleRetriever

Builds a searchable index of the target repo:
1. **Symbol index**: Tree-sitter extracts method/class names from every `.java` file
2. **TF-IDF matrix**: BM25-like sublinear TF, bigrams, 10k features max
3. **Cache**: `~/.cache/agents-backend/retrieval/` keyed by `hash(repo_path) + commit_sha`

Candidate search uses symbol index first (fast), falls back to TF-IDF cosine similarity.

#### MethodFingerprinter — 4-Tier Matching

When a method's name has changed between mainline and target:

| Tier | Confidence | Strategy |
|------|-----------|----------|
| 1 | 1.0 | Exact name match |
| 2 | 0.9 | Parameter signature match |
| 3 | 0.8 | Name similarity (Levenshtein ratio > 0.8) |
| 4 | 0.7 | Call graph similarity (Jaccard on method invocations > 0.3) |

**Outputs**:
```python
# ConsistencyMap: mainline → target symbol renames
consistency_map = {"alloc_buf": "Legacy_alloc_buf", "MAX_SIZE": "LEGACY_MAX"}

# MappedTargetContext: per-file hunk mappings
mapped_target_context = {
    "src/Foo.java": [{
        "hunk_index": 0,
        "mainline_method": "write",
        "target_file": "src/legacy/Foo.java",
        "target_method": "legacyWrite",
        "start_line": 42,
        "end_line": 88,
        "code_snippet": "..."
    }]
}
```

---

### Phase 2.5 — Planning Agent

**File**: `agents-backend/src/agents/planning_agent.py`

**Goal**: Convert `MappedTargetContext` into verified `old_string` / `new_string` str_replace instructions for every hunk. Does **not** edit files.

#### Per-Hunk Adaptation Classification

For each hunk, the Planning Agent classifies its adaptation type (TYPE I–V, as described in Section 2) and produces:

```python
{
    "hunk_index": 0,
    "target_file": "src/legacy/Foo.java",
    "adaptation_type": "TYPE_III",   # see taxonomy above
    "edit_type": "replace",          # replace | insert_before | insert_after | delete
    "old_string": "...",             # exact text currently in target file
    "new_string": "...",             # replacement text (with symbol substitutions applied)
    "verified": True,                # old_string confirmed to exist in file
    "verification_result": "EXACT_MATCH at line 59",
    "namespace_changes": [{"from": "MAX_SIZE", "to": "LEGACY_MAX", "reason": "..."}],
    "notes": "..."
}
```

#### Anchor Verification (4-Pass Algorithm)

To confirm `old_string` exists in the target file before handing off to the file editor:

1. **Exact match** — substring search (case-sensitive, whitespace-exact)
2. **Line-trimmed match** — strip leading/trailing whitespace per line
3. **Multiline-trimmed match** — normalize all internal whitespace
4. **Reconstructed match** — re-derive `old_string` from context lines in hunk

If none of the 4 passes find the anchor, the plan entry is marked `"verified": false` and TYPE_V repair subagent is triggered.

**Tools available to Planning Agent**:
- `read_file_range(target_file, start_line, end_line)`
- `grep_in_file(target_file, pattern)`
- `get_api_diff_map()` — signature differences between mainline and target
- `validate_plan_before_apply()` — pre-check for `old_string` existence

**Output** → `hunk_generation_plan: HunkGenerationPlan`

---

### Phase 3 — File Editor (Agent 3)

**File**: `agents-backend/src/agents/file_editor.py`

**Goal**: Apply the verified edit plans to the target repo files. Uses exact string replacement, then generates the final unified diff via `git diff HEAD`.

#### Why Not LLM-Generated Diffs?

LLM-generated unified diffs are fragile — wrong line counts, incorrect `@@` headers, missing context lines. Instead:
1. Apply str_replace edits **directly to the checked-out file**
2. Run `git diff HEAD -- <file>` to get machine-correct unified diff
3. Reset file to HEAD (`git checkout HEAD -- <file>`)
4. Store the `git diff` output as `AdaptedHunk.hunk_text`

This is the CLAW (Code Language Abstraction Workflow) approach.

#### Tool Hierarchy

Applied in priority order to maximize reliability:

**1. AST Tools (Highest Priority)** — via analysis-engine `ReplaceMethodBodyTool`:
- `replace_method_body(file_path, method_name, new_body)` — Spoon AST replacement, immune to line drift
- `replace_field(file_path, field_name, new_field_def)`
- `insert_import(file_path, import_statement)`
- `remove_method(file_path, method_name)`

**2. String Tools (Second Priority)**:
- `edit_file(file_path, old_string, new_string, replace_all=False)` — exact str_replace
- Immune to line number drift; fails safely if `old_string` not found

**3. Line-Based Fallback (Last Resort)**:
- `replace_lines(file_path, start_line, end_line, new_content)` — line-numbered replacement
- Requires delta tracking after each edit (bottom-to-top ordering)

**Verification Tools**:
- `check_java_syntax(file_path)` — fast javac syntax check (ignores symbol/classpath errors)
- `verify_guidelines(diff_text)` — detect dangling assignments, static fields in methods
- `read_full_file(file_path)` — read entire file for context

#### Execution Order

```
For each target file in plan:
  1. Read file around expected edit areas
  2. For each hunk (in reverse line order to avoid drift):
     a. Try edit_file() with plan's old_string/new_string
     b. On failure: escalate to AST tools or line-based fallback
     c. Track line delta for subsequent edits
  3. check_java_syntax() → fix obvious syntax errors
  4. git diff HEAD -- <file>  → capture hunk_text
  5. git checkout HEAD -- <file>  → restore clean state
  6. Intent verification LLM call: does diff implement SemanticBlueprint?
```

**Outputs** → `adapted_code_hunks: List[AdaptedHunk]`

```python
class AdaptedHunk(TypedDict):
    target_file: str        # Relative path in target repo
    mainline_file: str      # Original mainline file (lineage tracking)
    hunk_text: str          # Unified diff (machine-generated by git diff)
    insertion_line: int     # Anchor line in target file
    intent_verified: bool   # LLM confirmed diff implements fix intent
    file_operation: str     # "ADDED" | "DELETED" | "MODIFIED" | "RENAMED"
```

---

### Phase 4 — Validation Agent (Agent 4)

**File**: `agents-backend/src/agents/validation_agent.py`

**Goal**: "Prove Red, Make Green" — apply adapted hunks, compile, run tests, diagnose failures for retry.

#### Validation Steps

```
1. Hunk Application
   → git apply <adapted_hunk>
   → Classify failure: context_mismatch | target_file_missing | malformed_patch

2. Build
   → run_build_script() (Maven/Gradle depending on project)
   → Parse compiler errors: file paths, line numbers, symbol/signature mismatches
   → Classify: syntax_error | api_drift | unknown_build_failure

3. Tests
   → run_relevant_tests() on relevant test classes for modified files
   → Evaluate state transition: fail→pass (signal), pass→fail (regression)
   → Classify: valid_backport_signal | pass_to_fail_regression | inconclusive
```

#### Failure Classification & Routing

| Failure Category | Router Action |
|-----------------|---------------|
| `target_file_missing` | Re-route to `structural_locator` for fresh file search |
| `test_infrastructure` / `test_runner_config` | Stop retries (infra issue, not code) |
| `context_mismatch` | Re-route to `planning_agent` (attempts < 3) |
| `api_mismatch` | Re-route to `planning_agent` (Reasoning Architect diagnoses) |
| Max 3 attempts reached | Stop, output failure |
| `validation_passed = True` | Route to END |

**Outputs**:
```python
{
  "validation_passed": True/False,
  "validation_attempts": 2,
  "validation_failure_category": "context_mismatch",
  "validation_results": {
    "hunk_application": {"success": True, "raw": "..."},
    "build": {"success": True, "raw": "..."},
    "tests": {
      "success": True,
      "state_transition": {
        "fail_to_pass": ["org.example.FooTests#testBar"],
        "newly_passing": [],
        "pass_to_fail": [],
        "valid_backport_signal": True
      }
    }
  },
  "validation_error_context_structured": {
    "primary_failed_file": "src/Foo.java",
    "symbol_errors": ["alloc_buf not found"],
    "signature_errors": ["expected (String) found (String, int)"]
  }
}
```

---

### Retry — Reasoning Architect

**File**: `agents-backend/src/agents/reasoning_architect.py`

**Goal**: Diagnose exactly *what* went wrong in validation and produce **verified surgical operations** for the Planning Agent to use on the next attempt.

#### Diagnosis Process

```
1. diagnose_api_drift() → extract API changes between mainline and target
2. Read target file code around failure locations (via read_target_code_window)
3. grep_in_target_file() → find candidate code regions
4. compare_mainline_target() → identify root cause
5. Classify root cause: signature_drift | logic_moved | anchor_not_found
```

#### TypeV Rulebook

A deterministic classifier maps failure type → execution strategy:

| Failure Type | Strategy |
|-------------|----------|
| Compilation: symbol not found | TYPE_III — apply symbol rename from ConsistencyMap |
| Compilation: signature mismatch | TYPE_IV — adjust call sites + rename |
| Anchor not found in file | TYPE_V — structural rewrite of affected block |
| Method moved to different class | TYPE_II — relocate with Structural Locator |
| Logic completely refactored | TYPE_V heavy mode — full semantic rewrite |

When TYPE_V is triggered, `force_type_v_until_success=True` is set as a sticky latch — all subsequent retries stay in TYPE_V mode until validation passes.

**Outputs** → `surgical_plans: Dict[str, List[SurgicalOp]]`

```python
class SurgicalOp(TypedDict):
    target_file: str
    old_string: str          # exact text verified to exist
    new_string: str          # replacement text
    anchor_verified: bool    # confirmed via grep/AST
    verification_method: str # "exact" | "grep_confirmed" | "ast_boundary"
    confidence: float        # 0.0 – 1.0
```

---

## 5. Analysis Engine (Java MCP Tools)

**Location**: `analysis-engine/src/main/java/com/retrofit/analysis/tools/`
**Endpoint**: `http://localhost:8080/mcp/sse` (MCP over Server-Sent Events)

The analysis engine exposes Java-native tools that agents call via MCP. It uses **Spoon** (a Java source code analysis and transformation framework) for AST operations.

### Tool Reference

| Tool | Purpose | Key Parameters | Key Outputs |
|------|---------|---------------|-------------|
| `CompileTool` | Compile `.java` files via `javac` | `repoPath`, `filePaths[]` | `success`, `message`, `output_path` |
| `SpotBugsTool` | Static bug analysis on compiled classes | `compiledClassesPaths[]`, `sourcePath`, `auxClasspath[]` | `success`, `report`, `debug_log` |
| `GetClassContextTool` | Extract class structure and method bodies (Spoon AST) | `targetRepoPath`, `filePath`, `focusMethod?` | `context` (text), `start_line`, `end_line` |
| `GetDependencyTool` | Build method call + inheritance dependency graph | `targetRepoPath`, `filePaths[]`, `exploreNeighbors` | `nodes[]`, `edges[]` |
| `GetStructuralAnalysisTool` | Per-class structural analysis (fields, methods, calls) | `targetRepoPath`, `filePath` | `classes[]` |
| `GetJavaVersionTool` | Return runtime Java version | — | Version string e.g. `"17.0.1"` |
| `ReplaceMethodBodyTool` | AST-based code transformations (method/field/import) | See below | `success`, `message` |

### ReplaceMethodBodyTool Sub-Operations

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `execute` (replace method body) | `targetRepoPath`, `filePath`, `methodSignature`, `newBody` | Replace method body; supports wildcards e.g. `"parse(...)"` |
| `executeReplaceField` | `targetRepoPath`, `filePath`, `fieldName`, `newDeclaration` | Replace field declaration |
| `executeInsertImport` | `targetRepoPath`, `filePath`, `importStatement` | Add import if not present |
| `executeRemoveMethod` | `targetRepoPath`, `filePath`, `methodSignature` | Remove method from class |
| `executeGetMethodBoundaries` | `targetRepoPath`, `filePath`, `methodSignature` | Return `start_line`, `end_line` (1-indexed) |

**Why AST tools?**: Spoon operates on the AST, so operations like method body replacement are immune to line number drift — they find the target by name, not by position.

**Spoon Configuration**: `noClasspath=true` (ignores missing dependencies), compliance level 17 (Java 17 syntax), comments preserved, AST cache with up to 50 entries keyed by path + last-modified-time.

---

## 6. Key Data Structures

All types are defined in `agents-backend/src/state.py`.

### `FileChange` — Patch Parser Output

```python
class FileChange(TypedDict):
    file_path: str          # Repo-relative path (a/b/ prefixes stripped)
    change_type: str        # "MODIFIED" | "ADDED" | "DELETED" | "RENAMED"
    added_lines: list[str]  # Inserted lines (stripped)
    removed_lines: list[str]# Deleted lines (stripped)
    is_test_file: bool      # Heuristic: path contains "test"
    previous_file_path: str # Old path for RENAMED files
```

Produced by `PatchAnalyzer.analyze()` in `agents-backend/src/utils/patch_analyzer.py`.

### `SemanticBlueprint` — Agent 1 Output

```python
class SemanticBlueprint(TypedDict):
    root_cause_hypothesis: str   # The bug/vulnerability being fixed
    fix_logic: str               # The algorithm of the fix
    dependent_apis: list[str]    # Critical methods/constants the fix uses
    patch_intent_summary: str    # One sentence: what the patch accomplishes
    hunk_chain: list[HunkRole]   # Ordered causal chain of hunks
```

### `ConsistencyMap` — Agent 2 Output

```python
ConsistencyMap = dict[str, str]
# {"alloc_buf": "Legacy_alloc_buf", "MAX_BUF_SIZE": "LEGACY_MAX"}
# mainline symbol name → target repo symbol name
```

### `MappedTargetContext` — Agent 2 Output

```python
MappedTargetContext = dict[str, list[dict]]
# {
#   "src/Foo.java": [          # keyed by mainline file path
#     {
#       "hunk_index": 0,       # which hunk in this file
#       "mainline_method": "write",
#       "target_file": "src/legacy/Foo.java",
#       "target_method": "legacyWrite",
#       "start_line": 42,
#       "end_line": 88,
#       "code_snippet": "..."  # surrounding code from target
#     }
#   ]
# }
```

### `HunkGenerationPlan` — Planning Agent Output

```python
HunkGenerationPlan = dict[str, list[dict]]
# {
#   "src/Foo.java": [
#     {
#       "hunk_index": 0,
#       "target_file": "src/legacy/Foo.java",
#       "edit_type": "replace",          # replace|insert_before|insert_after|delete
#       "old_string": "exact text...",   # verified to exist in target file
#       "new_string": "replacement...",  # with ConsistencyMap substitutions applied
#       "verified": True,
#       "verification_result": "EXACT_MATCH at line 59",
#       "adaptation_type": "TYPE_III",
#       "namespace_changes": [{"from": "X", "to": "Y", "reason": "..."}],
#       "notes": "..."
#     }
#   ]
# }
```

### `AdaptedHunk` — Agent 3 Output

```python
class AdaptedHunk(TypedDict):
    target_file: str               # Relative path in target repo
    mainline_file: str             # Original mainline file (lineage tracking)
    hunk_text: str                 # Unified diff from git diff HEAD
    insertion_line: int            # Anchor line in target file
    intent_verified: bool          # LLM confirmed fix intent is implemented
    file_operation: Optional[str]  # "ADDED"|"DELETED"|"MODIFIED"|"RENAMED"
    file_operation_required: bool  # False if operation already applied/not needed
    path_resolution_reason: str    # Trace of how target_file was resolved
```

---

## 7. Evaluation Harness

### Dataset

**File**: `datasets/all_projects_final.csv`
- **490 entries** of real-world Java backport pairs
- Each row: `Project`, `Original Commit` (mainline), `Backport Commit` (target), `Type` (TYPE-I through TYPE-V)
- **Projects covered**: Elasticsearch, Crate, Druid, OpenCode, JDK11u-dev, JDK17u-dev

Test repositories are cached in `temp_repo_storage/` (Elasticsearch: 4.4GB, Druid: 1.4GB, Crate: 800MB, OpenCode: 315MB).

### Running Evaluation

**Main script**: `agents-backend/evaluate/full_run/evaluate_full_workflow.py`

```bash
# Full pipeline (all projects, all patches)
python3 evaluate/full_run/evaluate_full_workflow.py --mode full

# Single project
python3 evaluate/full_run/evaluate_full_workflow.py --mode full --project elasticsearch

# Single patch (force re-evaluation)
python3 evaluate/full_run/evaluate_full_workflow.py --force --patch-id elasticsearch_88cf2487

# Phase 1 only (fast, deterministic, no LLM)
python3 evaluate/full_run/evaluate_full_workflow.py --mode phase1

# Phase 2 only (structural locator)
python3 evaluate/full_run/evaluate_full_workflow.py --mode phase2 --phase2-reset

# Skip git cleanup between runs (faster for repeated runs)
python3 evaluate/full_run/evaluate_full_workflow.py --no-clean
```

**Configuration** (in evaluate_full_workflow.py):
```python
TARGET_PROJECTS = ["elasticsearch", "crate"]
MAX_PATCHES_PER_PROJECT = 10
DATASET_PATH = "datasets/all_projects_final.csv"
RESULTS_DIR = "evaluate/full_run/results"
PHASE0_CACHE_DIR = "evaluate/full_run/phase0_cache"
```

### Success Metrics

#### Primary: `exact_developer_patch`

**Definition**: When the generated patch is applied to the backport parent commit, does it produce **identical file states** as the developer's actual backport?

**Comparison method** (file-state, not textual diff):
1. Seed temporary git index at `backport_commit^` (parent of developer backport)
2. Apply generated patch to temporary index
3. For each Java code file in scope: compare git blob SHA
4. Line-by-line comparison with whitespace normalization
5. `exact_developer_patch = True` iff all blobs match

#### Secondary Metrics

| Metric | Description |
|--------|-------------|
| `validation_passed` | Did the pipeline produce code that compiles and passes tests? |
| `fail_to_pass` | Tests that transitioned failing → passing (valid backport signal) |
| `pass_to_fail` | Tests that regressed passing → failing (regressions) |
| `valid_backport_signal` | `(fail_to_pass OR newly_passing) AND NOT pass_to_fail` |
| `validation_attempts` | How many retry loops were needed |
| Token usage per node | Input/output tokens per agent |

### Result Files Layout

For each patch, results are stored in `evaluate/full_run/results/{project}/{patch_id}/`:

```
results/elasticsearch/elasticsearch_88cf2487/
├── pipeline_results.json                           # Master result + all phase outputs
├── phase1_context_analyzer_context_analyzer.json   # SemanticBlueprint
├── phase2_structural_locator_structural_locator.json # ConsistencyMap + MappedTargetContext
├── phase2_5_planning_agent_planning_agent.json     # HunkGenerationPlan
├── phase3_hunk_generator_hunk_generator.json       # AdaptedHunks + edit trajectory
├── phase4_validation_validation.json               # Validation results
├── tokens.txt                                      # Token usage per node (JSON)
├── log.txt                                         # Runtime execution log
├── transition_summary_log.md                       # Test state transitions
├── post_pipeline_developer_patch_compare_log.md    # Hunk-by-hunk comparison vs developer
├── full_trace_log.md                               # Agentic edit trajectory
├── mainline.patch                                  # Patch from mainline commit
├── target.patch                                    # Developer backport patch
├── generated_patch_agent_only.patch                # What agents generated (code only)
└── generated_patch_final_effective.patch           # Agent code + developer auxiliary hunks
```

**Aggregated summary**: `evaluate/full_run/results/pipeline_summary_full.json` — array of all patch results for the run.

### Two Patch Concepts

| Patch | Contents | Source |
|-------|---------|--------|
| Agent-only patch | Java code files only | H-MABS pipeline output |
| Final effective patch | Agent code + developer auxiliary | Agent code + test/non-Java files from developer backport |

The evaluation uses **agent-only patch** for `exact_developer_patch` comparison (fair comparison: agents are only responsible for code files).

---

## 8. Configuration & Setup

### Environment Variables (`.env`)

Copy `agents-backend/.env.example` to `agents-backend/.env`:

```bash
# LLM Provider
LLM_PROVIDER=openai         # openai | azure | groq | google | cerebras | bedrock
LLM_MODEL=gpt-4.1-mini      # model name for the selected provider
OPENAI_API_KEY=sk-...

# Azure OpenAI (if using azure)
AZURE_ENDPOINT=https://....openai.azure.com/
AZURE_CHAT_DEPLOYMENT=gpt-4o
AZURE_CHAT_VERSION=2024-02-15-preview
AZURE_OPENAI_API_KEY=...

# Google Gemini (if using google)
GOOGLE_API_KEY=...

# Groq (if using groq)
GROQ_API_KEY=...

# Cerebras (if using cerebras)
CEREBRAS_API_KEY=...

# Analysis engine
MCP_SERVER_URL=http://localhost:8080/mcp/sse
```

### Local Development

```bash
# 1. Start Analysis Engine (Java)
cd analysis-engine
mvn spring-boot:run

# 2. Install Python dependencies
cd agents-backend
pip install -r requirements.txt

# 3. Run pipeline
python src/main.py \
  --mainline-commit <hash> \
  --mainline-repo /path/to/mainline \
  --target-repo /path/to/target
```

### Docker Compose

```bash
docker-compose up --build   # Start analysis-engine + orchestrator
docker-compose down
```

Services:
- `analysis-engine`: port 8080, Java/Spoon MCP server
- `orchestrator`: Python agents-backend (depends on analysis-engine)
- Network: `backport-net` (bridge)

### Running Tests

```bash
cd agents-backend
pytest tests/                                    # All tests
pytest tests/test_hunk_generator.py -v           # Specific file
pytest -k "test_extract_hunk_block"              # Single test by name
```

Pytest config: `agents-backend/pyproject.toml` (`asyncio_mode = "auto"`).

---

## 9. Key File Reference

| Concept | File |
|---------|------|
| LangGraph graph definition + routing | `agents-backend/src/graph.py` |
| All shared state types | `agents-backend/src/state.py` |
| CLI entry point | `agents-backend/src/main.py` |
| Complexity classifier (TRIVIAL/STRUCTURAL/REWRITE) | `agents-backend/src/utils/patch_complexity.py` |
| Patch parser (FileChange, raw hunks) | `agents-backend/src/utils/patch_analyzer.py` |
| Phase 0 — Optimistic fast-path | `agents-backend/src/agents/phase0_optimistic.py` |
| Phase 1 — Context Analyzer | `agents-backend/src/agents/context_analyzer.py` |
| Phase 2 — Structural Locator | `agents-backend/src/agents/structural_locator.py` |
| Phase 2.5 — Planning Agent | `agents-backend/src/agents/planning_agent.py` |
| Phase 3 — File Editor (CLAW str_replace) | `agents-backend/src/agents/file_editor.py` |
| Phase 4 — Validation Agent | `agents-backend/src/agents/validation_agent.py` |
| Retry — Reasoning Architect | `agents-backend/src/agents/reasoning_architect.py` |
| LLM abstraction (multi-provider) | `agents-backend/src/utils/llm_provider.py` |
| Method fingerprinting (4-tier match) | `agents-backend/src/utils/method_fingerprinter.py` |
| Structural class matching | `agents-backend/src/utils/structural_matcher.py` |
| API drift detection | `agents-backend/src/utils/api_drift_detector.py` |
| Vector retrieval (symbol + TF-IDF) | `agents-backend/src/utils/retrieval/ensemble_retriever.py` |
| Anchor failure diagnosis | `agents-backend/src/utils/semantic_adaptation_helper.py` |
| Build/test/compile toolkit | `agents-backend/src/utils/validation_tools.py` |
| Full evaluation harness | `agents-backend/evaluate/full_run/evaluate_full_workflow.py` |
| Test result parser | `agents-backend/evaluate/helpers/collect_test_results.py` |
| Java MCP tools | `analysis-engine/src/main/java/com/retrofit/analysis/tools/` |
| MCP server endpoint | `analysis-engine/src/main/java/com/retrofit/analysis/mcp/McpServer.java` |
| Dataset (490 labeled backports) | `datasets/all_projects_final.csv` |
