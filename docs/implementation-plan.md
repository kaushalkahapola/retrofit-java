# Claude-Style Complex Patch Planning and Reasoning Implementation Plan

## 1) Executive Summary

This plan upgrades only the **complex patch path** (planning + reasoning) in `agents-backend/src` to a Claude Code style architecture.

What stays the same:
- Phase 0 optimistic path
- Agent 1 context analyzer
- Agent 2 structural locator
- Validation and evaluation framework as the final judge
- Deterministic edit application foundation (CLAW-style exact operations)

What changes:
- Complex retries move to a strict **Plan Mode -> Critic -> Act Mode** pipeline
- Replace monolithic, token-heavy free-form reasoning with isolated subagents and structured contracts
- Add adversarial plan evaluation before edits
- Add compacted, fresh-context retries (Ralph-loop style for retry iterations)


## 2) Why This Change Is Needed (Observed Failure Pattern)

Using `crate_30abc0f9` as the reference failure:

- Planning produced partially unresolved anchors (`verified: false`) and still proceeded.
- File editor escalated to open-ended ReAct editing for complex hunks.
- ReAct introduced duplicate imports and duplicate assignments in `DistributingConsumer.java`.
- Validation failed in build with coarse classification (`unknown_build_failure`), giving weak retry guidance.
- Reasoning architect consumed significant tokens but returned no usable surgical plan (`surgical_plans: {}`).
- Retry loop stagnated (`validation_repeated_plan_detected: true`) and did not converge.

Token cost from this single failure run (from `tokens.txt`):
- Total: ~1.23M tokens
- Hunk/file editing node: ~843k
- Reasoning architect: ~392k

Core issue: the current complex path allows too much unconstrained generation after weak diagnostics.


## 3) Target Architecture (Claude Methods Mapped to H-MABS)

We will adopt these methods from Claude architecture for complex cases only:

1. **Plan Mode vs Act Mode hard boundary**
   - Plan Mode: read-only exploration and contract creation
   - Act Mode: deterministic execution only from approved contract

2. **Single deterministic orchestrator loop**
   - Each loop iteration performs exactly one stage transition
   - No hidden fallback mode that bypasses planning gates

3. **Subagent isolation**
   - Independent context windows for anchor search, API drift, propagation scope
   - Prevent context pollution in parent reasoning path

4. **Programmatic tool-calling style**
   - Batch deterministic diagnostics and aggregate findings before LLM synthesis
   - Reduce many tool-call round trips

5. **Adversarial evaluator (critic)**
   - Generator proposes execution contract
   - Critic tries to reject it with strict failure checks before file edits

6. **Context compaction + fresh retries**
   - Retry with compact state artifacts only (not full noisy chat history)
   - Ralph-loop style reset between failed iterations


## 4) Scope and Non-Goals

### In Scope
- Complex path router and new planning/reasoning subgraph
- Structured execution contract for complex edits
- Critic gate before execution
- Retry memory compaction and fresh-session retry policy

### Out of Scope
- Replacing Phase 0/1/2 logic
- Rewriting validation harness or metrics framework
- Modifying simple Type I/II deterministic happy path behavior


## 5) Proposed Complex-Case Subgraph

Current retry path:
`validation fail -> planning_agent -> reasoning_architect -> file_editor -> validation`

New complex retry path:

1. `complex_router` (decide normal vs complex branch)
2. `plan_mode_orchestrator` (read-only + subagents + evidence pack)
3. `contract_synthesizer` (produce structured `ExecutionContract`)
4. `plan_critic` (adversarial reject/pass)
5. if pass -> `file_editor` in contract-only act mode
6. `validation`
7. on fail -> `retry_compactor` -> fresh plan-mode iteration


## 6) Data Model Additions (`agents-backend/src/state.py`)

Add the following fields:

- `complex_case_mode: NotRequired[bool]`
- `complex_case_reason: NotRequired[str]`
- `plan_mode_evidence: NotRequired[dict[str, Any]]`
- `execution_contract: NotRequired[dict[str, Any]]`
- `plan_critic_report: NotRequired[dict[str, Any]]`
- `retry_compacted_context: NotRequired[dict[str, Any]]`
- `complex_retry_iteration: NotRequired[int]`
- `complex_retry_fresh_session_id: NotRequired[str]`

### ExecutionContract schema (new)

