"""
H-MABS Orchestrator Graph (Phase 1)

4-Agent Pipeline:
  START
    -> phase_0_optimistic       (Fast-path direct git apply attempt)
       |-- fast_path_success=True  -> END   (skips all LLM agents)
       '-- fast_path_success=False
              -> context_analyzer   (Agent 1: Semantic Blueprint)
              -> structural_locator (Agent 2: Consistency Map + Mapped Context)
              -> hunk_generator     (Agent 3: initial deterministic apply)
              -> validation         (Agent 4: "Prove Red, Make Green" loop)
                 |-- passed          -> END
                 |-- failed, attempts < MAX_VALIDATION_ATTEMPTS -> planning_agent
                        -> reasoning_architect -> hunk_generator (failure-aware retry)
                 '-- failed, attempts >= MAX_VALIDATION_ATTEMPTS -> END (give up)

Note: The graph node "hunk_generator" is now backed by file_editor_node.
The node name is kept identical so all routing logic and result-file naming
(phase3_hunk_generator) remains unchanged.
"""

from langgraph.graph import END, START, StateGraph

from agents import (
    context_analyzer_node,
    file_editor_node,
    phase_0_optimistic,
    planning_agent_node,
    reasoning_architect_node,
    structural_locator_node,
    validation_agent,
)
from state import AgentState

# Maximum number of "Prove Red, Make Green" retry loops before giving up.
MAX_VALIDATION_ATTEMPTS = 3


def _validation_build_failed_in_state(state: AgentState) -> bool:
    """True when the last validation run recorded a failed compile/build step."""
    vr = state.get("validation_results") or {}
    if not isinstance(vr, dict):
        return False
    b = vr.get("build") or {}
    if isinstance(b, dict) and b.get("success") is False:
        return True
    return False


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------


def route_start(state: AgentState) -> str:
    """
    Route from START: check if phase 0 should be skipped.
    If skip_phase_0=True, go directly to context_analyzer.
    Otherwise, run phase_0_optimistic.
    """
    if state.get("skip_phase_0", False):
        print("Router: Skipping Phase 0 - entering full 4-agent pipeline directly.")
        return "context_analyzer"
    print("Router: Running Phase 0.")
    return "phase_0_optimistic"


def route_phase_0(state: AgentState) -> str:
    """
    After Phase 0: if the fast-path succeeded, go straight to END.
    Otherwise, enter the full 4-agent pipeline via context_analyzer.
    """
    if state.get("fast_path_success", False):
        print("Router: Phase 0 succeeded - taking fast-path exit.")
        return "END"
    print("Router: Phase 0 failed - entering full 4-agent pipeline.")
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
      - If failed but attempts remain -> planning_agent (failure-aware retry).
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
        # Simple failure loop: after we get concrete validation feedback, always
        # re-enter planner + reasoning before another edit pass.
        print(
            f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}). "
            "Routing to planning_agent for failure-aware repair."
        )
        return "planning_agent"

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
workflow.add_node("planning_agent", planning_agent_node)
workflow.add_node("reasoning_architect", reasoning_architect_node)
workflow.add_node("hunk_generator", file_editor_node)
workflow.add_node("validation", validation_agent)

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

# Phase 0 conditional branch: fast-path exit OR full pipeline
workflow.add_conditional_edges(
    "phase_0_optimistic",
    route_phase_0,
    {
        "END": END,
        "context_analyzer": "context_analyzer",
    },
)

# Linear pipeline: Agent 1 -> Agent 2 -> Planner -> Agent 3
workflow.add_edge("context_analyzer", "structural_locator")
workflow.add_conditional_edges(
    "structural_locator",
    route_after_structural,
    {
        "planning_agent": "planning_agent",
        "hunk_generator": "hunk_generator",
    },
)
workflow.add_edge("planning_agent", "reasoning_architect")
workflow.add_edge("reasoning_architect", "hunk_generator")
workflow.add_edge("hunk_generator", "validation")

# Validation feedback loop: pass -> END, fail -> retry Agent 3 or give up
workflow.add_conditional_edges(
    "validation",
    route_validation,
    {
        "END": END,
        "structural_locator": "structural_locator",
        "planning_agent": "planning_agent",
        "reasoning_architect": "reasoning_architect",
        "hunk_generator": "hunk_generator",
    },
)

# --- Compile ---
app = workflow.compile()
