"""
CLAW-adapted file operations data structures.

This module contains exact Python equivalents of CLAW's file operation models.
It follows CLAW's line number conventions:
- Internal: 0-indexed (for array operations)
- Output: 1-indexed (for human display)
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class StructuredPatchHunk:
    """
    Exact Python equivalent of CLAW's StructuredPatchHunk.

    Represents a single hunk in a patch with explicit line tracking.
    Following CLAW's approach: one hunk per file to avoid line number cascading.
    """

    old_start: int  # 1-indexed: where the old section starts in the original file
    old_lines: int  # Number of lines in the old section
    new_start: int  # 1-indexed: where the new section starts in the updated file
    new_lines: int  # Number of lines in the new section
    lines: List[str]  # Patch lines with +/- prefixes

    def to_dict(self):
        """Convert to JSON-friendly dict with camelCase keys."""
        return {
            "oldStart": self.old_start,
            "oldLines": self.old_lines,
            "newStart": self.new_start,
            "newLines": self.new_lines,
            "lines": self.lines,
        }


@dataclass
class TextFilePayload:
    """
    Exact Python equivalent of CLAW's TextFilePayload.

    Represents a text file or portion of a file.
    Uses 1-indexed start_line for human readability (following CLAW pattern).
    """

    file_path: str
    content: str
    num_lines: int  # Number of lines in this chunk/section
    start_line: int  # 1-indexed: where this chunk starts in the file
    total_lines: int  # Total lines in the entire file

    def to_dict(self):
        """Convert to JSON-friendly dict with camelCase keys."""
        return {
            "filePath": self.file_path,
            "content": self.content,
            "numLines": self.num_lines,
            "startLine": self.start_line,
            "totalLines": self.total_lines,
        }


@dataclass
class EditFileOutput:
    """
    Exact Python equivalent of CLAW's EditFileOutput.

    Complete output from file editing operation, including:
    - Original file content (for verification)
    - Updated file content (what was written)
    - Structured patch (how it changed)
    - Metadata about the operation
    """

    file_path: str
    old_string: str
    new_string: str
    original_file: str
    structured_patch: List[StructuredPatchHunk]
    user_modified: bool = False
    replace_all: bool = False
    git_diff: Optional[dict] = None

    def to_dict(self):
        """Convert to JSON-friendly dict with camelCase keys."""
        return {
            "filePath": self.file_path,
            "oldString": self.old_string,
            "newString": self.new_string,
            "originalFile": self.original_file,
            "structuredPatch": [p.to_dict() for p in self.structured_patch],
            "userModified": self.user_modified,
            "replaceAll": self.replace_all,
            "gitDiff": self.git_diff,
        }


@dataclass
class HunkContext:
    """
    Context extracted from a diff hunk.

    Used to match the exact strings that need to be replaced.
    """

    old_string: str  # The exact text to find and replace
    new_string: str  # The exact text to replace it with
    old_start: int  # 1-indexed line number in old file
    old_lines: int  # Number of lines affected
    new_start: int  # 1-indexed line number in new file
    new_lines: int  # Number of lines in new version
    context_lines: List[str] = field(
        default_factory=list
    )  # Context lines for verification

    def to_dict(self):
        """Convert to JSON-friendly dict."""
        return {
            "oldString": self.old_string,
            "newString": self.new_string,
            "oldStart": self.old_start,
            "oldLines": self.old_lines,
            "newStart": self.new_start,
            "newLines": self.new_lines,
            "contextLines": self.context_lines,
        }


@dataclass
class FileOperationResult:
    """
    Result of a file operation (read, edit, write).

    Provides comprehensive output including success status, details, and structured data.
    """

    success: bool
    file_path: str
    operation: str  # "read", "edit", "write"
    message: str
    error: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    structured_patch: Optional[List[StructuredPatchHunk]] = None
    original_content: Optional[str] = None
    updated_content: Optional[str] = None
    metadata: Optional[dict] = None

    def to_dict(self):
        """Convert to JSON-friendly dict."""
        return {
            "success": self.success,
            "filePath": self.file_path,
            "operation": self.operation,
            "message": self.message,
            "error": self.error,
            "suggestions": self.suggestions,
            "structuredPatch": [p.to_dict() for p in (self.structured_patch or [])],
            "originalContent": self.original_content,
            "updatedContent": self.updated_content,
            "metadata": self.metadata,
        }
