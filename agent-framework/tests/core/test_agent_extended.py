"""Extended agent loop tests: permission denial, unknown tool, ToolError,
max_iterations guard, provider error, multi-tool-call, session structure."""
from __future__ import annotations

import uuid

import pytest

from agent_framework.core.agent import (
    Agent,
    AssistantTextEvent,
    ErrorEvent,
    PermissionDecisionEvent,
    ToolResultEvent,
)
from agent_framework.core.errors import ToolError
from agent_framework.core.messages import Message, ToolCall
from agent_framework.core.permissions import (
    PermissionDecision,
    PermissionGate,
    PermissionRule,
    always_allow,
)
from agent_framework.core.persona import Persona
from agent_framework.core.provider import ModelProvider, ProviderResponse
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext, ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_persona(max_iterations: int = 10) -> Persona:
    return Persona(
        name="test",
        system_prompt="You are a test agent.",
        provider="fake/model",
        enabled_tools=["*"],
        max_iterations=max_iterations,
    )


def end_turn_resp(text: str = "done") -> ProviderResponse:
    return ProviderResponse(message=Message(role="assistant", content=text), stop_reason="end_turn")


def tool_call_resp(calls: list[tuple[str, dict]]) -> ProviderResponse:
    tcs = [ToolCall(id=uuid.uuid4().hex, name=n, arguments=a) for n, a in calls]
    return ProviderResponse(
        message=Message(role="assistant", content=None, tool_calls=tcs),
        stop_reason="tool_calls",
    )


class FakeProvider(ModelProvider):
    def __init__(self, responses: list[ProviderResponse]):
        super().__init__(model="fake/model")
        self._queue = list(responses)
        self._idx = 0

    async def complete(self, messages, tools, **kw) -> ProviderResponse:
        resp = self._queue[self._idx % len(self._queue)]
        self._idx += 1
        return resp


class AlwaysSucceedTool:
    name = "always_ok"
    description = "Succeeds and returns 'ok'."
    requires_permission = False
    input_schema: dict = {"type": "object", "properties": {}}

    async def run(self, arguments, *, context: ToolContext) -> str:
        return "ok"


class AlwaysErrorTool:
    name = "always_err"
    description = "Raises ToolError."
    requires_permission = False
    input_schema: dict = {"type": "object", "properties": {}}

    async def run(self, arguments, *, context: ToolContext) -> str:
        raise ToolError("always_err", "intentional error")


class AlwaysCrashTool:
    name = "always_crash"
    description = "Raises a bare exception."
    requires_permission = True
    input_schema: dict = {"type": "object", "properties": {}}

    async def run(self, arguments, *, context: ToolContext) -> str:
        raise RuntimeError("unexpected crash")


def make_registry(*tools) -> ToolRegistry:
    r = ToolRegistry()
    for t in tools:
        r.register(t)
    return r


async def collect(agent: Agent, session: Session, user_input: str) -> list:
    events = []
    async for ev in agent.run_turn(session, user_input):
        events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Permission denial
# ---------------------------------------------------------------------------

class TestPermissionDenial:
    @pytest.mark.asyncio
    async def test_denied_tool_produces_error_tool_result(self):
        deny_gate = PermissionGate(rules=[PermissionRule("always_crash", PermissionDecision.DENY)])
        registry = make_registry(AlwaysCrashTool())
        provider = FakeProvider([
            tool_call_resp([("always_crash", {})]),
            end_turn_resp("denied"),
        ])
        agent = Agent(provider=provider, tools=registry, permission_gate=deny_gate, persona=make_persona())
        session = Session.with_system_prompt("sys")
        events = await collect(agent, session, "try crash")

        perm_events = [e for e in events if isinstance(e, PermissionDecisionEvent)]
        assert perm_events[0].decision == PermissionDecision.DENY

        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert result_events[0].is_error
        assert "Permission denied" in result_events[0].result

    @pytest.mark.asyncio
    async def test_permission_denial_sends_error_result_to_model_and_loop_continues(self):
        """The loop must NOT crash on denial — it feeds the error back to the model."""
        deny_gate = PermissionGate(rules=[PermissionRule("always_crash", PermissionDecision.DENY)])
        registry = make_registry(AlwaysCrashTool())
        provider = FakeProvider([
            tool_call_resp([("always_crash", {})]),
            end_turn_resp("ok after denial"),
        ])
        agent = Agent(provider=provider, tools=registry, permission_gate=deny_gate, persona=make_persona())
        session = Session.with_system_prompt("sys")
        events = await collect(agent, session, "try")

        texts = [e.text for e in events if isinstance(e, AssistantTextEvent)]
        assert "ok after denial" in texts


# ---------------------------------------------------------------------------
# Unknown tool name
# ---------------------------------------------------------------------------

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_yields_error_result_not_crash(self):
        registry = make_registry(AlwaysSucceedTool())
        provider = FakeProvider([
            tool_call_resp([("nonexistent_tool", {})]),
            end_turn_resp("handled"),
        ])
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona())
        session = Session.with_system_prompt("sys")
        events = await collect(agent, session, "use missing tool")

        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert result_events[0].is_error
        assert "unknown tool" in result_events[0].result


# ---------------------------------------------------------------------------
# ToolError from tool.run
# ---------------------------------------------------------------------------

