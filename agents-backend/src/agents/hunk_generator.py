"""
Agent 3: Hunk Generator (The Surgeon)

H-MABS Phase 3 — Full Implementation.

Goal: Rewrite the mainline patch hunks surgically, hunk-by-hunk, to fit the
target repository's structure and naming conventions.

Key inputs from state:
  - semantic_blueprint:     Fix intent (Agent 1)
  - consistency_map:        Symbol renames (Agent 2)
  - mapped_target_context:  Exact insertion points (Agent 2)
  - patch_analysis:         Original FileChange list
  - patch_diff:             Raw diff text
  - validation_attempts:    Retry counter (0 = fresh run)
  - validation_error_context: Error logs injected on retry

Key outputs to state:
  - adapted_code_hunks:   list[AdaptedHunk]
  - adapted_test_hunks:   list[AdaptedHunk]
"""

import re
import json
import os
from langchain_core.messages import HumanMessage, SystemMessage
from state import AgentState, AdaptedHunk, SemanticBlueprint
from utils.patch_analyzer import PatchAnalyzer
from utils.llm_provider import get_llm
from agents.validation_tools import ValidationToolkit


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

_HUNK_REWRITE_SYSTEM = """You are an expert Java patch adapter specializing in backporting security fixes.

Your task is to rewrite a single unified diff hunk so it applies cleanly to an older version of a Java file.

Rules (follow ALL of them strictly):
1. Only modify the `+` lines (additions). Context lines (` ` prefixed) must stay unchanged.
2. Apply every symbol rename from the ConsistencyMap exactly.
3. Preserve the fix intent described in the SemanticBlueprint — this fix MUST still work.
4. Adjust the @@ line numbers to match the target file's insertion_line.
5. Output ONLY the unified diff hunk. Start with @@ and end with the last changed line.
6. Do NOT include any explanation, markdown fences, or comments outside the hunk."""


_HUNK_REWRITE_USER = """\
## Mainline Hunk (what you need to adapt)
```diff
{mainline_hunk}
```

## Target Method Body (where this hunk will be inserted)
```java
{target_method_body}
```

## ConsistencyMap (apply these renames to + lines)
{consistency_map}

## Fix Intent (SemanticBlueprint)
- Fix Logic: {fix_logic}
- Dependent APIs: {dependent_apis}

## Insertion Point in Target File
Line {insertion_line} in `{target_file}`

{retry_context}
Rewrite the hunk now. Output ONLY the unified diff block starting with @@."""


_TEST_HUNK_REWRITE_USER = """\
## Mainline Test Hunk (what you need to adapt)
```diff
{mainline_hunk}
```

## Target Test File Location
`{target_test_file}`

## ConsistencyMap (apply these renames)
{consistency_map}

## Root Cause Being Fixed (the test must target this)
{root_cause}

{retry_context}
Rewrite the test hunk to exercise the same vulnerability in the target codebase.
Output ONLY the unified diff block starting with @@."""


_BLUEPRINT_CHECK_SYSTEM = """You are a code reviewer verifying that a patch hunk preserves a specific fix intent.
Answer ONLY "YES" if the hunk correctly implements the fix logic, or "NO: <one-line reason>" if it does not."""


_BLUEPRINT_CHECK_USER = """\
## Generated Hunk
```diff
{generated_hunk}
```

## Expected Fix Logic
{fix_logic}

## Critical APIs That Must Appear
{dependent_apis}

Does the generated hunk correctly implement the fix logic? Answer YES or NO."""


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _extract_hunk_block(raw: str) -> str | None:
    """
    Extracts the first unified diff hunk (@@-prefixed block) from an LLM response.
    Strips markdown fences if present. Returns None if no valid hunk found.
    
    Important: Preserves all context lines and trailing whitespace needed for a valid patch.
    """
    if not raw:
        return None

    # Strip markdown code fences
    text = raw.strip()
    if "```" in text:
        # Extract content between first and last fence
        inner_lines = []
        in_fence = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                inner_lines.append(line)
        text = "\n".join(inner_lines).strip()

    # Find the first @@ line
    lines = text.splitlines()
    hunk_start = None
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            hunk_start = i
            break

    if hunk_start is None:
        return None

    # Collect hunk lines from @@ onwards
    # A hunk ends when we encounter a new file header OR when we've consumed all valid diff lines
    hunk_lines = []
    for line in lines[hunk_start:]:
        # Stop at new file/section headers (but these shouldn't appear in valid LLM output)
        if line.startswith("diff --git"):
            if hunk_lines:  # only break if we already have some hunk content
                break
        hunk_lines.append(line)

    if not hunk_lines:
        return None

    result = "\n".join(hunk_lines)
    # Ensure the result ends with a newline for proper unified diff format
    if not result.endswith("\n"):
        result += "\n"
    return result


