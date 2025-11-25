import asyncio
import sys
import os
from mcp import ClientSession
from mcp.client.sse import sse_client
from graph import app

# Add src to path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def main():
    # URL for the Analysis Engine SSE endpoint
    # In Docker, this might be http://analysis-engine:8080/mcp/sse
    # Locally, it's http://localhost:8080/mcp/sse
    sse_url = os.getenv("MCP_SERVER_URL", "http://localhost:8080/mcp/sse")
    
    print(f"Connecting to Analysis Engine at {sse_url}...")

    try:
        # Increase timeout to 60 seconds to avoid ReadTimeout during handshake
        async with sse_client(sse_url, timeout=60.0) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                print("Connected to Analysis Engine MCP Server via SSE.")
                
                # List tools to verify
                tools = await session.list_tools()
                print(f"Available tools: {[t.name for t in tools.tools]}")
                
                print("Running Orchestrator Graph...")
                inputs = {"messages": ["Start"]}
                config = {"configurable": {"mcp_session": session}}
                
                async for output in app.astream(inputs, config=config):
                    for key, value in output.items():
                        print(f"Output from {key}:")
                        # Pretty print messages
                        if "messages" in value:
                            for msg in value["messages"]:
                                print(f"  {msg.content}")
                        print("----")
    except Exception as e:
        print(f"Error running Orchestrator: {e}")

if __name__ == "__main__":
    asyncio.run(main())
