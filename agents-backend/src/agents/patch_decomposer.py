"""
Patch Decomposer — Convert untyped hunks into typed Changes.

This node runs once per pipeline run (after structural_locator) and decomposes
each hunk in patch_analysis into one or more typed Change objects.

Mostly deterministic (regex-based classification of ±lines), with one bounded
LLM fallback (1 call per file) for ambiguous cases.
"""

import json
import os
import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from state import AgentState, Change
from utils.llm_provider import get_llm
from utils.patch_analyzer import FileChange


_DECOMPOSER_SYSTEM = """You are a code change classifier. Your job is to take a unified diff hunk
and classify each added/removed section as a specific kind of change.

Output ONLY a JSON array of Change objects. Each Change must have: kind, target_file, payload,
[optional: anchor, class_name, method_hint, source_hunk_index].

kind options: "add_import", "add_field", "add_method", "add_ctor_param", "replace_statement", "delete_statement", "replace_block"

Keep it concise. If a hunk is ambiguous, classify as "replace_block"."""


def _classify_addition_hunk(hunk_text: str, target_file: str, source_index: int) -> list[Change]:
    """
    Classify a pure-addition hunk (only + lines, no - lines).

    Returns: list of typed Changes.
    """
    changes = []

    # Extract just the added lines (remove the +++ header and +/- prefixes)
    added_lines = [
        line[1:] for line in hunk_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]

    if not added_lines:
        return changes

    # Check if ALL lines are imports
    if all(line.strip().startswith("import ") and line.strip().endswith(";") for line in added_lines if line.strip()):
        for line in added_lines:
            if line.strip().startswith("import "):
                changes.append(Change(
                    kind="add_import",
                    target_file=target_file,
                    payload=line.rstrip(),
                    source_hunk_index=source_index,
                ))
        return changes

    # Check if this is a method declaration (starts with visibility + return type + name + ( )
    joined = "\n".join(added_lines)
    if re.search(r"^\s*(public|private|protected|static)*\s*\w+[\w\[\]\.]*\s+\w+\s*\(", joined, re.MULTILINE):
        # Likely a method — extract the primary class name from the file path
        class_name = _infer_class_name(target_file)
        changes.append(Change(
            kind="add_method",
            target_file=target_file,
            payload=joined,
            class_name=class_name,
            source_hunk_index=source_index,
        ))
        return changes

    # Check if this is a field declaration
    if any(re.search(r"^\s*(private|public|protected)\s+\w+[\w\[\]\.]*\s+\w+\s*(=|;)", line) for line in added_lines):
        class_name = _infer_class_name(target_file)
        changes.append(Change(
            kind="add_field",
            target_file=target_file,
            payload=joined,
            class_name=class_name,
            source_hunk_index=source_index,
        ))
        return changes

    # Default: treat as a replace_statement with empty anchor (insertion hint)
    changes.append(Change(
        kind="replace_statement",
        target_file=target_file,
        payload=joined,
        anchor="",
        source_hunk_index=source_index,
    ))

    return changes


def _classify_deletion_hunk(hunk_text: str, target_file: str, source_index: int) -> list[Change]:
    """
    Classify a pure-deletion hunk (only - lines).

    Returns: list of typed Changes.
    """
    changes = []

    deleted_lines = [
        line[1:] for line in hunk_text.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]

    if not deleted_lines:
        return changes

    # For now, treat all deletions as delete_statement
    # In future, could be more granular (delete_method, delete_field, etc.)
    joined = "\n".join(deleted_lines)
    changes.append(Change(
        kind="delete_statement",
        target_file=target_file,
        anchor=joined,
        payload="",
        source_hunk_index=source_index,
    ))

    return changes


