import os
import sys
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.config import settings

logger = logging.getLogger("devassist-mcp-client")

class MCPClientManager:
    """Manages the lifecycle of a connection to the GitHub MCP Server."""
    def __init__(self):
        self.server_params = None
        self.session: Optional[ClientSession] = None
        self._stdio_ctx = None
        self._session_ctx = None
        self._tools_cache: List[Dict[str, Any]] = []
        self._running = False

    async def start(self):
        """Starts the MCP server subprocess and connects to it."""
        if self._running:
            return
            
        mcp_server_path = Path(settings.DOCS_DIR).parent / "mcp_server" / "github_mcp.py"
        if not mcp_server_path.exists():
            logger.error(f"GitHub MCP Server script not found at {mcp_server_path}")
            raise FileNotFoundError(f"MCP Server script not found at {mcp_server_path}")
            
        logger.info(f"Starting GitHub MCP Server from: {mcp_server_path}")
        
        # Configure server parameters
        # Pass through the environment, specifically injecting GITHUB_PAT and GITHUB_REPOSITORY
        env = os.environ.copy()
        env["GITHUB_PAT"] = settings.GITHUB_PAT
        env["GITHUB_REPOSITORY"] = settings.GITHUB_REPOSITORY
        
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(mcp_server_path)],
            env=env
        )
        
        try:
            # Enter stdio client context
            self._stdio_ctx = stdio_client(self.server_params)
            read_stream, write_stream = await self._stdio_ctx.__aenter__()
            
            # Enter client session context
            self._session_ctx = ClientSession(read_stream, write_stream)
            self.session = await self._session_ctx.__aenter__()
            
            # Initialize session
            await self.session.initialize()
            logger.info("Successfully initialized GitHub MCP Server connection")
            self._running = True
            
            # Cache tools at startup
            await self.refresh_tools()
            
        except Exception as e:
            logger.error(f"Failed to start/connect to GitHub MCP Server: {str(e)}")
            await self.stop()
            raise e

    async def stop(self):
        """Stops the MCP server and cleans up connections."""
        logger.info("Stopping GitHub MCP Server client session...")
        self._running = False
        self._tools_cache = []
        
        if self.session:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing MCP session: {str(e)}")
            self.session = None
            
        if self._stdio_ctx:
            try:
                await self._stdio_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing stdio client: {str(e)}")
            self._stdio_ctx = None
            
        logger.info("GitHub MCP Server connection stopped.")

    async def refresh_tools(self) -> List[Dict[str, Any]]:
        """Queries the MCP server for available tools and caches them."""
        if not self.session:
            return []
            
        try:
            logger.info("Refreshing MCP tools list...")
            response = await self.session.list_tools()
            
            # Transform MCP tool objects into a clean dictionary list
            tools_list = []
            for tool in response.tools:
                tools_list.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })
            self._tools_cache = tools_list
            logger.info(f"Loaded {len(tools_list)} tools from GitHub MCP Server: {[t['name'] for t in tools_list]}")
            return tools_list
        except Exception as e:
            logger.error(f"Failed to refresh tools: {str(e)}")
            return self._tools_cache

    def get_cached_tools(self) -> List[Dict[str, Any]]:
        """Returns the list of tools cached in memory."""
        return self._tools_cache

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Invokes a tool on the GitHub MCP server."""
        if not self.session:
            raise RuntimeError("MCP client session is not active. Call start() first.")
            
        sanitized_args = {k: (f"<str len={len(v)}>" if isinstance(v, str) else v) for k, v in arguments.items()}
        logger.info(f"Calling MCP tool '{tool_name}' with arguments: {sanitized_args}")
        try:
            result = await self.session.call_tool(tool_name, arguments)
            
            # Format and return result content
            # MCP results can have text, image, or resource content
            content_pieces = []
            for content in result.content:
                if hasattr(content, "text"):
                    content_pieces.append(content.text)
                elif isinstance(content, dict) and "text" in content:
                    content_pieces.append(content["text"])
                    
            output = "\n".join(content_pieces)
            logger.info(f"MCP tool '{tool_name}' returned success (len: {len(output)})")
            return output
        except Exception as e:
            logger.error(f"Error executing MCP tool '{tool_name}': {str(e)}")
            raise e

# Global singleton instance
mcp_client_manager = None

def get_mcp_client():
    global mcp_client_manager
    if mcp_client_manager is None:
        mcp_client_manager = MCPClientManager()
    return mcp_client_manager
