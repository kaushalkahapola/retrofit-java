from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from state import AgentState
from utils.patch_analyzer import PatchAnalyzer
from utils.retrieval.ensemble_retriever import EnsembleRetriever
from utils.models import ImplementationPlan
from agents.reasoning_tools import ReasoningToolkit
import os
import json

async def reasoning_agent(state: AgentState, config):
    """
    The Architect (ReAct). Analyzes, plans, and directs the other agents.
    """
    print("Reasoning Agent: Starting ReAct Loop...")
    
    # 1. Patch Analysis (Pre-computation)
    patch_path = state.get("patch_path")
    if not patch_path or not os.path.exists(patch_path):
        return {"messages": [HumanMessage(content="Error: Patch file not found")]}

    with open(patch_path, "r", encoding="utf-8") as f:
        diff_text = f.read()
    
    analyzer = PatchAnalyzer()
    changes = analyzer.analyze(diff_text)
    
    # 2. Setup Retriever
    target_repo_path = state.get("target_repo_path")
    mainline_repo_path = state.get("mainline_repo_path")
    experiment_mode = state.get("experiment_mode", False)
    backport_commit = state.get("backport_commit")
    
    retriever = EnsembleRetriever(mainline_repo_path, target_repo_path)
    
    # Handle Experiment Mode
    commit_to_index = "HEAD"
    if experiment_mode and backport_commit:
        print(f"Experiment Mode: Checking out parent of {backport_commit}...")
        try:
            retriever.target_repo.git.checkout(f"{backport_commit}^")
            commit_to_index = "HEAD"
        except Exception as e:
            print(f"Error checking out commit: {e}")
            return {"messages": [HumanMessage(content=f"Error checking out commit: {e}")]}
    
    # Build Index
    retriever.build_index(commit_to_index)
    
    # 3. Setup Tools
    toolkit = ReasoningToolkit(retriever, target_repo_path, mainline_repo_path, changes)
    tools = toolkit.get_tools()
    
    # 4. Setup LLM & Agent
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    
    system_prompt = """You are an expert Java Backporting Architect.
Your goal is to create a detailed `ImplementationPlan` to backport a patch from a Mainline version to a Target version.

**Process**:
1.  **Analyze**: Use `get_patch_analysis` to understand what changed.
2.  **Explore**: For each modified file, use `search_candidates` to find potential matches in the Target.
3.  **Reference Graph**: Use `get_dependency_graph` on the **Mainline Repository** for the modified files (set `use_mainline=True`).
    *   **NEW**: The graph now includes **Method Calls**. Look at the `calls` list in the output to see which methods invoke which.
4.  **Target Graph**: Use `get_dependency_graph` on the **Target Repository** with ALL your candidate files.
5.  **Match & Verify**: Compare the two graphs.
    *   **Class Level**: If `A` depends on `B` in Mainline, look for `CandidateA` depending on `CandidateB`.
    *   **Method Level**: If `A.methodX()` calls `B.methodY()` in Mainline, look for that specific interaction in the Target.
    *   **CRITICAL**: This "Structural Matching" is your primary filter. Do it BEFORE reading code.
6.  **Deep Verification**: Use `get_class_context` (Smart Read) on the best-matching candidates.
    *   **Usage**: `get_class_context(file_path, focus_method="methodName")`
    *   This gives you the class skeleton + the FULL BODY of the method you are patching.
    *   Verify: Does the method exist? Is the logic similar? Is the fix already present?
    *   **Avoid `read_file`** unless you absolutely need to see the whole file (it wastes tokens).
7.  **Plan**: Once you have gathered enough information, call the `submit_plan` tool with the final `ImplementationPlan`.

**Crucial**:
*   **Structural Matching First**: Compare dependency graphs (Classes AND Methods) to identify the correct files.
*   **Smart Reading**: Use `get_class_context` to surgically inspect methods. Don't dump 2000 lines of code if you only need one function.
*   **Mainline Path**: You have access to `mainline_repo_path` in your state/tools. Use it for the reference graph.
*   **Testing**: You MUST verify the graph connectivity before submitting.
*   If a file is missing, check if it was renamed or if it should be created.
*   **DO NOT** output the JSON as text. You **MUST** call the `submit_plan` tool.
*   **AVOID INFINITE LOOPS**: If you have checked the files and have a good idea, just submit the plan. Do not keep searching endlessly.
"""

    agent = create_react_agent(llm, tools, prompt=system_prompt)
    
    # 5. Run Agent
    # Create a summary of changes for the prompt
    changes_summary = "\n".join([f"- {c.change_type}: {c.file_path}" for c in changes])
    
    initial_message = f"""Here is the summary of the patch changes:
{changes_summary}

I have also loaded the full patch analysis into your tools (`get_patch_analysis`).

Please proceed with the backport planning:
1. Analyze the changes.
2. Find corresponding target files.
3. Verify target file content.
4. Submit the plan.
"""
    
    inputs = {"messages": [HumanMessage(content=initial_message)]}
    
    print("Reasoning Agent: Thinking...")
    try:
        # Run the agent with streaming for real-time feedback
        print("\n--- Real-time Execution Log ---")
        final_state = None
        all_messages = []
        
        async for chunk in agent.astream(inputs, config={"recursion_limit": 50}):
            for node, values in chunk.items():
                if "messages" in values:
                    new_messages = values["messages"]
                    # In LangGraph, values["messages"] might be just the new ones or all, 
                    # but usually with create_react_agent it appends.
                    # Let's print the last one if it's new.
                    for msg in new_messages:
                        if msg not in all_messages:
                            all_messages.append(msg)
                            
                            if msg.type == "ai":
                                print(f"\n[Agent Thought]:\n{msg.content}")
                                if hasattr(msg, "tool_calls") and msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        print(f"  [Tool Call]: {tc['name']}")
                                        print(f"  [Args]: {tc['args']}")
                            elif msg.type == "tool":
                                print(f"\n[Tool Output ({msg.name})]:")
                                content = str(msg.content)
                                if len(content) > 500:
                                    print(f"  {content[:500]}... (truncated)")
                                else:
                                    print(f"  {content}")
            
            # Keep track of the final state
            final_state = values
        
        # Reconstruct result for compatibility with existing code
        result = {"messages": all_messages}
        
        # DEBUG: Print all messages (Summary)
        print("\n--- ReAct Trace Summary ---")
        trace_content = "# Reasoning Agent Trace\n\n"
        
        for msg in result["messages"]:
            print(f"[{msg.type}]: {msg.content}")
            
            if msg.type == "human":
                trace_content += f"## User Input\n{msg.content}\n\n"
            elif msg.type == "ai":
                trace_content += f"## Agent Thought\n{msg.content}\n\n"
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    trace_content += "### Tool Calls\n"
                    for tc in msg.tool_calls:
                        trace_content += f"- **{tc['name']}**: `{tc['args']}`\n"
                    trace_content += "\n"
            elif msg.type == "tool":
                # Pretty print JSON output
                try:
                    content_str = str(msg.content)
                    # Try to parse as JSON if it looks like one
                    if content_str.strip().startswith("{") or content_str.strip().startswith("["):
                         import ast
                         parsed = ast.literal_eval(content_str)
                         
                         # Special Handling for get_dependency_graph
                         if msg.name == "get_dependency_graph" and isinstance(parsed, dict) and "edges" in parsed:
                             trace_content += f"## Tool Output ({msg.name})\n"
                             # Mermaid Graph
                             trace_content += "```mermaid\ngraph TD\n"
                             nodes = set()
                             for edge in parsed.get("edges", []):
                                 src = edge.get("source", "").split(".")[-1]
                                 tgt = edge.get("target", "").split(".")[-1]
                                 rel = edge.get("relation", "related")
                                 nodes.add(src)
                                 nodes.add(tgt)
                                 trace_content += f"    {src} -->|{rel}| {tgt}\n"
                             trace_content += "```\n\n"
                             
                             formatted_json = json.dumps(parsed, indent=2)
                             trace_content += f"<details>\n<summary>Raw JSON Output</summary>\n\n```json\n{formatted_json}\n```\n</details>\n\n"
                             
                         # Special Handling for get_class_context
                         elif msg.name == "get_class_context" and isinstance(parsed, dict) and "context" in parsed:
                             trace_content += f"## Tool Output ({msg.name})\n"
                             trace_content += f"```java\n{parsed['context']}\n```\n\n"
                             
                         else:
                             formatted_json = json.dumps(parsed, indent=2)
                             trace_content += f"## Tool Output ({msg.name})\n```json\n{formatted_json}\n```\n\n"
                    else:
                         trace_content += f"## Tool Output ({msg.name})\n```\n{msg.content}\n```\n\n"
                except:
                    trace_content += f"## Tool Output ({msg.name})\n```\n{msg.content}\n```\n\n"
                
        print("-------------------\n")

        # Save to file unconditionally
        with open("reasoning_trace.md", "w", encoding="utf-8") as f:
            f.write(trace_content)
        print("Trace saved to reasoning_trace.md")

        # Extract the plan from the tool calls
        plan = None
        for message in reversed(result["messages"]):
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call["name"] == "submit_plan":
                        print("Found submit_plan tool call!")
                        plan_args = tool_call["args"]
                        if isinstance(plan_args, dict):
                            plan = ImplementationPlan(**plan_args)
                        else:
                            plan = plan_args
                        break
            if plan: break
            
        if not plan:
             return {"messages": [HumanMessage(content="Error: Agent failed to generate plan")]}

        if plan:
            print("\n--- Implementation Plan (ReAct) ---")
            
            # Append Plan to Trace
            with open("reasoning_trace.md", "a", encoding="utf-8") as f:
                f.write("# Final Implementation Plan\n\n")
                f.write(f"**Intent**: {plan.patch_intent}\n\n")
                
                f.write("## Compatibility Analysis\n")
                f.write(f"- **Java Version**: {plan.compatibility_analysis.java_version_differences}\n")
                f.write(f"- **Refactoring**: {plan.compatibility_analysis.refactoring_notes}\n")
                f.write(f"- **Missing Deps**: {plan.compatibility_analysis.missing_dependencies}\n\n")
                
                f.write("## File Mappings\n")
                f.write("| Source File | Target File | Confidence | Reasoning |\n")
                f.write("|---|---|---|---|\n")
                for m in plan.file_mappings:
                    f.write(f"| `{m.source_file}` | `{m.target_file}` | {m.confidence} | {m.reasoning} |\n")
                
                f.write("\n## Steps\n")
                for s in plan.steps:
                    f.write(f"### Step {s.step_id}: {s.action} `{s.file_path}`\n")
                    f.write(f"{s.description}\n")
                    if s.code_snippet:
                        f.write(f"```java\n{s.code_snippet}\n```\n")
            
            return {
                "messages": [HumanMessage(content="Plan Generated via ReAct")],
                "patch_analysis": changes,
                "implementation_plan": plan.dict()
            }

    except Exception as e:
        print(f"Error in ReAct Loop: {e}")
        import traceback
        traceback.print_exc()
        return {"messages": [HumanMessage(content=f"Error: {e}")]}
