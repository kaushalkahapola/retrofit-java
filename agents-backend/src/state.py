from typing import TypedDict, Annotated, Optional, NotRequired, Dict, Any
import operator
from langchain_core.messages import BaseMessage


# ---------------------------------------------------------------------------
# Intermediate Artifact Schemas
# ---------------------------------------------------------------------------


class HunkRole(TypedDict):
    """
    Per-hunk annotation produced by Agent 1.
    Explains each hunk's role and how it connects to adjacent hunks in the fix chain.
    """

    hunk_index: int  # 1-based index within the file
    file: str  # file path this hunk belongs to
    summary: str  # what this hunk changes in plain English
    role: str  # "core_fix" | "guard" | "propagation" | "declaration" | "cleanup" | "refactor"
    connects_to_next: (
        str  # how this hunk makes the next hunk necessary/possible (empty for last)
    )


class SemanticBlueprint(TypedDict):
    """
    Agent 1 (Context Analyzer) output.
    Describes WHY and HOW the mainline patch works, including an ordered
    causal chain showing how each hunk connects back to the patch intent.
    """

    root_cause_hypothesis: str  # e.g., "Missing bounds check on buffer_size"
    fix_logic: str  # e.g., "Add if(buffer_size > MAX) return; before memcpy"
    dependent_apis: list  # e.g., ["alloc_buf", "MAX_BUF_SIZE"]
    patch_intent_summary: str  # One-sentence overall goal of the entire patch
    hunk_chain: list  # Ordered list of HunkRole dicts - causal chain across all hunks


# Type aliases for semantic clarity
ConsistencyMap = dict[str, str]
"""
Agent 2 (Structural Locator) output.
Maps mainline symbols to their equivalent names in the target repo.
e.g., {"alloc_buf": "Legacy_alloc_buf", "MAX_SIZE": "LEGACY_MAX"}
"""

MappedTargetContext = dict[str, list[dict]]
"""
Agent 2 (Structural Locator) output.
Maps each source file to a list of hunk mappings (to support multiple hunks per file).
Each mapping stores the exact target file context (file path, insertion line numbers, surrounding code).
e.g., {
    "src/Foo.java": [
        {
            "hunk_index": 0,
            "mainline_method": "fooOld",
            "target_file": "src/Foo.java",
            "target_method": "legacyFoo",
            "start_line": 42,
            "end_line": 88,
            "code_snippet": "..."
        }
    ]
}
"""

HunkGenerationPlan = dict[str, list[dict[str, Any]]]
"""
Planning Agent output.
Per-mainline-file ordered hunk planning entries that include verified str_replace
edit instructions (old_string -> new_string) for Agent 3 (File Editor).
Each entry schema:
  {
    "hunk_index": int,
    "target_file": str,
    "edit_type": "replace" | "insert_before" | "insert_after" | "delete",
    "old_string": str,      # exact text verified to exist in target file
    "new_string": str,      # replacement text
    "verified": bool,       # True if old_string was confirmed in real file
    "verification_result": str,
    "notes": str
  }
"""


class SurgicalOp(TypedDict):
    """
    Verified deterministic operation produced by Reasoning Architect.
    """

    target_file: str
    old_string: str
    new_string: str
    anchor_verified: bool
    verification_method: str  # "exact" | "grep_confirmed" | "ast_boundary"
    confidence: float


class ReasoningContext(TypedDict):
    """
    Per-file reasoning context captured for surgical retry planning.
    """

    current_file: str
    failure_kind: str  # "signature_drift" | "logic_moved" | "anchor_not_found"
    build_diagnostics: dict[str, Any]
    side_files: NotRequired[list[str]]
    iteration: int
    surgical_ops: list[SurgicalOp]


class FileEdit(TypedDict):
    """
    One atomic str_replace edit applied directly to a checked-out target file.
    Produced by Agent 3 (File Editor) before git diff is run.
    """

    target_file: str  # repo-relative path edited
    mainline_file: str  # original mainline file (lineage tracking)
    old_string: str  # exact text replaced (empty string = pure insertion)
    new_string: str  # replacement / inserted text
    edit_type: str  # "replace" | "insert_before" | "insert_after" | "delete"
    verified: bool  # True if planner confirmed old_string exists in file
    verification_result: str  # e.g. "EXACT_MATCH at line 59"
    applied: bool  # True if str_replace succeeded at runtime
    apply_result: str  # success / error message from the apply step


