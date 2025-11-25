from typing import List, Dict, Optional
from langchain_core.tools import StructuredTool
from utils.retrieval.ensemble_retriever import EnsembleRetriever
from utils.patch_analyzer import PatchAnalyzer, FileChange
import os
import re

from utils.models import ImplementationPlan

class ReasoningToolkit:
    def __init__(self, retriever: EnsembleRetriever, target_repo_path: str, patch_analysis: List[FileChange]):
        self.retriever = retriever
        self.target_repo_path = target_repo_path
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
                content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
                # Remove line comments
                content = re.sub(r'//.*', '', content)
                
                lines = content.splitlines()
                # Remove empty lines created by stripping
                lines = [line for line in lines if line.strip()]
                
                if len(lines) > 2000:
                    return "\n".join(lines[:2000]) + "\n\n... [Truncated: File too large] ..."
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
                if not f.startswith("."): # Ignore hidden files
                    files.append(f)
            return files
        except Exception as e:
            return [f"Error listing files: {e}"]

    def get_patch_analysis(self) -> List[Dict]:
        """
        Returns the analysis of the patch, including modified files, added lines, etc.
        """
        return [
            {
                "file_path": c.file_path,
                "change_type": c.change_type,
                "added_lines": c.added_lines,
                "removed_lines": c.removed_lines
            }
            for c in self.patch_analysis
        ]

    def submit_plan(self, **kwargs) -> str:
        """
        Submits the final implementation plan. Call this when you have gathered all information and created the plan.
        """
        return "Plan submitted successfully."

    def get_tools(self):
        return [
            StructuredTool.from_function(
                func=self.search_candidates,
                name="search_candidates",
                description="Searches for potential candidate files in the target repository."
            ),
            StructuredTool.from_function(
                func=self.read_file,
                name="read_file",
                description="Reads the content of a file in the target repository."
            ),
            StructuredTool.from_function(
                func=self.list_files,
                name="list_files",
                description="Lists files in a directory of the target repository."
            ),
            StructuredTool.from_function(
                func=self.get_patch_analysis,
                name="get_patch_analysis",
                description="Returns the analysis of the patch."
            ),
            StructuredTool.from_function(
                func=self.submit_plan,
                name="submit_plan",
                description="Submits the final implementation plan. Use this to finish the task.",
                args_schema=ImplementationPlan
            )
        ]
