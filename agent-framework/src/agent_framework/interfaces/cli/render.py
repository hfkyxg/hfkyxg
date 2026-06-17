from __future__ import annotations

import asyncio
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from agent_framework.core.agent import (
    AgentEvent,
    AssistantTextEvent,
    ErrorEvent,
    PermissionDecisionEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from agent_framework.core.permissions import PermissionDecision

console = Console()


def render_event(event: AgentEvent) -> None:
    if isinstance(event, AssistantTextEvent):
        console.print(Text(event.text, style="white"))
    elif isinstance(event, ToolCallEvent):
        tc = event.tool_call
        body = f"[dim]{escape(str(tc.arguments))}[/dim]"
        console.print(Panel(body, title=f"[cyan]Tool: {tc.name}[/cyan]", border_style="cyan"))
    elif isinstance(event, PermissionDecisionEvent):
        if event.decision == PermissionDecision.DENY:
            console.print(f"[red]  ✗ Permission denied: {event.tool_name}[/red]")
        elif event.decision == PermissionDecision.ALLOW:
            console.print(f"[dim]  ✓ Allowed: {event.tool_name}[/dim]")
    elif isinstance(event, ToolResultEvent):
        style = "red" if event.is_error else "green"
        prefix = "✗" if event.is_error else "✓"
        preview = event.result[:300] + ("…" if len(event.result) > 300 else "")
        console.print(
            f"[{style}]  {prefix} {event.tool_name}:[/{style}] [dim]{escape(preview)}[/dim]"
        )
    elif isinstance(event, ErrorEvent):
        console.print(f"[bold red]Error: {escape(event.error)}[/bold red]")


def render_subagent_event(label: str, event: AgentEvent) -> None:
    """Render an event emitted by a subagent, indented and tagged with its persona."""
    tag = f"[magenta]└─ subagente:{label}[/magenta]"
    if isinstance(event, ToolCallEvent):
        tc = event.tool_call
        args = escape(str(tc.arguments))
        console.print(f"    {tag} [cyan]usa {tc.name}[/cyan] [dim]{args}[/dim]")
    elif isinstance(event, ToolResultEvent):
        style = "red" if event.is_error else "green"
        prefix = "✗" if event.is_error else "✓"
        preview = event.result[:200] + ("…" if len(event.result) > 200 else "")
        console.print(f"    {tag} [{style}]{prefix} {escape(preview)}[/{style}]")
    elif isinstance(event, AssistantTextEvent):
        preview = event.text[:200] + ("…" if len(event.text) > 200 else "")
        console.print(f"    {tag} [dim]{escape(preview)}[/dim]")
    elif isinstance(event, ErrorEvent):
        console.print(f"    {tag} [red]erro: {escape(event.error)}[/red]")


async def ask_permission(tool: Any, arguments: dict) -> bool:
    from rich.prompt import Confirm

    summary = str(arguments)[:200]
    console.print(f"\n[yellow]⚠ Agent wants to run [bold]{tool.name}[/bold]:[/yellow]")
    console.print(f"  [dim]{escape(summary)}[/dim]")
    # Confirm is blocking — wrap in executor to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: Confirm.ask("  Allow?", default=False))
    return result
