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
import difflib
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from state import AgentState, AdaptedHunk, SemanticBlueprint
from utils.patch_analyzer import PatchAnalyzer
from utils.llm_provider import get_llm
from utils.retrieval.ensemble_retriever import EnsembleRetriever
from agents.validation_tools import ValidationToolkit


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

_HUNK_REWRITE_SYSTEM = """You are an expert Java patch adapter specializing in backporting security fixes.

Your task is to adapt a mainline patch to an older version of a Java file.

Rules:
1. Preserve the fix intent described in the SemanticBlueprint.
2. Apply every symbol rename from the ConsistencyMap.
3. Output the FULL UPDATED BODY of the target method after the fix is applied.
4. If this is an import hunk (indicated in the prompt), output the new import statements only.
5. Do NOT include markdown fences, explanation, or comments outside the code."""


_HUNK_REWRITE_USER = """\
## Mainline Hunk (what you need to adapt)
```diff
{mainline_hunk}
```

## Target Method Body (Current version in target repo)
```java
{target_method_body}
```

## Surrounding Context in Target File
Before:
{context_before}
After:
{context_after}

## ConsistencyMap (apply these renames)
{consistency_map}

## Fix Intent (SemanticBlueprint)
- Fix Logic: {fix_logic}
- Dependent APIs: {dependent_apis}

{retry_context}
Based on the mainline hunk, rewrite the "Target Method Body" to include the fix. 
Output ONLY the full updated body of the method."""


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

## Developer Auxiliary Hunk Signals (tests/non-Java file ops)
{developer_aux_context}

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


def _generate_hunk_from_bodies(
    old_body: str, new_body: str, target_file: str, start_line: int
) -> str | None:
    """
    Generates a unified diff hunk between the old and new method bodies.
    Ensures technical correctness of the unified diff format.

    IMPORTANT: Preserves leading/trailing whitespace exactly — do NOT strip()
    the bodies before passing here, as that destroys Java indentation in context lines.
    """
    if not old_body and not new_body:
        return None

    # Ensure single trailing newline — but only strip trailing newlines, NOT leading whitespace
    old_body_fixed = old_body.rstrip("\n") + "\n"
    new_body_fixed = new_body.rstrip("\n") + "\n"

    old_lines = old_body_fixed.splitlines(keepends=True)
    new_lines = new_body_fixed.splitlines(keepends=True)

    # Generate diff with 3 lines of context
    diff_gen = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{target_file}",
        tofile=f"b/{target_file}",
        n=3,
    )

    lines = list(diff_gen)
    if not lines:
        return None

    # Unified diff format has 2 header lines (--- and +++) before hunks
    hunk_content = []
    found_header = False
    for line in lines:
        if line.startswith("@@"):
            found_header = True
            # Adjust the @@ header to use the actual start_line from Agent 2
            m = re.match(r"@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@(.*)", line)
            if m:
                src_count = m.group(2) or "1"
                tgt_count = m.group(4) or "1"
                ctx_info = m.group(5)
                # We anchor at the start_line provided by the locator
                # If start_line is 17, and diff says it starts at line 1 of the snippet,
                # then 17 is correct.
                line = f"@@ -{start_line},{src_count} +{start_line},{tgt_count} @@{ctx_info}\n"

        if found_header:
            # Ensure the line ends with a newline and has correct prefix
            if not line.endswith("\n"):
                line += "\n"
            hunk_content.append(line)

    if not hunk_content:
        return None

    return "".join(hunk_content)


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

    new_header = (
        f"@@ -{target_start_line},{src_count} +{target_start_line},{tgt_count} @@{ctx}"
    )
    return "\n".join([new_header] + lines[1:]) + "\n"


def _extract_target_start_line(hunk_text: str) -> int | None:
    """
    Extracts the target-side start line from a unified hunk header.
    """
    if not hunk_text:
        return None
    first_line = hunk_text.splitlines()[0] if hunk_text.splitlines() else ""
    m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", first_line)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _extract_added_lines(hunk_text: str) -> list[str]:
    """
    Returns all '+' body lines from a hunk (excluding the @@ header).
    """
    if not hunk_text:
        return []
    lines = hunk_text.splitlines()
    if not lines:
        return []
    return [line for line in lines[1:] if line.startswith("+")]


def _extract_removed_lines(hunk_text: str) -> list[str]:
    """
    Returns all '-' body lines from a hunk (excluding the @@ header).
    """
    if not hunk_text:
        return []
    lines = hunk_text.splitlines()
    if not lines:
        return []
    return [line for line in lines[1:] if line.startswith("-")]


def _read_actual_body_from_file(
    target_repo_path: str,
    target_file: str,
    insertion_line: int,
    raw_hunk: str,
) -> str:
    """
    Reads the ACTUAL lines from the target file around insertion_line,
    sized to match the original hunk's footprint (context + removed lines).

    This gives Agent 3 the true "old body" for programmatic diffing,
    instead of relying on Agent 2's code_snippet which may be stale or wrong.

    Returns the file content as a string, or empty string on failure.
    """
    if not target_repo_path or not target_file or insertion_line is None:
        return ""

    # Count how many lines the mainline hunk consumes on the source side
    # (context lines + removed lines = @@ -X,N @@ source_count)
    src_count = 0
    if raw_hunk:
        header_match = re.match(r"@@ -\d+(?:,(\d+))? \+\d+", raw_hunk)
        if header_match:
            src_count = int(header_match.group(1) or "1")

    # Default window: if hunk has no source lines, use 10
    if src_count <= 0:
        src_count = 10

    # Read the actual lines from the target file
    # Normalize path: strip leading slashes and git diff prefixes (a/ or b/)
    normalized = target_file.lstrip("/")
    if normalized.startswith("a/") or normalized.startswith("b/"):
        normalized = normalized[2:]
    full_path = os.path.join(target_repo_path, normalized)
    if not os.path.isfile(full_path):
        return ""

    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()

        start_idx = max(0, insertion_line - 1)
        end_idx = min(len(all_lines), start_idx + src_count)
        selected = all_lines[start_idx:end_idx]
        return "".join(selected)
    except Exception as e:
        print(f"    Agent 3: _read_actual_body_from_file failed: {e}")
        return ""


