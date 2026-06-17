from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from agent_framework.core.permissions import PermissionGate, always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry

if TYPE_CHECKING:
    from agent_framework.core.agent import AgentEvent


class Orchestrator:
    def __init__(
        self,
        base_tools: ToolRegistry,
        base_permission_gate: PermissionGate,
        workdir: str = ".",
    ) -> None:
        self.base_tools = base_tools
        self.base_permission_gate = base_permission_gate
        self.workdir = workdir
        # Optional hook(label, event) called for every event a subagent emits.
        # Lets interfaces render subagent activity live so users can watch it work.
        self.subagent_event_hook: Callable[[str, AgentEvent], None] | None = None

    async def spawn_subagent(
        self,
        *,
        task_prompt: str,
        persona: Persona,
        allowed_tools: set[str] | None = None,
        workdir: str | None = None,
    ) -> str:
        """Spawn an isolated child agent, run it to completion, return only the final text."""
        from agent_framework.core.agent import (
            AssistantTextEvent,
            TurnCompleteEvent,
        )

        registry = (
            self.base_tools.filtered(allowed_names=allowed_tools)
            if allowed_tools is not None
            else self.base_tools
        )
        gate = always_allow()  # subagents run non-interactively; trust caller's policy
        session = Session.with_system_prompt(persona.system_prompt)
        agent = self._build_agent(persona, registry, gate, workdir)

        final = ""
        async for event in agent.run_turn(session, task_prompt):
            if self.subagent_event_hook is not None:
                self.subagent_event_hook(persona.name, event)
            if isinstance(event, AssistantTextEvent):
                final = event.text
            elif isinstance(event, TurnCompleteEvent):
                final = event.final_text or final
        return final

    def _build_agent(self, persona, registry, gate, workdir):
        from agent_framework.core.agent import Agent
        from agent_framework.core.provider import ModelProvider

        agent = Agent(
            provider=ModelProvider.from_persona(persona),
            tools=registry,
            permission_gate=gate,
            persona=persona,
            workdir=workdir or self.workdir,
        )
        # Subagents can themselves delegate, sharing this orchestrator.
        agent._orchestrator = self
        return agent
