"""
Integration patch for planning_agent.py — shows exactly where to add
the rulebook call and how to thread the diagnosis into the planner prompt.

This is NOT a standalone file. Copy the relevant sections into
agents-backend/src/agents/planning_agent.py at the indicated locations.
"""

# ============================================================
# SECTION 1: Add this import at the top of planning_agent.py
# ============================================================

IMPORT_PATCH = '''
from type_v_rulebook import TypeVRulebook, RulebookDecision
from failure_diagnosis import FailureDiagnosisEngine
'''

# ============================================================
# SECTION 2: New helper — build per-file diagnosis and decisions
# ============================================================

BUILD_DIAGNOSES_FUNCTION = '''
def _build_rulebook_decisions(
    *,
    target_repo_path: str,
    mainline_repo_path: str,
    failing_plan_entries: list[dict],
    build_error: str,
    hunk_apply_error: str,
    consistency_map: dict,
) -> dict[str, "RulebookDecision"]:
    """
    Run the TYPE_V rulebook for each failing plan entry.
    Returns a dict keyed by target_file → RulebookDecision.
    
    Only called when:
      - validation_attempts > 0
      - force_type_v_until_success is True  OR  execution_type == TYPE_V
    """
    rulebook = TypeVRulebook(target_repo_path, mainline_repo_path)
    decisions: dict[str, RulebookDecision] = {}
    
    for entry in failing_plan_entries:
        target_file = str(entry.get("target_file") or "")
        if not target_file or target_file in decisions:
            continue
        
        decision = rulebook.apply(
            target_file=target_file,
            failed_plan_entry=entry,
            build_error=build_error,
            hunk_apply_error=hunk_apply_error,
            consistency_map=consistency_map or {},
        )
        decisions[target_file] = decision
    
    return decisions
'''

# ============================================================
# SECTION 3: Inject rulebook into the per-hunk loop
# ============================================================
# Inside planning_agent_node(), in the per-hunk processing loop,
# BEFORE the LLM planner call, add this block:

RULEBOOK_INJECTION = '''
# ------------------------------------------------------------------
# TYPE_V RULEBOOK: Run before LLM planning to guide it deterministically
# ------------------------------------------------------------------
rulebook_decision = None
if force_type_v_for_entry and validation_attempts > 0:
    rulebook = TypeVRulebook(target_repo_path, mainline_repo_path)
    rulebook_decision = rulebook.apply(
        target_file=target_file,
        failed_plan_entry=sanitized_entries[0] if sanitized_entries else {},
        build_error=str(validation_error_context or ""),
        consistency_map=consistency_map or {},
    )
    
    # If rulebook says remap to a different file, update target_file NOW
    # before we even call the LLM
    if rulebook_decision.action == "remap_file" and rulebook_decision.override_target_file:
        old_target = target_file
        target_file = rulebook_decision.override_target_file
        print(
            f"    Planning Agent: RULEBOOK remap: {old_target} → {target_file} "
            f"(confidence={rulebook_decision.confidence:.0%})"
        )
        # Re-run sanitize against new target
        new_content = _read_target_file(target_repo_path, target_file)
        if new_content:
            sanitized_entries = [
                _sanitize_entry_against_target(e, new_content)
                for e in sanitized_entries
            ]
    
    # If rulebook says apply to parent, redirect
    elif rulebook_decision.action == "apply_to_parent" and rulebook_decision.override_target_file:
        target_file = rulebook_decision.override_target_file
        print(
            f"    Planning Agent: RULEBOOK parent redirect → {target_file}"
        )
    
    # If rulebook says add side files, add them to the plan queue
    elif rulebook_decision.action == "add_side_file":
        for sf in rulebook_decision.additional_files:
            if sf not in mapped_target_context:
                # Add a minimal mapping so hunk generator picks it up
                mapped_target_context[sf] = [{
                    "hunk_index": 0,
                    "target_file": sf,
                    "start_line": None,
                    "code_snippet": "",
                    "anchor_reason": "rulebook_side_file",
                }]
                print(f"    Planning Agent: RULEBOOK added side file: {sf}")
'''

# ============================================================
# SECTION 4: Inject rulebook context into LLM prompt
# ============================================================
# In _build_hunk_planner_prompt(), add this to the prompt string:

PROMPT_INJECTION = '''
# Add after the drift_map section in the prompt:
rulebook_section = ""
if rulebook_decision and rulebook_decision.confidence > 0.4:
    rulebook_section = rulebook_decision.to_prompt_context()

# Then in the f-string:
f"""
...
API DRIFT MAP:
{json.dumps(drift_map or {}, indent=2)}

{rulebook_section}

Deterministic candidate operations:
...
"""
'''

# ============================================================
# SECTION 5: Modify _build_hunk_planner_prompt signature
# ============================================================
# Add `rulebook_decision: "RulebookDecision | None" = None` parameter
# and include it in the prompt body as shown above.

SUMMARY = """
Integration summary:
─────────────────────────────────────────────────────────────
1. Import TypeVRulebook and RulebookDecision at top of planning_agent.py
2. In the per-hunk loop (around line where force_type_v_for_entry is checked),
   insert the RULEBOOK_INJECTION block BEFORE the LLM planner call
3. Pass rulebook_decision to _build_hunk_planner_prompt
4. In _build_hunk_planner_prompt, render rulebook_decision.to_prompt_context()
   into the prompt between the drift_map and deterministic_entries sections

The rulebook:
- Runs git grep, reads files, checks superclasses — all deterministically
- Identifies the most likely fix strategy in < 1 second
- Tells the LLM exactly where to look and what to do
- Falls back to "full_react" only when deterministic analysis fails

Token savings:
- For LOGIC_MOVED: saves 5-10 LLM tool calls (no more grepping in the loop)
- For SIGNATURE_CHANGED: saves 3-5 calls (no more get_class_context dance)
- For PARENT_CLASS: saves the entire re-investigation pass
─────────────────────────────────────────────────────────────
"""