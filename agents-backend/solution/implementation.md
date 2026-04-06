This is a solid architectural diagnosis. Gemini's plan is conceptually right but vague on specifics. Let me give you a battle-tested implementation plan grounded in what's actually failing in your logs.

## What's Actually Breaking (Root Cause Analysis)

From `crate_3d3bf842/log.txt`, the failure cascade is:

1. Agent 3 hits tool budget (19 calls > 12 limit) because it spends 8 calls on `manage_todo` before doing real work
2. The ReAct agent searches `forInsert` in `ColumnIndexWriterProjection.java` — wrong file entirely
3. Planning Agent outputs unverified `old_string` anchors that don't exist in target files
4. No semantic separation between "what needs to change" and "where to find it"

The core architectural bug: **Agent 3 is a surgeon who also has to do their own pre-op imaging**. That's what's killing you.

---

## The Real Architecture

Gemini's plan is right about decoupling but wrong about *where* to put the reasoning. Here's the precise design:

```
VALIDATION FAILURE
      │
      ▼
  FailureRouter
      │
  ┌───┴──────────────────────┐
  │                          │
TYPE_I/II               TYPE_III/IV/V
(anchor_not_found)      (signature_drift, logic_moved)
      │                          │
      ▼                          ▼
PlanRepairAgent            ReasoningArchitect
(lightweight patch)        (full diagnosis loop)
      │                          │
      └──────────┬───────────────┘
                 ▼
          DeterministicEditor
          (zero reasoning, pure execution)
```

The **ReasoningArchitect** is the new brain. It runs per-file in isolation. It outputs a `SurgicalPlan` — a typed, verified list of `{old_string, new_string, anchor_verified: True}` operations. **Only verified anchors pass through.**

The **DeterministicEditor** is a neutered executor. It runs `claw_file_editor.edit_file()` in a loop. No LLM. No tools. Pure Python string replacement. If `old_string not in file_content` → instant bounce back to ReasoningArchitect with a structured error.

---

## Implementation Plan

### Phase 1: State Schema Extension

```python
# src/state.py additions

class SurgicalOp(TypedDict):
    target_file: str
    old_string: str           # verified to exist in file
    new_string: str
    anchor_verified: bool     # MUST be True to execute
    verification_method: str  # "exact" | "grep_confirmed" | "ast_boundary"
    confidence: float         # 0.0-1.0

class ReasoningContext(TypedDict):
    current_file: str
    failure_kind: str         # "signature_drift" | "logic_moved" | "anchor_not_found"
    build_diagnostics: dict
    iteration: int
    surgical_ops: List[SurgicalOp]

# Add to AgentState:
reasoning_context: NotRequired[ReasoningContext]
surgical_plans: NotRequired[Dict[str, List[SurgicalOp]]]  # per target_file
reasoning_iterations: NotRequired[int]
```

### Phase 2: The ReasoningArchitect Agent

This is the core. The key insight is **per-file isolated subgraph with forced tool sequencing**.

```python
# src/agents/reasoning_architect.py

_REASONING_SYSTEM = """You are the H-MABS Reasoning Architect.

Your ONLY job: produce a SurgicalPlan for ONE file.

[HARD CONSTRAINTS]
- You cannot edit files. Ever.
- Every old_string you submit MUST be confirmed via read_target_code_window or grep_in_file first.
- If you cannot confirm an anchor exists, you submit it with anchor_verified=False and confidence=0.
- You must diagnose BEFORE planning. Always call diagnose_api_drift first.

[THINKING PROTOCOL]
Before EVERY tool call, output your reasoning:
<thinking>
What failure am I diagnosing?
What exact code do I need to see?
What is the specific string I'm replacing?
</thinking>

[FILE ISOLATION]
You are working on: {current_file}
Ignore all other files. If you find yourself thinking about another file, stop.

[FAILURE CONTEXT]
{build_diagnostics}

[PATCH INTENT]
{patch_intent}

[OUTPUT CONTRACT]
Call submit_surgical_plan when you have ALL operations verified.
Do not call it until every op has anchor_verified=True.
"""
```

The toolset for this agent is **strictly scoped**:

```python
REASONING_TOOLS = [
    "diagnose_api_drift",        # runs FailureDiagnosisEngine on current_file only
    "read_target_code_window",   # reads lines N±radius from current_file
    "grep_in_target_file",       # searches current_file only (not repo-wide)
    "get_method_signature",      # returns exact signature from AST
    "compare_mainline_target",   # shows side-by-side mainline vs target for ONE method
    "submit_surgical_plan",      # terminal action - outputs SurgicalOp list
]
```

