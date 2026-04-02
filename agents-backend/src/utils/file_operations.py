"""
CLAW-adapted file operations implementation.

This module provides file operations following CLAW's proven patterns:
- Pre-mutation validation
- Exact string matching (no fuzzy)
- Comprehensive structured output
- Line number handling (0-indexed internally, 1-indexed for display)

These functions solve the H-MABS line number offset and patch application issues.
"""

import os
from typing import Optional, Tuple
from .file_operations_models import (
    StructuredPatchHunk,
    TextFilePayload,
    EditFileOutput,
    HunkContext,
    FileOperationResult,
)


def make_patch(original: str, updated: str) -> list[StructuredPatchHunk]:
    """
    Create a structured patch from original and updated content.

    CLAW's approach: Create a SINGLE hunk for the entire file.
    This avoids line number offset issues that occur with multi-hunk patches.

    Args:
        original: The original file content
        updated: The updated file content

    Returns:
        List containing a single StructuredPatchHunk for the entire file change
    """
    lines = []

    # Add removed lines (prefixed with -)
    for line in original.splitlines():
        lines.append(f"-{line}")

    # Add added lines (prefixed with +)
    for line in updated.splitlines():
        lines.append(f"+{line}")

    # Create single hunk for entire file (CLAW's approach)
    return [
        StructuredPatchHunk(
            old_start=1,  # Always 1 (full file replacement)
            old_lines=len(original.splitlines()),
            new_start=1,  # Always 1 (full file replacement)
            new_lines=len(updated.splitlines()),
            lines=lines,
        )
    ]


def read_file(
    path: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Tuple[bool, TextFilePayload | dict]:
    """
    Read file content with CLAW's line number handling.

    Line number convention (CLAW pattern):
    - Internal: 0-indexed (for array slicing)
    - Output: 1-indexed (for human display)

    Args:
        path: File path to read
        offset: 0-indexed starting line (optional)
        limit: Maximum number of lines to read (optional)

    Returns:
        Tuple of (success: bool, payload: TextFilePayload | error_dict)
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return False, {
            "error": str(e),
            "file_path": path,
        }

    lines = content.splitlines()

    # Convert offset to internal 0-indexed (with bounds checking)
    start_index = min(offset or 0, len(lines))
    end_index = min(start_index + (limit or len(lines)), len(lines))

    # Extract selected lines
    selected_lines = lines[start_index:end_index]
    selected_content = "\n".join(selected_lines) if selected_lines else ""

    # Return payload with 1-indexed start_line (CLAW convention)
    payload = TextFilePayload(
        file_path=os.path.abspath(path),
        content=selected_content,
        num_lines=max(0, end_index - start_index),
        start_line=start_index + 1,  # Convert to 1-indexed for display
        total_lines=len(lines),
    )

    return True, payload


def edit_file(
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> Tuple[bool, EditFileOutput | dict]:
    """
    Edit file with CLAW's proven pattern:
    1. Pre-validation before mutation (BEFORE writing to disk)
    2. Exact string matching (no fuzzy matching)
    3. Return comprehensive output with structured patch

    Args:
        path: File path to edit
        old_string: Exact text to find and replace
        new_string: Exact text to replace with
        replace_all: If True, replace all occurrences; if False, replace only first

    Returns:
        Tuple of (success: bool, output: EditFileOutput | error_dict)
    """
    try:
        # Step 1: Read original file
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            original_file = f.read()
    except Exception as e:
        return False, {
            "error": f"Could not read file: {e}",
            "file_path": path,
        }

    # Step 2: Pre-validation (CLAW approach - BEFORE mutation)
    if old_string == new_string:
        return False, {
            "error": "old_string and new_string must differ",
            "file_path": path,
        }

    if old_string not in original_file:
        return False, {
            "error": "old_string not found in file",
            "file_path": path,
            "old_string_preview": old_string[:100] + "..."
            if len(old_string) > 100
            else old_string,
            "suggestions": [
                "Check if the exact context matches the file",
                "Verify whitespace and indentation",
                "The file may have changed since the patch was generated",
            ],
        }

    # Step 3: Perform replacement (exact, no fuzzy)
    if replace_all:
        updated = original_file.replace(old_string, new_string)
    else:
        # Replace only first occurrence
        updated = original_file.replace(old_string, new_string, 1)

    # Step 4: Write to disk
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
    except Exception as e:
        return False, {
            "error": f"Could not write file: {e}",
            "file_path": path,
        }

    # Step 5: Return comprehensive output (CLAW pattern)
    output = EditFileOutput(
        file_path=os.path.abspath(path),
        old_string=old_string,
        new_string=new_string,
        original_file=original_file,
        structured_patch=make_patch(original_file, updated),
        user_modified=False,
        replace_all=replace_all,
    )

    return True, output


def write_file(
    path: str,
    content: str,
) -> Tuple[bool, FileOperationResult | dict]:
    """
    Write content to a file.

    Args:
        path: File path to write
        content: Content to write

    Returns:
        Tuple of (success: bool, result: FileOperationResult | error_dict)
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        result = FileOperationResult(
            success=True,
            file_path=os.path.abspath(path),
            operation="write",
            message=f"File written successfully: {path}",
        )
        return True, result
    except Exception as e:
        return False, {
            "error": f"Could not write file: {e}",
            "file_path": path,
        }


def extract_hunk_context_from_diff(hunk_text: str) -> Optional[HunkContext]:
    """
    Extract old_string and new_string from a unified diff hunk.

    This parses a standard unified diff format hunk and extracts the exact
    strings for matching.

    Args:
        hunk_text: The hunk text in unified diff format

    Returns:
        HunkContext with old_string, new_string, and line numbers, or None if parsing fails
    """
    lines = hunk_text.strip().split("\n")

    # First line should be the hunk header: @@ -start,count +start,count @@
    if not lines or not lines[0].startswith("@@"):
        return None

    try:
        # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
        header_parts = lines[0].split("@@")
        range_part = header_parts[1].strip()
        ranges = range_part.split()

        # Parse old range
        old_range = ranges[0].lstrip("-").split(",")
        old_start = int(old_range[0]) if old_range[0] else 1
        old_lines = int(old_range[1]) if len(old_range) > 1 else 1

        # Parse new range
        new_range = ranges[1].lstrip("+").split(",")
        new_start = int(new_range[0]) if new_range[0] else 1
        new_lines = int(new_range[1]) if len(new_range) > 1 else 1
    except (IndexError, ValueError):
        return None

    # Extract old and new strings from hunk lines
    old_lines_list = []
    new_lines_list = []
    context_lines = []

    for line in lines[1:]:
        if line.startswith("-") and not line.startswith("---"):
            # Removed line
            old_lines_list.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            # Added line
            new_lines_list.append(line[1:])
        elif line.startswith(" "):
            # Context line
            context_lines.append(line[1:])
        elif line.startswith("\\"):
            # "\ No newline at end of file" marker
            continue

    old_string = "\n".join(old_lines_list)
    new_string = "\n".join(new_lines_list)

    if not old_string and not new_string:
        return None

    return HunkContext(
        old_string=old_string,
        new_string=new_string,
        old_start=old_start,
        old_lines=old_lines,
        new_start=new_start,
        new_lines=new_lines,
        context_lines=context_lines,
    )
