from typing import List, Dict, Optional
from utils.mcp_client import get_client
import json

class ValidationToolkit:
    def __init__(self, target_repo_path: str):
        self.target_repo_path = target_repo_path
        self.client = get_client()

    def compile_files(self, file_paths: List[str]) -> Dict:
        """
        Compiles the specified files using the Analysis Engine.
        """
        return self.client.call_tool("compile", {
            "target_repo_path": self.target_repo_path,
            "file_paths": file_paths
        })

    def run_spotbugs(self, compiled_classes_path: str, source_path: str = None) -> Dict:
        """
        Runs SpotBugs on the compiled classes.
        """
        return self.client.call_tool("spotbugs", {
            "compiled_classes_path": compiled_classes_path,
            "source_path": source_path
        })

    def write_trace(self, trace_content: str, filename: str = "validation_trace.md"):
        """
        Writes the validation trace to a file.
        """
        with open(filename, "w", encoding="utf-8") as f:
            f.write(trace_content)
        print(f"Trace saved to {filename}")
