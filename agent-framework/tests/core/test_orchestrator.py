"""Tests for Orchestrator.spawn_subagent: isolation, tool filtering, result return."""
from __future__ import annotations

import pytest

from agent_framework.core.messages import Message
from agent_framework.core.orchestrator import Orchestrator
from agent_framework.core.permissions import always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.provider import ModelProvider, ProviderResponse
from agent_framework.core.tool import ToolContext, ToolRegistry


def make_persona(enabled: list[str] | None = None) -> Persona:
    return Persona(
        name="sub",
        system_prompt="You are a subagent.",
        provider="fake/model",
        enabled_tools=enabled or ["*"],
    )


class FakeProvider(ModelProvider):
    """Returns preset responses, patched in via monkeypatch."""
    def __init__(self, responses: list[ProviderResponse]):
        super().__init__(model="fake/model")
        self._responses = responses
        self._idx = 0
        self.received_messages: list[list[Message]] = []

    async def complete(self, messages, tools, **kw) -> ProviderResponse:
        self.received_messages.append(list(messages))
        resp = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return resp


class RecordingTool:
    """Records how many times it was invoked."""
    name = "recorder"
    description = "Records calls."
    requires_permission = False
    input_schema: dict = {"type": "object", "properties": {}}
    call_count = 0

    async def run(self, arguments, *, context: ToolContext) -> str:
        RecordingTool.call_count += 1
        return f"recorded call #{RecordingTool.call_count}"


class TestSpawnSubagent:
    @pytest.mark.asyncio
    async def test_returns_final_text_from_subagent(self, monkeypatch):
        end_resp = ProviderResponse(
            message=Message(role="assistant", content="subagent result text"),
            stop_reason="end_turn",
        )
        fake = FakeProvider([end_resp])
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda persona: fake,
        )
        registry = ToolRegistry()
        orch = Orchestrator(base_tools=registry, base_permission_gate=always_allow())
        result = await orch.spawn_subagent(task_prompt="do task", persona=make_persona())
        assert result == "subagent result text"

    @pytest.mark.asyncio
    async def test_subagent_gets_isolated_session(self, monkeypatch):
        """Subagent starts fresh — no messages from parent conversation."""
        end_resp = ProviderResponse(
            message=Message(role="assistant", content="isolated"),
            stop_reason="end_turn",
        )
        fake = FakeProvider([end_resp])
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda persona: fake,
        )
        registry = ToolRegistry()
        orch = Orchestrator(base_tools=registry, base_permission_gate=always_allow())

        # Spawn subagent — it should NOT see any parent messages
        await orch.spawn_subagent(task_prompt="isolated task", persona=make_persona())

        # The first messages seen by the fake provider should be exactly:
        # [system message from persona, user message with task_prompt]
        first_call_messages = fake.received_messages[0]
        roles = [m.role for m in first_call_messages]
        assert roles == ["system", "user"]
        assert first_call_messages[1].content == "isolated task"

    @pytest.mark.asyncio
    async def test_allowed_tools_filters_registry(self, monkeypatch):
        """When allowed_tools is specified, only those tools are available to the subagent."""
        end_resp = ProviderResponse(
            message=Message(role="assistant", content="done"),
            stop_reason="end_turn",
        )
        fake = FakeProvider([end_resp])
        captured_specs: list = []

        async def patched_complete(self_inner, messages, tools, **kw):
            captured_specs.extend(tools)
            return end_resp

        monkeypatch.setattr(fake.__class__, "complete", patched_complete)
        monkeypatch.setattr(
            "agent_framework.core.provider.ModelProvider.from_persona",
            lambda persona: fake,
        )

        from agent_framework.tools.files import ListDirTool, ReadFileTool

        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(ListDirTool())

        orch = Orchestrator(base_tools=registry, base_permission_gate=always_allow())
        await orch.spawn_subagent(
            task_prompt="only read",
            persona=make_persona(enabled=["*"]),
            allowed_tools={"read_file"},
        )
        tool_names = [s["function"]["name"] for s in captured_specs]
        assert "read_file" in tool_names
        assert "list_dir" not in tool_names