def _apply_hunk_deterministically(
    raw_hunk: str,
    consistency_map: dict,
    target_repo_path: str,
    target_file: str,
    insertion_line: int,
) -> str | None:
    """
    Applies a mainline hunk deterministically to the actual target file content.

    Strategy:
    1. Parse the mainline hunk into (removed_lines, added_lines, context_lines).
    2. Read the actual target file lines at insertion_line.
    3. Find where the removed lines appear in the actual file (fuzzy match by stripped content).
    4. Build new_body by replacing removed lines with added lines (with consistency map applied).
    5. Use difflib to generate the final hunk against the actual old_body.

    Returns a valid unified diff hunk string, or None if it cannot be applied.
    """
    if not raw_hunk or not target_repo_path or not target_file:
        return None

    hunk_lines = raw_hunk.splitlines()
    if not hunk_lines or not hunk_lines[0].startswith("@@"):
        return None

    # Parse source count from header
    header_match = re.match(r"@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))?", hunk_lines[0])
    src_count = int(header_match.group(1) or "1") if header_match else 10

    # Read actual file lines at insertion_line
    normalized = target_file.lstrip("/")
    if normalized.startswith("a/") or normalized.startswith("b/"):
        normalized = normalized[2:]
    full_path = os.path.join(target_repo_path, normalized)
    if not os.path.isfile(full_path):
        return None

    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            all_file_lines = f.readlines()
    except Exception:
        return None

    # Parse hunk body into removed/added/context sequences
    # Build a sequence of operations: ('context', line), ('removed', line), ('added', line)
    ops = []
    for line in hunk_lines[1:]:
        if line.startswith("-"):
            ops.append(("removed", line[1:]))
        elif line.startswith("+"):
            ops.append(("added", line[1:]))
        elif line.startswith(" "):
            ops.append(("context", line[1:]))
        # Skip lines that don't match any prefix (shouldn't happen in valid hunks)

    # Apply consistency map renames to added lines
    renamed_ops = []
    for kind, content in ops:
        if kind == "added" and consistency_map:
            for old, new in consistency_map.items():
                content = re.sub(rf"\b{re.escape(old)}\b", new, content)
        renamed_ops.append((kind, content))

    # Find the best matching window in the actual file for the removed/context lines
    # We search near insertion_line with a tolerance window
    removed_and_ctx = [
        (kind, c) for kind, c in renamed_ops if kind in ("removed", "context")
    ]
    if not removed_and_ctx:
        # Pure insertion — no context to match
        # Just insert added lines at insertion_line
        added_lines = [c for kind, c in renamed_ops if kind == "added"]
        if not added_lines:
            return None
        # Build a pure-insertion hunk
        added_with_prefix = [
            "+" + line if not line.startswith("+") else line for line in added_lines
        ]
        header = f"@@ -{insertion_line},0 +{insertion_line},{len(added_lines)} @@\n"
        body = "".join(
            (line if line.endswith("\n") else line + "\n") for line in added_with_prefix
        )
        return header + body

    # Build expected sequence of removed+context lines (stripped for matching)
    expected_stripped = [c.rstrip("\n").rstrip() for kind, c in removed_and_ctx]

    # Search for best match window in actual file
    search_start = max(0, insertion_line - 5)
    search_end = min(len(all_file_lines), insertion_line + src_count + 5)
    search_lines = all_file_lines[search_start:search_end]

    best_offset = 0
    best_score = -1
    window_size = len(expected_stripped)

    for offset in range(len(search_lines) - window_size + 1):
        window = search_lines[offset : offset + window_size]
        score = sum(
            1
            for exp, actual in zip(expected_stripped, window)
            if exp == actual.rstrip("\n").rstrip()
        )
        if score > best_score:
            best_score = score
            best_offset = offset

    # Determine actual start in full file
    actual_start_in_file = search_start + best_offset  # 0-indexed

    # Build old_body: the actual file lines that the hunk footprint covers
    old_body_lines = all_file_lines[
        actual_start_in_file : actual_start_in_file + src_count
    ]
    old_body = "".join(old_body_lines)

    # Build new_body by applying the hunk operations to the actual file content
    # Walk through ops and replace removed lines with actual file lines when they match
    new_body_lines = []
    file_cursor = actual_start_in_file  # points into all_file_lines

    for kind, content in renamed_ops:
        if kind == "context":
            # Keep the actual file line (preserves indentation exactly)
            if file_cursor < len(all_file_lines):
                new_body_lines.append(all_file_lines[file_cursor])
                file_cursor += 1
            else:
                new_body_lines.append(
                    content if content.endswith("\n") else content + "\n"
                )
        elif kind == "removed":
            # Skip the actual file line (it's being replaced/deleted)
            file_cursor += 1
        elif kind == "added":
            # Insert the new line (with consistency map already applied)
            new_body_lines.append(content if content.endswith("\n") else content + "\n")

    new_body = "".join(new_body_lines)

    # Use difflib to generate the final clean hunk
    actual_start_line = actual_start_in_file + 1  # 1-indexed
    result = _generate_hunk_from_bodies(
        old_body, new_body, target_file, actual_start_line
    )
    return result
    """
    Counts ' ' context lines in a unified diff hunk body.
    """
    if not hunk_text:
        return 0
    lines = hunk_text.splitlines()
    if not lines:
        return 0
    return sum(1 for line in lines[1:] if line.startswith(" "))


def _is_structurally_risky_candidate(
    base_hunk: str,
    candidate_hunk: str,
    *,
    operation: str,
    is_import_hunk: bool,
    is_declaration_or_class_hunk: bool,
) -> bool:
    """
    Rejects aggressive fallback hunks that are likely to apply at the wrong
    location (typically EOF) while still passing `git apply --check`.

    Risk patterns for MODIFIED files:
    - base has removals but candidate removes nothing
    - declaration/import hunks lost all context anchors
    - candidate is pure insertion despite base carrying context anchors
    """
    if (operation or "MODIFIED").upper() != "MODIFIED":
        return False

    base_removed = len(_extract_removed_lines(base_hunk))
    cand_removed = len(_extract_removed_lines(candidate_hunk))
    base_context = _count_context_lines(base_hunk)
    cand_context = _count_context_lines(candidate_hunk)

    # If base hunk replaces existing lines, candidate must preserve removals.
    if base_removed > 0 and cand_removed == 0:
        return True

    # Import/class-level hunks are anchor-sensitive and should keep context.
    if (is_import_hunk or is_declaration_or_class_hunk) and cand_context == 0:
        return True

    # Pure insertion fallback for a context-anchored base hunk is unsafe.
    if base_context > 0 and cand_context == 0 and cand_removed == 0:
        return True

    return False