**Critical**: No `grep_repo`, no cross-file reads, no `get_dependency_graph`. The agent cannot even accidentally look at the wrong file.

```python
async def reasoning_architect_node(state: AgentState, config) -> dict:
    """
    Runs ONCE PER FILE. Called in a loop from the router.
    Returns surgical_plans keyed by target_file.
    """
    failed_files = state.get("validation_retry_files") or []
    surgical_plans = {}
    
    for target_file in failed_files:
        # CLEAN SLATE: per-file isolation
        file_context = _build_file_context(state, target_file)
        file_toolkit = FileIsolatedToolkit(
            target_repo_path=state["target_repo_path"],
            target_file=target_file,  # locks all tools to this file
            mainline_repo_path=state["mainline_repo_path"],
            build_diagnostics=state.get("validation_error_context", ""),
        )
        
        agent = create_react_agent(
            llm, 
            tools=file_toolkit.get_tools(),
            prompt=_REASONING_SYSTEM.format(
                current_file=target_file,
                build_diagnostics=_extract_file_diagnostics(
                    state.get("validation_error_context", ""), 
                    target_file
                ),
                patch_intent=state.get("semantic_blueprint", {}).get("fix_logic", ""),
            )
        )
        
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=f"Diagnose and plan repairs for {target_file}")]},
            config={"recursion_limit": 20}  # tight budget
        )
        
        # Extract the plan from submit_surgical_plan tool call
        plan = _extract_surgical_plan(result)
        if plan:
            surgical_plans[target_file] = plan
    
    return {
        "surgical_plans": surgical_plans,
        "messages": [HumanMessage(content=f"Reasoning complete for {len(surgical_plans)} file(s)")]
    }
```

### Phase 3: FileIsolatedToolkit

This is the key innovation — a toolkit that **physically cannot read the wrong file**:

```python
class FileIsolatedToolkit:
    def __init__(self, target_repo_path, target_file, mainline_repo_path, build_diagnostics):
        self.repo = target_repo_path
        self.locked_file = target_file   # ALL reads go to this file only
        self.mainline = mainline_repo_path
        self.diagnostics = build_diagnostics
        self._hg_toolkit = HunkGeneratorToolkit(target_repo_path)
    
    def read_target_code_window(self, center_line: int, radius: int = 20) -> str:
        """Read a window of the TARGET FILE ONLY."""
        return self._hg_toolkit.read_file_window(
            self.locked_file, center_line, radius
        )
    
    def grep_in_target_file(self, search_text: str) -> str:
        """Grep in TARGET FILE ONLY. Cannot search other files."""
        return self._hg_toolkit.grep_in_file(
            self.locked_file, search_text
        )
    
    def diagnose_api_drift(self) -> dict:
        """
        Run FailureDiagnosisEngine scoped to this file.
        Returns structured diagnosis: signature changes, missing symbols, etc.
        """
        engine = FailureDiagnosisEngine(self.repo, self.mainline)
        # Extract the failed symbol from build diagnostics
        failed_symbol = _extract_primary_symbol_from_diagnostics(
            self.diagnostics, self.locked_file
        )
        return engine.diagnose(
            target_file=self.locked_file,
            failed_old_string="",
            failed_symbol=failed_symbol,
            build_error=self.diagnostics,
        ).to_dict()
    
    def get_method_signature(self, method_name: str) -> str:
        """Get exact current signature of a method in the target file."""
        content = _load_file_text(self.repo, self.locked_file)
        # Use regex to find exact signature
        pattern = re.compile(
            rf"(?:public|protected|private)[^{{]*\b{re.escape(method_name)}\s*\([^{{]*\)",
            re.MULTILINE
        )
        matches = list(pattern.finditer(content))
        if not matches:
            return f"Method {method_name} not found in {self.locked_file}"
        lines = content.splitlines()
        results = []
        for m in matches[:3]:
            line_no = content[:m.start()].count('\n') + 1
            results.append(f"Line {line_no}: {m.group(0).strip()}")
        return "\n".join(results)
    
    def submit_surgical_plan(self, operations: list[dict]) -> str:
        """
        Terminal action. Validates operations and stores them.
        Each op must have: old_string, new_string, anchor_verified, confidence.
        """
        # Store on toolkit instance for extraction
        self._submitted_plan = operations
        
        verified = sum(1 for op in operations if op.get("anchor_verified"))
        unverified = len(operations) - verified
        
        if unverified > 0:
            return (
                f"WARNING: {unverified}/{len(operations)} operations are unverified. "
                "Verify anchors with grep_in_target_file before submitting."
            )
        
        return f"Plan submitted: {len(operations)} verified operations for {self.locked_file}"
    
    def get_tools(self):
        return [
            StructuredTool.from_function(self.read_target_code_window, name="read_target_code_window"),
            StructuredTool.from_function(self.grep_in_target_file, name="grep_in_target_file"),
            StructuredTool.from_function(self.diagnose_api_drift, name="diagnose_api_drift"),
            StructuredTool.from_function(self.get_method_signature, name="get_method_signature"),
            StructuredTool.from_function(self.submit_surgical_plan, name="submit_surgical_plan"),
        ]
```