class TestToolError:
    @pytest.mark.asyncio
    async def test_tool_error_is_surfaced_as_error_result(self):
        registry = make_registry(AlwaysErrorTool())
        provider = FakeProvider([
            tool_call_resp([("always_err", {})]),
            end_turn_resp("got error"),
        ])
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona())
        session = Session.with_system_prompt("sys")
        events = await collect(agent, session, "run error tool")

        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert result_events[0].is_error
        assert "intentional error" in result_events[0].result

    @pytest.mark.asyncio
    async def test_bare_exception_from_tool_surfaced_as_error(self):
        registry = make_registry(AlwaysCrashTool())
        provider = FakeProvider([
            tool_call_resp([("always_crash", {})]),
            end_turn_resp("got crash"),
        ])
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona())
        session = Session.with_system_prompt("sys")
        events = await collect(agent, session, "run crashing tool")

        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert result_events[0].is_error
        assert "unexpected crash" in result_events[0].result


# ---------------------------------------------------------------------------
# Max iterations guard
# ---------------------------------------------------------------------------

class TestMaxIterations:
    @pytest.mark.asyncio
    async def test_max_iterations_yields_error_event(self):
        """If model keeps calling tools beyond max_iterations, ErrorEvent is emitted."""
        registry = make_registry(AlwaysSucceedTool())
        # Infinite tool calls — always returns a tool call response
        provider = FakeProvider([tool_call_resp([("always_ok", {})])])
        persona = make_persona(max_iterations=2)
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=persona)
        session = Session.with_system_prompt("sys")
        events = await collect(agent, session, "loop forever")

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert error_events
        assert "Max iterations" in error_events[-1].error


# ---------------------------------------------------------------------------
# Provider error
# ---------------------------------------------------------------------------

class TestProviderError:
    @pytest.mark.asyncio
    async def test_provider_exception_yields_error_event(self):
        class BrokenProvider(ModelProvider):
            def __init__(self):
                super().__init__(model="fake/model")
            async def complete(self, messages, tools, **kw):
                raise RuntimeError("network failure")

        agent = Agent(
            provider=BrokenProvider(),
            tools=ToolRegistry(),
            permission_gate=always_allow(),
            persona=make_persona(),
        )
        session = Session.with_system_prompt("sys")
        events = await collect(agent, session, "hi")

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert error_events
        assert "network failure" in error_events[0].error


# ---------------------------------------------------------------------------
# Multi-tool-call in one response
# ---------------------------------------------------------------------------

class TestMultiToolCall:
    @pytest.mark.asyncio
    async def test_two_tool_calls_in_one_response_both_executed(self):
        registry = make_registry(AlwaysSucceedTool())
        provider = FakeProvider([
            tool_call_resp([("always_ok", {}), ("always_ok", {})]),
            end_turn_resp("two done"),
        ])
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona())
        session = Session.with_system_prompt("sys")
        events = await collect(agent, session, "do two things")

        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert len(result_events) == 2
        assert all(not e.is_error for e in result_events)


# ---------------------------------------------------------------------------
# Session structure integrity
# ---------------------------------------------------------------------------

class TestSessionStructure:
    @pytest.mark.asyncio
    async def test_session_messages_after_full_turn(self):
        """After one full turn (user → tool call → tool result → final), session has correct roles."""
        registry = make_registry(AlwaysSucceedTool())
        provider = FakeProvider([
            tool_call_resp([("always_ok", {})]),
            end_turn_resp("final answer"),
        ])
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona())
        session = Session.with_system_prompt("sys")
        await collect(agent, session, "do something")

        roles = [m.role for m in session.messages]
        assert roles == ["system", "user", "assistant", "tool", "assistant"]

    @pytest.mark.asyncio
    async def test_session_tool_result_message_contains_result_content(self):
        registry = make_registry(AlwaysSucceedTool())
        provider = FakeProvider([
            tool_call_resp([("always_ok", {})]),
            end_turn_resp("done"),
        ])
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona())
        session = Session.with_system_prompt("sys")
        await collect(agent, session, "go")

        tool_messages = [m for m in session.messages if m.role == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0].tool_results[0].content == "ok"


# ---------------------------------------------------------------------------
# Persona tool filtering
# ---------------------------------------------------------------------------

class TestPersonaToolFiltering:
    @pytest.mark.asyncio
    async def test_tool_not_in_enabled_list_treated_as_unknown(self):
        """A tool present in registry but not in persona.enabled_tools is not exposed to model.
        If the model somehow still calls it, it's treated as an unknown tool."""
        registry = make_registry(AlwaysSucceedTool(), AlwaysErrorTool())
        persona = Persona(
            name="restricted",
            system_prompt="s",
            provider="fake/model",
            enabled_tools=["always_err"],  # always_ok NOT included
            max_iterations=5,
        )
        # Provider returns tool specs seen by it — we can't inspect that directly,
        # but if model calls always_ok it should be unknown in the filtered registry.
        provider = FakeProvider([
            tool_call_resp([("always_ok", {})]),
            end_turn_resp("done"),
        ])
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=persona)
        session = Session.with_system_prompt("sys")
        events = await collect(agent, session, "call always_ok")

        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert result_events[0].is_error  # unknown in filtered registry