def _to_context_free_hunk(hunk_text: str, target_start_line: int) -> str | None:
    """
    Build a context-free fallback hunk using only +/- lines.

    This helps when patch application fails due surrounding context drift while
    the changed lines themselves are still valid.
    """
    if not hunk_text:
        return None
    lines = hunk_text.splitlines()
    if not lines or not lines[0].startswith("@@"):
        return None

    body = [ln for ln in lines[1:] if ln.startswith("+") or ln.startswith("-")]
    if not body:
        return None

    removed = sum(1 for ln in body if ln.startswith("-"))
    added = sum(1 for ln in body if ln.startswith("+"))

    src_count = removed
    tgt_count = added

    header = f"@@ -{target_start_line},{src_count} +{target_start_line},{tgt_count} @@"
    out = "\n".join([header] + body)
    if not out.endswith("\n"):
        out += "\n"
    return out


def _to_addition_only_hunk(hunk_text: str, target_start_line: int) -> str | None:
    """
    Build an insertion-only fallback hunk from '+' lines.

    This is the last resort when replacement hunks cannot be applied cleanly.
    """
    plus_lines = _extract_added_lines(hunk_text)
    if not plus_lines:
        return None
    header = f"@@ -{target_start_line},0 +{target_start_line},{len(plus_lines)} @@"
    out = "\n".join([header] + plus_lines)
    if not out.endswith("\n"):
        out += "\n"
    return out


def _is_suspicious_plus_rewrite(
    base_hunk: str,
    candidate_hunk: str,
    consistency_map: dict,
) -> bool:
    """
    Guardrail against semantic drift in LLM rewrites.

    If a rewrite introduces unexpected numeric literals (common hallucination
    pattern from PR numbers/issue IDs) or diverges too far from the base '+'
    lines without any consistency-map pressure, prefer deterministic fallback.
    """
    base_plus = [ln[1:] for ln in _extract_added_lines(base_hunk)]
    cand_plus = [ln[1:] for ln in _extract_added_lines(candidate_hunk)]

    if not base_plus or len(base_plus) != len(cand_plus):
        return False

    base_text = "\n".join(base_plus)
    cand_text = "\n".join(cand_plus)
    if base_text == cand_text:
        return False

    base_nums = set(re.findall(r"\b\d+\b", base_text))
    cand_nums = set(re.findall(r"\b\d+\b", cand_text))
    unexpected_numeric = [n for n in (cand_nums - base_nums) if len(n) >= 4]
    if unexpected_numeric:
        return True

    if not consistency_map:
        similarity = difflib.SequenceMatcher(None, base_text, cand_text).ratio()
        if similarity < 0.6:
            return True

    return False


def _is_import_only_hunk(hunk_text: str) -> bool:
    """
    Detects if a hunk contains ONLY import statements (no other code).
    Used to identify hunks that should be handled conservatively without LLM rewriting.
    """
    if not hunk_text:
        return False
    lines = hunk_text.splitlines()
    if not lines or not lines[0].startswith("@@"):
        return False

    # Check if all non-header, non-whitespace lines are import statements or empty
    for line in lines[1:]:
        stripped = line.lstrip()
        if not stripped:  # empty line
            continue
        if stripped.startswith("//"):  # comment
            continue
        # Check if line is an import statement (in any of +, -, or space formats)
        content = (
            stripped[1:].strip()
            if len(stripped) > 1 and stripped[0] in {"+", "-", " "}
            else stripped
        )
        if content and not content.startswith("import "):
            return False

    return True


def _extract_imports_from_body(target_body: str) -> str:
    """
    Extracts all import statements from a Java file body snippet for reference.
    This provides context to the LLM so it knows what imports already exist.
    """
    if not target_body:
        return "(No imports found in target context)"

    imports = []
    for line in target_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            imports.append(stripped)

    if not imports:
        return "(No imports found in target context)"

    return "Existing imports:\n- " + "\n- ".join(imports)


def _extract_auxiliary_signals(
    developer_aux_hunks: list[dict[str, Any]],
) -> tuple[dict[str, str], str]:
    """
    Derive conservative rename/file-op hints from developer auxiliary hunks.
    """
    if not developer_aux_hunks:
        return {}, "(none)"

    extra_map: dict[str, str] = {}
    lines: list[str] = []

    for h in developer_aux_hunks:
        op = (h.get("file_operation") or "MODIFIED").upper()
        new_path = _normalize_rel_path(h.get("target_file") or "")
        old_path = _normalize_rel_path(
            h.get("old_target_file") or h.get("mainline_file") or ""
        )
        hunk_text = h.get("hunk_text") or ""

        if op == "RENAMED" and old_path and new_path and old_path != new_path:
            old_stem = os.path.splitext(os.path.basename(old_path))[0]
            new_stem = os.path.splitext(os.path.basename(new_path))[0]
            if old_stem and new_stem and old_stem != new_stem:
                extra_map.setdefault(old_stem, new_stem)
            lines.append(f"- `{op}`: `{old_path}` -> `{new_path}`")
        elif new_path:
            lines.append(f"- `{op}`: `{new_path}`")

        if hunk_text:
            removed_class = None
            added_class = None
            for raw_line in hunk_text.splitlines():
                s = raw_line.strip()
                m_removed = re.match(
                    r"^-\s*public\s+(?:final\s+)?(?:class|interface|enum)\s+(\w+)\b",
                    s,
                )
                if m_removed:
                    removed_class = m_removed.group(1)
                m_added = re.match(
                    r"^\+\s*public\s+(?:final\s+)?(?:class|interface|enum)\s+(\w+)\b",
                    s,
                )
                if m_added:
                    added_class = m_added.group(1)
            if removed_class and added_class and removed_class != added_class:
                extra_map.setdefault(removed_class, added_class)

    return extra_map, ("\n".join(lines[:10]) if lines else "(none)")


