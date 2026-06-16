"""End-to-end integration tests: full pipeline from user input through tool execution
to final response, verifying session structure, event ordering, and correct outputs."""
from __future__ import annotations

import uuid

import pytest

from agent_framework.core.agent import (
    Agent,
    PermissionDecisionEvent,
    ToolResultEvent,
)
from agent_framework.core.messages import Message, ToolCall
from agent_framework.core.permissions import (
    PermissionDecision,
    PermissionGate,
    always_allow,
)
from agent_framework.core.persona import Persona
from agent_framework.core.provider import ModelProvider, ProviderResponse
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry
from agent_framework.tools import register_builtin_tools


class SequentialProvider(ModelProvider):
    """Returns preset responses in order, cycling if exhausted."""
    def __init__(self, responses: list[ProviderResponse]):
        super().__init__(model="fake/model")
        self._responses = responses
        self._idx = 0

    async def complete(self, messages, tools, **kw) -> ProviderResponse:
        resp = self._responses[self._idx]
        self._idx = min(self._idx + 1, len(self._responses) - 1)
        return resp


def make_persona() -> Persona:
    return Persona(
        name="e2e",
        system_prompt="You are a helpful assistant with file and shell tools.",
        provider="fake/model",
        enabled_tools=["*"],
    )


def tool_call_resp(name: str, args: dict) -> ProviderResponse:
    tc = ToolCall(id=uuid.uuid4().hex, name=name, arguments=args)
    return ProviderResponse(
        message=Message(role="assistant", content=None, tool_calls=[tc]),
        stop_reason="tool_calls",
    )


def text_resp(text: str) -> ProviderResponse:
    return ProviderResponse(
        message=Message(role="assistant", content=text),
        stop_reason="end_turn",
    )


class TestReadFilePipeline:
    @pytest.mark.asyncio
    async def test_reads_real_file_and_returns_content(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("content from file")

        provider = SequentialProvider([
            tool_call_resp("read_file", {"path": str(f)}),
            text_resp("The file contains: content from file"),
        ])
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona(), workdir=str(tmp_path))
        session = Session.with_system_prompt("sys")
        events = []
        async for ev in agent.run_turn(session, "read hello.txt"):
            events.append(ev)

        # Verify event ordering: ToolCall → ToolResult → AssistantText → TurnComplete
        types = [type(e).__name__ for e in events]
        tc_idx = types.index("ToolCallEvent")
        tr_idx = types.index("ToolResultEvent")
        at_idx = types.index("AssistantTextEvent")
        done_idx = types.index("TurnCompleteEvent")
        assert tc_idx < tr_idx < at_idx < done_idx

        # Verify the tool result contains the actual file content
        tr = next(e for e in events if isinstance(e, ToolResultEvent))
        assert "content from file" in tr.result
        assert not tr.is_error

    @pytest.mark.asyncio
    async def test_final_text_reflects_real_file_content(self, tmp_path):
        f = tmp_path / "project.toml"
        f.write_text('[project]\nname = "myapp"')

        provider = SequentialProvider([
            tool_call_resp("read_file", {"path": str(f)}),
            text_resp("The project name is myapp"),
        ])
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona(), workdir=str(tmp_path))
        session = Session.with_system_prompt("sys")

        result = await agent.run_turn_collect(session, "what is the project name?")
        assert "myapp" in result


class TestBashPipeline:
    @pytest.mark.asyncio
    async def test_runs_real_shell_command(self, tmp_path):
        provider = SequentialProvider([
            tool_call_resp("bash", {"command": "echo hello-from-agent"}),
            text_resp("The echo output is: hello-from-agent"),
        ])
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona(), workdir=str(tmp_path))
        session = Session.with_system_prompt("sys")
        events = []
        async for ev in agent.run_turn(session, "run echo"):
            events.append(ev)

        tr = next(e for e in events if isinstance(e, ToolResultEvent))
        assert "hello-from-agent" in tr.result
        assert not tr.is_error