async def _check_intent(
    llm,
    hunk_text: str,
    blueprint: SemanticBlueprint,
) -> bool:
    """
    Sends a short verification prompt to the LLM asking if the generated hunk
    preserves the SemanticBlueprint's fix intent. Returns True on YES, False on NO.
    Fails open (returns True) on exception.
    """
    messages = [
        SystemMessage(content=_BLUEPRINT_CHECK_SYSTEM),
        HumanMessage(
            content=_BLUEPRINT_CHECK_USER.format(
                generated_hunk=hunk_text[:1500],
                fix_logic=blueprint.get("fix_logic", ""),
                dependent_apis=", ".join(blueprint.get("dependent_apis", [])),
            )
        ),
    ]
    try:
        response = await llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip().upper().startswith("YES")
    except Exception as e:
        print(f"    Agent 3: Blueprint check LLM call failed ({e}) — failing open.")
        return True


def _format_consistency_map(cm: dict) -> str:
    """
    Pretty-prints a ConsistencyMap for injection into an LLM prompt.
    Returns '(none)' if the map is empty.
    """
    if not cm:
        return "(none — no renames detected)"
    lines = [f"  {old} → {new}" for old, new in cm.items()]
    return "\n".join(lines)


def _rewrite_hunk_symbols(hunk_text: str, consistency_map: dict) -> str:
    """
    Deterministic pre-pass: applies ConsistencyMap renames to the + lines of a hunk.
    This reduces LLM hallucination by giving it pre-renamed text to refine.

    Only replaces whole-word occurrences to avoid partial matches.
    """
    if not consistency_map or not hunk_text:
        return hunk_text

    result_lines = []
    for line in hunk_text.splitlines():
        if line.startswith("+"):
            for old, new in consistency_map.items():
                line = re.sub(rf"\b{re.escape(old)}\b", new, line)
        result_lines.append(line)
    return "\n".join(result_lines) + "\n"


def _adjust_hunk_header(hunk_text: str, target_start_line: int) -> str:
    """
    Rewrites the @@ header of a hunk to anchor it at target_start_line.
    Recalculates the line counts (-count/+count) based on actual hunk content.
    """
    if not hunk_text or target_start_line is None:
        return hunk_text

    lines = hunk_text.splitlines()
    if not lines or not lines[0].startswith("@@"):
        return hunk_text

    # Parse existing header: @@ -a,b +c,d @@  <optional context>
    header = lines[0]
    m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", header)
    if not m:
        return hunk_text

    ctx = m.group(5)  # trailing comment

    # Count actual diff lines from body
    removed_count = 0
    added_count = 0
    context_count = 0
    
    for line in lines[1:]:
        if line.startswith("-"):
            removed_count += 1
        elif line.startswith("+"):
            added_count += 1
        elif line.startswith(" "):
            context_count += 1
        # Empty lines within the hunk body (just "") are part of the hunk, skip trailing empty
    
    # Calculate the correct counts
    src_count = context_count + removed_count
    tgt_count = context_count + added_count
    
    # Handle edge case: if counts are 0, default to 1
    if src_count == 0:
        src_count = 1
    if tgt_count == 0:
        tgt_count = 1

    new_header = f"@@ -{target_start_line},{src_count} +{target_start_line},{tgt_count} @@{ctx}"
    return "\n".join([new_header] + lines[1:]) + "\n"