def _stabilize_hunk_structure(base_hunk: str, candidate_hunk: str) -> str:
    """
    Keeps the original hunk structure and replaces only '+' lines with candidate '+'.

    This prevents malformed hunks when LLM output drops diff prefixes on context lines.
    If candidate '+' count does not match base '+', falls back to base_hunk.
    """
    if not base_hunk:
        return candidate_hunk or base_hunk

    base_lines = base_hunk.splitlines()
    if not base_lines or not base_lines[0].startswith("@@"):
        return candidate_hunk or base_hunk

    candidate_plus = _extract_added_lines(candidate_hunk or "")
    base_plus_count = sum(1 for line in base_lines[1:] if line.startswith("+"))

    if base_plus_count == 0:
        return base_hunk if base_hunk.endswith("\n") else base_hunk + "\n"

    if len(candidate_plus) != base_plus_count:
        return base_hunk if base_hunk.endswith("\n") else base_hunk + "\n"

    out = [base_lines[0]]
    plus_idx = 0
    for line in base_lines[1:]:
        if line.startswith("+"):
            out.append(candidate_plus[plus_idx])
            plus_idx += 1
        else:
            out.append(line)

    stabilized = "\n".join(out)
    if not stabilized.endswith("\n"):
        stabilized += "\n"
    return stabilized


def _normalize_rel_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/").lstrip("/")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p


def _is_test_file(file_path: str) -> bool:
    """
    Simple heuristic to determine if a file is a test file.
    """
    lower_path = (file_path or "").lower()
    return "test" in lower_path or lower_path.endswith("test.java")


def _exists_file(repo_path: str, rel_path: str) -> bool:
    if not repo_path or not rel_path:
        return False
    full_path = os.path.normpath(os.path.join(repo_path, _normalize_rel_path(rel_path)))
    return os.path.isfile(full_path)


def _exists_dir(repo_path: str, rel_path: str) -> bool:
    if not repo_path:
        return False
    rel = _normalize_rel_path(rel_path)
    full_path = os.path.normpath(os.path.join(repo_path, rel)) if rel else repo_path
    return os.path.isdir(full_path)


def _first_candidate_path(candidates: list[dict[str, Any]] | None) -> str | None:
    for cand in candidates or []:
        if not isinstance(cand, dict):
            continue
        p = cand.get("file") or cand.get("file_path") or cand.get("path")
        if p:
            return _normalize_rel_path(str(p))
    return None


def _find_candidate_target_path(
    retriever: EnsembleRetriever | None,
    file_path: str,
    original_commit: str,
) -> str | None:
    if not retriever:
        return None
    p = _normalize_rel_path(file_path)
    if not p:
        return None
    try:
        candidates = retriever.find_candidates(p, original_commit or "HEAD")
        return _first_candidate_path(candidates)
    except Exception:
        return None


def _infer_target_directory_from_siblings(
    mainline_file: str,
    mainline_repo_path: str,
    retriever: EnsembleRetriever | None,
    original_commit: str,
) -> str | None:
    if not retriever or not mainline_repo_path:
        return None

    file_path = _normalize_rel_path(mainline_file)
    parent = os.path.dirname(file_path)
    if not parent:
        return None

    parent_abs = os.path.join(mainline_repo_path, parent)
    if not os.path.isdir(parent_abs):
        return None

    sibling_dirs: list[str] = []
    try:
        for name in os.listdir(parent_abs):
            if not name.endswith(".java"):
                continue
            sibling_rel = _normalize_rel_path(os.path.join(parent, name))
            if sibling_rel == file_path:
                continue
            mapped = _find_candidate_target_path(
                retriever, sibling_rel, original_commit
            )
            if mapped:
                sibling_dirs.append(os.path.dirname(mapped))
            if len(sibling_dirs) >= 3:
                break
    except Exception:
        return None

    if not sibling_dirs:
        return None

    return max(set(sibling_dirs), key=sibling_dirs.count)


def _resolve_operation_plan(
    *,
    change_type: str,
    mainline_file: str,
    previous_mainline_file: str | None,
    target_repo_path: str,
    mainline_repo_path: str,
    retriever: EnsembleRetriever | None,
    original_commit: str,
) -> dict[str, Any]:
    op = (change_type or "MODIFIED").upper()
    mainline_file = _normalize_rel_path(mainline_file)
    previous_mainline_file = _normalize_rel_path(previous_mainline_file or "") or None

    def resolve_existing(path_hint: str) -> str | None:
        p = _normalize_rel_path(path_hint)
        if p and _exists_file(target_repo_path, p):
            return p
        return _find_candidate_target_path(retriever, p, original_commit)

    plan: dict[str, Any] = {
        "target_file": mainline_file,
        "old_target_file": None,
        "effective_operation": op,
        "operation_required": True,
        "reason": "default",
    }

    if op == "ADDED":
        target_file = mainline_file
        parent_dir = os.path.dirname(target_file)
        if parent_dir and not _exists_dir(target_repo_path, parent_dir):
            inferred_dir = _infer_target_directory_from_siblings(
                mainline_file=mainline_file,
                mainline_repo_path=mainline_repo_path,
                retriever=retriever,
                original_commit=original_commit,
            )
            if inferred_dir:
                target_file = _normalize_rel_path(
                    os.path.join(inferred_dir, os.path.basename(mainline_file))
                )
                plan["reason"] = "added_file_sibling_directory_inference"

        existing_match = resolve_existing(target_file)
        if existing_match:
            plan.update(
                {
                    "target_file": existing_match,
                    "effective_operation": "MODIFIED",
                    "operation_required": True,
                    "reason": "added_file_already_exists_in_target",
                }
            )
            return plan

        plan.update(
            {
                "target_file": target_file,
                "effective_operation": "ADDED",
                "operation_required": True,
            }
        )
        return plan

    if op == "DELETED":
        delete_target = resolve_existing(mainline_file)
        if not delete_target:
            return {
                "target_file": mainline_file,
                "old_target_file": None,
                "effective_operation": "DELETED",
                "operation_required": False,
                "reason": "delete_target_not_found",
            }

        return {
            "target_file": delete_target,
            "old_target_file": None,
            "effective_operation": "DELETED",
            "operation_required": _exists_file(target_repo_path, delete_target),
            "reason": "delete_target_mapped",
        }

    if op == "RENAMED":
        old_hint = previous_mainline_file or mainline_file
        old_target = resolve_existing(old_hint)
        new_target = mainline_file
        new_parent = os.path.dirname(new_target)
        if new_parent and not _exists_dir(target_repo_path, new_parent):
            inferred_dir = _infer_target_directory_from_siblings(
                mainline_file=mainline_file,
                mainline_repo_path=mainline_repo_path,
                retriever=retriever,
                original_commit=original_commit,
            )
            if inferred_dir:
                new_target = _normalize_rel_path(
                    os.path.join(inferred_dir, os.path.basename(new_target))
                )

        existing_new = resolve_existing(new_target)
        if existing_new:
            new_target = existing_new

        old_exists = bool(old_target and _exists_file(target_repo_path, old_target))
        new_exists = bool(new_target and _exists_file(target_repo_path, new_target))

        if old_exists and not new_exists:
            return {
                "target_file": new_target,
                "old_target_file": old_target,
                "effective_operation": "RENAMED",
                "operation_required": True,
                "reason": "rename_required_old_exists_new_missing",
            }
        if not old_exists and new_exists:
            return {
                "target_file": new_target,
                "old_target_file": old_target,
                "effective_operation": "MODIFIED",
                "operation_required": True,
                "reason": "rename_already_applied_in_target",
            }
        if old_exists and new_exists:
            return {
                "target_file": new_target,
                "old_target_file": old_target,
                "effective_operation": "MODIFIED",
                "operation_required": True,
                "reason": "both_old_and_new_exist_skip_explicit_rename",
            }
        return {
            "target_file": new_target,
            "old_target_file": old_target,
            "effective_operation": "RENAMED",
            "operation_required": False,
            "reason": "rename_no_viable_target",
        }

    # MODIFIED and fallback
    mapped_target = resolve_existing(mainline_file)
    if mapped_target:
        plan["target_file"] = mapped_target
        plan["reason"] = "modified_target_mapped"
    return plan