```json
{
  "contract_id": "sha256",
  "files": [
    {
      "target_file": "...",
      "operations": [
        {
          "op_id": "...",
          "edit_type": "replace|insert_before|insert_after|delete",
          "old_string": "...",
          "new_string": "...",
          "anchor_proof": {
            "method": "exact|trimmed|ast_boundary|grep_confirmed",
            "line": 123,
            "evidence": "..."
          },
          "invariants": ["..."],
          "required_symbols": ["..."],
          "confidence": 0.0
        }
      ]
    }
  ],
  "retry_scope": {
    "files": ["..."],
    "hunks": [0, 2]
  },
  "generator_notes": "..."
}
```


## 7) Node-by-Node Implementation Plan

### Phase A - Routing and Feature Flags

Files:
- `agents-backend/src/graph.py`
- `agents-backend/src/state.py`

Tasks:
1. Add `complex_router` decision function.
2. Introduce feature flags:
   - `ENABLE_COMPLEX_CLAUDE_MODE`
   - `ENABLE_PLAN_CRITIC`
   - `ENABLE_FRESH_RETRY_CONTEXT`
3. Route only complex failures into new subgraph.
4. Preserve existing path as fallback when flags are off.

Acceptance criteria:
- Existing non-complex runs produce identical routing and outputs.
- Complex branch can be toggled per run without code changes.


### Phase B - Plan Mode Orchestrator

New file:
- `agents-backend/src/agents/plan_mode_orchestrator.py`

Purpose:
- Enforce read-only planning stage.

Subagent set (isolated contexts):
1. `AnchorLocationExplorer`
2. `ApiSignatureDriftExplorer`
3. `PropagationScopeExplorer`

Implementation details:
- Use current read/grep/mcp tools only.
- No file-edit tools exposed in Plan Mode.
- Run subagents in parallel when independent.
- Emit normalized `plan_mode_evidence` JSON with confidence per claim.

Acceptance criteria:
- No file content mutation during Plan Mode.
- Evidence pack is deterministic in shape and machine-consumable.


### Phase C - Contract Synthesizer

Refactor file:
- `agents-backend/src/agents/planning_agent.py`

Changes:
1. Split logic into:
   - evidence ingestion
   - contract synthesis
2. Replace free-form per-hunk output with strict `execution_contract`.
3. Hard-fail if required anchors are unresolved.
4. Include retry scope and confidence in output.

Acceptance criteria:
- Planning output for complex mode is always a valid `ExecutionContract` or explicit fail.
- No silent fallback to ambiguous unverified operations.


### Phase D - Adversarial Critic Gate

New file:
- `agents-backend/src/agents/plan_critic.py`

Purpose:
- Reject weak contracts before edit execution.

Critic checks:
1. Duplicate import/field insertion risk
2. Constructor signature propagation completeness
3. Missing required symbol/invariant paths
4. Anchor ambiguity and multi-match risk
5. Side-file propagation omissions

Output:
- `plan_critic_report = { pass: bool, blockers: [...], severity: ..., suggestions: [...] }`

Routing:
- if `pass=false`, loop back to Plan Mode with blocker list
- if `pass=true`, continue to Act Mode

Acceptance criteria:
- Known malformed contracts are rejected pre-edit.
- Critic report is attached to state and trace logs.


### Phase E - Act Mode Hardening

Refactor file:
- `agents-backend/src/agents/file_editor.py`

Changes in complex mode only:
1. Consume only approved `execution_contract` operations.
2. Disable open-ended ReAct fallback for complex mode.
3. Keep deterministic apply + existing syntax/invariant gates.
4. Preserve existing behavior outside complex mode.

Acceptance criteria:
- Complex mode edits are fully contract-driven.
- No unrestricted edit-agent behavior after critic approval.


### Phase F - Retry Compaction and Fresh Session Strategy

New file:
- `agents-backend/src/agents/retry_compactor.py`

Purpose:
- Prevent retry context rot and repeated-plan loops.

Compacted payload should include only:
- last build failure structured diagnostics
- critic blockers
- failed files/hunks
- last contract hash
- repeated patch/plan indicators

Policy:
- each complex retry starts from compacted context
- no reuse of long ReAct/tool transcript context

Acceptance criteria:
- Retry prompts shrink substantially.
- repeated-plan loops trigger stronger targeted replanning signal.