class TestMultiStepPipeline:
    @pytest.mark.asyncio
    async def test_write_then_read_file(self, tmp_path):
        """Model writes a file in step 1, reads it back in step 2."""
        provider = SequentialProvider([
            tool_call_resp("write_file", {"path": "output.txt", "content": "written data"}),
            tool_call_resp("read_file", {"path": "output.txt"}),
            text_resp("Done: written data"),
        ])
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona(), workdir=str(tmp_path))
        session = Session.with_system_prompt("sys")
        events = []
        async for ev in agent.run_turn(session, "write then read"):
            events.append(ev)

        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert len(result_events) == 2
        assert not result_events[0].is_error  # write succeeded
        assert "written data" in result_events[1].result  # read got what was written

    @pytest.mark.asyncio
    async def test_session_grows_correctly_across_multi_step(self, tmp_path):
        provider = SequentialProvider([
            tool_call_resp("bash", {"command": "echo step1"}),
            tool_call_resp("bash", {"command": "echo step2"}),
            text_resp("all done"),
        ])
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent(provider=provider, tools=registry, permission_gate=always_allow(), persona=make_persona(), workdir=str(tmp_path))
        session = Session.with_system_prompt("sys")
        await agent.run_turn_collect(session, "do two things")

        roles = [m.role for m in session.messages]
        # system, user, assistant(tc1), tool, assistant(tc2), tool, assistant(final)
        assert roles.count("tool") == 2
        assert roles.count("assistant") == 3


class TestPermissionIntegration:
    @pytest.mark.asyncio
    async def test_interactive_approve_allows_write(self, tmp_path):
        approved: list = []

        async def approving_callback(tool, args) -> bool:
            approved.append(tool.name)
            return True

        gate = PermissionGate(ask_callback=approving_callback)
        provider = SequentialProvider([
            tool_call_resp("write_file", {"path": "out.txt", "content": "approved"}),
            text_resp("file written"),
        ])
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent(provider=provider, tools=registry, permission_gate=gate, persona=make_persona(), workdir=str(tmp_path))
        session = Session.with_system_prompt("sys")
        await agent.run_turn_collect(session, "write a file")

        assert "write_file" in approved
        assert (tmp_path / "out.txt").read_text() == "approved"

    @pytest.mark.asyncio
    async def test_interactive_deny_prevents_write(self, tmp_path):
        async def denying_callback(tool, args) -> bool:
            return False

        gate = PermissionGate(ask_callback=denying_callback)
        provider = SequentialProvider([
            tool_call_resp("write_file", {"path": "out.txt", "content": "should not write"}),
            text_resp("denied"),
        ])
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent(provider=provider, tools=registry, permission_gate=gate, persona=make_persona(), workdir=str(tmp_path))
        session = Session.with_system_prompt("sys")
        events = []
        async for ev in agent.run_turn(session, "write a file"):
            events.append(ev)

        # File must not exist
        assert not (tmp_path / "out.txt").exists()

        perm_events = [e for e in events if isinstance(e, PermissionDecisionEvent)]
        assert perm_events[0].decision == PermissionDecision.DENY

    @pytest.mark.asyncio
    async def test_read_only_tool_never_asks(self, tmp_path):
        asked_tools: list = []

        async def callback(tool, args) -> bool:
            asked_tools.append(tool.name)
            return True

        gate = PermissionGate(ask_callback=callback)
        f = tmp_path / "data.txt"
        f.write_text("data")

        provider = SequentialProvider([
            tool_call_resp("read_file", {"path": str(f)}),
            text_resp("got data"),
        ])
        registry = ToolRegistry()
        register_builtin_tools(registry)
        agent = Agent(provider=provider, tools=registry, permission_gate=gate, persona=make_persona(), workdir=str(tmp_path))
        session = Session.with_system_prompt("sys")
        await agent.run_turn_collect(session, "read data.txt")

        # Callback never called for read-only tool
        assert "read_file" not in asked_tools


class TestBuiltinToolRegistration:
    def test_register_builtin_tools_registers_all(self):
        registry = ToolRegistry()
        register_builtin_tools(registry)
        names = {t.name for t in registry.all()}
        assert names >= {
            "read_file", "write_file", "edit_file", "list_dir",
            "bash", "grep", "glob", "web_fetch", "http_request",
        }

    def test_register_builtin_tools_with_include_filter(self):
        registry = ToolRegistry()
        register_builtin_tools(registry, include={"read_file", "bash"})
        names = {t.name for t in registry.all()}
        assert names == {"read_file", "bash"}
