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
    toolkit = ReasoningToolkit(retriever, target_repo_path, changes)
    tools = toolkit.get_tools()
    
    # 4. Setup LLM & Agent
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    
    system_prompt = """You are an expert Java Backporting Architect.
Your goal is to create a detailed `ImplementationPlan` to backport a patch from a Mainline version to a Target version.

**Process**:
1.  **Analyze**: Use `get_patch_analysis` to understand what changed.
2.  **Explore**: For each modified file, use `search_candidates` to find the corresponding file in the target.
3.  **Verify**: Use `read_file` to check the content of the target file.
    *   Does the file exist?
    *   Does it already have the fix?
    *   Are there missing dependencies?
    *   Are there Java version differences (e.g., `var` vs explicit types)?
4.  **Plan**: Once you have gathered enough information, call the `submit_plan` tool with the final `ImplementationPlan`.

**Crucial**:
*   You MUST use `read_file` to inspect the target code before making a decision.
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
        # Run the agent
        result = await agent.ainvoke(inputs, config={"recursion_limit": 50})
        
        # DEBUG: Print all messages
        print("\n--- ReAct Trace ---")
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
                trace_content += f"## Tool Output ({msg.name})\n```\n{msg.content}\n```\n\n"
                
        print("-------------------\n")

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
            # ... (fallback logic) ...
            pass

        if plan:
            print("\n--- Implementation Plan (ReAct) ---")
            # ... (print logic) ...
            
            # Append Plan to Trace
            trace_content += "# Final Implementation Plan\n\n"
            trace_content += f"**Intent**: {plan.patch_intent}\n\n"
            
            trace_content += "## Compatibility Analysis\n"
            trace_content += f"- **Java Version**: {plan.compatibility_analysis.java_version_differences}\n"
            trace_content += f"- **Refactoring**: {plan.compatibility_analysis.refactoring_notes}\n"
            trace_content += f"- **Missing Deps**: {plan.compatibility_analysis.missing_dependencies}\n\n"
            
            trace_content += "## File Mappings\n"
            for m in plan.file_mappings:
                trace_content += f"- `{m.source_file}` -> `{m.target_file}` (Conf: {m.confidence})\n"
            
            trace_content += "\n## Steps\n"
            for s in plan.steps:
                trace_content += f"### Step {s.step_id}: {s.action} `{s.file_path}`\n"
                trace_content += f"{s.description}\n"
                if s.code_snippet:
                    trace_content += f"```java\n{s.code_snippet}\n```\n"
            
            # Save to file
            with open("reasoning_trace.md", "w", encoding="utf-8") as f:
                f.write(trace_content)
            print("Trace saved to reasoning_trace.md")
            
            return {
                "messages": [HumanMessage(content="Plan Generated via ReAct")],
                "patch_analysis": changes,
                "implementation_plan": plan.dict()
            }
        else:
             return {"messages": [HumanMessage(content="Error: Agent failed to generate plan")]}

    except Exception as e:
        print(f"Error in ReAct Loop: {e}")
        import traceback
        traceback.print_exc()
        return {"messages": [HumanMessage(content=f"Error: {e}")]}