def _classify_mixed_hunk(hunk_text: str, target_file: str, source_index: int) -> list[Change]:
    """
    Classify a mixed hunk (both + and - lines).

    Tries to align pairs; if alignment is ambiguous, emits a single replace_block.

    Returns: list of typed Changes.
    """
    changes = []

    lines = hunk_text.splitlines()
    deleted_lines = [line[1:] for line in lines if line.startswith("-") and not line.startswith("---")]
    added_lines = [line[1:] for line in lines if line.startswith("+") and not line.startswith("+++")]

    if not deleted_lines or not added_lines:
        return changes

    # Simple heuristic: if counts match, pair them up line-by-line
    if len(deleted_lines) == len(added_lines) and len(deleted_lines) <= 3:
        for old, new in zip(deleted_lines, added_lines):
            changes.append(Change(
                kind="replace_statement",
                target_file=target_file,
                anchor=old.rstrip(),
                payload=new.rstrip(),
                source_hunk_index=source_index,
            ))
        return changes

    # Otherwise, emit a single replace_block covering the whole thing
    deleted = "\n".join(deleted_lines)
    added = "\n".join(added_lines)
    changes.append(Change(
        kind="replace_block",
        target_file=target_file,
        anchor=deleted,
        payload=added,
        source_hunk_index=source_index,
    ))

    return changes


def _infer_class_name(file_path: str) -> str:
    """
    Infer the primary class name from a Java file path.

    Heuristic: take the filename without .java extension, assuming one public class per file.
    """
    basename = os.path.basename(file_path)
    if basename.endswith(".java"):
        return basename[:-5]
    return basename


async def _llm_decompose_fallback(hunk_text: str, file_skeleton: str) -> Optional[list[Change]]:
    """
    LLM fallback: ask gpt-4.1-mini to classify a complex hunk.

    Returns: list of Change dicts, or None if LLM fails.
    """
    llm = get_llm(temperature=0)

    prompt = f"""Here is a unified diff hunk and the class skeleton of the target file:

HUNK:
{hunk_text}

CLASS SKELETON:
{file_skeleton}

Classify each change as a typed Change. Output ONLY a JSON array. Example:
[
  {{"kind": "replace_statement", "target_file": "Foo.java", "anchor": "old line", "payload": "new line"}},
  {{"kind": "add_method", "target_file": "Foo.java", "payload": "public void newMethod() {{ ... }}", "class_name": "Foo"}}
]
"""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=_DECOMPOSER_SYSTEM),
            HumanMessage(content=prompt),
        ])
        text = response.content if hasattr(response, "content") else str(response)

        # Extract JSON from response
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return parsed if isinstance(parsed, list) else None
    except Exception as e:
        print(f"LLM decompose fallback failed: {e}")

    return None


def patch_decomposer(state: AgentState, config) -> dict:
    """
    Decompose patch_analysis into typed Changes.

    Runs once per pipeline (not per retry). Stores result in state.typed_changes.
    """
    print("Patch Decomposer: Starting typed change extraction...")

    patch_analysis = state.get("patch_analysis") or []
    if not patch_analysis:
        return {"typed_changes": {}}

    target_repo_path = state.get("target_repo_path", "")
    typed_changes: dict[str, list[Change]] = {}

    for file_change in patch_analysis:
        if not isinstance(file_change, dict):
            continue

        target_file = file_change.get("target_file", "")
        if not target_file or not target_file.endswith(".java"):
            # Skip non-Java files
            continue

        hunks = file_change.get("hunks", [])
        file_changes: list[Change] = []

        for hunk_idx, hunk in enumerate(hunks):
            if not isinstance(hunk, dict):
                continue

            hunk_text = hunk.get("text", "")
            if not hunk_text.strip():
                continue

            # Classify hunk
            has_additions = any(line.startswith("+") for line in hunk_text.splitlines() if not line.startswith("+++"))
            has_deletions = any(line.startswith("-") for line in hunk_text.splitlines() if not line.startswith("---"))

            if has_additions and not has_deletions:
                changes = _classify_addition_hunk(hunk_text, target_file, hunk_idx)
            elif has_deletions and not has_additions:
                changes = _classify_deletion_hunk(hunk_text, target_file, hunk_idx)
            else:
                changes = _classify_mixed_hunk(hunk_text, target_file, hunk_idx)

            file_changes.extend(changes)

        if file_changes:
            typed_changes[target_file] = file_changes
            print(f"  Decomposed {target_file}: {len(file_changes)} typed changes")

    print(f"Patch Decomposer: Extracted {sum(len(c) for c in typed_changes.values())} total changes")

    return {
        "typed_changes": typed_changes,
        "messages": [],
    }
