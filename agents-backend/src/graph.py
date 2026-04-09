"""
H-MABS Orchestrator Graph

Pipeline:
  START
    -> phase_0_optimistic       (Fast-path direct git apply attempt)
       |-- fast_path_success=True  -> END
       '-- fast_path_success=False
              -> context_analyzer   (semantic blueprint; deterministic for TRIVIAL/STRUCTURAL)
              -> structural_locator (find target locations, no planning)
              -> [TRIVIAL]  hunk_generator (dumb apply)  -> validation
              -> [STRUCTURAL/REWRITE]  recovery_agent (semantic planning)
                 |-- produces plan -> hunk_generator -> validation
                 |-- applies directly -> validation
                 '-- no_fix_found   -> END
              validation:
                 |-- passed          -> END
                 |-- failed, attempts < MAX_VALIDATION_ATTEMPTS -> recovery_agent
                 '-- failed, attempts >= MAX_VALIDATION_ATTEMPTS -> END

Flow breakdown:
1. Context Analyzer: extract blueprint (deterministic for TRIVIAL/STRUCTURAL)
2. Structural Locator: find target locations (no planning)
3. Routing by complexity:
   - TRIVIAL: File Editor dumb mode (deterministic apply of mainline edits verbatim)
   - STRUCTURAL/REWRITE: recovery_agent directly (semantic planning, skips doomed dumb pass)
4. Validation: test the result
5. Recovery Agent (STRUCTURAL first pass OR after validation failure):
   - Full ReAct pass with semantic analysis + planning
   - Creates structured plan from scratch
   - File Editor applies recovery plan deterministically (max 2 retries)

Key insight: STRUCTURAL/REWRITE patches skip hunk_generator on the first pass to
preserve all MAX_VALIDATION_ATTEMPTS for meaningful recovery attempts.
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

# Maximum number of validation attempts before giving up.
# Set to 3 so that when Phase 3 bails out with "no adapted hunks" (attempt 1),
# recovery_agent still gets a real post-build retry (attempt 2 → attempt 3).
MAX_VALIDATION_ATTEMPTS = 3


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
        print(
            "Router: Skipping Phase 0 - entering context_analyzer for semantic blueprint."
        )
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
    print(
        "Router: Phase 0 failed - entering dumb apply pipeline (context_analyzer -> structural_locator -> file_editor dumb mode)."
    )
    return "context_analyzer"


def route_after_structural(state: AgentState) -> str:
    """
    Route after structural locator.

    TRIVIAL patches go to hunk_generator for a deterministic dumb apply.
    STRUCTURAL/REWRITE patches skip hunk_generator (which would fail fast
    with no plan anyway) and route directly to recovery_agent for semantic
    planning. This preserves all 3 validation attempts for complex patches.
    """
    complexity = str(state.get("patch_complexity") or "").upper()
    if complexity in ("STRUCTURAL", "REWRITE"):
        print(
            f"Router: {complexity} patch -> skipping hunk_generator, "
            "routing directly to recovery_agent (preserves validation attempts)."
        )
        return "recovery_agent"
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


def route_after_recovery(state: AgentState) -> str:
    """
    After recovery planning:
      - DIRECT-APPLY: if recovery_agent already mutated files on disk via
        apply_edit and produced adapted_code_hunks, skip hunk_generator and
        go straight to validation.
      - If recovery reports no_fix_found or no actionable plan, stop.
      - If deterministic brief indicates file remap / logic moved, re-run locator.
      - Otherwise apply planned edits in file editor.
    """
    if state.get("recovery_applied_directly"):
        print(
            "Router: Recovery applied edits directly. "
            "Routing straight to validation (skipping hunk_generator)."
        )
        return "validation"

    recovery_status = str(state.get("recovery_agent_status") or "").strip().lower()
    if recovery_status == "no_fix_found":
        print("Router: Recovery reported no_fix_found. Stopping retries and exiting.")
        return "END"

    # If recovery did not produce actionable edits, do not route to file editor
    # with an empty plan (STRUCTURAL/REWRITE will fail-fast there).
    plan = state.get("hunk_generation_plan") or {}
    has_actionable_plan = bool(
        isinstance(plan, dict) and any(isinstance(v, list) and v for v in plan.values())
    )
    if not has_actionable_plan:
        print(
            "Router: Recovery did not produce actionable plan. "
            "Stopping retries and exiting."
        )
        return "END"

    brief = state.get("recovery_brief") or {}
    diag = brief.get("diagnosis") if isinstance(brief, dict) else {}
    rule = brief.get("rulebook_decision") if isinstance(brief, dict) else {}

    kind = str((diag or {}).get("kind") or "").strip().lower()
    action = str((rule or {}).get("action") or "").strip().lower()
    remap_actions = {"remap_file", "remap_anchor"}

    if kind in {"logic_moved", "target_file_missing"} or action in remap_actions:
        print(
            "Router: Recovery brief indicates remap/logic move. "
            "Routing to structural_locator before file_editor."
        )
        return "structural_locator"

    print("Router: Recovery produced actionable plan. Routing to hunk_generator.")
    return "hunk_generator"


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

# Linear pipeline: Agent 1 -> Agent 2 -> Agent 3 (or recovery for complex patches)
workflow.add_edge("context_analyzer", "structural_locator")
workflow.add_conditional_edges(
    "structural_locator",
    route_after_structural,
    {
        "hunk_generator": "hunk_generator",
        "recovery_agent": "recovery_agent",
    },
)
workflow.add_edge("hunk_generator", "validation")
workflow.add_conditional_edges(
    "recovery_agent",
    route_after_recovery,
    {
        "structural_locator": "structural_locator",
        "hunk_generator": "hunk_generator",
        "validation": "validation",
        "END": END,
    },
)

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
