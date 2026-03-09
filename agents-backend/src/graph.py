"""
H-MABS Orchestrator Graph (Phase 1)

4-Agent Pipeline:
  START
    -> phase_0_optimistic       (Fast-path direct git apply attempt)
       |-- fast_path_success=True  -> END   (skips all LLM agents)
       '-- fast_path_success=False
              -> context_analyzer   (Agent 1: Semantic Blueprint)
              -> structural_locator (Agent 2: Consistency Map + Mapped Context)
              -> hunk_generator     (Agent 3: Adapted Code/Test Hunks)
              -> validation         (Agent 4: "Prove Red, Make Green" loop)
                 |-- passed          -> END
                 |-- failed, attempts < MAX_VALIDATION_ATTEMPTS -> hunk_generator (retry)
                 '-- failed, attempts >= MAX_VALIDATION_ATTEMPTS -> END (give up)
"""

from langgraph.graph import StateGraph, START, END
from state import AgentState
from agents import (
    phase_0_optimistic,
    context_analyzer_node,
    structural_locator_node,
    hunk_generator_node,
    validation_agent,
)

# Maximum number of "Prove Red, Make Green" retry loops before giving up.
MAX_VALIDATION_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------

def route_phase_0(state: AgentState) -> str:
    """
    After Phase 0: if the fast-path succeeded, go straight to END.
    Otherwise, enter the full 4-agent pipeline via context_analyzer.
    """
    if state.get("fast_path_success", False):
        print("Router: Phase 0 succeeded — taking fast-path exit.")
        return "END"
    print("Router: Phase 0 failed — entering full 4-agent pipeline.")
    return "context_analyzer"


def route_validation(state: AgentState) -> str:
    """
    After Agent 4 (validation):
      - If validation passed -> END.
      - If failed but attempts remain -> hunk_generator (retry loop).
      - If failed and exhausted retries -> END (give up, output failure).
    """
    passed = state.get("validation_passed", False)
    attempts = state.get("validation_attempts", 0)

    if passed:
        print(f"Router: Validation PASSED after {attempts} attempt(s). Done.")
        return "END"

    if attempts < MAX_VALIDATION_ATTEMPTS:
        print(
            f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}). "
            "Routing back to hunk_generator for retry."
        )
        return "hunk_generator"

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
workflow.add_node("phase_0_optimistic",  phase_0_optimistic)
workflow.add_node("context_analyzer",    context_analyzer_node)
workflow.add_node("structural_locator",  structural_locator_node)
workflow.add_node("hunk_generator",      hunk_generator_node)
workflow.add_node("validation",          validation_agent)

# --- Wire edges ---

# Entry point
workflow.add_edge(START, "phase_0_optimistic")

# Phase 0 conditional branch: fast-path exit OR full pipeline
workflow.add_conditional_edges(
    "phase_0_optimistic",
    route_phase_0,
    {
        "END":              END,
        "context_analyzer": "context_analyzer",
    },
)

# Linear pipeline: Agent 1 -> Agent 2 -> Agent 3
workflow.add_edge("context_analyzer",   "structural_locator")
workflow.add_edge("structural_locator", "hunk_generator")
workflow.add_edge("hunk_generator",     "validation")

# Validation feedback loop: pass -> END, fail -> retry Agent 3 or give up
workflow.add_conditional_edges(
    "validation",
    route_validation,
    {
        "END":           END,
        "hunk_generator": "hunk_generator",
    },
)

# --- Compile ---
app = workflow.compile()
