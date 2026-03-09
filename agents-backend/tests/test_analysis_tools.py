import sys
import os
import json
import asyncio
import pytest
# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from utils.mcp_client import get_client

@pytest.mark.asyncio
async def test_tools():
    client = get_client()
    
    repo_path = r"f:\retrofit-java\analysis-engine" # Use analysis-engine itself as test repo
    test_file = "src/main/java/com/retrofit/analysis/tools/GetDependencyTool.java"
    
    print("\n--- Testing GetDependencyTool (Method Calls) ---")
    try:
        graph = client.call_tool("get_dependency_graph", {
            "target_repo_path": repo_path,
            "file_paths": [test_file],
            "explore_neighbors": False
        })
        
        # Check for 'calls' in methods
        nodes = graph.get("nodes", [])
        if nodes:
            methods = nodes[0].get("methods", [])
            print(f"Found {len(methods)} methods in {nodes[0]['simpleName']}")
            for m in methods[:3]: # Print first 3
                print(f"  Method: {m['simpleName']}")
                if "calls" in m:
                    print(f"    Calls: {len(m['calls'])} other methods")
                    for c in m['calls'][:2]:
                        print(f"      - {c}")
        else:
            print("Error: No nodes returned.")
            
    except Exception as e:
        print(f"Error testing dependency graph: {e}")

    print("\n--- Testing GetClassContextTool ---")
    try:
        context = client.call_tool("get_class_context", {
            "target_repo_path": repo_path,
            "file_path": test_file,
            "focus_method": "execute" 
        })
        
        content = context.get("context", "")
        print(f"Context Length: {len(content)} chars")
        print("Preview (First 500 chars):")
        print(content[:500])
        
        if "// [FOCUS] Full Body" in content:
            print("\nSUCCESS: Found focus marker!")
        else:
            print("\nFAILURE: Focus marker not found.")
            
    except Exception as e:
        print(f"Error testing class context: {e}")

if __name__ == "__main__":
    asyncio.run(test_tools())
