"""Scripted offline demo — runs the full agent loop with NO API key.

Creates a throwaway workspace, then drives the demo persona (mock provider)
through a sequence of real tool calls: write a file, read it back, list the
directory, run a shell command, and grep. Everything actually executes.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from rich.console import Console

from agent_framework.core.agent import Agent
from agent_framework.core.orchestrator import Orchestrator
from agent_framework.core.permissions import PermissionGate
from agent_framework.core.persona import Persona
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry
from agent_framework.interfaces.cli.banner import print_banner
from agent_framework.interfaces.cli.render import render_event
from agent_framework.tools import register_builtin_tools

console = Console()

_SCRIPT = [
    "escreva o arquivo hello.txt",
    "leia o arquivo hello.txt",
    "liste o diretório .",
    "rode: echo apathy-esta-vivo",
    "busque apathy .",
]


def _demo_persona() -> Persona:
    return Persona(
        name="demo",
        system_prompt="apathy offline demo agent.",
        provider="mock/demo",
        enabled_tools=["read_file", "write_file", "list_dir", "bash", "grep", "glob"],
        max_iterations=6,
    )


async def run_demo() -> None:
    print_banner(console, subtitle="offline demo — no API key required")

    workspace = Path(tempfile.mkdtemp(prefix="apathy-demo-"))
    console.print(f"  [dim]workspace: {workspace}[/dim]\n")

    registry = ToolRegistry()
    register_builtin_tools(registry)
    # Autopilot: this is a sandboxed throwaway dir, so don't prompt on every action.
    gate = PermissionGate(autopilot=True, workspace_root=str(workspace))
    orchestrator = Orchestrator(
        base_tools=registry, base_permission_gate=gate, workdir=str(workspace)
    )
    persona = _demo_persona()
    agent = Agent.from_persona(persona, registry, gate, str(workspace))
    agent._orchestrator = orchestrator
    session = Session.with_system_prompt(persona.system_prompt)

    for step, prompt in enumerate(_SCRIPT, 1):
        console.rule(f"[bold blue]passo {step}[/bold blue]  ›  {prompt}")
        async for event in agent.run_turn(session, prompt):
            render_event(event)
        console.print()

    console.print(
        "[bold green]✓ Demo concluída — o loop de ferramentas funcionou "
        "de ponta a ponta.[/bold green]"
    )
    console.print(f"[dim]Artefatos em: {workspace}[/dim]")
