"""
H-MABS Orchestrator Graph

Pipeline:
  START
    -> phase_0_optimistic       (Fast-path direct git apply attempt)
       |-- fast_path_success=True  -> END
       '-- fast_path_success=False
              -> context_analyzer   (semantic blueprint; deterministic for TRIVIAL/STRUCTURAL)
              -> structural_locator (find target locations, no planning)
              -> hunk_generator     (file_editor)
                 |-- TRIVIAL patch: dumb mode (deterministic apply only)
                 |-- STRUCTURAL/REWRITE patch: fails fast, no plan available
              -> validation
                 |-- passed          -> END
                 |-- failed, attempts < MAX_VALIDATION_ATTEMPTS -> recovery_agent
                 '-- failed, attempts >= MAX_VALIDATION_ATTEMPTS -> END

Flow breakdown:
1. Context Analyzer: extract blueprint (deterministic for TRIVIAL/STRUCTURAL)
2. Structural Locator: find target locations (no planning)
3. File Editor (dumb mode for TRIVIAL only):
   - TRIVIAL patches: try deterministic apply of mainline edits verbatim
   - STRUCTURAL/REWRITE patches: fail fast (require planning, will trigger recovery_agent)
4. Validation: test the result
5. Recovery Agent (if validation fails):
   - Full ReAct pass with semantic analysis + planning
   - Creates structured plan from scratch
   - File Editor applies recovery plan deterministically (max 2 retries)

Key insight: Dumb mode only works for simple patches (TRIVIAL). Complex patches
(STRUCTURAL/REWRITE) trigger recovery_agent immediately, which does full planning.
"""

from langgraph.graph import END, START, StateGraph

from agents import (
    context_analyzer_node,
    file_editor_node,
    phase_0_optimistic,
    recovery_agent_node,
    structural_locator_node,
    validation_agent,
)
from state import AgentState

# Maximum number of "Prove Red, Make Green" retry loops before giving up.
# With dumb run + recovery cycle, max 2 recovery attempts before admitting defeat.
MAX_VALIDATION_ATTEMPTS = 2


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------


def route_start(state: AgentState) -> str:
    """
    Route from START: check if phase 0 should be skipped.
    If skip_phase_0=True, go directly to context_analyzer (dumb apply path).
    Otherwise, run phase_0_optimistic.
    """
    if state.get("skip_phase_0", False):
        print("Router: Skipping Phase 0 - entering context_analyzer for semantic blueprint.")
        return "context_analyzer"
    print("Router: Running Phase 0.")
    return "phase_0_optimistic"


def route_phase_0(state: AgentState) -> str:
    """
    After Phase 0: if the fast-path succeeded, go straight to END.
    Otherwise, enter the dumb apply pipeline via context_analyzer.
    """
    if state.get("fast_path_success", False):
        print("Router: Phase 0 succeeded - taking fast-path exit.")
        return "END"
    print("Router: Phase 0 failed - entering dumb apply pipeline (context_analyzer -> structural_locator -> file_editor dumb mode).")
    return "context_analyzer"


def route_after_structural(state: AgentState) -> str:
    """
    Route after structural locator.

    Always go directly to Agent 3 (file editor) for an initial
    deterministic "dumb apply" pass. Planning/reasoning are reserved for
    post-validation retries with concrete failure diagnostics.
    """
    print("Router: structural mapping complete -> hunk_generator (initial pass).")
    return "hunk_generator"


def route_validation(state: AgentState) -> str:
    """
    After Agent 4 (validation):
      - If validation passed -> END.
      - If failed but attempts remain -> recovery_agent (failure-aware retry).
      - If failed and exhausted retries -> END (give up, output failure).
    """
    passed = state.get("validation_passed", False)
    attempts = state.get("validation_attempts", 0)

    if passed:
        print(f"Router: Validation PASSED after {attempts} attempt(s). Done.")
        return "END"

    failure_category = (state.get("validation_failure_category") or "").strip().lower()
    infra_inconclusive = bool(
        state.get("validation_infrastructure_inconclusive", False)
    )
    infra_failure = bool(state.get("validation_infrastructure_failure", False))

    if infra_inconclusive or failure_category in {
        "test_runner_config",
        "test_infrastructure",
        "inconclusive_tests_observed_none",
    }:
        print(
            "Router: Validation failed due to test infrastructure/runner issue. "
            "Stopping retries as infrastructure-inconclusive."
        )
        return "END"

    if infra_failure:
        print(
            "Router: Validation reported infrastructure failure. "
            "Not retrying generation."
        )
        return "END"

    if failure_category == "target_file_missing":
        if attempts < MAX_VALIDATION_ATTEMPTS:
            print(
                f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}) — "
                "target file missing. Re-routing to structural_locator for fresh file search."
            )
            return "structural_locator"
        print("Router: Target file missing but max retries reached. Exiting.")
        return "END"

    if attempts < MAX_VALIDATION_ATTEMPTS:
        print(
            f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}). "
            "Routing to recovery_agent for autonomous replanning."
        )
        return "recovery_agent"

    print(
        f"Router: Validation FAILED after {MAX_VALIDATION_ATTEMPTS} attempt(s). "
        "Max retries reached. Exiting."
    )
    return "END"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)

# --- Register nodes ---
workflow.add_node("phase_0_optimistic", phase_0_optimistic)
workflow.add_node("context_analyzer", context_analyzer_node)
workflow.add_node("structural_locator", structural_locator_node)
workflow.add_node("hunk_generator", file_editor_node)
workflow.add_node("validation", validation_agent)
workflow.add_node("recovery_agent", recovery_agent_node)

# --- Wire edges ---

# Entry point with conditional routing
workflow.add_conditional_edges(
    START,
    route_start,
    {
        "phase_0_optimistic": "phase_0_optimistic",
        "context_analyzer": "context_analyzer",
    },
)

# Phase 0 conditional branch: fast-path exit OR dumb apply pipeline
workflow.add_conditional_edges(
    "phase_0_optimistic",
    route_phase_0,
    {
        "END": END,
        "context_analyzer": "context_analyzer",
    },
)

# Linear pipeline: Agent 1 -> Agent 2 -> Agent 3
workflow.add_edge("context_analyzer", "structural_locator")
workflow.add_edge("structural_locator", "hunk_generator")
workflow.add_edge("hunk_generator", "validation")
workflow.add_edge("recovery_agent", "hunk_generator")

# Validation feedback loop: pass -> END, fail -> retry Agent 3 or give up
workflow.add_conditional_edges(
    "validation",
    route_validation,
    {
        "END": END,
        "structural_locator": "structural_locator",
        "recovery_agent": "recovery_agent",
        "hunk_generator": "hunk_generator",
    },
)

# --- Compile ---
app = workflow.compile()
