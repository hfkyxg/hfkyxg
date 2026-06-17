"""Tests for the real MCP server — list_tools and call_tool over the protocol."""
from __future__ import annotations

import mcp.types as types

from agent_framework.mcp_server.server import build_server


async def test_list_tools_exposes_all_builtins():
    server = build_server()
    req = types.ListToolsRequest(method="tools/list")
    result = await server.request_handlers[types.ListToolsRequest](req)
    tools = result.root.tools
    names = {t.name for t in tools}
    # Core tools must all be present
    for expected in ("read_file", "write_file", "bash", "web_search",
                     "organize_files", "cloud_sync", "email_send", "task"):
        assert expected in names
    assert len(tools) >= 17


async def test_each_tool_has_valid_schema():
    server = build_server()
    req = types.ListToolsRequest(method="tools/list")
    result = await server.request_handlers[types.ListToolsRequest](req)
    for t in result.root.tools:
        assert t.description
        assert isinstance(t.inputSchema, dict)
        assert t.inputSchema.get("type") == "object"


async def test_call_tool_list_dir(tmp_path):
    (tmp_path / "hello.txt").write_text("hi")
    server = build_server(workdir=str(tmp_path))
    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(
            name="list_dir", arguments={"path": str(tmp_path)}
        ),
    )
    result = await server.request_handlers[types.CallToolRequest](req)
    text = result.root.content[0].text
    assert "hello.txt" in text


async def test_call_unknown_tool_returns_error():
    server = build_server()
    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name="does_not_exist", arguments={}),
    )
    result = await server.request_handlers[types.CallToolRequest](req)
    text = result.root.content[0].text.lower()
    # MCP wraps handler exceptions; the message should mention the bad tool name
    assert "does_not_exist" in text or "error" in text or "not found" in text
