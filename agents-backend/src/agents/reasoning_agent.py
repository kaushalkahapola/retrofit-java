from langchain_core.messages import HumanMessage
from state import AgentState
from utils.patch_analyzer import PatchAnalyzer
import os

async def reasoning_agent(state: AgentState, config):
    """
    The Architect. Analyzes, plans, and directs the other agents.
    """
    print("Reasoning Agent: Analyzing patch and planning...")
    
    patch_path = state.get("patch_path")
    if not patch_path or not os.path.exists(patch_path):
        print(f"Error: Patch file not found at {patch_path}")
        return {"messages": [HumanMessage(content="Error: Patch file not found")]}

    try:
        with open(patch_path, "r", encoding="utf-8") as f:
            diff_text = f.read()
        
        analyzer = PatchAnalyzer()
        changes = analyzer.analyze(diff_text)
        
        print(f"\n--- Patch Analysis Results ({len(changes)} files) ---")
        for change in changes:
            print(f"File: {change.file_path}")
            print(f"  Type: {change.change_type}")
            print(f"  Added Lines: {len(change.added_lines)}")
            print(f"  Removed Lines: {len(change.removed_lines)}")
            print(f"  Is Test: {change.is_test_file}")
        print("---------------------------------------------------\n")
        
        # Store analysis in state
        return {
            "messages": [HumanMessage(content="Patch Analyzed")],
            "patch_analysis": changes
        }
        
    except Exception as e:
        print(f"Error analyzing patch: {e}")
        return {"messages": [HumanMessage(content=f"Error analyzing patch: {e}")]}
