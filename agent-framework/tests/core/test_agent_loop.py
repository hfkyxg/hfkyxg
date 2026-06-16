import uuid

import pytest

from agent_framework.core.agent import (
    Agent,
    AssistantTextEvent,
    ToolResultEvent,
)
from agent_framework.core.messages import Message, ToolCall
from agent_framework.core.permissions import always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.provider import ModelProvider, ProviderResponse
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry


class FakeProvider(ModelProvider):
    def __init__(self, responses):
        super().__init__(model="fake/model")
        self._responses = responses
        self._i = 0

    async def complete(self, messages, tools, **kw):
        r = self._responses[self._i % len(self._responses)]
        self._i += 1
        return r


def simple_end_turn_response(text: str) -> ProviderResponse:
    return ProviderResponse(
        message=Message(role="assistant", content=text),
        stop_reason="end_turn",
    )


def persona_all_tools() -> Persona:
    return Persona(
        name="test",
        system_prompt="You are a test agent.",
        provider="fake/model",
        enabled_tools=["*"],
    )


@pytest.mark.asyncio
async def test_simple_text_response():
    provider = FakeProvider([simple_end_turn_response("Hello!")])
    registry = ToolRegistry()
    agent = Agent(
        provider=provider,
        tools=registry,
        permission_gate=always_allow(),
        persona=persona_all_tools(),
    )
    session = Session.with_system_prompt("sys")
    events = []
    async for ev in agent.run_turn(session, "hi"):
        events.append(ev)
    texts = [e.text for e in events if isinstance(e, AssistantTextEvent)]
    assert "Hello!" in texts


@pytest.mark.asyncio
async def test_tool_call_round_trip(tmp_path):
    from agent_framework.tools.files import ReadFileTool

    f = tmp_path / "hello.txt"
    f.write_text("world")

    tc_id = uuid.uuid4().hex
    tool_call_resp = ProviderResponse(
        message=Message(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id=tc_id, name="read_file", arguments={"path": str(f)})],
        ),
        stop_reason="tool_calls",
    )
    final_resp = simple_end_turn_response("The file says: world")
    provider = FakeProvider([tool_call_resp, final_resp])
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    agent = Agent(
        provider=provider,
        tools=registry,
        permission_gate=always_allow(),
        persona=persona_all_tools(),
        workdir=str(tmp_path),
    )
    session = Session.with_system_prompt("sys")
    events = []
    async for ev in agent.run_turn(session, "read hello.txt"):
        events.append(ev)
    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert tool_results
    assert not tool_results[0].is_error
    assert "world" in tool_results[0].result
