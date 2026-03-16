from dataclasses import dataclass
from typing import List, Optional
from unidiff import PatchSet
import io

@dataclass
class FileChange:
    file_path: str
    change_type: str  # "MODIFIED", "ADDED", "DELETED", "RENAMED"
    added_lines: List[str]
    removed_lines: List[str]
    is_test_file: bool

class PatchAnalyzer:
    def __init__(self):
        pass

    def parse_diff(self, diff_text: str) -> PatchSet:
        """
        Parses a raw git diff string into a unidiff PatchSet.
        """
        return PatchSet(io.StringIO(diff_text))

    def analyze(self, diff_text: str, with_test_changes: bool = False) -> List[FileChange]:
        """
        Analyzes a raw git diff and returns structured information about each file change.
        
        Args:
            diff_text: Raw unified diff text
            with_test_changes: If False (default), filters out test file changes.
                             If True, includes all changes including test files.
        
        Returns:
            List[FileChange]: File changes, optionally filtered to exclude test files
        """
        patch_set = self.parse_diff(diff_text)
        changes = []

        for patched_file in patch_set:
            change_type = "MODIFIED"
            if patched_file.is_added_file:
                change_type = "ADDED"
            elif patched_file.is_removed_file:
                change_type = "DELETED"
            elif patched_file.is_rename:
                change_type = "RENAMED"

            added_lines = []
            removed_lines = []

            for hunk in patched_file:
                for line in hunk:
                    if line.is_added:
                        added_lines.append(line.value.strip())
                    elif line.is_removed:
                        removed_lines.append(line.value.strip())

            file_path = patched_file.path
            is_test_file = self._is_test_file(file_path)
            
            # Skip test file changes if with_test_changes is False
            if not with_test_changes and is_test_file:
                continue

            changes.append(FileChange(
                file_path=file_path,
                change_type=change_type,
                added_lines=added_lines,
                removed_lines=removed_lines,
                is_test_file=is_test_file
            ))

        return changes

    def _is_test_file(self, file_path: str) -> bool:
        """
        Heuristic to determine if a file is a test file.
        """
        lower_path = file_path.lower()
        return "test" in lower_path or lower_path.endswith("test.java")

    def extract_raw_hunks(self, diff_text: str, with_test_changes: bool = False) -> dict:
        """
        Extracts raw hunk text per file from a unified diff.
        
        Args:
            diff_text: Raw unified diff text
            with_test_changes: If False (default), filters out test file hunks.
                             If True, includes all hunks including test files.

        Returns:
            dict mapping file_path -> list of hunk strings (each hunk is the raw
            unified-diff text including the @@ header and context lines).  This
            lets Agent 1 pass individual hunks into an LLM prompt without having
            to re-parse the full diff.
        """
        patch_set = self.parse_diff(diff_text)
        result: dict[str, list[str]] = {}

        for patched_file in patch_set:
            file_path = patched_file.path
            
            # Skip test files if with_test_changes is False
            if not with_test_changes and self._is_test_file(file_path):
                continue
            
            hunks: list[str] = []
            for hunk in patched_file:
                lines = []
                # Reconstruct hunk header
                lines.append(
                    f"@@ -{hunk.source_start},{hunk.source_length} "
                    f"+{hunk.target_start},{hunk.target_length} @@"
                )
                for line in hunk:
                    if line.is_added:
                        lines.append(f"+{line.value}")
                    elif line.is_removed:
                        lines.append(f"-{line.value}")
                    else:
                        lines.append(f" {line.value}")
                hunks.append("".join(lines))
            result[file_path] = hunks

        return result