# ---------------------------------------------------------------------------
# Core Agent Node
# ---------------------------------------------------------------------------


async def hunk_generator_node(state: AgentState, config) -> dict:
    """
    Agent 3 node function.

    Iterates over every modified hunk in the patch, rewrites it for the target
    via LLM, validates format (dry-run) and intent (blueprint check), and
    stores the results as AdaptedHunk lists.

    IMPORTANT: The insertion_line field in each AdaptedHunk is critical for proper
    application order. When multiple hunks target the same file, they are assembled
    in top-to-bottom order and applied as one per-file patch section so standard patch
    engines can resolve offsets as earlier hunks are applied.
    """
    print("Agent 3 (Hunk Generator): Starting surgical hunk rewrite...")

    consistency_map: dict = state.get("consistency_map") or {}
    mapped_target_context: dict = state.get("mapped_target_context") or {}
    semantic_blueprint: SemanticBlueprint = state.get("semantic_blueprint")
    patch_analysis: list = state.get("patch_analysis") or []
    patch_diff: str = state.get("patch_diff") or ""
    target_repo_path: str = state.get("target_repo_path", "")
    mainline_repo_path: str = state.get("mainline_repo_path", "")
    original_commit: str = state.get("original_commit", "HEAD")
    validation_attempts: int = state.get("validation_attempts") or 0
    error_context: str = state.get("validation_error_context") or ""
    retry_files_raw = state.get("validation_retry_files") or []
    with_test_changes: bool = state.get("with_test_changes", False)
    developer_aux_hunks: list[dict[str, Any]] = (
        state.get("developer_auxiliary_hunks") or []
    )
    retry_files = {_normalize_rel_path(p) for p in retry_files_raw if p}
    aux_consistency_map, aux_context = _extract_auxiliary_signals(developer_aux_hunks)
    if aux_consistency_map:
        merged_cm = dict(consistency_map)
        for old, new in aux_consistency_map.items():
            merged_cm.setdefault(old, new)
        consistency_map = merged_cm

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
        retry_files_note = (
            f"Impacted files from previous validation: {sorted(retry_files)}\n"
            if retry_files
            else ""
        )
        retry_context_str = (
            f"## RETRY #{validation_attempts} — Previous Validation Failed\n"
            f"```\n{error_context[:600]}\n```\n"
            f"{retry_files_note}"
            f"Adjust the hunk to fix the above error.\n"
        )
        print(
            f"  Agent 3: Retry #{validation_attempts} — injecting validation error into prompts."
        )

    # ------------------------------------------------------------------
    # Setup tools
    # ------------------------------------------------------------------
    # Setup LLM
    llm = get_llm(temperature=0)

    analyzer = PatchAnalyzer()
    raw_hunks_by_file = (
        analyzer.extract_raw_hunks(patch_diff, with_test_changes=with_test_changes)
        if patch_diff
        else {}
    )
    file_only_ops = (
        analyzer.extract_file_only_operations(
            patch_diff, with_test_changes=with_test_changes
        )
        if patch_diff
        else []
    )
    toolkit = ValidationToolkit(target_repo_path) if target_repo_path else None
    retriever = None
    if target_repo_path and mainline_repo_path:
        try:
            retriever = EnsembleRetriever(mainline_repo_path, target_repo_path)
        except Exception as e:
            print(
                f"  Agent 3: Warning — retriever unavailable for file-op mapping: {e}"
            )

    fix_logic = semantic_blueprint.get("fix_logic", "")
    dependent_apis = semantic_blueprint.get("dependent_apis", [])
    root_cause = semantic_blueprint.get("root_cause_hypothesis", "")
    cm_formatted = _format_consistency_map(consistency_map)

    # ------------------------------------------------------------------
    # Segregate changes
    # ------------------------------------------------------------------
    code_changes = [
        fc
        for fc in patch_analysis
        if not (
            fc.is_test_file
            if hasattr(fc, "is_test_file")
            else fc.get("is_test_file", False)
        )
    ]
    test_changes = [
        fc
        for fc in patch_analysis
        if (
            fc.is_test_file
            if hasattr(fc, "is_test_file")
            else fc.get("is_test_file", False)
        )
    ]

    # Filter test changes based on with_test_changes flag
    if not with_test_changes:
        test_changes = []

    print(
        f"  Agent 3: {len(code_changes)} code file(s), {len(test_changes)} test file(s) to process."
    )

    # --- Early Exit: If Agent 2 produced no mappings and we're on a retry, abort ---
    # If there are code files but no mapped context, and this is a retry, don't loop endlessly.
    if code_changes and not mapped_target_context and validation_attempts > 0:
        print(
            f"  Agent 3: Aborting retry — Agent 2 has no target context and retrying won't help."
        )
        return {
            "messages": [
                HumanMessage(
                    content="Agent 3: No target context from Agent 2. Cannot proceed."
                )
            ],
            "adapted_code_hunks": [],
            "adapted_test_hunks": [],
            "validation_passed": False,  # Signal validation failure to exit loop
            "validation_attempts": validation_attempts,
            "validation_error_context": "Agent 3 Early Exit: Agent 2 failed to map files. No source context available for hunk generation.",
        }

    adapted_code_hunks: list[AdaptedHunk] = []
    adapted_test_hunks: list[AdaptedHunk] = []
    trace = "# Hunk Generator Trace\n\n"
    trace += f"| target_file | hunk_index | dry_run | intent_ok |\n|---|---|---|---|\n"

    # ------------------------------------------------------------------
    # Code hunk processing
    # ------------------------------------------------------------------
    for change in code_changes:
        mainline_file = (
            change.file_path
            if hasattr(change, "file_path")
            else change.get("file_path", "?")
        )
        change_type = (
            change.change_type
            if hasattr(change, "change_type")
            else change.get("change_type", "MODIFIED")
        )
        previous_mainline_file = (
            change.previous_file_path
            if hasattr(change, "previous_file_path")
            else change.get("previous_file_path")
        )
        op_plan = _resolve_operation_plan(
            change_type=change_type,
            mainline_file=mainline_file,
            previous_mainline_file=previous_mainline_file,
            target_repo_path=target_repo_path,
            mainline_repo_path=mainline_repo_path,
            retriever=retriever,
            original_commit=original_commit,
        )

        if not op_plan.get("operation_required", True) and not raw_hunks_by_file.get(
            mainline_file, []
        ):
            print(
                f"  Agent 3: Skipping {change_type} for {mainline_file} "
                f"(reason={op_plan.get('reason')})"
            )
            continue
        # Get list of mappings for this file (now returns list instead of single dict)
        mapped_ctx_list = mapped_target_context.get(mainline_file, [])
        raw_hunks = raw_hunks_by_file.get(mainline_file, [])

        if retry_files:
            candidate_paths = {
                _normalize_rel_path(mainline_file),
                _normalize_rel_path(op_plan.get("target_file") or ""),
            }
            if mapped_ctx_list:
                candidate_paths.add(
                    _normalize_rel_path(
                        (mapped_ctx_list[0] or {}).get("target_file", "")
                    )
                )
            if not any(p for p in candidate_paths if p in retry_files):
                continue

        if not mapped_ctx_list:
            print(
                f"  Agent 3: Skipping {mainline_file} — no target context from Agent 2."
            )
            continue

        print(
            f"  Agent 3: Processing {len(raw_hunks)} hunk(s) for {mainline_file} with {len(mapped_ctx_list)} mapping(s)"
        )

        for hunk_idx, raw_hunk in enumerate(raw_hunks):
            # Get the mapping for this hunk (or reuse first one if not enough mappings)
            mapped_ctx = mapped_ctx_list[min(hunk_idx, len(mapped_ctx_list) - 1)]

            target_file = _normalize_rel_path(
                mapped_ctx.get("target_file", mainline_file)
            )
            planned_target_file = op_plan.get("target_file")
            if planned_target_file:
                target_file = planned_target_file
            insertion_line = mapped_ctx.get("start_line")
            target_body = mapped_ctx.get("code_snippet", "")
            surrounding_context = mapped_ctx.get(
                "surrounding_context", {"before": [], "after": []}
            )
            raw_start_line = _extract_target_start_line(raw_hunk)
            target_method = (mapped_ctx.get("target_method") or "").strip().lower()
            mainline_method = (mapped_ctx.get("mainline_method") or "").strip().lower()
            is_declaration_or_class_hunk = target_method in {
                "<import>",
                "<class_declaration>",
            } or mainline_method.startswith("<")

            # IMPROVEMENT: If insertion_line is None, try to extract from raw hunk header
            if insertion_line is None:
                try:
                    # Parse @@ -X,Y +A,B @@ to get actual line numbers
                    hunk_header_match = re.search(r"@@ -\d+(?:,\d+)? \+(\d+)", raw_hunk)
                    if hunk_header_match:
                        insertion_line = int(hunk_header_match.group(1))
                        print(
                            f"  Agent 3: Extracted insertion_line {insertion_line} from hunk {hunk_idx} header"
                        )
                except Exception as e:
                    print(
                        f"  Agent 3: Could not extract insertion_line from hunk {hunk_idx}: {e}"
                    )

            # Declaration/class-level mappings often return coarse line anchors (e.g., 1).
            # Prefer raw hunk header anchor in those cases.
            if raw_start_line and (
                is_declaration_or_class_hunk
                or (isinstance(insertion_line, int) and insertion_line <= 1)
            ):
                insertion_line = raw_start_line

            # Default fallback
            insertion_line = insertion_line or 1

            # Deterministic symbol substitution pre-pass
            pre_rewritten = _rewrite_hunk_symbols(raw_hunk, consistency_map)

            # For import-only hunks, skip LLM rewriting to avoid corruption
            # Import statements are fragile and LLM tends to duplicate existing imports
            is_import_hunk = _is_import_only_hunk(raw_hunk)

            # --- New: Dynamic Context Verification ---
            if toolkit and insertion_line:
                # Read lines around the insertion point to verify context
                # Use a try-except block to safely call read_file_range
                try:
                    actual_context = toolkit.read_file_range(
                        target_file, max(1, insertion_line - 3), insertion_line + 3
                    )
                    if actual_context and "Error" not in actual_context:
                        print(
                            f"    Agent 3: Verified target context for {target_file}:{insertion_line}"
                        )
                except AttributeError:
                    print(
                        f"    Agent 3 Warning: toolkit does not support read_file_range"
                    )
                except Exception as e:
                    print(f"    Agent 3 Warning: context verification failed: {e}")

            if is_import_hunk:
                adapted_hunk_text = _adjust_hunk_header(pre_rewritten, insertion_line)
                print(
                    f"    Agent 3: Skipped LLM rewrite for import-only hunk {hunk_idx}"
                )
            else:
                # --- DETERMINISTIC PATH (preferred) ---
                # Apply the hunk directly against the actual file content.
                # This avoids LLM hallucination and whitespace corruption entirely.
                adapted_hunk_text = _apply_hunk_deterministically(
                    pre_rewritten,
                    consistency_map,
                    target_repo_path,
                    target_file,
                    insertion_line,
                )
                if adapted_hunk_text:
                    print(
                        f"    Agent 3: Deterministic hunk applied for hunk {hunk_idx}"
                    )
                else:
                    # --- LLM FALLBACK ---
                    # Only used when deterministic path fails (e.g., no file access).
                    actual_old_body = _read_actual_body_from_file(
                        target_repo_path, target_file, insertion_line, raw_hunk
                    )
                    effective_old_body = (
                        actual_old_body if actual_old_body.strip() else target_body
                    )
                    print(
                        f"    Agent 3: Deterministic path failed for hunk {hunk_idx}; "
                        f"falling back to LLM rewrite"
                    )

                    for attempt in range(2):
                        prompt = _HUNK_REWRITE_USER.format(
                            mainline_hunk=pre_rewritten,
                            target_method_body=effective_old_body,
                            context_before="\n".join(
                                surrounding_context.get("before", [])
                            ),
                            context_after="\n".join(
                                surrounding_context.get("after", [])
                            ),
                            consistency_map=cm_formatted,
                            fix_logic=fix_logic,
                            dependent_apis=", ".join(dependent_apis),
                            retry_context=retry_context_str,
                        )
                        try:
                            response = await llm.ainvoke(
                                [
                                    SystemMessage(content=_HUNK_REWRITE_SYSTEM),
                                    HumanMessage(content=prompt),
                                ]
                            )
                            raw_content = (
                                response.content
                                if hasattr(response, "content")
                                else str(response)
                            )
                            updated_body = raw_content.strip()
                            code_match = re.search(
                                r"```(?:java|diff)?\n(.*?)```", raw_content, re.DOTALL
                            )
                            if code_match:
                                updated_body = code_match.group(1).strip()
                            elif "```" in raw_content:
                                inner_lines = raw_content.splitlines()
                                body_lines = []
                                in_fence = False
                                for line in inner_lines:
                                    if line.strip().startswith("```"):
                                        in_fence = not in_fence
                                        continue
                                    if in_fence:
                                        body_lines.append(line)
                                if body_lines:
                                    updated_body = "\n".join(body_lines)

                            if updated_body:
                                adapted_hunk_text = _generate_hunk_from_bodies(
                                    effective_old_body,
                                    updated_body,
                                    target_file,
                                    insertion_line,
                                )
                                if adapted_hunk_text:
                                    break
                            print(
                                f"    Agent 3: LLM body extraction failed (attempt {attempt + 1}/2)"
                            )
                        except Exception as e:
                            print(
                                f"    Agent 3: LLM error on hunk {hunk_idx} (attempt {attempt + 1}/2): {e}"
                            )

                if not adapted_hunk_text:
                    # Last resort: deterministic pre-rewrite with adjusted header
                    adapted_hunk_text = _adjust_hunk_header(
                        pre_rewritten, insertion_line
                    )
                    print(
                        f"    Agent 3: Last resort — using pre-rewrite header adjustment for hunk {hunk_idx}"
                    )

            # Dry-run validation
            dry_run_ok = False
            if toolkit:
                candidates: list[tuple[str, str]] = []

                def _push_candidate(label: str, htxt: str | None) -> None:
                    if not htxt:
                        return
                    for _, existing in candidates:
                        if existing == htxt:
                            return
                    candidates.append((label, htxt))

                _push_candidate("primary", adapted_hunk_text)

                # Conservative fallback sequence for context drift:
                # 1) deterministic pre-rewrite
                # 2) context-free (+/- only)
                # 3) insertion-only (+ only)
                deterministic_hunk = _adjust_hunk_header(pre_rewritten, insertion_line)
                _push_candidate("deterministic", deterministic_hunk)

                effective_op = (
                    op_plan.get("effective_operation") or "MODIFIED"
                ).upper()

                # Aggressive context-dropping fallbacks are unsafe for import/class
                # declaration hunks because they often apply at EOF.
                if (
                    effective_op == "MODIFIED"
                    and not is_import_hunk
                    and not is_declaration_or_class_hunk
                    and len(_extract_removed_lines(deterministic_hunk)) > 0
                ):
                    _push_candidate(
                        "context-free",
                        _to_context_free_hunk(deterministic_hunk, insertion_line),
                    )

                last_err = ""
                selected_label = "primary"
                for label, candidate_hunk in candidates:
                    if _is_structurally_risky_candidate(
                        pre_rewritten,
                        candidate_hunk,
                        operation=effective_op,
                        is_import_hunk=is_import_hunk,
                        is_declaration_or_class_hunk=is_declaration_or_class_hunk,
                    ):
                        print(
                            f"    Agent 3: Skipping risky fallback ({label}) "
                            f"for {target_file}[{hunk_idx}]"
                        )
                        continue
                    dr = toolkit.apply_hunk_dry_run(target_file, candidate_hunk)
                    if dr["success"]:
                        adapted_hunk_text = candidate_hunk
                        dry_run_ok = True
                        selected_label = label
                        break
                    last_err = dr.get("output", "")

                if dry_run_ok and selected_label != "primary":
                    print(
                        f"    Agent 3: Dry-run fallback selected ({selected_label}) "
                        f"for {target_file}[{hunk_idx}]"
                    )
                elif not dry_run_ok:
                    print(
                        f"    Agent 3: Dry-run failed for {target_file}[{hunk_idx}]: {last_err[:150]}"
                    )
            else:
                dry_run_ok = True  # No toolkit → assume ok (local dev mode)

            # Blueprint intent check
            intent_ok = await _check_intent(llm, adapted_hunk_text, semantic_blueprint)
            if not intent_ok:
                print(
                    f"    Agent 3: Blueprint check failed for {target_file}[{hunk_idx}] — flagging."
                )

            hunk: AdaptedHunk = {
                "target_file": target_file,
                "mainline_file": mainline_file,
                "hunk_text": adapted_hunk_text,
                "insertion_line": insertion_line,
                "intent_verified": intent_ok,
                "file_operation": op_plan.get("effective_operation", change_type),
                "old_target_file": op_plan.get("old_target_file"),
                "file_operation_required": op_plan.get("operation_required", True),
                "path_resolution_reason": op_plan.get("reason", "unknown"),
            }
            adapted_code_hunks.append(hunk)
            trace += (
                f"| `{target_file}` | {hunk_idx} | "
                f"{'✅' if dry_run_ok else '❌'} | {'✅' if intent_ok else '❌'} |\n"
            )

    # ------------------------------------------------------------------
    # Test hunk processing
    # ------------------------------------------------------------------
    for change in test_changes:
        mainline_test = (
            change.file_path
            if hasattr(change, "file_path")
            else change.get("file_path", "?")
        )
        previous_mainline_file = (
            change.previous_file_path
            if hasattr(change, "previous_file_path")
            else change.get("previous_file_path")
        )
        change_type = (
            change.change_type
            if hasattr(change, "change_type")
            else change.get("change_type", "MODIFIED")
        )
        op_plan = _resolve_operation_plan(
            change_type=change_type,
            mainline_file=mainline_test,
            previous_mainline_file=previous_mainline_file,
            target_repo_path=target_repo_path,
            mainline_repo_path=mainline_repo_path,
            retriever=retriever,
            original_commit=original_commit,
        )
        # Get list of mappings for this test file
        mapped_ctx_list = mapped_target_context.get(mainline_test, [])
        raw_hunks = raw_hunks_by_file.get(mainline_test, [])

        if not mapped_ctx_list:
            print(
                f"  Agent 3: Skipping test {mainline_test} — no target test file (Agent 4 will synthesize)."
            )
            continue

        # For test files, typically only one mapping
        mapped_ctx = mapped_ctx_list[0]
        target_test_file = _normalize_rel_path(mapped_ctx.get("target_file") or "")
        planned_target_test_file = _normalize_rel_path(op_plan.get("target_file") or "")
        if planned_target_test_file:
            target_test_file = planned_target_test_file

        if not target_test_file:
            print(
                f"  Agent 3: Skipping test {mainline_test} — target test file is null (Agent 4 will synthesize)."
            )
            continue

        print(
            f"  Agent 3: Rewriting {len(raw_hunks)} test hunk(s) for {mainline_test} → {target_test_file}"
        )

        for hunk_idx, raw_hunk in enumerate(raw_hunks):
            pre_rewritten = _rewrite_hunk_symbols(raw_hunk, consistency_map)

            adapted_hunk_text = None
            for attempt in range(2):
                prompt = _TEST_HUNK_REWRITE_USER.format(
                    mainline_hunk=pre_rewritten,
                    target_test_file=target_test_file,
                    consistency_map=cm_formatted,
                    root_cause=root_cause,
                    developer_aux_context=aux_context,
                    retry_context=retry_context_str,
                )
                try:
                    response = await llm.ainvoke(
                        [
                            SystemMessage(content=_HUNK_REWRITE_SYSTEM),
                            HumanMessage(content=prompt),
                        ]
                    )
                    raw_content = (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    )
                    extracted = _extract_hunk_block(raw_content)
                    if extracted:
                        adapted_hunk_text = extracted
                        break
                    print(
                        f"    Agent 3: Test hunk parse failed (attempt {attempt + 1}/2)"
                    )
                except Exception as e:
                    print(
                        f"    Agent 3: LLM error on test hunk {hunk_idx} (attempt {attempt + 1}/2): {e}"
                    )

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
                "file_operation": op_plan.get("effective_operation", change_type),
                "old_target_file": op_plan.get("old_target_file"),
                "file_operation_required": op_plan.get("operation_required", True),
                "path_resolution_reason": op_plan.get("reason", "unknown"),
            }
            adapted_test_hunks.append(hunk)
            trace += (
                f"| `{target_test_file}` (test) | {hunk_idx} | "
                f"{'✅' if dry_run_ok else '❌'} | — |\n"
            )

    # ------------------------------------------------------------------
    # File-only operations processing (rename, pure delete, etc.)
    # ------------------------------------------------------------------
    for op in file_only_ops:
        file_path = op.get("file_path", "?")
        change_type = op.get("change_type", "MODIFIED")
        is_test = op.get("is_test_file", False)
        new_path = op.get("new_path", file_path)
        previous_mainline_file = file_path if change_type == "RENAMED" else None

        op_plan = _resolve_operation_plan(
            change_type=change_type,
            mainline_file=new_path if change_type == "RENAMED" else file_path,
            previous_mainline_file=previous_mainline_file,
            target_repo_path=target_repo_path,
            mainline_repo_path=mainline_repo_path,
            retriever=retriever,
            original_commit=original_commit,
        )

        if not op_plan.get("operation_required", True):
            print(
                f"  Agent 3: Skipping structural {change_type} for {file_path} "
                f"(reason={op_plan.get('reason')})"
            )
            continue

        # Skip test file operations if not requested
        if is_test and not with_test_changes:
            continue

        # Create a minimal AdaptedHunk for structural operations
        # These have no hunk_text since they're metadata-only
        hunk: AdaptedHunk = {
            "target_file": op_plan.get("target_file")
            or (new_path if change_type == "RENAMED" else file_path),
            "mainline_file": file_path,
            "hunk_text": "",  # No hunks for structural operations
            "insertion_line": 0,
            "intent_verified": True,  # No intent check needed for renames
            "file_operation": op_plan.get("effective_operation", change_type),
            "old_target_file": op_plan.get("old_target_file"),
            "file_operation_required": op_plan.get("operation_required", True),
            "path_resolution_reason": op_plan.get("reason", "unknown"),
        }

        if is_test:
            adapted_test_hunks.append(hunk)
        else:
            adapted_code_hunks.append(hunk)

        trace += f"| `{hunk['target_file']}` ({hunk['file_operation']}) | — | — | — |\n"
        print(
            f"  Agent 3: Added {hunk['file_operation']} operation for {file_path} "
            f"(target={hunk['target_file']}, reason={hunk.get('path_resolution_reason')})"
        )

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