### Phase 4: Neutered DeterministicEditor

Replace the ReAct loop in `file_editor.py` with this:

```python
def _execute_surgical_plan(
    surgical_ops: list[SurgicalOp],
    target_file: str,
    target_repo_path: str,
    toolkit: HunkGeneratorToolkit,
) -> tuple[bool, str, list[FileEdit]]:
    """
    Pure deterministic execution. Zero LLM calls.
    Returns (success, failure_reason, applied_edits).
    """
    edits = []
    
    # Pre-flight: verify ALL anchors exist before touching anything
    full_path = os.path.join(target_repo_path, target_file)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"file_read_error:{e}", []
    
    for i, op in enumerate(surgical_ops):
        if not op.get("anchor_verified"):
            return False, f"op_{i}_not_verified", []
        
        old_string = op["old_string"]
        if old_string not in content:
            # Structured bounce-back: tells ReasoningArchitect exactly what failed
            return False, json.dumps({
                "type": "anchor_not_found",
                "operation_index": i,
                "failed_old_string_preview": old_string[:120],
                "target_file": target_file,
            }), []
    
    # All anchors verified — now execute
    for i, op in enumerate(surgical_ops):
        result = toolkit.str_replace_in_file(
            target_file, 
            op["old_string"], 
            op["new_string"]
        )
        if not result.startswith("SUCCESS"):
            return False, f"op_{i}_apply_failed:{result}", edits
        
        edits.append({
            "target_file": target_file,
            "old_string": op["old_string"],
            "new_string": op["new_string"],
            "edit_type": "replace",
            "verified": True,
            "verification_result": op.get("verification_method", "exact"),
            "applied": True,
            "apply_result": result,
        })
        
        # Re-read content after each edit to prevent stale state
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
    
    return True, "success", edits
```

Then in `file_editor_node`:

```python
# Replace the entire deterministic/ReAct decision block with:
surgical_plans = state.get("surgical_plans") or {}
plan_for_file = surgical_plans.get(target_file) or plan_entries  # fallback to planner

if surgical_plans.get(target_file):
    # Fast path: reasoning architect already did the hard work
    ok, reason, edits = _execute_surgical_plan(
        surgical_ops=surgical_plans[target_file],
        target_file=target_file,
        target_repo_path=target_repo_path,
        toolkit=toolkit,
    )
    if not ok:
        # Bounce back: structured failure for next reasoning iteration
        task_entry["status"] = "failed"
        task_entry["reason"] = "surgical_plan_execution_failed"
        task_entry["error"] = reason
        _git_reset_file(target_repo_path, target_file)
        continue
    adapted_file_edits.extend(edits)
else:
    # Original deterministic/ReAct path for non-TYPE_V cases
    # ... existing code ...
```

### Phase 5: Graph Rewiring

