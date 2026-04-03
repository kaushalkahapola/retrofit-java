"""
HunkGeneratorToolkit — Tools for the Intelligent Hunk Generator (Agent 3)

Provides a rich set of tools that allow the hunk generator to:
1. Read exact file content around an insertion point (read_file_window)
2. Search for a string in a file and get its exact line number (grep_in_file)
3. Fetch a numbered line range from a file (get_exact_lines)
4. Verify whether specific context text appears at a given line (verify_context_at_line)
5. Manage a per-hunk todo list so the agent can plan "get more context" tasks
   before committing to a diff output

These tools directly address the root causes identified in the analysis:
  - LLM blindly uses code_snippet context without knowing if it exactly matches
    the real file at the insertion line
  - No way to look up the actual neighbors of an insertion point
  - No mechanism to flag "I need more information before I can generate this hunk"
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from langchain_core.tools import StructuredTool


class HunkGeneratorToolkit:
    """
    Lightweight toolkit bound to a single target repository.

    All file paths are relative to target_repo_path. Absolute paths are also
    accepted and normalised automatically.
    """

    def __init__(self, target_repo_path: str) -> None:
        self.target_repo_path = target_repo_path
        # Per-session todo list: list[{"id": str, "status": str, "task": str}]
        self._todos: list[dict[str, str]] = []
        self._todo_counter: int = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _full_path(self, rel_path: str) -> str:
        """Resolve a repo-relative path to an absolute path."""
        p = (rel_path or "").strip().replace("\\", "/").lstrip("/")
        if p.startswith("a/") or p.startswith("b/"):
            p = p[2:]
        full = os.path.normpath(os.path.join(self.target_repo_path, p))
        return full

    def _read_lines(self, rel_path: str) -> list[str] | None:
        """Return all lines of a file, or None if the file cannot be read."""
        try:
            with open(
                self._full_path(rel_path), "r", encoding="utf-8", errors="replace"
            ) as f:
                return f.read().splitlines()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Tool 1: read_file_window
    # ------------------------------------------------------------------

    def read_file_window(
        self,
        file_path: str,
        center_line: int,
        radius: int = 15,
    ) -> str:
        """
        Read a window of lines from a target file centred on *center_line*
        (1-indexed). Returns lines with their 1-indexed line numbers so the
        agent can see exactly what appears at and around the insertion point.

        Use this tool to verify the real file content before writing context
        lines in a diff hunk. This is the primary tool to call when you are
        unsure whether the code_snippet you received matches the actual file.

        Args:
            file_path:   Repo-relative path to the file.
            center_line: 1-indexed line to centre the window on.
            radius:      Number of lines to include above and below center_line.
                         Default 15 (i.e. up to 31 lines total).

        Returns:
            A string with numbered lines like:
                59:  abstract class DataNodeRequestSender {
                60:      private final ClusterService clusterService;
                ...
            Or an error message if the file cannot be read.
        """
        lines = self._read_lines(file_path)
        if lines is None:
            return f"ERROR: Cannot read file '{file_path}' in target repo."

        total = len(lines)
        # Convert to 0-indexed for slicing
        center_0 = max(0, center_line - 1)
        start_0 = max(0, center_0 - radius)
        end_0 = min(total, center_0 + radius + 1)

        out_parts: list[str] = [
            f"[read_file_window] {file_path}  (total lines: {total})",
            f"Showing lines {start_0 + 1}–{end_0}  (center={center_line}):",
            "",
        ]
        for i in range(start_0, end_0):
            marker = " >" if (i == center_0) else "  "
            out_parts.append(f"{marker}{i + 1:5d}: {lines[i]}")

        return "\n".join(out_parts)

    # ------------------------------------------------------------------
    # Tool 2: grep_in_file
    # ------------------------------------------------------------------

    def grep_in_file(
        self,
        file_path: str,
        search_text: str,
        is_regex: bool = False,
        max_results: int = 10,
    ) -> str:
        """
        Search for *search_text* in a target file and return every matching
        line with its 1-indexed line number.

        Use this tool to find the exact line number where a specific string
        appears in the target file. This is essential for anchoring context
        lines in a hunk so that git-apply can match them.

        Args:
            file_path:   Repo-relative path to the file.
            search_text: Literal text or regex pattern to search for.
            is_regex:    If True, treat search_text as a Python regex.
                         Default False (literal string search).
            max_results: Maximum number of matches to return. Default 10.

        Returns:
            Formatted list of matches with line numbers, e.g.:
                Line  59: abstract class DataNodeRequestSender {
                Line 340: private List<NodeRequest> selectNodeRequests(...)
            Or "No matches found" / an error message.
        """
        lines = self._read_lines(file_path)
        if lines is None:
            return f"ERROR: Cannot read file '{file_path}' in target repo."

        matches: list[tuple[int, str]] = []
        try:
            pattern = re.compile(search_text) if is_regex else None
        except re.error as e:
            return f"ERROR: Invalid regex pattern: {e}"

        for i, line in enumerate(lines, start=1):
            if pattern:
                if pattern.search(line):
                    matches.append((i, line))
            else:
                if search_text in line:
                    matches.append((i, line))
            if len(matches) >= max_results:
                break

        if not matches:
            return f"No matches found for '{search_text}' in '{file_path}'."

        out_parts = [
            f"[grep_in_file] Matches for '{search_text}' in {file_path}:",
            "",
        ]
        for lineno, text in matches:
            out_parts.append(f"  Line {lineno:5d}: {text}")

        if len(matches) == max_results:
            out_parts.append(f"  ... (truncated at {max_results} results)")

        return "\n".join(out_parts)

    # ------------------------------------------------------------------
    # Tool 3: get_exact_lines
    # ------------------------------------------------------------------

    def get_exact_lines(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
    ) -> str:
        """
        Return the exact content of lines *start_line* to *end_line*
        (inclusive, 1-indexed) from a target file.

        Use this to extract precise context lines to embed verbatim in your
        diff hunk header. The text returned is exactly what git-apply will
        compare against.

        Args:
            file_path:  Repo-relative path to the file.
            start_line: First line to return (1-indexed, inclusive).
            end_line:   Last line to return (1-indexed, inclusive).

        Returns:
            Numbered lines like:
                126:      nodePermits.putIfAbsent(node, new Semaphore(1));
                127:      ...
        """
        lines = self._read_lines(file_path)
        if lines is None:
            return f"ERROR: Cannot read file '{file_path}' in target repo."

        total = len(lines)
        s = max(0, start_line - 1)  # 0-indexed
        e = min(total, end_line)  # 0-indexed exclusive

        if s >= e:
            return (
                f"ERROR: Line range {start_line}-{end_line} is out of bounds "
                f"for '{file_path}' (total lines: {total})."
            )

        out_parts = [
            f"[get_exact_lines] {file_path}  lines {start_line}-{min(end_line, total)}:",
            "",
        ]
        for i in range(s, e):
            out_parts.append(f"{i + 1:5d}: {lines[i]}")

        return "\n".join(out_parts)

    # ------------------------------------------------------------------
    # Tool 4: verify_context_at_line
    # ------------------------------------------------------------------

    def verify_context_at_line(
        self,
        file_path: str,
        line_number: int,
        expected_text: str,
    ) -> str:
        """
        Check whether *expected_text* appears at or very near *line_number*
        (1-indexed) in the target file.

        Use this BEFORE finalising context lines in a hunk to confirm that
        the text you plan to use as a context line actually matches the file.
        This prevents git-apply context-mismatch failures.

        Returns one of:
          - "EXACT_MATCH at line N" — the text matches exactly at that line
          - "TRIMMED_MATCH at line N" — matches after stripping whitespace
          - "NEARBY_MATCH at line N (searched ±5)" — found within ±5 lines
          - "NOT_FOUND (searched ±10 lines around N)" — does not match nearby
          - An error message if the file cannot be read.

        Args:
            file_path:     Repo-relative path to the file.
            line_number:   Expected 1-indexed line number.
            expected_text: The text to verify (a single line, without prefix).
        """
        lines = self._read_lines(file_path)
        if lines is None:
            return f"ERROR: Cannot read file '{file_path}' in target repo."

        total = len(lines)
        idx_0 = line_number - 1  # 0-indexed

        # Pass 1: exact match at stated line
        if 0 <= idx_0 < total and lines[idx_0] == expected_text:
            return f"EXACT_MATCH at line {line_number}: '{expected_text}'"

        # Pass 2: trimmed match at stated line
        if 0 <= idx_0 < total and lines[idx_0].strip() == expected_text.strip():
            return (
                f"TRIMMED_MATCH at line {line_number}: '{expected_text}' "
                f"(actual: '{lines[idx_0]}')"
            )

        # Pass 3: search ±5 lines
        radius = 5
        lo = max(0, idx_0 - radius)
        hi = min(total, idx_0 + radius + 1)
        for i in range(lo, hi):
            if lines[i].strip() == expected_text.strip():
                return (
                    f"NEARBY_MATCH at line {i + 1} (searched ±{radius}): "
                    f"'{expected_text}' — you may need to update your hunk header "
                    f"from line {line_number} to line {i + 1}."
                )

        # Pass 4: wider search ±10
        wide = 10
        lo = max(0, idx_0 - wide)
        hi = min(total, idx_0 + wide + 1)
        for i in range(lo, hi):
            if expected_text.strip() in lines[i]:
                return (
                    f"SUBSTRING_MATCH at line {i + 1} (searched ±{wide}): "
                    f"line contains '{expected_text.strip()}' — use exact line content."
                )

        return (
            f"NOT_FOUND: '{expected_text}' not found within ±{wide} lines of "
            f"line {line_number} in '{file_path}'. "
            "Use grep_in_file to locate the exact line number."
        )

    # ------------------------------------------------------------------
    # Tool 5: todo_list — plan & track context-gathering tasks
    # ------------------------------------------------------------------

    def manage_todo(
        self,
        action: str,
        task: str = "",
        todo_id: str = "",
    ) -> str:
        """
        Manage a personal todo list for planning hunk-generation work.

        This is the key tool that makes hunk generation intelligent: use it to
        create tasks like "get more context around line 59" BEFORE generating
        the diff. Complete tasks in order so you have all the information you
        need before writing the final hunk.

        Actions:
          "add"      — Add a new task. Requires *task* text.
                       Example: manage_todo("add", task="Read file window around line 59 to verify class body context")
          "complete" — Mark a task done. Requires *todo_id*.
          "list"     — Show all current tasks with their status.
          "clear"    — Remove all completed tasks.

        Recommended workflow:
          1. Call manage_todo("add", ...) for each context-gathering step you need.
          2. Call manage_todo("list") to review your plan.
          3. Execute each tool call (read_file_window, grep_in_file, etc.).
          4. Call manage_todo("complete", todo_id=<id>) after each step.
          5. Only generate the final hunk once all todos are completed.

        Returns a formatted string describing the result.
        """
        action = (action or "").strip().lower()

        if action == "add":
            if not task:
                return "ERROR: 'add' action requires a non-empty 'task' string."
            self._todo_counter += 1
            todo_id_new = f"todo_{self._todo_counter}"
            self._todos.append({"id": todo_id_new, "status": "pending", "task": task})
            return f"Added todo [{todo_id_new}]: {task}"

        elif action == "complete":
            if not todo_id:
                return "ERROR: 'complete' action requires a 'todo_id'."
            for t in self._todos:
                if t["id"] == todo_id:
                    t["status"] = "done"
                    return f"Completed [{todo_id}]: {t['task']}"
            return f"ERROR: todo_id '{todo_id}' not found."

        elif action == "list":
            if not self._todos:
                return "Todo list is empty."
            lines = ["[Todo List]", ""]
            for t in self._todos:
                icon = "✅" if t["status"] == "done" else "⬜"
                lines.append(f"  {icon} [{t['id']}] {t['task']}")
            pending = sum(1 for t in self._todos if t["status"] == "pending")
            lines.append(f"\n{pending} pending / {len(self._todos)} total")
            return "\n".join(lines)

        elif action == "clear":
            before = len(self._todos)
            self._todos = [t for t in self._todos if t["status"] != "done"]
            removed = before - len(self._todos)
            return f"Cleared {removed} completed task(s). {len(self._todos)} remaining."

        else:
            return (
                f"ERROR: Unknown action '{action}'. "
                "Valid actions: 'add', 'complete', 'list', 'clear'."
            )

    # ------------------------------------------------------------------
    # Tool 6: get_file_info
    # ------------------------------------------------------------------

    def get_file_info(self, file_path: str) -> str:
        """
        Return basic metadata about a target file: total line count and the
        first 10 lines. Useful for a quick sanity-check that you are looking
        at the correct file before diving deeper.

        Args:
            file_path: Repo-relative path to the file.
        """
        lines = self._read_lines(file_path)
        if lines is None:
            return f"ERROR: Cannot read file '{file_path}' in target repo."

        preview = "\n".join(f"{i + 1:5d}: {l}" for i, l in enumerate(lines[:10]))
        return (
            f"[get_file_info] {file_path}\n"
            f"Total lines: {len(lines)}\n\n"
            f"First 10 lines:\n{preview}"
        )

    # ------------------------------------------------------------------
    # Tool 7: build_unified_hunk
    # ------------------------------------------------------------------

    def build_unified_hunk(
        self,
        file_path: str,
        start_line: int,
        old_count: int,
        context_before: str = "",
        removed_lines: str = "",
        added_lines: str = "",
        context_after: str = "",
    ) -> str:
        """
        Build a syntactically valid unified diff hunk from structured pieces.

        Inputs `removed_lines` and `added_lines` are newline-separated payload lines
        (WITHOUT '-'/'+' prefixes). This tool applies correct diff prefixes and
        computes a valid +count from the resulting body shape.
        """
        before = [x for x in str(context_before or "").splitlines()]
        removed = [x for x in str(removed_lines or "").splitlines()]
        added = [x for x in str(added_lines or "").splitlines()]
        after = [x for x in str(context_after or "").splitlines()]

        body: list[str] = []
        body.extend([f" {x}" for x in before])
        body.extend([f"-{x}" for x in removed])
        body.extend([f"+{x}" for x in added])
        body.extend([f" {x}" for x in after])

        src_count = sum(1 for ln in body if ln.startswith(" ") or ln.startswith("-"))
        tgt_count = sum(1 for ln in body if ln.startswith(" ") or ln.startswith("+"))

        src_start = max(0, int(start_line or 0))
        src_count = int(old_count or src_count)
        if src_count < 0:
            src_count = 0

        header = f"@@ -{src_start},{src_count} +{src_start},{tgt_count} @@"
        out = "\n".join([header] + body)
        if not out.endswith("\n"):
            out += "\n"
        return out

    # ------------------------------------------------------------------
    # LangChain tool registration
    # ------------------------------------------------------------------

    def get_tools(self) -> list[StructuredTool]:
        """Return all tools as LangChain StructuredTool objects."""
        return [
            StructuredTool.from_function(
                func=self.read_file_window,
                name="read_file_window",
                description=(
                    "Read a window of lines from a target file centred on center_line "
                    "(1-indexed). Returns numbered lines so you can see exact content "
                    "around the insertion point. Use BEFORE writing context lines in a hunk."
                ),
            ),
            StructuredTool.from_function(
                func=self.grep_in_file,
                name="grep_in_file",
                description=(
                    "Search for a string (or regex) in a target file and return matching "
                    "lines with their 1-indexed line numbers. Use to anchor the correct "
                    "line number for a context line before writing a hunk header."
                ),
            ),
            StructuredTool.from_function(
                func=self.get_exact_lines,
                name="get_exact_lines",
                description=(
                    "Return the exact content of lines start_line to end_line (inclusive, "
                    "1-indexed) from a target file. Use to extract verbatim context lines "
                    "to embed in a diff hunk."
                ),
            ),
            StructuredTool.from_function(
                func=self.verify_context_at_line,
                name="verify_context_at_line",
                description=(
                    "Check whether expected_text appears at line_number (1-indexed) in the "
                    "target file. Returns EXACT_MATCH, TRIMMED_MATCH, NEARBY_MATCH, or "
                    "NOT_FOUND. Call this BEFORE finalising context lines in a hunk to "
                    "prevent git-apply failures."
                ),
            ),
            StructuredTool.from_function(
                func=self.manage_todo,
                name="manage_todo",
                description=(
                    "Manage a personal todo list for planning hunk work. Actions: "
                    "'add' (add a task), 'complete' (mark done), 'list' (show all), "
                    "'clear' (remove done tasks). Use to plan context-gathering steps "
                    "BEFORE generating the final diff output."
                ),
            ),
            StructuredTool.from_function(
                func=self.get_file_info,
                name="get_file_info",
                description=(
                    "Return total line count and first 10 lines of a target file. "
                    "Quick sanity-check to confirm you are looking at the right file."
                ),
            ),
            StructuredTool.from_function(
                func=self.build_unified_hunk,
                name="build_unified_hunk",
                description=(
                    "Build a valid unified diff hunk from structured fields. "
                    "Pass removed/added lines WITHOUT diff prefixes; tool adds '-', '+' "
                    "and computes header counts safely to avoid malformed hunks."
                ),
            ),
        ]
