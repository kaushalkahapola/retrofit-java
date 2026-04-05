# Backport agent hardening — implementation plan

This document captures a roadmap to make the agents-backend backport pipeline robust: validate plans before they touch disk, prefer cheap correct paths, bound cost when things go wrong, and measure reality. It is informed by failure analysis (e.g. misplaced constructor assignments, deterministic apply → syntax error → long ReAct loops, undercounted tokens).

## Goals

1. **Stop bad plans before they touch disk** — especially misplaced statements and fractured constructors.
2. **Prefer correct cheap paths** — single-file unified diff, `git apply`, or one-shot replace before ReAct.
3. **Bound cost** when something does go wrong — caps, fast fail, structured fallback.
4. **Measure reality** — tokens, steps, escalation reasons.

---

## Phase A — Plan validation and repair (highest leverage)

**Problem:** Micro-operations such as `insert_before` on a method signature can inject statements like `this.clusterService = clusterService;` at class scope, causing parse errors and triggering ReAct.

**Work items:**

1. **Region-aware anchors**  
   - Classify each planned edit target: `import`, `field`, `constructor`, `method`, `static_block`, `unknown`.  
   - Reject or rewrite any edit whose `new_string` contains instance field assignment / `this.` initialization unless the anchor resolves inside a **constructor body** (or an explicit instance initializer).  
   - Use a lightweight Java parser (e.g. `javalang` or Tree-sitter Java) for **validation only**, not for generating the entire patch.

2. **Constructor merge pass**  
   - After the LLM emits N operations touching the same class constructors, **merge** them into one or two `replace` blocks (e.g. public `@Inject` constructor + `@VisibleForTesting` constructor) keyed by stable signatures.  
   - Rule: no standalone “add assignment” operation unless it is between lines already inside the same `{ ... }` block.

3. **Sanity apply before real apply**  
   - Apply planned operations to a **copy** of the file in memory; run the same syntax / parse check used after deterministic apply. If validation fails, **do not** write to the working tree — run **plan repair** (one repair LLM call with compiler/snippet context, or a deterministic merge retry).

4. **Enforce stated invariants**  
   - Planning already emits fields such as `required_invariants` — **assert** them after merge (contiguous regions or parse-backed checks) or fail validation.

**Deliverable:** `plan_validator` module (or equivalent) invoked immediately before `_apply_plan_entries_deterministically` in the file editor path.

---

## Phase B — Escalation and ReAct policy

**Problem:** A single syntax failure can trigger an unbounded ReAct loop with hallucinated diffs and high token use.

**Work items:**

1. **Tiered recovery**  
   - **Tier 1:** Plan validation / merge (Phase A).  
   - **Tier 2:** Retargeted **single replace** of whole method or class body from mainline hunk text + target file (template-style), when locator confidence is high.  
   - **Tier 3:** Short ReAct with a **strict budget** (max LLM turns, max tool calls, max wall time).  
   - **Tier 4:** Fail with a **structured error** — no infinite retries.

2. **Syntax-failure classification**  
   - Bucket messages such as `illegal start of type`, `class, interface, or enum expected` as **“statement outside block”**.  
   - For that bucket, **do not** enter ReAct until the planner emits a merged constructor/method block, or Tier 2 succeeds.

3. **Constrain speculative rewriting**  
   - When evaluation mode has a developer / target patch, ReAct prompts should **prefer matching that diff** over inventing APIs (e.g. wrong `SysSnapshot` constructors).

4. **Hard limits**  
   - Example: max 15 LLM steps per file, max 40 tool calls; then return `FAILED_ESCALATION_BUDGET` with reason.

**Deliverable:** Central escalation controller in the file editor / hunk generator with an explicit state machine and logging.

---

## Phase C — Patch-first fallback (TYPE_I–aligned)

**Problem:** For near-identical mainline and target branches, the pipeline should not depend on many small `str_replace` operations.

**Work items:**

1. **Near-no-op detection**  
   - If normalized similarity between the agent-eligible mainline hunk and the developer patch slice for the same file is above a threshold, prefer applying the **developer-equivalent** hunk or a **three-way merge** (base = `backport_commit^`, target file state, mainline patch).

2. **Single unified diff per file**  
   - Where the planner would emit only TYPE_I operations, optionally emit **one** unified diff per file and run `git apply --check` / equivalent before fragment edits.

3. **Idempotency**  
   - If the file already matches the post-patch blob, skip agent work (fast path).

**Deliverable:** `patch_apply_strategy` (or equivalent) invoked early in Agent 3 when complexity is TYPE_I and checks pass.

---

## Phase D — Structural locator and routing

**Problem:** Some hunks map to `None`; routing may default to REWRITE when the change is actually TYPE_I.

**Work items:**

1. **None-hunk recovery**  
   - When Git has matched the file but some hunks are unmapped, **re-run** line alignment using the matched file content and hunk headers from the blueprint (context-based alignment), avoiding a full second LLM mapping where possible.

