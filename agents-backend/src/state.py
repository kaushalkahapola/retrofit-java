from typing import TypedDict, Annotated, Optional
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
    hunk_index: int       # 1-based index within the file
    file: str             # file path this hunk belongs to
    summary: str          # what this hunk changes in plain English
    role: str             # "core_fix" | "guard" | "propagation" | "declaration" | "cleanup" | "refactor"
    connects_to_next: str # how this hunk makes the next hunk necessary/possible (empty for last)


class SemanticBlueprint(TypedDict):
    """
    Agent 1 (Context Analyzer) output.
    Describes WHY and HOW the mainline patch works, including an ordered
    causal chain showing how each hunk connects back to the patch intent.
    """
    root_cause_hypothesis: str       # e.g., "Missing bounds check on buffer_size"
    fix_logic: str                   # e.g., "Add if(buffer_size > MAX) return; before memcpy"
    dependent_apis: list             # e.g., ["alloc_buf", "MAX_BUF_SIZE"]
    patch_intent_summary: str        # One-sentence overall goal of the entire patch
    hunk_chain: list                 # Ordered list of HunkRole dicts — causal chain across all hunks


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



class AdaptedHunk(TypedDict):
    """
    Agent 3 (Hunk Generator) output per hunk.
    Represents a single rewritten patch hunk ready for application.
    """
    target_file: str        # Relative path in target repo
    mainline_file: str      # Original mainline file path (for lineage tracking)
    hunk_text: str          # Unified Diff hunk string (@@-header + +/- lines)
    insertion_line: int     # Line number in target file where the hunk should anchor
    intent_verified: bool   # True if the blueprint validation LLM call passed


# ---------------------------------------------------------------------------
# Core Agent State
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    """
    Shared state passed between all H-MABS agents in the LangGraph pipeline.
    """
    # --- Core I/O fields (inputs from main.py) ---
    messages: Annotated[list[BaseMessage], operator.add]
    patch_path: str                  # Absolute path to the mainline patch file
    patch_diff: str                  # Raw unified diff text (loaded by phase_0 or context_analyzer)
    commit_message: str              # Commit message from the mainline backport commit
    target_repo_path: str            # Absolute path to the target (older) repository
    mainline_repo_path: str          # Absolute path to the mainline (newer) repository
    experiment_mode: bool            # If True, checkout parent commit before indexing
    backport_commit: str             # Commit hash of the backport in the target repo
    original_commit: str             # Commit hash in the mainline repo

    # --- Phase 0: Control flags ---
    skip_phase_0: bool               # If True, skip phase 0 and go directly to context analyzer
    compile_only: bool               # If True, validation only applies patch and compiles (no tests)
    with_test_changes: bool          # If False (default), ignore test file changes/hunks in all phases

    # --- Phase 0: Pre-computed analysis ---
    patch_analysis: list             # List[FileChange] — from PatchAnalyzer

    # --- Phase 0 fast-path result ---
    fast_path_success: bool          # True if git apply --check & tests passed cleanly

    # --- Agent 1 (Context Analyzer) outputs ---
    semantic_blueprint: Optional[SemanticBlueprint]  # Blueprint of why/how the patch works

    # --- Agent 2 (Structural Locator) outputs ---
    consistency_map: Optional[ConsistencyMap]        # Mainline symbol -> Target symbol mapping
    mapped_target_context: Optional[MappedTargetContext]  # Exact target insertion context

    # --- Legacy / Agent 2 compatibility ---
    implementation_plan: dict        # ImplementationPlan dict (kept for backward compat with validation)
    retrieval_results: dict          # Map: source_file -> list of candidates (from EnsembleRetriever)

    # --- Agent 3 (Hunk Generator) outputs ---
    adapted_code_hunks: list[AdaptedHunk]  # Generated/adapted fix patch hunks
    adapted_test_hunks: list[AdaptedHunk]  # Generated/adapted test patch hunks

    # --- Agent 4 (Validation) feedback ---
    validation_attempts: int         # Counter for "Prove Red, Make Green" retry loop
    validation_passed: bool          # Final validation outcome (True = success)
    validation_error_context: str    # Error logs from failed validation (fed back to Agent 3)
    validation_results: dict[str, dict] # Detailed results per step (e.g. "hunk_application": {...})
