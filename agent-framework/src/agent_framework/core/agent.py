from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_framework.core.errors import ToolError
from agent_framework.core.messages import Message, ToolCall, ToolResult
from agent_framework.core.permissions import PermissionDecision, PermissionGate
from agent_framework.core.persona import Persona
from agent_framework.core.provider import ModelProvider, ProviderResponse
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext, ToolRegistry

# --- Events ---


@dataclass
class AssistantTextEvent:
    text: str


@dataclass
class ToolCallEvent:
    tool_call: ToolCall


@dataclass
class PermissionDecisionEvent:
    tool_name: str
    decision: PermissionDecision
    arguments: dict[str, Any]


@dataclass
class ToolResultEvent:
    tool_name: str
    result: str
    is_error: bool


@dataclass
class TurnCompleteEvent:
    final_text: str | None


@dataclass
class ErrorEvent:
    error: str


AgentEvent = (
    AssistantTextEvent
    | ToolCallEvent
    | PermissionDecisionEvent
    | ToolResultEvent
    | TurnCompleteEvent
    | ErrorEvent
)


# --- Agent ---


class Agent:
    def __init__(
        self,
        provider: ModelProvider,
        tools: ToolRegistry,
        permission_gate: PermissionGate,
        persona: Persona,
        workdir: str = ".",
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.permission_gate = permission_gate
        self.persona = persona
        self.workdir = workdir
        self._orchestrator = None  # set by Orchestrator when spawning subagents

    async def run_turn(
        self, session: Session, user_input: str
    ) -> AsyncIterator[AgentEvent]:
        session.append(Message(role="user", content=user_input))

        context = ToolContext(
            workdir=Path(self.workdir),
            session=session,
            permission_gate=self.permission_gate,
            orchestrator=self._orchestrator,
        )

        for _iteration in range(self.persona.max_iterations):
            # Determine which tools to expose based on persona's enabled_tools
            if self.persona.allows_all_tools():
                registry = self.tools
            else:
                registry = self.tools.filtered(allowed_names=set(self.persona.enabled_tools))

            try:
                resp: ProviderResponse = await self.provider.complete(
                    session.messages, registry.specs()
                )
            except Exception as exc:
                yield ErrorEvent(error=str(exc))
                return

            session.append(resp.message)

            if resp.message.content:
                yield AssistantTextEvent(text=resp.message.content)

            if resp.stop_reason != "tool_calls" or not resp.message.tool_calls:
                yield TurnCompleteEvent(final_text=resp.message.content)
                return

            # Execute all tool calls sequentially to avoid context conflicts
            tool_results: list[ToolResult] = []
            for tc in resp.message.tool_calls:
                yield ToolCallEvent(tool_call=tc)

                try:
                    tool = registry.get(tc.name)
                except KeyError:
                    result = ToolResult(
                        tool_call_id=tc.id,
                        content=f"Error: unknown tool '{tc.name}'",
                        is_error=True,
                    )
                    yield ToolResultEvent(tool_name=tc.name, result=result.content, is_error=True)
                    tool_results.append(result)
                    continue

                decision = await self.permission_gate.check(tool, tc.arguments)
                yield PermissionDecisionEvent(
                    tool_name=tc.name, decision=decision, arguments=tc.arguments
                )

                if decision == PermissionDecision.DENY:
                    result = ToolResult(
                        tool_call_id=tc.id,
                        content=f"Permission denied for tool '{tc.name}'",
                        is_error=True,
                    )
                else:
                    try:
                        output = await tool.run(tc.arguments, context=context)
                        result = ToolResult(tool_call_id=tc.id, content=output)
                    except ToolError as exc:
                        result = ToolResult(tool_call_id=tc.id, content=str(exc), is_error=True)
                    except Exception as exc:
                        result = ToolResult(
                            tool_call_id=tc.id,
                            content=f"Unexpected error in '{tc.name}': {exc}",
                            is_error=True,
                        )

                yield ToolResultEvent(
                    tool_name=tc.name, result=result.content, is_error=result.is_error
                )
                tool_results.append(result)

            # Append all tool results as a single message
            session.append(Message(role="tool", tool_results=tool_results))

        yield ErrorEvent(error=f"Max iterations ({self.persona.max_iterations}) reached")

    async def run_turn_collect(self, session: Session, user_input: str) -> str:
        """Convenience: drives run_turn to completion and returns final text."""
        final = ""
        async for event in self.run_turn(session, user_input):
            if isinstance(event, AssistantTextEvent):
                final = event.text
            elif isinstance(event, TurnCompleteEvent):
                final = event.final_text or final
        return final

    @classmethod
    def from_persona(
        cls,
        persona: Persona,
        tools: ToolRegistry,
        permission_gate: PermissionGate,
        workdir: str = ".",
    ) -> Agent:
        provider = ModelProvider.from_persona(persona)
        return cls(
            provider=provider,
            tools=tools,
            permission_gate=permission_gate,
            persona=persona,
            workdir=workdir,
        )
