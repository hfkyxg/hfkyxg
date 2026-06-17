"""Tests for MockProvider: heuristic tool selection and result summarization."""
from __future__ import annotations

import pytest

from agent_framework.core.agent import Agent, AssistantTextEvent, ToolResultEvent
from agent_framework.core.messages import Message, ToolResult
from agent_framework.core.mock_provider import MockProvider
from agent_framework.core.permissions import always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry
from agent_framework.tools import register_builtin_tools


def specs_for(*names: str) -> list[dict]:
    return [{"type": "function", "function": {"name": n, "description": "", "parameters": {}}} for n in names]


def demo_persona() -> Persona:
    return Persona(
        name="demo",
        system_prompt="demo",
        provider="mock/demo",
        enabled_tools=["*"],
        max_iterations=6,
    )


class TestToolSelection:
    @pytest.mark.asyncio
    async def test_read_request_emits_read_file(self):
        p = MockProvider()
        msgs = [Message(role="user", content="leia o arquivo README.md")]
        resp = await p.complete(msgs, specs_for("read_file"))
        assert resp.stop_reason == "tool_calls"
        assert resp.message.tool_calls[0].name == "read_file"

    @pytest.mark.asyncio
    async def test_run_request_emits_bash(self):
        p = MockProvider()
        msgs = [Message(role="user", content="rode: echo hi")]
        resp = await p.complete(msgs, specs_for("bash"))
        assert resp.message.tool_calls[0].name == "bash"
        assert resp.message.tool_calls[0].arguments["command"] == "echo hi"

    @pytest.mark.asyncio
    async def test_list_request_emits_list_dir(self):
        p = MockProvider()
        msgs = [Message(role="user", content="liste o diretório src")]
        resp = await p.complete(msgs, specs_for("list_dir"))
        assert resp.message.tool_calls[0].name == "list_dir"

    @pytest.mark.asyncio
    async def test_search_request_emits_grep(self):
        p = MockProvider()
        msgs = [Message(role="user", content="busque TODO")]
        resp = await p.complete(msgs, specs_for("grep"))
        assert resp.message.tool_calls[0].name == "grep"
        assert resp.message.tool_calls[0].arguments["pattern"] == "TODO"

    @pytest.mark.asyncio
    async def test_unmatched_request_returns_text(self):
        p = MockProvider()
        msgs = [Message(role="user", content="olá, tudo bem?")]
        resp = await p.complete(msgs, specs_for("read_file"))
        assert resp.stop_reason == "end_turn"
        assert resp.message.content

    @pytest.mark.asyncio
    async def test_does_not_call_unavailable_tool(self):
        """If the persona doesn't enable bash, a run request must fall back to text."""
        p = MockProvider()
        msgs = [Message(role="user", content="rode: echo hi")]
        resp = await p.complete(msgs, specs_for("read_file"))  # bash NOT available
        assert resp.stop_reason == "end_turn"


class TestResultSummarization:
    @pytest.mark.asyncio
    async def test_tool_result_is_summarized_and_ends_turn(self):
        p = MockProvider()
        msgs = [
            Message(role="user", content="leia x"),
            Message(role="assistant", content=None),
            Message(role="tool", tool_results=[ToolResult(tool_call_id="1", content="file body")]),
        ]
        resp = await p.complete(msgs, specs_for("read_file"))
        assert resp.stop_reason == "end_turn"
        assert "file body" in resp.message.content

    @pytest.mark.asyncio
    async def test_error_result_marked(self):
        p = MockProvider()
        msgs = [
            Message(role="tool", tool_results=[ToolResult(tool_call_id="1", content="boom", is_error=True)]),
        ]
        resp = await p.complete(msgs, specs_for("read_file"))
        assert "erro" in resp.message.content


class TestEndToEndOffline:
    @pytest.mark.asyncio
    async def test_full_loop_writes_and_reads_file(self, tmp_path):
        """The whole agent loop runs offline via the mock provider."""
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent.from_persona(demo_persona(), registry, always_allow(), str(tmp_path))
        session = Session.with_system_prompt("demo")

        # write
        await agent.run_turn_collect(session, "escreva o arquivo nota.txt")
        assert (tmp_path / "nota.txt").exists()

        # read it back — final text should echo the content
        result = await agent.run_turn_collect(session, "leia o arquivo nota.txt")
        assert "apathy" in result.lower()

    @pytest.mark.asyncio
    async def test_full_loop_runs_bash(self, tmp_path):
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent.from_persona(demo_persona(), registry, always_allow(), str(tmp_path))
        session = Session.with_system_prompt("demo")

        events = []
        async for ev in agent.run_turn(session, "rode: echo apathy-vivo"):
            events.append(ev)

        results = [e for e in events if isinstance(e, ToolResultEvent)]
        assert results and "apathy-vivo" in results[0].result
        texts = [e for e in events if isinstance(e, AssistantTextEvent)]
        assert texts