# ---------------------------------------------------------------------------
# Core Agent Node
# ---------------------------------------------------------------------------

async def hunk_generator_node(state: AgentState, config) -> dict:
    """
    Agent 3 node function.

    Iterates over every modified hunk in the patch, rewrites it for the target
    via LLM, validates format (dry-run) and intent (blueprint check), and
    stores the results as AdaptedHunk lists.
    """
    print("Agent 3 (Hunk Generator): Starting surgical hunk rewrite...")

    consistency_map: dict = state.get("consistency_map") or {}
    mapped_target_context: dict = state.get("mapped_target_context") or {}
    semantic_blueprint: SemanticBlueprint = state.get("semantic_blueprint")
    patch_analysis: list = state.get("patch_analysis") or []
    patch_diff: str = state.get("patch_diff") or ""
    target_repo_path: str = state.get("target_repo_path", "")
    validation_attempts: int = state.get("validation_attempts") or 0
    error_context: str = state.get("validation_error_context") or ""
    with_test_changes: bool = state.get("with_test_changes", False)

    if not semantic_blueprint:
        msg = "Agent 3 Error: No semantic_blueprint in state. Agents 1 & 2 must run first."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    if not patch_diff:
        msg = "Agent 3 Error: No patch_diff in state."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # Retry feedback injection
    retry_context_str = ""
    if validation_attempts > 0 and error_context:
        retry_context_str = (
            f"## RETRY #{validation_attempts} — Previous Validation Failed\n"
            f"```\n{error_context[:600]}\n```\n"
            f"Adjust the hunk to fix the above error.\n"
        )
        print(f"  Agent 3: Retry #{validation_attempts} — injecting validation error into prompts.")

    # ------------------------------------------------------------------
    # Setup tools
    # ------------------------------------------------------------------
    # Setup LLM
    llm = get_llm(temperature=0)
    
    analyzer = PatchAnalyzer()
    raw_hunks_by_file = analyzer.extract_raw_hunks(patch_diff, with_test_changes=with_test_changes) if patch_diff else {}
    toolkit = ValidationToolkit(target_repo_path) if target_repo_path else None

    fix_logic = semantic_blueprint.get("fix_logic", "")
    dependent_apis = semantic_blueprint.get("dependent_apis", [])
    root_cause = semantic_blueprint.get("root_cause_hypothesis", "")
    cm_formatted = _format_consistency_map(consistency_map)

    # ------------------------------------------------------------------
    # Segregate changes
    # ------------------------------------------------------------------
    code_changes = [fc for fc in patch_analysis
                    if not (fc.is_test_file if hasattr(fc, "is_test_file") else fc.get("is_test_file", False))]
    test_changes = [fc for fc in patch_analysis
                    if (fc.is_test_file if hasattr(fc, "is_test_file") else fc.get("is_test_file", False))]
    
    # Filter test changes based on with_test_changes flag
    if not with_test_changes:
        test_changes = []

    print(f"  Agent 3: {len(code_changes)} code file(s), {len(test_changes)} test file(s) to process.")

    # --- Early Exit: If Agent 2 produced no mappings and we're on a retry, abort ---
    # If there are code files but no mapped context, and this is a retry, don't loop endlessly.
    if code_changes and not mapped_target_context and validation_attempts > 0:
        print(f"  Agent 3: Aborting retry — Agent 2 has no target context and retrying won't help.")
        return {
            "messages": [HumanMessage(content="Agent 3: No target context from Agent 2. Cannot proceed.")],
            "adapted_code_hunks": [],
            "adapted_test_hunks": [],
            "validation_passed": False,  # Signal validation failure to exit loop
            "validation_attempts": validation_attempts,
            "validation_error_context": "Agent 3 Early Exit: Agent 2 failed to map files. No source context available for hunk generation."
        }

    adapted_code_hunks: list[AdaptedHunk] = []
    adapted_test_hunks: list[AdaptedHunk] = []
    trace = "# Hunk Generator Trace\n\n"
    trace += f"| target_file | hunk_index | dry_run | intent_ok |\n|---|---|---|---|\n"

    # ------------------------------------------------------------------
    # Code hunk processing
    # ------------------------------------------------------------------
    for change in code_changes:
        mainline_file = change.file_path if hasattr(change, "file_path") else change.get("file_path", "?")
        mapped_ctx = mapped_target_context.get(mainline_file)
        raw_hunks = raw_hunks_by_file.get(mainline_file, [])

        if not mapped_ctx:
            print(f"  Agent 3: Skipping {mainline_file} — no target context from Agent 2.")
            continue

        target_file = mapped_ctx.get("target_file", mainline_file)
        insertion_line = mapped_ctx.get("start_line")
        target_body = mapped_ctx.get("code_snippet", "")
        
        # IMPROVEMENT: If insertion_line is None, try to extract from raw hunk header
        if insertion_line is None and raw_hunks:
            try:
                first_hunk = raw_hunks[0]
                # Parse @@ -X,Y +A,B @@ to get actual line numbers
                hunk_header_match = re.search(r'@@ -\d+(?:,\d+)? \+(\d+)', first_hunk)
                if hunk_header_match:
                    insertion_line = int(hunk_header_match.group(1))
                    print(f"  Agent 3: Extracted insertion_line {insertion_line} from hunk header")
            except Exception as e:
                print(f"  Agent 3: Could not extract insertion_line from hunk: {e}")
        
        # Default fallback
        insertion_line = insertion_line or 1

        print(f"  Agent 3: Rewriting {len(raw_hunks)} hunk(s) for {mainline_file} → {target_file}")

        for hunk_idx, raw_hunk in enumerate(raw_hunks):
            # Deterministic symbol substitution pre-pass
            pre_rewritten = _rewrite_hunk_symbols(raw_hunk, consistency_map)

            # LLM rewrite (up to 2 attempts)
            adapted_hunk_text = None
            for attempt in range(2):
                # Use full method body context (no truncation)
                # The LLM needs complete context to properly understand method structure,
                # boundaries, and surrounding code patterns for accurate hunk adaptation.
                # If token budget is a concern, this can be adjusted, but complete context
                # produces more accurate hunks.
                prompt = _HUNK_REWRITE_USER.format(
                    mainline_hunk=pre_rewritten,
                    target_method_body=target_body,  # Use full body, not truncated
                    consistency_map=cm_formatted,
                    fix_logic=fix_logic,
                    dependent_apis=", ".join(dependent_apis),
                    insertion_line=insertion_line,
                    target_file=target_file,
                    retry_context=retry_context_str,
                )
                try:
                    response = await llm.ainvoke([
                        SystemMessage(content=_HUNK_REWRITE_SYSTEM),
                        HumanMessage(content=prompt),
                    ])
                    raw_content = response.content if hasattr(response, "content") else str(response)
                    extracted = _extract_hunk_block(raw_content)
                    if extracted:
                        adapted_hunk_text = _adjust_hunk_header(extracted, insertion_line)
                        break
                    print(f"    Agent 3: Hunk parse failed (attempt {attempt+1}/2)")
                except Exception as e:
                    print(f"    Agent 3: LLM error on hunk {hunk_idx} (attempt {attempt+1}/2): {e}")

            if not adapted_hunk_text:
                # Fallback: use the deterministic pre-rewrite with adjusted header
                adapted_hunk_text = _adjust_hunk_header(pre_rewritten, insertion_line)
                print(f"    Agent 3: Fallback — using deterministic pre-rewrite for hunk {hunk_idx}")

            # Dry-run validation
            dry_run_ok = False
            if toolkit:
                dr = toolkit.apply_hunk_dry_run(target_file, adapted_hunk_text)
                dry_run_ok = dr["success"]
                if not dry_run_ok:
                    print(f"    Agent 3: Dry-run failed for {target_file}[{hunk_idx}]: {dr['output'][:150]}")
            else:
                dry_run_ok = True  # No toolkit → assume ok (local dev mode)

            # Blueprint intent check
            intent_ok = await _check_intent(llm, adapted_hunk_text, semantic_blueprint)
            if not intent_ok:
                print(f"    Agent 3: Blueprint check failed for {target_file}[{hunk_idx}] — flagging.")

            hunk: AdaptedHunk = {
                "target_file": target_file,
                "mainline_file": mainline_file,
                "hunk_text": adapted_hunk_text,
                "insertion_line": insertion_line,
                "intent_verified": intent_ok,
            }
            adapted_code_hunks.append(hunk)
            trace += f"| `{target_file}` | {hunk_idx} | {'✅' if dry_run_ok else '❌'} | {'✅' if intent_ok else '❌'} |\n"

    # ------------------------------------------------------------------
    # Test hunk processing
    # ------------------------------------------------------------------
    for change in test_changes:
        mainline_test = change.file_path if hasattr(change, "file_path") else change.get("file_path", "?")
        mapped_ctx = mapped_target_context.get(f"test:{mainline_test}")
        raw_hunks = raw_hunks_by_file.get(mainline_test, [])

        target_test_file = (mapped_ctx or {}).get("target_file")
        if not target_test_file:
            print(f"  Agent 3: Skipping test {mainline_test} — no target test file (Agent 4 will synthesize).")
            continue

        print(f"  Agent 3: Rewriting {len(raw_hunks)} test hunk(s) for {mainline_test} → {target_test_file}")

        for hunk_idx, raw_hunk in enumerate(raw_hunks):
            pre_rewritten = _rewrite_hunk_symbols(raw_hunk, consistency_map)

            adapted_hunk_text = None
            for attempt in range(2):
                prompt = _TEST_HUNK_REWRITE_USER.format(
                    mainline_hunk=pre_rewritten,
                    target_test_file=target_test_file,
                    consistency_map=cm_formatted,
                    root_cause=root_cause,
                    retry_context=retry_context_str,
                )
                try:
                    response = await llm.ainvoke([
                        SystemMessage(content=_HUNK_REWRITE_SYSTEM),
                        HumanMessage(content=prompt),
                    ])
                    raw_content = response.content if hasattr(response, "content") else str(response)
                    extracted = _extract_hunk_block(raw_content)
                    if extracted:
                        adapted_hunk_text = extracted
                        break
                    print(f"    Agent 3: Test hunk parse failed (attempt {attempt+1}/2)")
                except Exception as e:
                    print(f"    Agent 3: LLM error on test hunk {hunk_idx} (attempt {attempt+1}/2): {e}")

            if not adapted_hunk_text:
                adapted_hunk_text = pre_rewritten

            dry_run_ok = False
            if toolkit:
                dr = toolkit.apply_hunk_dry_run(target_test_file, adapted_hunk_text)
                dry_run_ok = dr["success"]
            else:
                dry_run_ok = True

            hunk: AdaptedHunk = {
                "target_file": target_test_file,
                "mainline_file": mainline_test,
                "hunk_text": adapted_hunk_text,
                "insertion_line": 1,
                "intent_verified": True,  # Tests don't undergo blueprint check
            }
            adapted_test_hunks.append(hunk)
            trace += f"| `{target_test_file}` (test) | {hunk_idx} | {'✅' if dry_run_ok else '❌'} | — |\n"

    # ------------------------------------------------------------------
    # Write trace and finalize
    # ------------------------------------------------------------------
    print(
        f"Agent 3: Complete. {len(adapted_code_hunks)} code hunk(s), "
        f"{len(adapted_test_hunks)} test hunk(s) generated."
    )
    try:
        with open("hunk_generator_trace.md", "w", encoding="utf-8") as f:
            f.write(trace)
        print("  Agent 3: Trace written to hunk_generator_trace.md")
    except Exception as e:
        print(f"  Agent 3: Warning — could not write trace: {e}")

    return {
        "messages": [
            HumanMessage(
                content=(
                    f"Agent 3 complete. {len(adapted_code_hunks)} code hunk(s) and "
                    f"{len(adapted_test_hunks)} test hunk(s) adapted."
                )
            )
        ],
        "adapted_code_hunks": adapted_code_hunks,
        "adapted_test_hunks": adapted_test_hunks,
    }
