"""Rich live dashboard for the apathy serve daemon."""
from __future__ import annotations

import asyncio
import sys
import threading
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_framework.core.runtime import AgentRuntime


def _uptime(start: datetime) -> str:
    now = datetime.now()
    delta = int((now - start).total_seconds())
    h, rem = divmod(delta, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


async def run_dashboard(runtime: AgentRuntime, refresh_rate: float = 0.5) -> None:
    """Run the Rich live dashboard. Handles keyboard input for permissions."""
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    start_time = datetime.now()
    input_queue: asyncio.Queue[str] = asyncio.Queue()
    stop_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Keyboard reader in a background thread
    # ------------------------------------------------------------------

    def _read_stdin() -> None:
        try:
            for line in sys.stdin:
                if stop_event.is_set():
                    break
                asyncio.run_coroutine_threadsafe(input_queue.put(line.strip()), loop)
        except (EOFError, OSError):
            # CI / non-interactive: stdin closed
            pass

    loop = asyncio.get_running_loop()
    stdin_thread = threading.Thread(target=_read_stdin, daemon=True)
    stdin_thread.start()

    # ------------------------------------------------------------------
    # Input handler coroutine
    # ------------------------------------------------------------------

    async def _handle_input() -> None:
        while not stop_event.is_set():
            try:
                line = await asyncio.wait_for(input_queue.get(), timeout=0.1)
            except TimeoutError:
                continue

            parts = line.strip().split(None, 1)
            if not parts:
                continue
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ("q", "quit"):
                stop_event.set()
                await runtime.stop()
            elif cmd in ("a", "allow") and arg:
                await runtime.approve_permission(arg, allow=True)
            elif cmd in ("d", "deny") and arg:
                await runtime.approve_permission(arg, allow=False)
            elif cmd in ("t", "trigger") and arg:
                try:
                    await runtime.trigger_manual(arg)
                except ValueError as exc:
                    runtime._log(f"[cli] error: {exc}")
            # "p" pause / "r" refresh -- no-ops (handled by refresh_rate)

    asyncio.create_task(_handle_input())

    # ------------------------------------------------------------------
    # Layout builder
    # ------------------------------------------------------------------

    def _build_layout() -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="jobs", minimum_size=6),
            Layout(name="perms", size=5),
            Layout(name="log", minimum_size=6),
            Layout(name="footer", size=1),
        )
        return layout

    def _render_header(layout: Layout) -> None:
        num_workflows = len(runtime.workflows)
        queued = sum(1 for j in runtime.jobs.values() if j.status.value == "queued")
        running = sum(1 for j in runtime.jobs.values() if j.status.value == "running")
        uptime = _uptime(start_time)
        text = Text()
        text.append(f"  workflows: {num_workflows}", style="bold cyan")
        text.append(f"  |  workers: {runtime.num_workers}", style="cyan")
        text.append(f"  |  queued: {queued}", style="yellow")
        text.append(f"  |  running: {running}", style="green")
        text.append(f"  |  uptime: {uptime}", style="dim")
        layout["header"].update(Panel(text, title="apathy daemon", border_style="cyan"))

    def _render_jobs(layout: Layout) -> None:
        table = Table(title=None, expand=True, show_header=True, header_style="bold")
        table.add_column("ID", style="dim", width=8)
        table.add_column("WORKFLOW", style="cyan", max_width=18)
        table.add_column("STEP", max_width=14)
        table.add_column("PERSONA", max_width=12)
        table.add_column("STATUS", justify="center", width=12)
        table.add_column("TASK")

        status_styles = {
            "queued": "yellow",
            "running": "green bold",
            "done": "dim",
            "failed": "red bold",
            "waiting_perm": "magenta bold",
        }

        # Show most-recent 15 jobs
        recent = list(runtime.jobs.values())[-15:]
        for job in reversed(recent):
            style = status_styles.get(job.status.value, "")
            task_preview = job.task[:50].replace("\n", " ")
            table.add_row(
                job.id,
                job.workflow_name,
                job.step_name,
                job.persona_name,
                Text(job.status.value.upper(), style=style),
                task_preview,
            )

        layout["jobs"].update(Panel(table, title="Active Jobs", border_style="blue"))

    def _render_perms(layout: Layout) -> None:
        if not runtime.perm_requests:
            layout["perms"].update(
                Panel("[dim]No pending permission requests[/dim]", border_style="dim")
            )
            return
        lines: list[str] = []
        for req_id, req in runtime.perm_requests.items():
            args_preview = str(req.arguments)[:60]
            lines.append(
                f"  [[bold]{req_id}[/bold]] job {req.job_id} wants: "
                f"[yellow]{req.tool_name}[/yellow] {args_preview}"
            )
        hint = (
            "  Press: [green]a <id>[/green]llow  [red]d <id>[/red]eny  (60s timeout -> deny)"
        )
        lines.append(hint)
        layout["perms"].update(
            Panel("\n".join(lines), title="Permission Requests", border_style="yellow")
        )

    def _render_log(layout: Layout) -> None:
        lines = list(runtime.event_log)[:10]
        text = "\n".join(lines) if lines else "[dim]No events yet[/dim]"
        layout["log"].update(Panel(text, title="Event Log", border_style="dim"))

    def _render_footer(layout: Layout) -> None:
        layout["footer"].update(
            Text(
                " [t]rigger <name>  [a]llow <id>  [d]eny <id>  [q]uit",
                style="dim",
            )
        )

    layout = _build_layout()

    with Live(layout, refresh_per_second=int(1 / refresh_rate), screen=False) as _live:
        while not stop_event.is_set() and not runtime._stop_event.is_set():
            _render_header(layout)
            _render_jobs(layout)
            _render_perms(layout)
            _render_log(layout)
            _render_footer(layout)
            await asyncio.sleep(refresh_rate)

    stop_event.set()
