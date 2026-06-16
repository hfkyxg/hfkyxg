from __future__ import annotations

import asyncio

from rich.console import Console
from rich.prompt import Prompt

from agent_framework.core.agent import Agent
from agent_framework.core.orchestrator import Orchestrator
from agent_framework.core.permissions import PermissionGate
from agent_framework.core.persona import Persona
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry
from agent_framework.interfaces.cli.render import ask_permission, render_event
from agent_framework.tools import register_builtin_tools

console = Console()


async def run_repl(persona: Persona, workdir: str) -> None:
    registry = ToolRegistry()
    register_builtin_tools(registry)

    gate = PermissionGate(ask_callback=ask_permission)
    orchestrator = Orchestrator(base_tools=registry, base_permission_gate=gate, workdir=workdir)

    agent = Agent.from_persona(persona, registry, gate, workdir)
    agent._orchestrator = orchestrator

    session = Session.with_system_prompt(persona.system_prompt)
    console.print(
        f"[bold green]agent-framework[/bold green] — persona: [cyan]{persona.name}[/cyan]"
    )
    console.print(f"  model: [dim]{persona.provider}[/dim]  workdir: [dim]{workdir}[/dim]")
    console.print("  Type [bold]/exit[/bold] or Ctrl+C to quit.\n")

    loop = asyncio.get_event_loop()
    while True:
        try:
            user_input = await loop.run_in_executor(
                None, lambda: Prompt.ask("[bold blue]you[/bold blue]")
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if user_input.strip().lower() in ("/exit", "/quit", "exit", "quit"):
            console.print("[dim]Goodbye.[/dim]")
            break
        if not user_input.strip():
            continue

        console.print()
        async for event in agent.run_turn(session, user_input):
            render_event(event)
        console.print()
