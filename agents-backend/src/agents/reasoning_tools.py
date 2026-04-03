from typing import List, Dict, Optional
from langchain_core.tools import StructuredTool
from utils.retrieval.ensemble_retriever import EnsembleRetriever
from utils.patch_analyzer import PatchAnalyzer, FileChange
import os
import re
import subprocess

from utils.models import ImplementationPlan
from utils.structural_matcher import find_best_matches


class ReasoningToolkit:
    def __init__(
        self,
        retriever: EnsembleRetriever,
        target_repo_path: str,
        mainline_repo_path: str,
        patch_analysis: List[FileChange],
    ):
        self.retriever = retriever
        self.target_repo_path = target_repo_path
        self.mainline_repo_path = mainline_repo_path
        self.patch_analysis = patch_analysis

    def search_candidates(self, file_path: str) -> List[Dict]:
        """
        Searches for potential candidate files in the target repository that correspond to the given source file path.
        Returns a list of candidates with scores and reasoning.
        """
        return self.retriever.find_candidates(file_path, "HEAD")

    def read_file(self, file_path: str) -> str:
        """
        Reads the content of a file in the target repository.
        The file_path should be relative to the target repository root.
        """
        full_path = os.path.join(self.target_repo_path, file_path)
        if not os.path.exists(full_path):
            return f"Error: File not found at {file_path}"
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

                # Strip Comments to avoid Recitation/Copyright filters
                # Remove block comments
                content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
                # Remove line comments
                content = re.sub(r"//.*", "", content)

                lines = content.splitlines()
                # Remove empty lines created by stripping
                lines = [line for line in lines if line.strip()]

                if len(lines) > 2000:
                    return (
                        "\n".join(lines[:2000])
                        + "\n\n... [Truncated: File too large] ..."
                    )
                return "\n".join(lines)
        except Exception as e:
            return f"Error reading file: {e}"

    def list_files(self, directory: str = ".") -> List[str]:
        """
        Lists files in a directory of the target repository.
        Useful for exploring the directory structure.
        """
        full_path = os.path.join(self.target_repo_path, directory)
        if not os.path.exists(full_path):
            return [f"Error: Directory not found at {directory}"]

        try:
            files = []
            for f in os.listdir(full_path):
                if not f.startswith("."):  # Ignore hidden files
                    files.append(f)
            return files
        except Exception as e:
            return [f"Error listing files: {e}"]

    def get_dependency_graph(
        self,
        file_paths: List[str],
        explore_neighbors: bool = False,
        use_mainline: bool = False,
    ) -> Dict:
        """
        Analyzes dependencies between a list of Java files.
        Returns a graph where nodes are files and edges are dependencies (imports, inheritance, usage).

        Args:
            file_paths: List of relative paths to Java files.
            explore_neighbors: If True, also analyzes all other Java files in the same directory as the input files.
            use_mainline: If True, analyzes the Mainline repository instead of the Target repository.
        """
        from utils.mcp_client import get_client

        client = get_client()

        repo_path = self.mainline_repo_path if use_mainline else self.target_repo_path

        return client.call_tool(
            "get_dependency_graph",
            {
                "target_repo_path": repo_path,
                "file_paths": file_paths,
                "explore_neighbors": explore_neighbors,
            },
        )

    def get_class_context(
        self,
        file_path: str,
        focus_method: Optional[str] = None,
        use_mainline: bool = False,
    ):
        """
        Reads a Java file and returns a skeleton view with the full body of the focused method.
        Useful for verifying specific methods without reading the entire file.
        """
        from utils.mcp_client import get_client

        client = get_client()

        repo_path = self.mainline_repo_path if use_mainline else self.target_repo_path
        # Normalize empty/null-ish focus values to None for MCP.
        focus = focus_method.strip() if isinstance(focus_method, str) else focus_method
        if focus in {"", "null", "None"}:
            focus = None

        return client.call_tool(
            "get_class_context",
            {
                "target_repo_path": repo_path,
                "file_path": file_path,
                "focus_method": focus,
            },
        )

    def get_structural_analysis(
        self, file_path: str, use_mainline: bool = False
    ) -> Dict:
        """
        Gets rich structural analysis (AST) for a file.
        """
        from utils.mcp_client import get_client

        client = get_client()

        repo_path = self.mainline_repo_path if use_mainline else self.target_repo_path

        # The Java side returns a list of classes, we usually just want the first/main one for matching
        result = client.call_tool(
            "get_structural_analysis",
            {"target_repo_path": repo_path, "file_path": file_path},
        )
        return result

    def match_structure(
        self, mainline_file_path: str, candidate_file_paths: List[str]
    ) -> str:
        """
        Determines the best matching target file(s) for a given mainline file using structural analysis.
        Returns a JSON string describing the best match and the reasoning.
        """
        import json

        # 1. Analyze Mainline File
        mainline_analysis = self.get_structural_analysis(
            mainline_file_path, use_mainline=True
        )
        if "classes" not in mainline_analysis or not mainline_analysis["classes"]:
            return json.dumps(
                {"error": f"Could not analyze mainline file: {mainline_file_path}"}
            )
        mainline_node_data = mainline_analysis["classes"][
            0
        ]  # Assume one top level class for now

        # 2. Analyze Candidate Files
        candidates_data = []
        for cand_path in candidate_file_paths:
            cand_analysis = self.get_structural_analysis(cand_path, use_mainline=False)
            if "classes" in cand_analysis and cand_analysis["classes"]:
                # Inject the file path into the data so the matcher knows which file it is
                data = cand_analysis["classes"][0]
                data["file_path"] = cand_path
                candidates_data.append(data)

        if not candidates_data:
            return json.dumps({"error": "No valid candidates to analyze."})

        # 3. Run Matcher
        result_dict = find_best_matches(mainline_node_data, candidates_data)
        matches = result_dict["matches"]
        completeness = result_dict["completeness"]

        # 4. Format Output
        results = []
        for m in matches:
            results.append(
                {
                    "file_path": m["data"]["file_path"],
                    "score": round(m["score"], 2),
                    "reasoning": "High structural similarity (Inheritance/Calls/Fields)",
                }
            )

        return json.dumps(
            {
                "matches": results,
                "verification": {
                    "completeness_ratio": round(completeness["ratio"], 2),
                    "missing_features": completeness["missing"],
                    "status": "COMPLETE"
                    if not completeness["missing"]
                    else "PARTIAL_MATCH",
                },
            },
            indent=2,
        )

    def find_method_match(
        self,
        target_file_path: str,
        old_method_name: str,
        old_signature: str,
        old_calls: List[str],
    ) -> str:
        """
        Uses Method Fingerprinting to find a renamed method in a target file.
        Returns a JSON string with the best match.
        """
        from utils.method_fingerprinter import MethodFingerprinter
        from utils.mcp_client import get_client

        # 1. Get all methods from the target file using GetDependencyTool
        # We need to analyze just this one file to get its method list
        client = get_client()
        graph = client.call_tool(
            "get_dependency_graph",
            {
                "target_repo_path": self.target_repo_path,
                "file_paths": [target_file_path],
                "explore_neighbors": False,
            },
        )

        candidate_methods = []
        for node in graph.get("nodes", []):
            if node.get("id").endswith(
                target_file_path.replace("/", ".").replace(".java", "")
            ):  # Rough match
                candidate_methods = node.get("methods", [])
                break

        if not candidate_methods:
            # Fallback: try to find any node that looks like the file
            if graph.get("nodes"):
                candidate_methods = graph.get("nodes")[0].get("methods", [])

        # 2. Tier 1: Git Tracing & Pickaxe
        # We need the Mainline Commit ID to do tracing properly.
        # But `find_method_match` doesn't currently take it.
        # Ideally we'd modify the tool signature. For now, let's use Pickaxe (which works if we search "recently").

        from utils.method_discovery import GitMethodTracer, BodySimilarityMatcher

        tracer = GitMethodTracer(self.target_repo_path)

        # Try finding where the signature moved
        moved_file = tracer.find_moved_method_by_pickaxe(old_method_name, old_signature)
        if moved_file and moved_file.endswith(
            target_file_path.split("/")[-1]
        ):  # Simple check if it points to our file
            # It found it in this file!
            # Now find which method name it is?
            # Pickaxe just says "The signature void foo() appeared in this file".
            # It implies the method name is still 'foo'.
            pass

        # 3. Tier 2: Body Similarity (Content Diff)
        # We need the BODY of the old method.
        # Argument `old_code` is passed to this tool.
        # We also need the BODY of the candidate methods.
        # `get_dependency_graph` does NOT return bodies.
        # We need `read_file` or `get_class_context` to get bodies.
        # This is expensive (N reads).
        # Optimization: Only read bodies of Top-3 candidates from Name/Signature match?

        body_matcher = BodySimilarityMatcher()
        best_body_score = 0
        best_body_cand = None

        # If we have old code, try to match it against candidates
        # For now, we assume candidates don't have bodies unless we fetch them.
        # Let's skip expensive N-fetches for this baseline step unless we are desperate.

        # 4. Tier 3: Call Graph (Existing Fingerprinter)
        fingerprinter = MethodFingerprinter()
        result = fingerprinter.find_match(
            old_method_name=old_method_name,
            old_signature=old_signature,
            old_code="",  # Optional for now
            old_calls=old_calls,
            candidate_methods=candidate_methods,
        )

        return str(result)

    # ------------------------------------------------------------------
    # Patch Applicability Check (used by Phase 0 and exposed as LLM tool)
    # ------------------------------------------------------------------

    def check_patch_applicability(self) -> Dict:
        """
        Public method: Attempts `git apply --check` of the current patch against the
        target repo. Returns {"success": bool, "output": str}.
        Called by phase0_optimistic.py.
        """
        patch_path = None
        for change in self.patch_analysis:
            # Resolve the patch file path from the retriever's stored patch path
            break
        # Walk up from ensemble retriever target path to find the patch
        # The patch path is injected externally — this method wraps the git call.
        return self._run_git_apply_check(self.retriever.target_repo.working_dir)

    def check_patch_applicability_internal(self, patch_path: str) -> str:
        """
        LLM-facing tool wrapper. Runs `git apply --check` with the given patch path.
        Returns a summary string suitable for LLM consumption.
        """
        result = self._run_git_apply_check(
            self.retriever.target_repo.working_dir, patch_path
        )
        if result["success"]:
            return "Patch applies cleanly. No conflicts detected."
        return f"Patch does NOT apply cleanly:\n{result['output']}"

    def _run_git_apply_check(self, repo_dir: str, patch_path: str = None) -> Dict:
        """
        Core implementation: runs `git apply --check <patch_path>` in repo_dir.
        If patch_path is None, looks for the patch file from state (best-effort).
        """
        if not patch_path:
            return {
                "success": False,
                "output": "No patch path provided to git apply check.",
            }
        try:
            result = subprocess.run(
                ["git", "apply", "--check", patch_path],
                capture_output=True,
                text=True,
                cwd=repo_dir,
            )
            if result.returncode == 0:
                return {"success": True, "output": result.stdout or "Clean apply."}
            else:
                return {"success": False, "output": result.stderr or result.stdout}
        except Exception as e:
            return {
                "success": False,
                "output": f"Exception during git apply check: {e}",
            }

    # ------------------------------------------------------------------
    # Struct / Class Definition Fetcher (Agent 1 support)
    # ------------------------------------------------------------------

    def get_struct_definition(
        self, struct_name: str, use_mainline: bool = True
    ) -> Dict:
        """
        Retrieves the full definition of a class or struct by name from AST analysis.
        Useful for Agent 1 to pull dependent types referenced in the patch.

        Args:
            struct_name: Simple class/interface/struct name (e.g. 'ByteBuffer').
            use_mainline: If True (default), searches the mainline repository.

        Returns:
            Dict with 'class_name', 'fields', 'methods', 'superclass', 'interfaces' keys.
            Returns {'error': ...} if not found.
        """
        from utils.mcp_client import get_client

        client = get_client()
        repo_path = self.mainline_repo_path if use_mainline else self.target_repo_path

        # Use ripgrep-style search to find the file defining the struct first
        try:
            result = subprocess.run(
                [
                    "grep",
                    "-r",
                    "--include=*.java",
                    "-l",
                    f"class {struct_name}|interface {struct_name}",
                    repo_path,
                ],
                capture_output=True,
                text=True,
            )
            candidates = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except Exception:
            candidates = []

        if not candidates:
            return {
                "error": f"No file found defining '{struct_name}' in {'mainline' if use_mainline else 'target'} repo."
            }

        # Analyze the first match
        rel_path = os.path.relpath(candidates[0], repo_path)
        analysis = client.call_tool(
            "get_structural_analysis",
            {
                "target_repo_path": repo_path,
                "file_path": rel_path,
            },
        )
        classes = analysis.get("classes", [])
        for cls in classes:
            if cls.get("simpleName") == struct_name or cls.get("name", "").endswith(
                struct_name
            ):
                return cls
        # Return first class if name filter didn't hit
        return (
            classes[0]
            if classes
            else {"error": f"Struct '{struct_name}' not found in {rel_path}."}
        )

    def get_function_body(
        self, file_path: str, function_name: str, use_mainline: bool = True
    ) -> str:
        """
        Retrieves the exact body of a function from a file.
        Useful for Agent 1 to isolate logic.
        """
        # We reuse get_class_context which already focuses on a specific method.
        # It returns a string representation with the method body fully expanded and other methods stubbed.
        # This is exactly what we need.
        context = self.get_class_context(
            file_path, focus_method=function_name, use_mainline=use_mainline
        )
        return str(context)

    # ------------------------------------------------------------------
    # Git & Diff Operators (Phase 5)
    # ------------------------------------------------------------------

    def git_log_follow(self, file_path: str, use_mainline: bool = False) -> str:
        """
        Retrieves the git history for a file, following renames.
        Useful for Agent 2 to find where a file moved.
        """
        repo_path = self.mainline_repo_path if use_mainline else self.target_repo_path
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--follow",
                    "--name-status",
                    "--oneline",
                    "--",
                    file_path,
                ],
                capture_output=True,
                text=True,
                cwd=repo_path,
                check=True,
            )
            return result.stdout or "No history found."
        except subprocess.CalledProcessError as e:
            return f"Error running git log: {e.stderr}"

    def git_blame_lines(
        self, file_path: str, start_line: int, end_line: int, use_mainline: bool = False
    ) -> str:
        """
        Retrieves git blame for specific lines in a file.
        Useful for Agent 1/2 to understand lineage of the code.
        """
        repo_path = self.mainline_repo_path if use_mainline else self.target_repo_path
        try:
            result = subprocess.run(
                ["git", "blame", "-L", f"{start_line},{end_line}", "--", file_path],
                capture_output=True,
                text=True,
                cwd=repo_path,
                check=True,
            )
            return result.stdout or "No blame found."
        except subprocess.CalledProcessError as e:
            return f"Error running git blame: {e.stderr}"

    def grep_repo(self, search_text: str, is_regex: bool = False) -> str:
        """
        Performs a repository-wide search for a code snippet in Java files.
        Returns a list of matching files and line numbers.
        """
        hits = self.retriever.grep_repo(search_text, is_regex)
        if not hits:
            return f"No matches found for '{search_text}'."

        lines = [f"Found {len(hits)} match(es):"]
        for h in hits[:20]:  # Limit to 20 hits for LLM consumption
            lines.append(f"  {h['file']}:{h['line']} :: {h['content'].strip()}")
        if len(hits) > 20:
            lines.append(f"  ... (truncated {len(hits) - 20} more matches)")
        return "\n".join(lines)

    def find_symbol_locations(self, symbol_name: str) -> str:
        """
        Uses the repository index to find all Java files where a specific
        class or method name is declared.
        """
        files = self.retriever.find_symbol_locations(symbol_name)
        if not files:
            return f"Symbol '{symbol_name}' not found in target repository index."
        return f"Symbol '{symbol_name}' declared in:\n  - " + "\n  - ".join(files)

    def find_text_neighbors(
        self,
        search_text: str,
        context_lines: int = 4,
        max_hits: int = 20,
    ) -> str:
        """
        Repository-wide lexical search with small local context windows.
        Helps Agent 2 locate semantically-equivalent logic even when file mapping diverges.
        """
        txt = str(search_text or "").strip()
        if not txt:
            return "ERROR: search_text is required."

        hits = self.retriever.grep_repo(txt, is_regex=False)
        if not hits:
            return f"No matches found for '{txt}'."

        ctx_n = max(1, min(int(context_lines or 4), 20))
        cap = max(1, min(int(max_hits or 20), 100))
        out: list[str] = [
            f"Found {min(len(hits), cap)} / {len(hits)} hit(s) for '{txt}':"
        ]

        for h in hits[:cap]:
            file_path = h.get("file")
            line_no = int(h.get("line") or 1)
            line_txt = (h.get("content") or "").strip()
            out.append(f"- {file_path}:{line_no}: {line_txt}")

            full_path = os.path.join(self.target_repo_path, file_path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
                lo = max(1, line_no - ctx_n)
                hi = min(len(lines), line_no + ctx_n)
                for ln in range(lo, hi + 1):
                    marker = ">" if ln == line_no else " "
                    out.append(f"    {marker}{ln:5d}: {lines[ln - 1]}")
            except Exception:
                out.append("    [context unavailable]")

        return "\n".join(out)

    def git_pickaxe(self, file_path: str, snippet: str) -> str:
        """
        Uses git log -S (pickaxe) to find commits that introduced or removed
        a specific code snippet in a file's history.
        Helps trace logic migrations and renames.
        """
        cmd = [
            "git",
            "-C",
            self.target_repo_path,
            "log",
            "-S",
            snippet,
            "--oneline",
            "--name-status",
            "--",
            file_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout:
                return f"Git Pickaxe results for content '{snippet}' in history of {file_path}:\n{result.stdout}"
            return f"No git history hits for content '{snippet}' in {file_path}."
        except Exception as e:
            return f"Error running git pickaxe: {e}"

    def map_hunk_lines(self, mainline_hunk: str, target_method_body: str) -> int:
        """
        Programmatic helper to find the most likely 1-indexed insertion line
        in target_method_body matching the context lines of mainline_hunk.
        Useful to verify LLM anchoring of diffs.
        """
        lines = target_method_body.splitlines()
        hunk_lines = mainline_hunk.splitlines()

        # Extract context lines (lines starting with ' ' in the hunk)
        context_lines = [
            h[1:].strip()
            for h in hunk_lines
            if h.startswith(" ") and len(h) > 1 and h[1:].strip()
        ]
        if not context_lines:
            return 1

        for i, t_line in enumerate(lines):
            if context_lines[0] in t_line:
                return i + 1  # 1-indexed
        return 1

    def get_tools(self):
        return [
            StructuredTool.from_function(
                func=self.search_candidates,
                name="search_candidates",
                description="Finds candidate files in the target repo that match a modified file from the patch.",
            ),
            StructuredTool.from_function(
                func=self.get_dependency_graph,
                name="get_dependency_graph",
                description="Builds a dependency graph (classes + method calls) for a list of files.",
            ),
            StructuredTool.from_function(
                func=self.get_class_context,
                name="get_class_context",
                description="Reads a Java file intelligently. Returns class structure + full body of ONE focused method.",
            ),
            StructuredTool.from_function(
                func=self.find_method_match,
                name="find_method_match",
                description="Smartly finds a renamed method in a target file using Name, Signature, or Call Graph.",
                args_schema=None,  # Let LangChain infer or define strict schema if needed
            ),
            StructuredTool.from_function(
                func=self.read_file,
                name="read_file",
                description="Reads the FULL content of a file from the target repo. Use sparingly.",
            ),
            StructuredTool.from_function(
                func=self.list_files,
                name="list_files",
                description="Lists files in a directory of the target repo.",
            ),
            StructuredTool.from_function(
                func=self.match_structure,
                name="match_structure",
                description="Deterministic Structural Matcher. Finds the best target file(s) for a mainline file by comparing inheritance, calls, and fields. Handles 1-to-N splits.",
            ),
            StructuredTool.from_function(
                func=self.check_patch_applicability_internal,
                name="check_patch_applicability",
                description="Optimistic Check: Checks if the patch applies cleanly to the target using 'git apply --check'. Input: absolute path to patch file.",
            ),
            StructuredTool.from_function(
                func=self.get_struct_definition,
                name="get_struct_definition",
                description="Retrieves the full class/struct definition by name from the mainline or target repo. Useful for understanding dependent types referenced in the patch.",
            ),
            StructuredTool.from_function(
                func=self.get_function_body,
                name="get_function_body",
                description="Retrieves the exact body of a function/method from a file. Useful for isolating logic.",
            ),
            StructuredTool.from_function(
                func=self.git_log_follow,
                name="git_log_follow",
                description="Retrieves the git history for a file, following renames.",
            ),
            StructuredTool.from_function(
                func=self.git_blame_lines,
                name="git_blame_lines",
                description="Retrieves git blame for specific lines in a file.",
            ),
            StructuredTool.from_function(
                func=self.grep_repo,
                name="grep_repo",
                description="High-performance literal or regex search across all Java files in the target repository. Returns file:line hits.",
            ),
            StructuredTool.from_function(
                func=self.find_symbol_locations,
                name="find_symbol_locations",
                description="Finds all Java files where a specific class or method name is declared using the repository index.",
            ),
            StructuredTool.from_function(
                func=self.find_text_neighbors,
                name="find_text_neighbors",
                description="Searches for literal text across Java files and returns local context windows around each hit. Useful for locating moved logic when path mapping is unreliable.",
            ),
            StructuredTool.from_function(
                func=self.git_pickaxe,
                name="git_pickaxe",
                description="Traces the history of a specific code snippet using 'git log -S'. Helps find renames and moved logic.",
            ),
            StructuredTool.from_function(
                func=self.map_hunk_lines,
                name="map_hunk_lines",
                description="Finds the most likely 1-indexed insertion line in target_method_body matching the context lines of mainline_hunk.",
            ),
        ]
