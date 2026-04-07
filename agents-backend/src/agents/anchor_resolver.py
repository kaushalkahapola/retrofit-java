"""
Anchor Resolver — Convert typed Changes into deterministic FileEdits.

For each Change, attempts to resolve it deterministically using java_structure utilities.
If an anchor cannot be found, marks the Change as "drifted" for later LLM resolution.
"""

import os
from typing import Optional

from state import AgentState, Change, FileEdit
from utils.java_structure import (
    find_imports_section,
    find_class_final_brace,
    find_class_body,
    find_method_body,
    find_field_declarations_end,
    has_import,
)


def anchor_resolver(state: AgentState, config) -> dict:
    """
    Resolve typed changes into deterministic FileEdits.

    For each Change:
    - If it's add_import, add_field, add_method → emit FileEdit directly
    - If it's replace_statement, replace_block → find anchor in target file
    - If anchor not found → mark as drifted

    Returns: {resolved_edits: list[FileEdit], drifted_changes: list[Change]}
    """
    print("Anchor Resolver: Starting deterministic change resolution...")

    typed_changes = state.get("typed_changes", {})
    target_repo_path = state.get("target_repo_path", "")

    if not typed_changes:
        return {"resolved_edits": [], "drifted_changes": []}

    resolved_edits: list[FileEdit] = []
    drifted_changes: list[Change] = []

    for target_file, changes in typed_changes.items():
        full_path = os.path.join(target_repo_path, target_file)

        for change in changes:
            if not isinstance(change, dict):
                continue

            kind = change.get("kind", "")
            payload = change.get("payload", "")
            class_name = change.get("class_name", "")
            anchor = change.get("anchor", "")

            try:
                if kind == "add_import":
                    # Check if already present
                    if has_import(full_path, payload):
                        change["status"] = "skipped"
                        change["reason"] = "Import already exists"
                        continue

                    # Find imports section end
                    try:
                        import_start, import_end = find_imports_section(full_path)
                        edit = FileEdit(
                            target_file=target_file,
                            mainline_file=target_file,
                            old_string="",
                            new_string=payload,
                            edit_type="insert_after",
                            verified=True,
                            verification_result=f"insert after line {import_end}",
                            applied=False,
                            apply_result="pending",
                        )
                        resolved_edits.append(edit)
                        change["status"] = "resolved"
                    except ValueError:
                        # No imports section; insert after package declaration
                        with open(full_path, "r") as f:
                            lines = f.readlines()
                        insert_line = 1
                        for i, line in enumerate(lines):
                            if line.strip().startswith("package "):
                                insert_line = i + 1
                                break
                        edit = FileEdit(
                            target_file=target_file,
                            mainline_file=target_file,
                            old_string="",
                            new_string=payload,
                            edit_type="insert_after",
                            verified=True,
                            verification_result=f"insert after line {insert_line}",
                            applied=False,
                            apply_result="pending",
                        )
                        resolved_edits.append(edit)
                        change["status"] = "resolved"

                elif kind == "add_field":
                    if not class_name:
                        raise ValueError("add_field requires class_name")

                    field_end = find_field_declarations_end(full_path, class_name)
                    edit = FileEdit(
                        target_file=target_file,
                        mainline_file=target_file,
                        old_string="",
                        new_string=payload,
                        edit_type="insert_after",
                        verified=True,
                        verification_result=f"insert after line {field_end}",
                        applied=False,
                        apply_result="pending",
                    )
                    resolved_edits.append(edit)
                    change["status"] = "resolved"

                elif kind == "add_method":
                    if not class_name:
                        raise ValueError("add_method requires class_name")

                    closing_brace_line = find_class_final_brace(full_path, class_name)
                    # Insert one line before the closing brace
                    with open(full_path, "r") as f:
                        lines = f.readlines()

                    # Find a good anchor point (e.g., the last line of the class body before the brace)
                    insert_before_line = closing_brace_line - 1
                    if insert_before_line > 0:
                        anchor_text = lines[insert_before_line - 1].rstrip()
                    else:
                        anchor_text = lines[closing_brace_line - 1].rstrip()

                    edit = FileEdit(
                        target_file=target_file,
                        mainline_file=target_file,
                        old_string=anchor_text,
                        new_string=anchor_text + "\n\n" + payload,
                        edit_type="replace",
                        verified=True,
                        verification_result=f"replace at line {closing_brace_line - 1}",
                        applied=False,
                        apply_result="pending",
                    )
                    resolved_edits.append(edit)
                    change["status"] = "resolved"

                elif kind == "add_ctor_param":
                    # Constructor parameter insertion — more complex, skip for now
                    change["status"] = "drifted"
                    change["reason"] = "add_ctor_param requires method body inspection"
                    drifted_changes.append(change)

                elif kind in ["replace_statement", "replace_block"]:
                    if not anchor:
                        # No anchor — mark as drifted
                        change["status"] = "drifted"
                        change["reason"] = "No anchor provided"
                        drifted_changes.append(change)
                        continue

                    # Try to find the exact anchor in the target file
                    with open(full_path, "r") as f:
                        content = f.read()

                    # Count occurrences
                    count = content.count(anchor)
                    if count == 0:
                        # Anchor not found — drifted
                        change["status"] = "drifted"
                        change["reason"] = "Anchor not found in target file"
                        drifted_changes.append(change)
                    elif count == 1:
                        # Found uniquely — resolve it
                        edit = FileEdit(
                            target_file=target_file,
                            mainline_file=target_file,
                            old_string=anchor,
                            new_string=payload,
                            edit_type="replace",
                            verified=True,
                            verification_result="exact anchor found",
                            applied=False,
                            apply_result="pending",
                        )
                        resolved_edits.append(edit)
                        change["status"] = "resolved"
                    else:
                        # Multiple matches — try method_hint narrowing
                        method_hint = change.get("method_hint", "")
                        if method_hint:
                            # Try to narrow using the method hint
                            try:
                                start_line, end_line, method_text = find_method_body(
                                    full_path, class_name, method_hint
                                )
                                if anchor in method_text:
                                    edit = FileEdit(
                                        target_file=target_file,
                                        mainline_file=target_file,
                                        old_string=anchor,
                                        new_string=payload,
                                        edit_type="replace",
                                        verified=True,
                                        verification_result=f"found in method {method_hint}",
                                        applied=False,
                                        apply_result="pending",
                                    )
                                    resolved_edits.append(edit)
                                    change["status"] = "resolved"
                                else:
                                    change["status"] = "drifted"
                                    change["reason"] = f"Anchor not in method {method_hint}"
                                    drifted_changes.append(change)
                            except ValueError:
                                change["status"] = "drifted"
                                change["reason"] = f"Method {method_hint} not found"
                                drifted_changes.append(change)
                        else:
                            # Ambiguous — mark drifted and let LLM resolve
                            change["status"] = "drifted"
                            change["reason"] = f"Anchor found {count} times; need method hint"
                            drifted_changes.append(change)

                elif kind == "delete_statement":
                    if not anchor:
                        change["status"] = "drifted"
                        change["reason"] = "delete_statement requires anchor"
                        drifted_changes.append(change)
                        continue

                    with open(full_path, "r") as f:
                        content = f.read()

                    if anchor in content:
                        edit = FileEdit(
                            target_file=target_file,
                            mainline_file=target_file,
                            old_string=anchor,
                            new_string="",
                            edit_type="delete",
                            verified=True,
                            verification_result="exact anchor found",
                            applied=False,
                            apply_result="pending",
                        )
                        resolved_edits.append(edit)
                        change["status"] = "resolved"
                    else:
                        change["status"] = "drifted"
                        change["reason"] = "Anchor not found for deletion"
                        drifted_changes.append(change)

                else:
                    print(f"  WARNING: Unknown change kind: {kind}")

            except Exception as e:
                print(f"  ERROR resolving change in {target_file}: {e}")
                change["status"] = "drifted"
                change["reason"] = str(e)
                drifted_changes.append(change)

    print(
        f"Anchor Resolver: Resolved {len(resolved_edits)} edits, "
        f"{len(drifted_changes)} drifted changes"
    )

    return {
        "resolved_edits": resolved_edits,
        "drifted_changes": drifted_changes,
    }
