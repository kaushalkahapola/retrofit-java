"""
Dependency Analyzer Node for LangGraph.
"""

from typing import Dict, Any, List
from state import AgentState
from utils.dependency_graph import JavaDependencyAnalyzer
import os

JAVA_KEYWORDS = {
    "abstract", "continue", "for", "new", "switch", "assert", "default", "if", "package", "synchronized",
    "boolean", "do", "goto", "private", "this", "break", "double", "implements", "protected", "throw",
    "byte", "else", "import", "public", "throws", "case", "enum", "instanceof", "return", "transient",
    "catch", "extends", "int", "short", "try", "char", "final", "interface", "static", "void",
    "class", "finally", "long", "strictfp", "volatile", "const", "float", "native", "super", "while",
    "true", "false", "null"
}

async def dependency_analyzer_node(state: AgentState, config: dict = None) -> Dict[str, Any]:
    """
    Analyzes cross-file dependencies when a method signature change is detected.
    Adds call-sites to the validation_retry_files list.
    """
    print("--- DEPENDENCY ANALYZER ---")
    
    repo_path = state.get("target_repo_path")
    if not repo_path:
        return {}
        
    analyzer = JavaDependencyAnalyzer(repo_path)
    
    # We look for methods that were modified in the patch
    # and check if their signatures changed.
    # This information can be derived from structural_locator results.
    
    # For now, let's look at validation_build_missing_symbols as a trigger
    missing_symbols = state.get("validation_build_missing_symbols") or []
    blueprint = state.get("semantic_blueprint") or {}
    dependent_apis = blueprint.get("dependent_apis") or []
    
    # We combine them to ensure we catch all potential call-sites
    symbols_to_search = set(missing_symbols) | set(dependent_apis)
    
    retry_files = list(state.get("validation_retry_files") or [])
    new_files_to_retry = []
    
    for symbol in symbols_to_search:
        # Filter out Java keywords and common/short terms
        if symbol in JAVA_KEYWORDS or len(symbol) <= 4:
            continue
            
        # Exclude very common generic terms
        if symbol.lower() in {"symbol", "object", "value", "result", "estimate", "estimation"}:
            continue

        # If the symbol looks like a method name (starts with lowercase)
        if symbol and symbol[0].islower():
            print(f"Searching for call-sites of symbol: {symbol}")
            call_sites = analyzer.find_all_call_sites(symbol)
            for site in call_sites:
                file_path = site["file"]
                if file_path not in retry_files and file_path not in new_files_to_retry:
                    print(f"Found call-site in {file_path}, adding to retry list.")
                    new_files_to_retry.append(file_path)
                    
    if not new_files_to_retry:
        return {}
        
    existing_notes = state.get("notes") or ""
    return {
        "validation_retry_files": retry_files + new_files_to_retry,
        "notes": (existing_notes + f"|dep_analyzer_added_{len(new_files_to_retry)}_files").strip("|")
    }