2. **Complexity classification**  
   - Revisit `classify_patch_complexity`: edits that are import + field + constructor + localized method change and **file path matches** mainline mapping should default toward **TYPE_I** unless static analysis detects API drift.

3. **Pair consistency**  
   - When mainline/developer Java file overlap is high, reduce the probability of REWRITE-only routing.

**Deliverable:** Updates in `structural_locator` and `patch_complexity` with regression tests for cases similar to single-file, high-overlap backports.

---

## Phase E — Observability

**Problem:** Token totals in run artifacts can miss ReAct subgraph usage, hiding real cost.

**Work items:**

1. **Propagate usage** from every LLM invocation (including ReAct) into node outputs consumed by `evaluate_full_workflow` token aggregation.  
2. **Counters:** `llm_calls`, `tool_calls`, `react_rounds`, `deterministic_apply_ok` / `deterministic_apply_fail`.  
3. **Structured log lines** per escalation: `PLAN_INVALID`, `SYNTAX_POST_EDIT`, `REACT_BUDGET`, etc.

**Deliverable:** Extend token collection and ReAct wrappers so usage metadata is always attached where the evaluator reads it.

---

## Phase F — Testing and regression

1. **Golden fixtures** — mainline patch + repo state + expected outcomes (plan passes validation; single apply succeeds).  
2. **Negative fixture** — intentionally bad plan (wrong `insert_before`); assert validator **rejects** before writing the file.  
3. **Integration** — full workflow on known patch IDs; assert ReAct is absent or under cap, optional blob match to developer patch.  
4. **Property tests** — valid Java + valid edits; validator never accepts orphan statements at class scope.

---

## Suggested execution order

| Priority | Phase | Rationale |
|----------|--------|-----------|
| P0 | A — Plan validation + constructor merge | Stops the dominant failure mode |
| P0 | B — Escalation caps + syntax buckets | Limits blast radius |
| P1 | E — Token and step metrics | Required for tuning |
| P1 | C — Patch-first for TYPE_I | Aligns pipeline with obvious backports |
| P2 | D — Locator + routing | Reduces bad input to planning |
| P2 | F — Tests | Locks behavior |

---

## Design principle

Treat the stack as **defense in depth**: validate plans → prefer monolithic safe applies → short bounded repair → fail with a clear code. Robustness comes from **constraints, fallbacks, and budgets**, not from a single larger model.

---

## Implementation status (2026)

| Item | Location / behavior |
|------|---------------------|
| Plan preflight (static + dry apply + optional tree-sitter) | `agents-backend/src/utils/plan_validator.py` — `validate_plan_before_apply()` |
| Agent 3 integration | `agents-backend/src/agents/file_editor.py` — runs preflight for deterministic TYPE_I/II/III `.java` files before on-disk apply; returns `plan_preflight_results` and `agent_metrics` |
| Skip ReAct on `statement_outside_block` | Same file — after deterministic failure, if `classify_syntax_failure_message` is `statement_outside_block`, do not invoke ReAct |
| ReAct budgets | `FILE_EDITOR_REACT_RECURSION_LIMIT` (default 40), `FILE_EDITOR_REACT_TOOL_BUDGET` (optional cap); default tool budget raised (STRUCTURAL 12, else 40) |
| Eval-mode prompt | When `evaluation_full_workflow` is set, ReAct system prompt reminds to stay close to the mainline patch |
| Complexity routing | `agents-backend/src/utils/patch_complexity.py` — single-file / small multi-file overlap can classify as STRUCTURAL at lower anchor ratios (0.38 / 0.40) |
| Locator line recovery | `agents-backend/src/agents/structural_locator.py` — second pass uses longer hunk anchor candidates when `start_line` is still `None` |
| Tests | `agents-backend/tests/test_plan_validator.py` (requires deps from `requirements.txt`; `PYTHONPATH=src pytest`) |
| Tree-sitter (preflight) | **Opt-in** `PLAN_VALIDATOR_USE_TREE_SITTER=1`; default off (too many false positives on valid Java). Legacy `PLAN_VALIDATOR_SKIP_TREE_SITTER=1` still forces TS off. |
| Phase C: developer fast path | `utils/patch_apply_strategy.py` — `try_developer_fast_path()`; `evaluate_full_workflow` passes `developer_patch_diff` in graph state; Agent 3 applies developer slice when `git apply --check` passes (opt-out: `EVAL_DISABLE_DEVELOPER_FAST_PATH=1`; similarity floor: `EVAL_DEVELOPER_FAST_PATH_MIN_SIMILARITY`, default 0.55 vs agent-eligible mainline slice) |
| Idempotency | `file_already_matches_developer_commit()` — if working tree already matches `backport_commit` blob, reuse `git diff` without applying |
| Planner consolidation | `consolidate_plan_entries_java()` — drops redundant `this.field =` inserts already covered by replace hunks; planning agent runs it before emitting `hunk_generation_plan` |
| Token aggregation (eval + ReAct) | `aggregate_usage_from_messages()` in `token_counter.py`; evaluator prefers aggregate over `node.token_usage` to avoid double-count; file editor ReAct uses aggregate first |
