from __future__ import annotations

from agent_framework.core.permissions import PermissionGate, always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry


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

    async def spawn_subagent(
        self,
        *,
        task_prompt: str,
        persona: Persona,
        allowed_tools: set[str] | None = None,
        workdir: str | None = None,
    ) -> str:
        """Spawn an isolated child agent, run it to completion, return only the final text result."""
        from agent_framework.core.agent import Agent
        from agent_framework.core.provider import ModelProvider

        registry = (
            self.base_tools.filtered(allowed_names=allowed_tools)
            if allowed_tools is not None
            else self.base_tools
        )
        gate = always_allow()  # subagents run non-interactively; trust caller's policy
        session = Session.with_system_prompt(persona.system_prompt)
        agent = Agent(
            provider=ModelProvider.from_persona(persona),
            tools=registry,
            permission_gate=gate,
            persona=persona,
            workdir=workdir or self.workdir,
        )
        return await agent.run_turn_collect(session, task_prompt)
