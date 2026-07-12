import os
import sys
import asyncio
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

async def run_mcp_test():
    print("=== RUNNING MCP SERVER TEST ===")
    
    mcp_server_script = backend_dir.parent / "mcp_server" / "github_mcp.py"
    if not mcp_server_script.exists():
        print(f"[ERROR] MCP server script not found at {mcp_server_script}")
        sys.exit(1)
        
    print(f"Server script located at: {mcp_server_script}")
    
    # Configure parameters. We provide fake token so it initializes without erroring out.
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(mcp_server_script)],
        env={**os.environ, "GITHUB_PAT": "fake-pat-for-testing", "GITHUB_REPOSITORY": "test/repo"}
    )
    
    print("Spawning MCP Server and establishing stdio client...")
    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                print("Client session created. Initializing...")
                await session.initialize()
                print("Session initialized successfully!")
                
                # List tools
                print("Retrieving tools list...")
                response = await session.list_tools()
                tools = response.tools
                
                print(f"Found {len(tools)} tools exposed by the MCP server:")
                tool_names = []
                for tool in tools:
                    print(f" - Tool: '{tool.name}' | Desc: '{tool.description}'")
                    tool_names.append(tool.name)
                    
                # Assertions
                assert "github_search_code" in tool_names, "Missing github_search_code tool"
                assert "github_create_issue" in tool_names, "Missing github_create_issue tool"
                assert "github_comment_pr" in tool_names, "Missing github_comment_pr tool"
                
                print("\n[SUCCESS] MCP Server Test Passed! The server launches, initializes, and exposes GitHub tools correctly.")
                
    except Exception as e:
        print(f"\n[ERROR] MCP Server connection failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_mcp_test())
