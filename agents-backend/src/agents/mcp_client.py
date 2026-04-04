"""
MCP Client for Python - Communicates with Java MCP server for code transformations.
Provides caching, connection pooling, and async capabilities.
"""

import os
import json
import asyncio
import aiohttp
from typing import Any, Dict, Optional
from functools import lru_cache
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class McpClientError(Exception):
    """Exception raised for MCP client errors."""

    pass


class McpClient:
    """
    Python client for communicating with the Java MCP server.

    Features:
    - Connection pooling (aiohttp)
    - Response caching with TTL
    - Async and sync methods
    - Health checking
    - Automatic request ID generation
    """

    def __init__(
        self, mcp_server_url: Optional[str] = None, cache_ttl_seconds: int = 300
    ):
        """
        Initialize the MCP client.

        Args:
            mcp_server_url: URL of the MCP server (defaults to MCP_SERVER_URL env var)
            cache_ttl_seconds: Cache expiration time in seconds (default 5 minutes)
        """
        self.mcp_server_url = mcp_server_url or os.getenv(
            "MCP_SERVER_URL", "http://localhost:8080"
        )
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.response_cache: Dict[str, tuple] = {}  # (response, expiration_time)
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_counter = 0

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Establish connection pool."""
        if self._session is None:
            connector = aiohttp.TCPConnector(limit=20, limit_per_host=5)
            self._session = aiohttp.ClientSession(
                connector=connector, timeout=aiohttp.ClientTimeout(total=60)
            )

    async def disconnect(self):
        """Close connection pool."""
        if self._session:
            await self._session.close()
            self._session = None

    async def call_tool_async(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call an MCP tool asynchronously.

        Args:
            tool_name: Name of the MCP tool
            arguments: Tool arguments

        Returns:
            Tool response as dictionary

        Raises:
            McpClientError: If the call fails
        """
        if self._session is None:
            raise McpClientError(
                "Not connected. Use 'async with McpClient() as client:' or call connect()"
            )

        # Check cache
        cache_key = self._generate_cache_key(tool_name, arguments)
        cached_response, expiration = self.response_cache.get(cache_key, (None, None))
        if cached_response and datetime.now() < expiration:
            logger.debug(f"Cache hit for {tool_name}")
            return cached_response

        # Build request
        self._request_counter += 1
        request_id = str(self._request_counter)

        request_body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        try:
            async with self._session.post(
                f"{self.mcp_server_url}/mcp/sync/call",
                json=request_body,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise McpClientError(
                        f"MCP server returned status {resp.status}: {error_text}"
                    )

                response_data = await resp.json()

                # Extract result
                if "error" in response_data:
                    raise McpClientError(f"MCP error: {response_data['error']}")

                result = response_data.get("result", {})

                # Cache the response
                self.response_cache[cache_key] = (
                    result,
                    datetime.now() + self.cache_ttl,
                )

                return result

        except aiohttp.ClientError as e:
            raise McpClientError(f"Connection error: {e}")
        except json.JSONDecodeError as e:
            raise McpClientError(f"Invalid JSON response: {e}")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool synchronously.

        Args:
            tool_name: Name of the MCP tool
            arguments: Tool arguments

        Returns:
            Tool response as dictionary
        """
        # Create event loop if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Ensure we're connected
        if self._session is None:
            loop.run_until_complete(self.connect())

        return loop.run_until_complete(self.call_tool_async(tool_name, arguments))

    async def health_check(self) -> bool:
        """
        Check if the MCP server is reachable.

        Returns:
            True if server is healthy, False otherwise
        """
        if self._session is None:
            await self.connect()

        try:
            async with self._session.head(
                f"{self.mcp_server_url}/mcp/sync/call",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return 200 <= resp.status < 300
        except:
            return False

    def clear_cache(self):
        """Clear the response cache."""
        self.response_cache.clear()

    @staticmethod
    def _generate_cache_key(tool_name: str, arguments: Dict[str, Any]) -> str:
        """Generate a cache key for a tool call."""
        try:
            args_json = json.dumps(arguments, sort_keys=True)
        except:
            args_json = str(arguments)
        return f"{tool_name}:{args_json}"
