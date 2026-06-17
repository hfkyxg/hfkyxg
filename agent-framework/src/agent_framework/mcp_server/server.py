"""Real MCP server — exposes apathy's tools to any MCP client.

Run it so editors and assistants that speak the Model Context Protocol
(VS Code, Cursor, Claude Desktop, Zed, …) can call apathy's 17 built-in tools:

    uv run python -m agent_framework.mcp_server

Configure a client (e.g. Claude Desktop's claude_desktop_config.json or
VS Code's .vscode/mcp.json):

    {
      "mcpServers": {
        "apathy": {
          "command": "uv",
          "args": ["run", "python", "-m", "agent_framework.mcp_server"]
        }
      }
    }
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from agent_framework.core.permissions import always_allow
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext, ToolRegistry
from agent_framework.tools import register_builtin_tools


def build_server(workdir: str = ".") -> Server:
    """Create an MCP Server wired to apathy's ToolRegistry."""
    registry = ToolRegistry()
    register_builtin_tools(registry)

    server: Server = Server("apathy")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.input_schema,
            )
            for t in registry.all()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        try:
            tool = registry.get(name)
        except KeyError as exc:
            return [types.TextContent(type="text", text=f"Error: {exc}")]

        ctx = ToolContext(
            workdir=Path(workdir),
            session=Session(),
            permission_gate=always_allow(),
        )
        try:
            result = await tool.run(arguments, context=ctx)
        except Exception as exc:  # surface tool errors to the MCP client
            return [types.TextContent(type="text", text=f"Tool error in {name}: {exc}")]
        return [types.TextContent(type="text", text=str(result))]

    return server


async def serve_stdio(workdir: str = ".") -> None:
    server = build_server(workdir)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(serve_stdio())


if __name__ == "__main__":
    main()
