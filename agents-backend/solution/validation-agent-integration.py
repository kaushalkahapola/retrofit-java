"""
Integration patch for validation_agent.py — extract failure context
that feeds the rulebook.

The key change: when build/compile fails, extract not just the
error text but structured failure context that identifies:
  - which file failed
  - which symbol failed
  - whether it's an anchor problem or API problem

This structured context is stored in validation_results and read
by the planning agent on the next retry.
"""

# ============================================================
# SECTION 1: New structured error extraction
# ============================================================

EXTRACT_FAILURE_CONTEXT = '''
def _extract_structured_failure_context(
    build_error: str,
    hunk_apply_error: str,
    effective_hunks: list,
) -> dict:
    """
    Produce a structured failure context dict for the rulebook.
    Stored in validation_results["structured_failure"] and
    passed to the planning agent as validation_error_context_structured.
    """
    text = str(build_error or hunk_apply_error or "")
    
    # Extract failed file + line from javac output
    file_line_pattern = re.compile(r"([a-zA-Z0-9_/.-]+\\.java):(\\d+):")
    failed_locations = []
    for m in file_line_pattern.finditer(text):
        failed_locations.append({
            "file": m.group(1),
            "line": int(m.group(2)),
        })
    
    # Extract "cannot find symbol" details
    symbol_errors = []
    for m in re.finditer(r"symbol:\\s+(variable|method|class)\\s+(\\w+)", text):
        symbol_errors.append({
            "kind": m.group(1),
            "name": m.group(2),
        })
    
    # Extract "cannot be applied to given types" — signature mismatch
    sig_errors = []
    for m in re.finditer(
        r"method (\\w+)\\([^)]*\\) in class (\\S+) cannot be applied",
        text,
    ):
        sig_errors.append({
            "method": m.group(1),
            "class": m.group(2),
        })
    
    # Map errors to hunks
    failed_hunk_targets = []
    for loc in failed_locations[:5]:
        for hunk in effective_hunks:
            target_f = str(hunk.get("target_file") or "").replace("\\\\", "/")
            if target_f.endswith(loc["file"]) or loc["file"].endswith(target_f):
                failed_hunk_targets.append({
                    "target_file": hunk.get("target_file"),
                    "mainline_file": hunk.get("mainline_file"),
                    "error_line": loc["line"],
                })
                break
    
    return {
        "raw_error": text[:3000],
        "failed_locations": failed_locations[:5],
        "symbol_errors": symbol_errors[:10],
        "signature_errors": sig_errors[:5],
        "failed_hunk_targets": failed_hunk_targets,
        "primary_failed_file": failed_locations[0]["file"] if failed_locations else "",
        "primary_failed_symbol": symbol_errors[0]["name"] if symbol_errors else "",
    }
'''

# ============================================================
# SECTION 2: Where to call it in validation_agent.py
# ============================================================
# In the build failure handler, after _classify_build_failure():

BUILD_FAILURE_HANDLER_PATCH = '''
# After existing classification:
failure_category, retry_files, diagnostics, analysis, retry_hunks = (
    _classify_build_failure(build_res.get("output", ""), target_repo_path, effective_code_hunks)
)

# ADD THIS:
structured_failure = _extract_structured_failure_context(
    build_error=build_res.get("output", ""),
    hunk_apply_error="",
    effective_hunks=effective_code_hunks,
)
validation_results["structured_failure"] = structured_failure

# Pass primary_failed_file and symbol to retry state:
return {
    ...
    "validation_error_context": f"Build failed: {analysis}",
    "validation_error_context_structured": structured_failure,  # ADD THIS
    "validation_failure_category": failure_category,
    ...
}
'''

# ============================================================
# SECTION 3: In planning_agent_node, read structured context
# ============================================================

PLANNING_AGENT_READ_CONTEXT = '''
# At the top of planning_agent_node, add:
structured_failure = state.get("validation_error_context_structured") or {}
primary_failed_file = structured_failure.get("primary_failed_file", "")
primary_failed_symbol = structured_failure.get("primary_failed_symbol", "")

# Use these in the rulebook call:
rulebook_decision = rulebook.apply(
    target_file=target_file,
    failed_plan_entry=sanitized_entries[0] if sanitized_entries else {},
    build_error=validation_error_context,
    consistency_map=consistency_map or {},
    # NEW: pass structured context too
    failed_symbol_override=primary_failed_symbol if primary_failed_file == target_file else "",
)
'''

# ============================================================
# SECTION 4: State schema additions for state.py
# ============================================================

STATE_ADDITIONS = '''
# In AgentState TypedDict, add:

validation_error_context_structured: NotRequired[dict[str, Any]]
    # Structured failure context from validation agent.
    # Contains: failed_locations, symbol_errors, signature_errors,
    # primary_failed_file, primary_failed_symbol.
    # Fed to TypeVRulebook for deterministic pre-analysis.
'''