"""
H-MABS Orchestrator Graph (Phase 1)

4-Agent Pipeline:
  START
    -> phase_0_optimistic       (Fast-path direct git apply attempt)
       |-- fast_path_success=True  -> END   (skips all LLM agents)
       '-- fast_path_success=False
              -> context_analyzer   (Agent 1: Semantic Blueprint)
              -> structural_locator (Agent 2: Consistency Map + Mapped Context)
              -> planning_agent     (Phase 2.5: str_replace Edit Plans)
              -> hunk_generator     (Agent 3: File Editor - direct edits + git diff)
              -> validation         (Agent 4: "Prove Red, Make Green" loop)
                 |-- passed          -> END
                 |-- failed, attempts < MAX_VALIDATION_ATTEMPTS -> hunk_generator (retry)
                 '-- failed, attempts >= MAX_VALIDATION_ATTEMPTS -> END (give up)

Note: The graph node "hunk_generator" is now backed by file_editor_node.
The node name is kept identical so all routing logic and result-file naming
(phase3_hunk_generator) remains unchanged.
"""

from langgraph.graph import StateGraph, START, END
from state import AgentState
from agents import (
    phase_0_optimistic,
    context_analyzer_node,
    structural_locator_node,
    planning_agent_node,
    file_editor_node,
    validation_agent,
)

# Maximum number of "Prove Red, Make Green" retry loops before giving up.
MAX_VALIDATION_ATTEMPTS = 3


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
        failure_category = (
            (state.get("validation_failure_category") or "").strip().lower()
        )
        failed_stage = (state.get("validation_failed_stage") or "").strip().lower()

        # 1. Identical Patch Guard: force replanning if the patch didn't change
        # but validation still fails.
        if failed_stage == "generation_contract_failed":
            print(
                f"Router: Generation contract FAILED. Routing to planning_agent for structural fix."
            )
            return "planning_agent"

        build_diagnostics = (
            (state.get("validation_results") or {}).get("build") or {}
        ).get("diagnostics") or {}
        build_issue_types = {
            str((issue or {}).get("error_type") or "").strip().lower()
            for issue in (build_diagnostics.get("issues") or [])
            if isinstance(issue, dict)
        }
        latest_hunk_apply_failed = bool(
            ((state.get("validation_results") or {}).get("hunk_application") or {}).get(
                "success"
            )
            is False
        )
        if failure_category == "mapping_required":
            locator_retry_count = int(state.get("structural_locator_retries") or 0)
            if locator_retry_count >= 2:
                print(
                    f"Router: mapping_required persists after {locator_retry_count} locator run(s). Exiting."
                )
                return "END"
            print(
                f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}) with "
                "mapping-required diagnosis. Routing to structural_locator for remap."
            )
            return "structural_locator"
        if latest_hunk_apply_failed and failure_category in {
            "path_or_file_operation",
        }:
            print(
                f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}) with "
                "path/file-operation issue. Routing back to structural_locator for remap."
            )
            return "structural_locator"
        if latest_hunk_apply_failed and failure_category in {
            "context_mismatch",
            "hunk_application_failed",
        }:
            print(
                f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}) with "
                "context mismatch. Routing to planning_agent for anchor replanning."
            )
            return "planning_agent"
        if failure_category == "context_mismatch" and failed_stage in {
            "hunk_sanity_failed",
            "generation_contract_failed",
            "incomplete_todo_steps",
        }:
            print(
                f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}) due "
                f"generation stage '{failed_stage}'. Routing to planning_agent."
            )
            return "planning_agent"
        if failure_category == "context_mismatch" and (
            "api_or_signature_mismatch" in build_issue_types
            or "java_syntax_or_patch_artifact" in build_issue_types
        ):
            print(
                f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}) with "
                f"build diagnostics {sorted(build_issue_types)}. Routing to planning_agent."
            )
            return "planning_agent"
        if failure_category == "empty_generation":
            print(
                f"Router: Validation FAILED (attempt {attempts}/{MAX_VALIDATION_ATTEMPTS}) with "
                "empty generation output. Routing to planning_agent."
            )
            return "planning_agent"
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
workflow.add_node("phase_0_optimistic", phase_0_optimistic)
workflow.add_node("context_analyzer", context_analyzer_node)
workflow.add_node("structural_locator", structural_locator_node)
workflow.add_node("planning_agent", planning_agent_node)
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
workflow.add_edge("structural_locator", "planning_agent")
workflow.add_edge("planning_agent", "hunk_generator")
workflow.add_edge("hunk_generator", "validation")

# Validation feedback loop: pass -> END, fail -> retry Agent 3 or give up
workflow.add_conditional_edges(
    "validation",
    route_validation,
    {
        "END": END,
        "structural_locator": "structural_locator",
        "planning_agent": "planning_agent",
        "hunk_generator": "hunk_generator",
    },
)

# --- Compile ---
app = workflow.compile()
