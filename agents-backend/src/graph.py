from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from langchain_core.messages import BaseMessage, HumanMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]

async def reasoning_agent(state: AgentState, config):
    print("Reasoning Agent: Deciding what to do...")
    return {"messages": [HumanMessage(content="Check Java Version")]}

async def analysis_tool_node(state: AgentState, config):
    session = config.get("configurable", {}).get("mcp_session")
    if session:
        print("Analysis Tool: Calling MCP...")
        try:
            result = await session.call_tool("get_java_version", {})
            content = result.content[0].text
            return {"messages": [HumanMessage(content=f"Java Version: {content}")]}
        except Exception as e:
            return {"messages": [HumanMessage(content=f"Error calling tool: {e}")]}
    else:
        return {"messages": [HumanMessage(content="Error: No MCP session")]}

workflow = StateGraph(AgentState)
workflow.add_node("reasoning", reasoning_agent)
workflow.add_node("analysis", analysis_tool_node)

workflow.set_entry_point("reasoning")
workflow.add_edge("reasoning", "analysis")
workflow.add_edge("analysis", END)

app = workflow.compile()
