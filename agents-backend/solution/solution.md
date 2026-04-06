Looking at your codebase, I can see the core problem clearly. For complex TYPE_V patches, the agents are doing too much guessing and not enough systematic investigation. Let me design a proper rulebook-driven approach.This is a genuinely hard problem. Let me map out the failure modes precisely, then design a proper rulebook-driven solution.Now let me build the complete solution. The key insight is: **validation already tells you what went wrong**. You just need a structured rulebook that uses that diagnostic info, not a free-form ReAct agent burning tokens.

Here's the complete design:

---

## The Problem in One Sentence

Your TYPE_V path currently says "here's the failure, do whatever you want to fix it." What it should say is "here's the failure, follow this specific decision tree."

## Root Cause Analysis of Your Three Failure Modes

**Failure 1: API drift** — the method exists but its signature changed (new param, different return type). Your current code detects `cannot find symbol` but doesn't map it to "which method in the target has the same name but different signature."

**Failure 2: Logic must change other files** — your patch analysis only looks at files changed in mainline. If target has `FooService` calling `BarHelper` and the fix actually needs to touch `BarHelper`, you never discover this.

**Failure 3: Code moved/refactored** — structural locator can handle this but only for the primary file. When planning fails for a hunk, there's no systematic "where did this logic go?" investigation.

## The Solution: A `FailureDrivenRulebook` subagent

Instead of giving the LLM all tools and hoping for the best, create a **deterministic pre-analysis step** that runs before planning retries and produces a `diagnosis` object. Then the planning/editing agents consume that structured diagnosis.

Here's the full implementation:Here's the complete solution:

## The Core Insight

Your validation agent already knows *what* failed. The problem is this information arrives as a raw error string and the LLM spends 5-10 tool calls re-discovering what the error already told you. The fix is to run a **deterministic pre-analysis pass** before any LLM retry.

## How it works

**`failure_diagnosis.py`** — runs `git grep`, reads files, checks inheritance chains. Zero LLM calls, zero tokens. Produces a typed `Diagnosis` object with a `FailureKind`:
- `LOGIC_MOVED` — symbol found in a different file via grep
- `SIGNATURE_CHANGED` — method exists but with different params
- `PARENT_CLASS_CHANGE` — anchor text is in the superclass, not the subclass
- `SIDE_FILE_NEEDED` — compiler errors reference files outside your edit scope
- `ANCHOR_NOT_FOUND` — anchor line found in a different file

**`type_v_rulebook.py`** — decision tree that takes the `Diagnosis` and returns a `RulebookDecision` with a concrete `action` (`remap_file`, `adapt_signature`, `apply_to_parent`, `add_side_file`). The `to_prompt_context()` method renders this into a structured prompt section that tells the LLM exactly where to go and what to do — no re-investigation.

## Integration (3 files to touch)

1. `planning_agent.py` — inject the rulebook call before the LLM planner loop. For `remap_file`, it updates `target_file` *before* the LLM ever sees the prompt. For `adapt_signature`, it provides the exact verified signature. For `add_side_file`, it inserts the uncovered file into `mapped_target_context`.

2. `validation_agent.py` — extract structured failure context (failed file, failed symbol) and store it in state as `validation_error_context_structured`.

3. `state.py` — add one field: `validation_error_context_structured: NotRequired[dict]`.

## On your other attempts (repomap, TargetScout, etc.)

They failed because they ran *speculatively on every patch*. The rulebook runs the same underlying checks but only when a real failure signal triggers them — that's why it's cheap. Your `GetDependencyTool` with `explore_neighbors=True` is actually the right tool for `LOGIC_MOVED` scenarios; the rulebook calls it as a targeted fallback when `git grep` finds hits in multiple files.
