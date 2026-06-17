"""Tests for offline subagent delegation via the MockProvider + Orchestrator."""
from __future__ import annotations

import pytest

from agent_framework.core.agent import Agent
from agent_framework.core.messages import Message
from agent_framework.core.mock_provider import MockProvider
from agent_framework.core.orchestrator import Orchestrator
from agent_framework.core.permissions import always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry
from agent_framework.tools import register_builtin_tools


def demo_persona() -> Persona:
    return Persona(
        name="demo",
        system_prompt="demo",
        provider="mock/demo",
        enabled_tools=["read_file", "write_file", "list_dir", "bash", "grep", "task"],
        max_iterations=6,
    )


def specs(*names: str) -> list[dict]:
    return [
        {"type": "function", "function": {"name": n, "description": "", "parameters": {}}}
        for n in names
    ]


class TestDelegationDetection:
    @pytest.mark.asyncio
    async def test_delegue_triggers_task_with_subtask(self):
        p = MockProvider()
        msgs = [Message(role="user", content="delegue ao subagente: escreva o arquivo a.txt")]
        resp = await p.complete(msgs, specs("task", "write_file"))
        tc = resp.message.tool_calls[0]
        assert tc.name == "task"
        assert tc.arguments["prompt"] == "escreva o arquivo a.txt"

    @pytest.mark.asyncio
    async def test_bare_subagente_in_content_does_not_trigger(self):
        """The word 'subagente' inside content must NOT be read as delegation."""
        p = MockProvider()
        msgs = [Message(role="user", content="escreva o arquivo x.txt com conteúdo feito-pelo-subagente")]
        resp = await p.complete(msgs, specs("task", "write_file"))
        tc = resp.message.tool_calls[0]
        assert tc.name == "write_file"
        assert "subagente" in tc.arguments["content"]

    @pytest.mark.asyncio
    async def test_delegation_falls_back_to_write_when_task_unavailable(self):
        p = MockProvider()
        msgs = [Message(role="user", content="delegue ao subagente: faça algo")]
        resp = await p.complete(msgs, specs("write_file"))  # no task tool
        # without task available, "faça algo"/delegation can't map -> text answer
        assert resp.stop_reason == "end_turn"


class TestEndToEndDelegation:
    @pytest.mark.asyncio
    async def test_parent_delegates_and_subagent_writes_file(self, tmp_path):
        registry = ToolRegistry()
        register_builtin_tools(registry, task_personas={"demo": demo_persona()})

        gate = always_allow()
        orch = Orchestrator(base_tools=registry, base_permission_gate=gate, workdir=str(tmp_path))
        agent = Agent.from_persona(demo_persona(), registry, gate, str(tmp_path))
        agent._orchestrator = orch
        session = Session.with_system_prompt("demo")

        target = tmp_path / "delegated.txt"
        await agent.run_turn_collect(
            session,
            f"delegue ao subagente: escreva o arquivo {target} com conteúdo conteudo-do-sub",
        )
        assert target.exists()
        assert "conteudo-do-sub" in target.read_text()

    @pytest.mark.asyncio
    async def test_subagent_event_hook_is_called(self, tmp_path):
        """The orchestrator streams subagent events so interfaces can show them."""
        seen: list[str] = []

        registry = ToolRegistry()
        register_builtin_tools(registry, task_personas={"demo": demo_persona()})
        gate = always_allow()
        orch = Orchestrator(base_tools=registry, base_permission_gate=gate, workdir=str(tmp_path))
        orch.subagent_event_hook = lambda label, ev: seen.append(type(ev).__name__)

        agent = Agent.from_persona(demo_persona(), registry, gate, str(tmp_path))
        agent._orchestrator = orch
        session = Session.with_system_prompt("demo")

        await agent.run_turn_collect(
            session,
            f"delegue ao subagente: escreva o arquivo {tmp_path / 'h.txt'} com conteúdo oi",
        )
        assert "ToolResultEvent" in seen  # subagent's tool execution was observed
