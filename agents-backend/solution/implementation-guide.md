# TYPE_V Complex Patch Rulebook — Implementation Guide

## Problem Summary

For complex TYPE_V patches, three failure modes are not handled:
1. **API drift** — method exists in target but signature changed
2. **Side-file edits needed** — fix requires touching files not in mainline patch
3. **Logic moved** — code refactored to different class/file

The current approach: give LLM all tools, hope it finds the answer.
This burns tokens, is unreliable, and causes infinite retry loops.

## The Fix: Deterministic Pre-Analysis → Targeted LLM Call

```
Validation fails
      ↓
FailureDiagnosisEngine.diagnose()   ← deterministic, no LLM, ~0 tokens
      ↓
TypeVRulebook.apply()               ← decision tree, no LLM
      ↓  
RulebookDecision                    ← "remap_file" | "adapt_signature" | "apply_to_parent"
      ↓
LLM planning prompt + structured context  ← 1 focused LLM call
      ↓
File editor applies the targeted edit
```

## Files to Add

Place in `agents-backend/src/agents/`:
- `failure_diagnosis.py` — the diagnosis engine
- `type_v_rulebook.py` — the decision tree

## Changes to Existing Files

### 1. `planning_agent.py` — inject rulebook before LLM call

```python
# At top:
from type_v_rulebook import TypeVRulebook, RulebookDecision

# In the per-hunk loop, BEFORE the LLM planner call:
rulebook_decision = None
if force_type_v_for_entry and validation_attempts > 0:
    rulebook = TypeVRulebook(target_repo_path, mainline_repo_path)
    rulebook_decision = rulebook.apply(
        target_file=target_file,
        failed_plan_entry=sanitized_entries[0] if sanitized_entries else {},
        build_error=str(validation_error_context or ""),
        consistency_map=consistency_map or {},
    )
    
    # Act on remap decisions immediately (no LLM needed)
    if rulebook_decision.action == "remap_file" and rulebook_decision.override_target_file:
        target_file = rulebook_decision.override_target_file
        new_content = _read_target_file(target_repo_path, target_file)
        if new_content:
            sanitized_entries = [_sanitize_entry_against_target(e, new_content) for e in sanitized_entries]
    
    elif rulebook_decision.action == "apply_to_parent":
        target_file = rulebook_decision.override_target_file
    
    elif rulebook_decision.action == "add_side_file":
        for sf in rulebook_decision.additional_files:
            if sf not in mapped_target_context:
                mapped_target_context[sf] = [{"hunk_index": 0, "target_file": sf, 
                    "start_line": None, "code_snippet": "", "anchor_reason": "rulebook_side_file"}]

# In _build_hunk_planner_prompt, add rulebook_decision parameter and render:
if rulebook_decision and rulebook_decision.confidence > 0.4:
    prompt += "\n\n" + rulebook_decision.to_prompt_context()
```

### 2. `validation_agent.py` — extract structured failure context

```python
# After build failure classification, before return:
structured_failure = {
    "raw_error": build_output[:3000],
    "failed_locations": _extract_failed_locations(build_output),   # file + line
    "symbol_errors": _extract_symbol_errors(build_output),         # cannot find symbol
    "primary_failed_file": first_failing_file,
    "primary_failed_symbol": first_failing_symbol,
}
return {
    ...,
    "validation_error_context_structured": structured_failure,
}
```

### 3. `state.py` — add one field

```python
validation_error_context_structured: NotRequired[dict[str, Any]]
```

## Decision Tree Logic

| Diagnosis | Action | What the rulebook does |
|-----------|--------|------------------------|
| Symbol found in different file | `remap_file` | Updates `target_file` before LLM call |
| Method exists but signature changed | `adapt_signature` | Provides exact target signature + param diff |
| Anchor text found in parent class | `apply_to_parent` | Redirects edit to parent file |
| Build error mentions uncovered file | `add_side_file` | Adds file to `mapped_target_context` |
| Anchor line found in another file | `remap_anchor` | Provides exact line + snippet |
| None of the above | `full_react` | Falls back to current ReAct loop |

## What This Fixes

| Scenario | Before | After |
|----------|--------|-------|
| `FooService.doThing()` moved to `BaseService.doThing()` | 5-10 tool calls, often wrong | 1 grep → instant remap |
| Target adds a `context` param to a method | 3+ tool calls to find signature | 1 file read → provides exact sig |
| Fix requires changing `Bar.java` too | Never discovered | Build error → side file added |
| Edit belongs in superclass | Repeated anchor failures | grep parent class → instant redirect |

## Token Impact

- `remap_file`: saves ~5-10 ReAct tool calls per retry (~2k tokens)
- `adapt_signature`: saves ~3-5 calls (~1.5k tokens)  
- `apply_to_parent`: saves entire re-investigation pass (~3k tokens)
- `full_react` fallback: same as current (no regression)

## Repomap and Other Tools — Verdict

**Repomap**: Useful for cross-file call graph analysis, but only worthwhile
if you can build it cheaply. The Java analysis engine already does this.
Use `GetDependencyTool` with `explore_neighbors=True` as a targeted call
from the rulebook's `_check_symbol_moved` method — don't build the whole
repomap upfront.

**Tree-sitter signature extraction**: Already in `method_fingerprinter.py`.
The rulebook's `_check_signature_changed` uses regex which is faster for
this targeted case. Only escalate to tree-sitter if regex fails.

**SymbolDrift / TargetScout**: Likely failed because they ran speculatively
on every patch rather than only when a specific failure is diagnosed.
The rulebook approach runs these exact checks but only when triggered
by a real failure signal.
