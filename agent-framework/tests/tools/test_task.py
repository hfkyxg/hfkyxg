"""Tests for TaskTool: delegation, persona resolution, error cases."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_framework.core.errors import ToolError
from agent_framework.core.messages import Message
from agent_framework.core.orchestrator import Orchestrator
from agent_framework.core.permissions import always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.provider import ModelProvider, ProviderResponse
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext, ToolRegistry
from agent_framework.tools.task import TaskTool


def make_persona(name: str = "worker") -> Persona:
    return Persona(
        name=name,
        system_prompt="You are a worker.",
        provider="fake/model",
        enabled_tools=["*"],
    )


def end_resp(text: str) -> ProviderResponse:
    return ProviderResponse(
        message=Message(role="assistant", content=text),
        stop_reason="end_turn",
    )


class FakeProvider(ModelProvider):
    def __init__(self, text: str):
        super().__init__(model="fake/model")
        self._text = text

    async def complete(self, messages, tools, **kw) -> ProviderResponse:
        return end_resp(self._text)


def make_context(orchestrator: Orchestrator | None = None) -> ToolContext:
    return ToolContext(
        workdir=Path("."),
        session=Session(),
        permission_gate=always_allow(),
        orchestrator=orchestrator,
    )


class TestTaskTool:
    @pytest.mark.asyncio
    async def test_delegates_and_returns_subagent_result(self, monkeypatch):
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda p: FakeProvider("subagent result"),
        )
        personas = {"default": make_persona("default")}
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        tool = TaskTool(personas=personas)
        ctx = make_context(orchestrator=orch)
        result = await tool.run({"prompt": "do something"}, context=ctx)
        assert result == "subagent result"

    @pytest.mark.asyncio
    async def test_raises_when_no_orchestrator(self):
        tool = TaskTool(personas={"default": make_persona()})
        ctx = make_context(orchestrator=None)
        with pytest.raises(ToolError, match="No orchestrator"):
            await tool.run({"prompt": "do something"}, context=ctx)

    @pytest.mark.asyncio
    async def test_raises_when_persona_not_found(self, monkeypatch):
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        tool = TaskTool(personas={"default": make_persona()})
        ctx = make_context(orchestrator=orch)
        with pytest.raises(ToolError, match="not found"):
            await tool.run({"prompt": "do something", "persona": "nonexistent"}, context=ctx)

    @pytest.mark.asyncio
    async def test_uses_named_persona(self, monkeypatch):
        received_personas: list[str] = []

        async def patched_spawn(self_inner, *, task_prompt, persona, **kw):
            received_personas.append(persona.name)
            return "ok"

        monkeypatch.setattr(Orchestrator, "spawn_subagent", patched_spawn)
        personas = {
            "default": make_persona("default"),
            "researcher": make_persona("researcher"),
        }
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        tool = TaskTool(personas=personas)
        ctx = make_context(orchestrator=orch)
        await tool.run({"prompt": "research this", "persona": "researcher"}, context=ctx)
        assert received_personas == ["researcher"]

    @pytest.mark.asyncio
    async def test_passes_allowed_tools(self, monkeypatch):
        captured: dict = {}

        async def patched_spawn(self_inner, *, task_prompt, persona, allowed_tools=None, **kw):
            captured["allowed_tools"] = allowed_tools
            return "done"

        monkeypatch.setattr(Orchestrator, "spawn_subagent", patched_spawn)
        personas = {"default": make_persona()}
        orch = Orchestrator(base_tools=ToolRegistry(), base_permission_gate=always_allow())
        tool = TaskTool(personas=personas)
        ctx = make_context(orchestrator=orch)
        await tool.run(
            {"prompt": "task", "allowed_tools": ["read_file", "bash"]},
            context=ctx,
        )
        assert captured["allowed_tools"] == {"read_file", "bash"}
