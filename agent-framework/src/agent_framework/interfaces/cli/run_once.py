"""Single-shot, non-interactive task execution — `apathy run "<task>"`.

Drives one full agent turn and prints the events. Useful for scripting and
automation. With --yes (or autopilot personas) it never prompts.
"""
from __future__ import annotations

import os

from rich.console import Console
from rich.tree import Tree

from agent_framework.core.agent import Agent
from agent_framework.core.orchestrator import Orchestrator
from agent_framework.core.permissions import PermissionGate, always_allow
from agent_framework.core.persona import Persona
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolRegistry
from agent_framework.interfaces.cli.render import (
    ask_permission,
    render_event,
    render_subagent_event,
)
from agent_framework.tools import register_builtin_tools


def _show_workspace_tree(workspace: str, console: Console) -> None:
    """Print a Rich tree of files created in workspace."""
    all_files: list[tuple[str, str]] = []  # (rel_path, abs_path)
    for dirpath, dirnames, filenames in os.walk(workspace):
        dirnames.sort()
        for fname in sorted(filenames):
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, workspace)
            all_files.append((rel_path, abs_path))

    if not all_files:
        return

    tree = Tree(f"[cyan]{workspace}/[/cyan]")

    # Build nested structure
    dir_nodes: dict[str, object] = {}

    for rel_path, abs_path in all_files:
        parts = rel_path.split(os.sep)
        # Create intermediate directory nodes
        current = tree
        for part in parts[:-1]:
            key = part
            if key not in dir_nodes:
                dir_nodes[key] = current.add(f"[cyan]{part}/[/cyan]")  # type: ignore[attr-defined]
            current = dir_nodes[key]  # type: ignore[assignment]
        # Add file leaf
        try:
            size = os.path.getsize(abs_path)
            with open(abs_path, "rb") as f:
                line_count = f.read().count(b"\n")
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.2f} MB"
            current.add(f"[white]{parts[-1]}[/white] [dim]({line_count} lines, {size_str})[/dim]")  # type: ignore[attr-defined]
        except OSError:
            current.add(f"[white]{parts[-1]}[/white]")  # type: ignore[attr-defined]

    console.print(tree)


async def run_once(
    persona: Persona,
    task: str,
    workdir: str,
    *,
    auto_approve: bool = False,
    extra_personas: dict[str, Persona] | None = None,
    event_hook: object | None = None,
    permission_gate: PermissionGate | None = None,
) -> None:
    registry = ToolRegistry()
    personas = {persona.name: persona}
    if extra_personas:
        personas.update(extra_personas)
    register_builtin_tools(registry, task_personas=personas)

    if permission_gate is not None:
        gate = permission_gate
    elif auto_approve:
        gate = always_allow()
    else:
        gate = PermissionGate(ask_callback=ask_permission)

    orchestrator = Orchestrator(base_tools=registry, base_permission_gate=gate, workdir=workdir)
    orchestrator.subagent_event_hook = render_subagent_event

    agent = Agent.from_persona(persona, registry, gate, workdir)
    agent._orchestrator = orchestrator
    session = Session.with_system_prompt(persona.system_prompt)

    async for event in agent.run_turn(session, task):
        if event_hook is not None:
            import inspect
            if inspect.iscoroutinefunction(event_hook):
                await event_hook(event)  # type: ignore[call-arg]
            else:
                event_hook(event)  # type: ignore[call-arg]
        else:
            render_event(event)
