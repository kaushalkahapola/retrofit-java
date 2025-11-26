import httpx
import json
import uuid
from typing import Dict, Any, Optional

class AnalysisEngineClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls a tool on the Analysis Engine synchronously.
        """
        url = f"{self.base_url}/mcp/sync/call"
        
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            # Using a synchronous client for simplicity in tool calls
            # Increased timeout for Spoon analysis which can be slow
            with httpx.Client(timeout=900.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                if "error" in result:
                    raise Exception(f"MCP Error: {result['error']['message']}")
                    
                if "result" in result and "content" in result["result"]:
                    # Extract the text content
                    content = result["result"]["content"]
                    if isinstance(content, list) and len(content) > 0:
                        text_content = content[0].get("text", "")
                        # The text content might be a JSON string of the hierarchy map
                        try:
                            return json.loads(text_content)
                        except:
                            # If it's just a string (like version), return as dict
                            return {"text": text_content}
                
                return result.get("result", {})
                
        except Exception as e:
            print(f"Error calling analysis engine: {e}")
            return {"error": str(e)}

# Singleton instance
_client = None

def get_client(base_url: str = "http://localhost:8080") -> AnalysisEngineClient:
    global _client
    if _client is None:
        _client = AnalysisEngineClient(base_url)
    return _client