### Phase G - Reasoning Architect Refactor (Optional but Recommended)

Refactor file:
- `agents-backend/src/agents/reasoning_architect.py`

Role update:
- from monolithic ReAct fixer to structured evidence producer or contract delta proposer

Key rule:
- return surgical deltas only, never broad free-form plans

Acceptance criteria:
- surgical output is non-empty for diagnosable failures or explicit typed reason for none.


## 8) Programmatic Tool-Calling Adaptation Details

In Plan Mode, adopt batched diagnostics to reduce token/latency:

1. Build one probe manifest per file:
   - anchor probes
   - signature probes
   - symbol declaration probes
   - caller/callee probes

2. Execute probes deterministically.

3. Send compact aggregate results to synthesizer/critic (not full raw logs).

Benefits:
- fewer LLM round-trips
- less context bloat
- more deterministic retry behavior


## 9) Detailed Rollout Sequence

### Milestone 1: Scaffolding
- add router + state fields + flags
- no behavior change when disabled

### Milestone 2: Plan Mode + Contract
- implement plan_mode_orchestrator and execution_contract output
- keep old reasoning path behind fallback flag

### Milestone 3: Critic + Act Mode lock
- enforce critic pass before complex execution
- disable free-form ReAct in complex mode

### Milestone 4: Retry compaction
- add retry_compactor and fresh-session retries

### Milestone 5: Evaluation and tuning
- run hard-set (including `crate_30abc0f9`)
- compare against baseline metrics


## 10) Testing Plan

### Unit tests
- `complex_router` classification triggers
- execution contract schema validation
- critic blockers for known bad contract patterns
- retry compactor output correctness

### Integration tests
- complex-case graph transition tests
- critic reject -> replan loop
- critic pass -> deterministic apply -> validation

### Regression tests
- ensure non-complex patches follow existing route unchanged

### Evaluation tests
- run Type IV/V subset from dataset
- include crate failure corpus and prior stagnation cases


## 11) Success Metrics and Exit Criteria

Primary:
- increase validation pass rate on complex set
- increase exact developer patch match on complex set

Secondary:
- reduce `unknown_build_failure` frequency
- reduce retries ending with repeated plan hash
- reduce median complex-run token usage (target: 40-60% reduction)

Operational:
- no increase in trivial/structural simple-case failure rate


## 12) Risks and Mitigations

1. **Risk:** critic too strict, blocks valid plans
   - Mitigation: severity tiers and controlled bypass flag for A/B runs

2. **Risk:** contract synthesis underfits rare cases
   - Mitigation: typed fallback mode that asks for targeted additional evidence only

3. **Risk:** migration complexity in existing graph
   - Mitigation: feature-flagged rollout and path-level canary runs

4. **Risk:** reduced flexibility from no free-form ReAct in complex mode
   - Mitigation: allow bounded contract-delta loop (plan->critic->contract) instead of direct edit free-form


## 13) File-Level Change Checklist

Mandatory:
- `agents-backend/src/state.py`
- `agents-backend/src/graph.py`
- `agents-backend/src/agents/planning_agent.py`
- `agents-backend/src/agents/file_editor.py`

New modules:
- `agents-backend/src/agents/plan_mode_orchestrator.py`
- `agents-backend/src/agents/plan_critic.py`
- `agents-backend/src/agents/retry_compactor.py`

Recommended:
- `agents-backend/src/agents/reasoning_architect.py` (refactor to structured role)

Tests to add:
- `agents-backend/tests/test_complex_router.py`
- `agents-backend/tests/test_execution_contract.py`
- `agents-backend/tests/test_plan_critic.py`
- `agents-backend/tests/test_retry_compactor.py`
- `agents-backend/tests/test_complex_subgraph_integration.py`


## 14) Immediate Next Actions

1. Implement Milestone 1 (router + flags + state additions).
2. Create `ExecutionContract` schema and validator utilities.
3. Build Plan Mode orchestrator with three read-only subagents.
4. Add critic node and wire reject/pass routing.
5. Lock complex Act Mode to contract-only edits.


## 15) Expected Outcome

After this migration, complex backport retries will be:
- more deterministic
- less token-expensive
- less prone to duplicate/malformed edits
- better at converging from concrete diagnostics

This preserves the strengths of H-MABS while upgrading the weakest part (complex reasoning/planning loop) with proven Claude-style architecture patterns.
