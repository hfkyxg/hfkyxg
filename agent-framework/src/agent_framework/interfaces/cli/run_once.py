"""Single-shot, non-interactive task execution — `apathy run "<task>"`.

Drives one full agent turn and prints the events. Useful for scripting and
automation. With --yes (or autopilot personas) it never prompts.
"""
from __future__ import annotations

from agent_framework.core.agent import Agent
from agent_framework.core.orchestrator import Orchestrator
from agent_framework.core.permissions import PermissionGate, always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry
from agent_framework.interfaces.cli.render import ask_permission, render_event
from agent_framework.tools import register_builtin_tools


async def run_once(
    persona: Persona,
    task: str,
    workdir: str,
    *,
    auto_approve: bool = False,
) -> None:
    registry = ToolRegistry()
    register_builtin_tools(registry, task_personas={persona.name: persona})

    gate = always_allow() if auto_approve else PermissionGate(ask_callback=ask_permission)
    orchestrator = Orchestrator(base_tools=registry, base_permission_gate=gate, workdir=workdir)

    agent = Agent.from_persona(persona, registry, gate, workdir)
    agent._orchestrator = orchestrator
    session = Session.with_system_prompt(persona.system_prompt)

    async for event in agent.run_turn(session, task):
        render_event(event)
