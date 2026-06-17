"""Rich live dashboard for `apathy serve`."""
from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from agent_framework.core.runtime import AgentRuntime


def _header(runtime: AgentRuntime) -> Panel:
    wf_count = len(runtime._workflows)
    queued = runtime.queued_count
    t = Text()
    t.append("  workflows: ", style="dim")
    t.append(str(wf_count), style="bold cyan")
    t.append("  │  workers: ", style="dim")
    t.append(str(runtime.num_workers), style="bold cyan")
    t.append("  │  queued: ", style="dim")
    t.append(str(queued), style="bold yellow" if queued else "bold cyan")
    t.append("  │  uptime: ", style="dim")
    t.append(runtime.uptime, style="bold green")
    t.append("  │  [t]rigger  [q]uit", style="dim")
    return Panel(t, title="[bold magenta]apathy daemon[/bold magenta]", border_style="magenta")


def _jobs_table(runtime: AgentRuntime) -> Table:
    table = Table(title="Active Jobs", show_header=True, header_style="bold cyan", expand=True)
    table.add_column("ID", width=10)
    table.add_column("Workflow")
    table.add_column("Step")
    table.add_column("Status", width=10)
    table.add_column("Duration", width=8)
    table.add_column("Task", no_wrap=True)

    _min = datetime.datetime.min
    recent = sorted(
        runtime.jobs.values(),
        key=lambda j: j.started_at or j.finished_at or _min,
        reverse=True,
    )[:12]
    for job in recent:
        status_color = {
            "queued": "yellow",
            "running": "green",
            "done": "dim",
            "failed": "red",
        }.get(job.status.value, "white")
        table.add_row(
            job.id,
            job.workflow_name,
            job.step_name,
            f"[{status_color}]{job.status.value}[/{status_color}]",
            job.duration,
            job.task[:60],
        )
    return table


def _perm_panel(runtime: AgentRuntime) -> Panel:
    pending = runtime.pending_permissions
    if not pending:
        content = Text("No pending permission requests.", style="dim")
    else:
        lines = []
        for req in pending[:5]:
            args_preview = ", ".join(
                f"{k}={str(v)[:20]}" for k, v in req.arguments.items()
            )
            lines.append(f"[{req.id}] {req.tool_name}({args_preview})  job={req.job_id}")
        content = Text("\n".join(lines))
    return Panel(content, title="[yellow]Permission Requests[/yellow]", border_style="yellow")


def _log_panel(runtime: AgentRuntime) -> Panel:
    lines = list(runtime.event_log)[-15:]
    content = Text("\n".join(lines) or "(no events yet)", style="dim")
    return Panel(content, title="[blue]Event Log[/blue]", border_style="blue")


def _build_layout(runtime: AgentRuntime) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="bottom", size=10),
    )
    layout["body"].split_row(
        Layout(name="jobs", ratio=2),
        Layout(name="perms", ratio=1),
    )
    layout["header"].update(_header(runtime))
    layout["body"]["jobs"].update(_jobs_table(runtime))
    layout["body"]["perms"].update(_perm_panel(runtime))
    layout["bottom"].update(_log_panel(runtime))
    return layout


async def run_dashboard(
    runtime: AgentRuntime,
    *,
    refresh_per_second: int = 2,
) -> None:
    console = Console()
    console.print("[bold magenta]apathy daemon[/bold magenta] starting...")

    await runtime.start()

    with Live(
        _build_layout(runtime),
        console=console,
        refresh_per_second=refresh_per_second,
        screen=True,
    ) as live:
        try:
            while True:
                await asyncio.sleep(0.5)
                live.update(_build_layout(runtime))
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass

    await runtime.stop()
    console.print("[dim]apathy daemon stopped.[/dim]")