```python
# src/graph.py

workflow.add_node("reasoning_architect", reasoning_architect_node)

def route_validation(state: AgentState) -> str:
    passed = state.get("validation_passed", False)
    attempts = state.get("validation_attempts", 0)
    
    if passed:
        return "END"
    
    if attempts >= MAX_VALIDATION_ATTEMPTS:
        return "END"
    
    failure_category = state.get("validation_failure_category", "")
    complexity = state.get("patch_complexity", "REWRITE").upper()
    failed_stage = state.get("validation_failed_stage", "")
    
    # Route to reasoning architect for complex failures
    needs_reasoning = (
        complexity in {"REWRITE"}
        and failure_category == "context_mismatch"
        and (
            "api_or_signature_mismatch" in _get_build_issue_types(state)
            or failed_stage == "generation_contract_failed"
            or bool(state.get("force_type_v_until_success"))
        )
        # Don't route to reasoning if it already ran and failed identically
        and not bool(state.get("validation_repeated_patch_detected"))
    )
    
    if needs_reasoning:
        print(f"Router: Routing to reasoning_architect (complexity={complexity}, category={failure_category})")
        return "reasoning_architect"
    
    # ... rest of existing routing logic ...

# Wire it up:
workflow.add_conditional_edges(
    "validation",
    route_validation,
    {
        "END": END,
        "structural_locator": "structural_locator",
        "planning_agent": "planning_agent",
        "hunk_generator": "hunk_generator",
        "reasoning_architect": "reasoning_architect",  # NEW
    }
)

workflow.add_edge("reasoning_architect", "hunk_generator")
```

---

## The Fix for Your Specific Failure

Here's what happens to `crate_3d3bf842` under the new architecture:

**Step 1** — Validation fails: `api_or_signature_mismatch`, `REWRITE` complexity. Router sends to `reasoning_architect`.

**Step 2** — ReasoningArchitect boots for `ColumnIndexWriterProjection.java` **only**. System prompt is locked to that file. The `FileIsolatedToolkit` physically cannot read `ShardUpsertRequest.java`.

**Step 3** — Agent calls `diagnose_api_drift()`. Gets back: `FailureKind.SIGNATURE_CHANGED`, `symbol='ColumnIndexWriterProjection'`, `new_signature` contains `long fullDocSizeEstimate` at position 14.

**Step 4** — Agent calls `get_method_signature("ColumnIndexWriterProjection")`. Gets back exact target constructor at line 67-80 with exact whitespace.

**Step 5** — Agent calls `grep_in_target_file("List<Symbol> returnValues)")` to confirm the anchor. Gets: `Line 80: List<Symbol> returnValues) {`. Anchor confirmed.

**Step 6** — Agent calls `submit_surgical_plan` with:
```json
{
  "old_string": "                                       List<? extends Symbol> outputs,\n                                       List<Symbol> returnValues) {",
  "new_string": "                                       List<? extends Symbol> outputs,\n                                       List<Symbol> returnValues,\n                                       long fullDocSizeEstimate) {",
  "anchor_verified": true,
  "verification_method": "grep_confirmed",
  "confidence": 0.98
}
```

**Step 7** — DeterministicEditor runs `claw_file_editor.edit_file()`. `old_string in content` → True. Replace executes. Done in 2 Python lines.

**Total tool calls: 4. No hallucination. No cross-file contamination. No budget overflow.**

---

## What NOT to Do (Gemini's Mistakes)

1. **Don't delete the ReAct loop from Agent 3 entirely.** You still need it for TYPE_I-IV cases where ReasoningArchitect never runs. Keep the existing path, just add the surgical plan fast-path above it.

2. **Don't add `<thinking>` tags as literal XML in the prompt.** Modern Claude handles CoT internally. The `<thinking>` instruction is for older GPT models. For Claude, use `extended_thinking` or just structure the reasoning through tool-call sequencing.

3. **Don't make one reasoning agent handle all files simultaneously.** The per-file isolation is the whole point. Run it sequentially or with `asyncio.gather` but with truly isolated state per file.

4. **Don't skip the pre-flight anchor verification in DeterministicEditor.** Verify ALL anchors before touching ANY file. Partial application with a mid-run failure leaves files in broken states.

---

## Implementation Priority

Start with these in order:

1. `FileIsolatedToolkit` — 2-3 hours. This is the highest-leverage change. It alone stops the cross-file contamination bug.

2. `_execute_surgical_plan` in `file_editor.py` — 1 hour. Add it above the existing deterministic path, conditional on `surgical_plans` being populated.

3. `reasoning_architect_node` — 3-4 hours. Wire it to use `FileIsolatedToolkit` and output `SurgicalPlan`.

4. Graph rewiring — 1 hour. Add the node and routing condition.

5. State schema extension — 30 minutes.

Total: one focused engineering day gets you a working prototype. The `crate_3d3bf842` patch should pass on retry #1 under the new architecture.