class AdaptedHunk(TypedDict):
    """
    Agent 3 (File Editor) output per modified file.
    hunk_text is now produced by `git diff HEAD -- <file>` after direct file edits,
    not by an LLM writing unified diff syntax. This guarantees syntactic correctness.
    """

    target_file: str  # Relative path in target repo
    mainline_file: str  # Original mainline file path (for lineage tracking)
    hunk_text: str  # Unified Diff hunk string (@@-header + +/- lines)
    insertion_line: int  # Line number in target file where the hunk should anchor
    intent_verified: bool  # True if the blueprint validation LLM call passed
    file_operation: Optional[str]  # "ADDED" | "DELETED" | "MODIFIED" | "RENAMED"
    old_target_file: NotRequired[
        Optional[str]
    ]  # Resolved old path for rename operations
    file_operation_required: NotRequired[
        bool
    ]  # False when operation is already applied/not needed
    path_resolution_reason: NotRequired[str]  # Trace hint for path decision
    dry_run_error: NotRequired[
        Optional[Dict[str, Any]]
    ]  # CLAW-inspired: structured error info from Phase 3 dry-run validation
    dry_run_error_message: NotRequired[
        Optional[str]
    ]  # Human-readable error from Phase 3 validation


# ---------------------------------------------------------------------------
# Core Agent State
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    """
    Shared state passed between all H-MABS agents in the LangGraph pipeline.
    """

    # --- Core I/O fields (inputs from main.py) ---
    messages: Annotated[list[BaseMessage], operator.add]
    patch_path: str  # Absolute path to the mainline patch file
    patch_diff: str  # Raw unified diff text (loaded by phase_0 or context_analyzer)
    commit_message: str  # Commit message from the mainline backport commit
    target_repo_path: str  # Absolute path to the target (older) repository
    mainline_repo_path: str  # Absolute path to the mainline (newer) repository
    experiment_mode: bool  # If True, checkout parent commit before indexing
    backport_commit: str  # Commit hash of the backport in the target repo
    original_commit: str  # Commit hash in the mainline repo

    # --- Phase 0: Control flags ---
    skip_phase_0: bool  # If True, skip phase 0 and go directly to context analyzer
    compile_only: bool  # If True, validation only applies patch and compiles (no tests)
    with_test_changes: (
        bool  # If False (default), ignore test file changes/hunks in all phases
    )
    apply_only_validation: bool  # If True, validation only checks hunk application
    skip_compilation_checks: (
        bool  # If True, compile-only mode skips compilation/static checks
    )
    evaluation_full_workflow: (
        bool  # If True, run full eval flow in validation (apply+build+tests)
    )
    developer_patch_diff: NotRequired[
        str
    ]  # Full developer backport diff (eval harness); enables developer fast path in Agent 3

    # --- Phase 0: Pre-computed analysis ---
    patch_analysis: list  # List[FileChange] - from PatchAnalyzer
    patch_complexity: NotRequired[str]  # TRIVIAL | STRUCTURAL | REWRITE
    complexity_reason: NotRequired[str]  # Deterministic classifier reason
    complexity_details: NotRequired[dict[str, Any]]  # Classifier diagnostics

    # --- Phase 0 fast-path result ---
    fast_path_success: bool  # True if git apply --check & tests passed cleanly
    phase_0_test_targets: dict  # Relevant targets selected for baseline/post test runs
    phase_0_baseline_test_result: (
        dict  # Test result on parent commit with developer test-only changes
    )
    phase_0_post_patch_test_result: dict  # Test result after applying candidate patch
    phase_0_transition_evaluation: dict  # Baseline->post transition decision details
    use_phase_0_cache: bool  # If True, Phase 0 may reuse cached evaluation outputs

    # --- Agent 1 (Context Analyzer) outputs ---
    semantic_blueprint: Optional[
        SemanticBlueprint
    ]  # Blueprint of why/how the patch works

    # --- Agent 2 (Structural Locator) outputs ---
    consistency_map: Optional[
        ConsistencyMap
    ]  # Mainline symbol -> Target symbol mapping
    mapped_target_context: Optional[
        MappedTargetContext
    ]  # Exact target insertion context
    hunk_generation_plan: Optional[
        HunkGenerationPlan
    ]  # Planner output: verified per-hunk anchors/context for generation
    generation_checklist: NotRequired[
        list[dict[str, Any]]
    ]  # Per-hunk generation status (success/failed/noop) for fail-closed orchestration
    reasoning_context: NotRequired[ReasoningContext]
    surgical_plans: NotRequired[
        dict[str, list[SurgicalOp]]
    ]  # per-target-file surgical operations from Reasoning Architect
    reasoning_iterations: NotRequired[int]

    # --- Legacy / Agent 2 compatibility ---
    implementation_plan: (
        dict  # ImplementationPlan dict (kept for backward compat with validation)
    )
    retrieval_results: (
        dict  # Map: source_file -> list of candidates (from EnsembleRetriever)
    )

    # --- Agent 3 (File Editor) outputs ---
    adapted_file_edits: list[
        FileEdit
    ]  # Atomic str_replace records applied to target files
    all_adapted_file_edits: NotRequired[
        list[list[FileEdit]]
    ]  # History of file edits across all validation retries
    agent_trajectory_edits: NotRequired[
        list[list[dict[str, Any]]]
    ]  # Raw tool calls (replace_line) made by the ReAct agent across retries
    adapted_code_hunks: list[
        AdaptedHunk
    ]  # Generated/adapted fix patch hunks (hunk_text = git diff output)
    adapted_test_hunks: list[AdaptedHunk]  # Generated/adapted test patch hunks
    developer_auxiliary_hunks: list[
        AdaptedHunk
    ]  # Developer backport test/non-Java hunks merged in phase 4

    # --- Agent 4 (Validation) feedback ---
    validation_attempts: int  # Counter for "Prove Red, Make Green" retry loop
    validation_passed: bool  # Final validation outcome (True = success)
    validation_error_context: (
        str  # Error logs from failed validation (fed back to Agent 3)
    )
    validation_results: dict[
        str, dict
    ]  # Detailed results per step (e.g. "hunk_application": {...})
    validation_error_context_structured: NotRequired[dict[str, Any]]
    # Structured failure context from validation agent.
    # Contains: failed_locations, symbol_errors, signature_errors,
    # primary_failed_file, primary_failed_symbol.
    # Fed to TypeVRulebook for deterministic pre-analysis.

    validation_infrastructure_failure: NotRequired[
        bool
    ]  # True when failure is test infra/runner related (not code generation)
    validation_infrastructure_inconclusive: NotRequired[
        bool
    ]  # True when result is infra-inconclusive and should stop retries
    validation_failure_category: NotRequired[
        str
    ]  # "path_or_file_operation" | "context_mismatch" | ...
    validation_retry_files: NotRequired[
        list[str]
    ]  # Retry scope: files implicated in last validation failure
    validation_retry_hunks: NotRequired[
        list[int]
    ]  # Retry scope: hunk indices implicated in last validation failure
    validation_failed_stage: NotRequired[
        str
    ]  # Stage where generation/validation failed (e.g. hunk_sanity_failed)
    force_type_v_until_success: NotRequired[
        bool
    ]  # Sticky latch: keep execution_type TYPE_V across retries until validation passes
    force_type_v_reason: NotRequired[
        str
    ]  # Human-readable reason for sticky TYPE_V latch
    force_type_v_retry_files: NotRequired[
        list[str]
    ]  # Optional scope for TYPE_V latch (restricts heavy mode to implicated files)
    generated_patch_hash: NotRequired[
        str
    ]  # Last generated code-patch hash (used to avoid identical retry loops)
    last_plan_signature: NotRequired[
        str
    ]  # Hash of last planner output to detect identical planning loops
    validation_repeated_patch_detected: NotRequired[
        bool
    ]  # True when file editor regenerated same patch hash on retry
    validation_repeated_plan_detected: NotRequired[
        bool
    ]  # True when planner generated same plan signature on retry
    best_effort_adapted_code_hunks: NotRequired[
        list
    ]  # Best generated code hunks preserved even when contract gates fail
    pair_consistency: NotRequired[
        dict[str, Any]
    ]  # Mainline/backport commit-pair overlap metrics (diagnostics)
    failed_locator_paths: NotRequired[
        list[str]
    ]  # Repository-relative paths already investigated and ruled out
    token_usage: NotRequired[
        dict[str, Any]
    ]  # Node-local token usage payload (used by evaluator aggregation)
    agent_token_usage: NotRequired[
        dict[str, dict[str, Any]]
    ]  # Per-node token accounting (exact or estimated)

    # --- Apply mode flag for dumb vs plan-based recovery ---
    apply_mode: NotRequired[
        str
    ]  # "dumb" (initial attempt, no planning) | "plan" (recovery path, use plan)

    # --- Recovery agent path ---
    recovery_agent_summary: NotRequired[
        str
    ]  # Short summary of latest recovery planning outcome
    recovery_brief: NotRequired[
        dict[str, Any]
    ]  # Deterministic recovery pre-analysis (diagnosis/rulebook/drift)
    recovery_obligations: NotRequired[
        list[dict[str, Any]]
    ]  # Required connected-impact obligations for recovery
    recovery_investigation: NotRequired[
        list[dict[str, Any]]
    ]  # Evidence gathered by recovery agent
    recovery_decisions: NotRequired[
        list[dict[str, Any]]
    ]  # Per-obligation decisions: edited | verified_no_change | blocked
    recovery_scope_files: NotRequired[
        list[str]
    ]  # Files in required recovery scope for this retry
    recovery_strategy_history: NotRequired[
        list[str]
    ]  # Anti-stagnation strategy sequence attempted during recovery
    recovery_plan_version: NotRequired[int]  # Monotonic recovery plan contract version
    recovery_risk_notes: NotRequired[
        list[str]
    ]  # Risk notes emitted by recovery self-review
    recovery_agent_status: NotRequired[
        str
    ]  # Optional terminal status from recovery agent (e.g. no_fix_found)
    recovery_applied_directly: NotRequired[
        bool
    ]  # True when recovery agent mutated files via apply_edit; router skips hunk_generator
    recovery_agent_mode: NotRequired[
        bool
    ]  # True while in recovery agent execution context
    recovery_plan_text: NotRequired[
        str
    ]  # Natural-language adaptation plan produced by redesigned recovery agent
