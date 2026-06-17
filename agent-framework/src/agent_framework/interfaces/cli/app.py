from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from agent_framework.core.persona import Persona

app = typer.Typer(
    name="apathy",
    help="apathy — autonomous agent framework with parallel multi-agent execution",
    no_args_is_help=True,
)


@app.command()
def chat(
    persona: Path = typer.Option(
        Path("personas/default.yaml"),
        "--persona",
        "-p",
        help="Path to persona YAML file",
        exists=True,
    ),
    workdir: str = typer.Option(
        ".", "--workdir", "-w", help="Working directory for file/shell tools"
    ),
) -> None:
    """Start an interactive chat session with the agent."""
    from agent_framework.interfaces.cli.repl import run_repl

    p = Persona.from_yaml(persona)
    asyncio.run(run_repl(p, workdir))


@app.command()
def build(
    objective: str = typer.Argument(..., help="What to build, e.g. 'a REST API with FastAPI'"),
    workspace: Path = typer.Option(
        Path("./build-output"),
        "--workspace",
        "-w",
        help="Directory where the project will be created",
    ),
    personas_dir: Path = typer.Option(
        Path("personas"),
        "--personas-dir",
        help="Directory containing role persona YAML files",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only, do not execute"),
) -> None:
    """Build a software project using a team of specialized agents working in parallel."""
    from agent_framework.interfaces.cli.crew_runner import run_build

    asyncio.run(run_build(objective, workspace, personas_dir, dry_run=dry_run))


@app.command()
def run(
    task: str = typer.Argument(..., help="The task to run, in natural language"),
    persona: Path = typer.Option(
        Path("personas/default.yaml"),
        "--persona",
        "-p",
        help="Path to persona YAML file",
        exists=True,
    ),
    workdir: str = typer.Option(
        ".", "--workdir", "-w", help="Working directory for file/shell tools"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Auto-approve all tool actions (non-interactive)"
    ),
) -> None:
    """Run a single task non-interactively and print the result (scriptable)."""
    from agent_framework.interfaces.cli.run_once import run_once

    p = Persona.from_yaml(persona)
    asyncio.run(run_once(p, task, workdir, auto_approve=yes))


@app.command()
def create(
    project_type: Annotated[str, typer.Argument(help="Project type: fastapi, cli, webapp, data")],
    name: Annotated[str, typer.Option("--name", "-n", help="Project name")] = "myapp",
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("./output"),
    persona: Annotated[Path, typer.Option("--persona", "-p")] = Path("personas/demo.yaml"),
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Auto-approve all actions")] = False,
) -> None:
    """Create a complete project autonomously (no API key required with demo persona)."""
    from rich.console import Console

    from agent_framework.interfaces.cli.run_once import _show_workspace_tree, run_once

    console = Console()
    workspace_resolved = workspace.resolve()
    console.print(
        f"[bold cyan]Creating[/bold cyan] [yellow]{project_type}[/yellow] project "
        f"'[green]{name}[/green]' in [blue]{workspace_resolved}[/blue]..."
    )
    workspace_resolved.mkdir(parents=True, exist_ok=True)
    (workspace_resolved / "tests").mkdir(exist_ok=True)

    p = Persona.from_yaml(persona)
    prompt = (
        f"crie um projeto {project_type} completo chamado {name} "
        f"no diretório {workspace_resolved}"
    )
    asyncio.run(run_once(p, prompt, str(workspace_resolved), auto_approve=yes))
    _show_workspace_tree(str(workspace_resolved), console)


@app.command()
def organize(
    path: Annotated[Path, typer.Argument(help="Directory to organize")] = Path("."),
    mode: Annotated[
        str, typer.Option("--mode", "-m", help="by_type, by_date, or by_size")
    ] = "by_type",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show plan without moving files")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Auto-approve")] = False,
) -> None:
    """Autonomously organize files in a directory by type, date, or size."""
    from rich.console import Console
    from rich.table import Table

    from agent_framework.tools.organize import (
        ALWAYS_SKIP,
        CATEGORIES,
        FileOrganizeTool,
        _categorize,
    )

    console = Console()
    root = path.resolve()

    if not root.exists():
        console.print(f"[red]Directory not found: {root}[/red]")
        raise typer.Exit(1)

    # Scan first
    files = [
        f for f in root.rglob("*")
        if f.is_file()
        and not any(part in ALWAYS_SKIP for part in f.parts)
        and not f.name.startswith(".")
        and f.name != "manifest.json"
    ]

    if not files:
        console.print("[yellow]No files to organize.[/yellow]")
        return

    # Show preview table
    table = Table(title=f"[bold]apathy organize[/bold] — {root} (mode={mode})")
    table.add_column("File", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Size", justify="right")
    table.add_column("Destination", style="yellow")

    already = set()
    for f in files[:30]:
        try:
            rel = f.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) > 1 and parts[0] in {*CATEGORIES.keys(), "misc"}:
            continue
        if mode == "by_type":
            cat = _categorize(f)
            dest = f"{cat}/{f.name}"
        elif mode == "by_date":
            from datetime import datetime
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            cat = mtime.strftime("%Y-%m")
            dest = f"{cat}/{f.name}"
        else:
            size = f.stat().st_size
            cat = "large" if size > 1_000_000 else "medium" if size > 100_000 else "small"
            dest = f"{cat}/{f.name}"
        size_str = f"{f.stat().st_size / 1024:.1f} KB"
        table.add_row(str(rel), cat, size_str, dest)
        already.add(str(rel))

    if len(files) > 30:
        table.add_row(f"... +{len(files) - 30} more", "", "", "")

    console.print(table)

    if dry_run:
        console.print("[dim]--dry-run: nenhum arquivo foi movido.[/dim]")
        return

    if not yes:
        confirm = typer.confirm(f"Organizar {len(files)} arquivo(s) em {root}?")
        if not confirm:
            console.print("[dim]Cancelado.[/dim]")
            return

    # Execute via tool
    import asyncio

    from agent_framework.core.permissions import always_allow
    from agent_framework.core.session import Session
    from agent_framework.core.tool import ToolContext
    tool = FileOrganizeTool()
    ctx = ToolContext(
        workdir=root,
        session=Session(),
        permission_gate=always_allow(),
    )
    result = asyncio.run(
        tool.run({"path": str(root), "mode": mode, "dry_run": False}, context=ctx)
    )
    console.print(f"\n[bold green]✓[/bold green] {result}")


@app.command(name="parallel-demo")
def parallel_demo(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("/tmp/apathy-parallel"),
) -> None:
    """Demo: 4 specialized agents building a project simultaneously (no API key needed)."""
    import time

    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    from agent_framework.core.persona import Persona
    from agent_framework.interfaces.cli.run_once import run_once

    console = Console()
    ws = workspace.resolve()
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "tests").mkdir(exist_ok=True)

    persona_path = Path("personas/demo.yaml")
    p = Persona.from_yaml(persona_path)

    # 4 independent tasks to run in parallel
    tasks = [
        {
            "id": "backend",
            "label": "Backend Agent",
            "icon": "🔧",
            "prompt": (
                f"escreva o arquivo {ws}/backend.py"
                " com conteúdo: api fastapi completa com CRUD"
            ),
            "color": "cyan",
        },
        {
            "id": "frontend",
            "label": "Frontend Agent",
            "icon": "🎨",
            "prompt": f"escreva o arquivo {ws}/index.html com conteúdo: pagina web com dashboard",
            "color": "magenta",
        },
        {
            "id": "infra",
            "label": "Infra Agent",
            "icon": "🐳",
            "prompt": f"escreva o arquivo {ws}/Dockerfile com conteúdo: container python",
            "color": "blue",
        },
        {
            "id": "tests",
            "label": "QA Agent",
            "icon": "✅",
            "prompt": (
                f"escreva o arquivo {ws}/tests/test_backend.py"
                " com conteúdo: testes pytest fastapi"
            ),
            "color": "green",
        },
    ]

    state: dict[str, dict] = {
        t["id"]: {"status": "QUEUED", "start": None, "end": None, "result": ""} for t in tasks
    }

    def make_table() -> Table:
        now = time.time()
        tbl = Table(title="apathy parallel-demo — 4 agentes em paralelo", expand=True)
        tbl.add_column("Agente", style="bold", width=20)
        tbl.add_column("Status", justify="center", width=14)
        tbl.add_column("Duração", justify="right", width=10)
        tbl.add_column("Resultado", no_wrap=False)
        for t in tasks:
            s = state[t["id"]]
            st = s["status"]
            if st == "QUEUED":
                status_str = Text("QUEUED", style="dim")
                dur = "-"
            elif st == "RUNNING":
                status_str = Text("RUNNING ⟳", style="yellow bold")
                dur = f"{now - s['start']:.1f}s" if s["start"] else "-"
            elif st == "DONE":
                status_str = Text("DONE ✓", style="green bold")
                dur = f"{s['end'] - s['start']:.1f}s" if s["start"] and s["end"] else "-"
            else:
                status_str = Text("FAILED ✗", style="red bold")
                dur = "-"
            result_preview = (s["result"] or "")[:80]
            tbl.add_row(
                f"{t['icon']} [{t['color']}]{t['label']}[/{t['color']}]",
                status_str,
                dur,
                result_preview,
            )
        return tbl

    async def run_task(t: dict) -> None:
        state[t["id"]]["status"] = "RUNNING"
        state[t["id"]]["start"] = time.time()
        try:
            # Capture events silently — we track state via the state dict
            events: list[str] = []

            async def hook(ev) -> None:
                from agent_framework.core.agent import ToolResultEvent
                if isinstance(ev, ToolResultEvent):
                    events.append((ev.result or "")[:120])

            await run_once(p, t["prompt"], str(ws), auto_approve=True, event_hook=hook)
            state[t["id"]]["status"] = "DONE"
            state[t["id"]]["result"] = events[-1] if events else "arquivo criado"
        except Exception as exc:
            state[t["id"]]["status"] = "FAILED"
            state[t["id"]]["result"] = str(exc)[:80]
        finally:
            state[t["id"]]["end"] = time.time()

    async def _run_all() -> None:
        start_wall = time.time()
        with Live(make_table(), console=console, refresh_per_second=4) as live:
            # Fire all 4 agents at the same time
            coros = [run_task(t) for t in tasks]
            task_handles = [asyncio.create_task(c) for c in coros]

            while not all(s["status"] in ("DONE", "FAILED") for s in state.values()):
                live.update(make_table())
                await asyncio.sleep(0.25)

            await asyncio.gather(*task_handles, return_exceptions=True)
            live.update(make_table())

        elapsed = time.time() - start_wall
        done = sum(1 for s in state.values() if s["status"] == "DONE")
        done_files = "\n".join(
            f"  [green]✓[/green] {ws}/{t['id']}"
            for t in tasks if state[t["id"]]["status"] == "DONE"
        )
        console.print(
            Panel(
                f"[bold green]{done}/{len(tasks)} agentes concluídos"
                f" em {elapsed:.1f}s[/bold green]\n"
                f"Arquivos gerados em [blue]{ws}[/blue]\n\n"
                + done_files,
                title="✓ Paralelismo real com asyncio.gather",
                border_style="green",
            )
        )
        # Show the tree
        from agent_framework.interfaces.cli.run_once import _show_workspace_tree
        _show_workspace_tree(str(ws), console)

    asyncio.run(_run_all())


@app.command()
def watch(
    path: Annotated[Path, typer.Argument(help="Directory to watch")] = Path("."),
    pattern: Annotated[str, typer.Option("--pattern", "-p", help="File glob pattern")] = "*",
    run_cmd: Annotated[
        str, typer.Option("--run", "-r", help="Shell command to run on each event (use {file})")
    ] = "",
) -> None:
    """Watch a directory for file changes and react in real-time."""
    import time

    from rich.console import Console
    from rich.live import Live
    from rich.table import Table

    from agent_framework.core.watcher import FileWatcher

    console = Console()
    root = path.resolve()

    if not root.exists():
        console.print(f"[red]Directory not found: {root}[/red]")
        raise typer.Exit(1)

    console.print(
        f"[bold cyan]apathy watch[/bold cyan] — "
        f"watching [blue]{root}[/blue] for [yellow]{pattern}[/yellow] changes\n"
        f"[dim]Ctrl+C to stop[/dim]"
    )

    events_log: list[dict] = []

    def make_table() -> Table:
        tbl = Table(title=f"File Events — {root}/{pattern}", expand=True)
        tbl.add_column("Time", style="dim", width=10)
        tbl.add_column("Event", justify="center", width=10)
        tbl.add_column("File", style="cyan")
        tbl.add_column("Action", style="green")

        for ev in events_log[-20:]:
            tbl.add_row(
                ev["time"],
                f"[yellow]{ev['type']}[/yellow]",
                ev["file"],
                ev.get("action", ""),
            )
        if not events_log:
            tbl.add_row("[dim]waiting...[/dim]", "", "", "")
        return tbl

    async def _watch() -> None:
        watcher = FileWatcher(str(root), pattern=pattern, events=["created", "modified", "deleted"])
        with Live(make_table(), console=console, refresh_per_second=2) as live:
            try:
                async for evt in watcher.watch():
                    action = ""
                    if run_cmd and evt.type in ("created", "modified"):
                        cmd = run_cmd.replace("{file}", str(evt.path))
                        import subprocess
                        try:
                            out = subprocess.check_output(
                                cmd, shell=True, text=True, timeout=10,
                                stderr=subprocess.STDOUT
                            )
                            action = out.strip()[:60]
                        except subprocess.CalledProcessError as e:
                            action = f"[red]✗ {e.output.strip()[:60]}[/red]"
                        except subprocess.TimeoutExpired:
                            action = "[red]timeout[/red]"

                    events_log.append({
                        "time": time.strftime("%H:%M:%S"),
                        "type": evt.type,
                        "file": str(Path(evt.path).relative_to(root)),
                        "action": action,
                    })
                    live.update(make_table())
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass

    try:
        asyncio.run(_watch())
    except KeyboardInterrupt:
        console.print("\n[dim]Watcher stopped.[/dim]")


@app.command()
def demo() -> None:
    """Run a scripted offline demo -- proves the full agent loop with NO API key."""
    from agent_framework.interfaces.cli.demo_runner import run_demo

    asyncio.run(run_demo())


@app.command()
def tools() -> None:
    """List all built-in tools and whether they require permission."""
    from rich.console import Console
    from rich.table import Table

    from agent_framework.core.tool import ToolRegistry
    from agent_framework.tools import register_builtin_tools

    registry = ToolRegistry()
    register_builtin_tools(registry)

    table = Table(title="apathy -- built-in tools")
    table.add_column("Tool", style="cyan")
    table.add_column("Permission", justify="center")
    table.add_column("Description")
    for t in registry.all():
        perm = "[yellow]asks[/yellow]" if t.requires_permission else "[green]auto[/green]"
        table.add_row(t.name, perm, t.description.split(".")[0])
    Console().print(table)


@app.command()
def version() -> None:
    """Show the apathy version."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _v

    from rich.console import Console

    try:
        v = _v("apathy")
    except PackageNotFoundError:
        v = "0.1.0 (dev)"
    Console().print(f"[bold]apathy[/bold] {v}")


# ---------------------------------------------------------------------------
# Daemon / runtime commands
# ---------------------------------------------------------------------------


def _load_personas(persona_dir: Path) -> dict:
    """Load all personas from a directory."""
    personas: dict = {}
    if persona_dir.is_dir():
        for yaml_file in sorted(persona_dir.glob("*.yaml")):
            try:
                p = Persona.from_yaml(yaml_file)
                personas[p.name] = p
            except Exception:
                pass
        # Also load from roles/ subdirectory
        roles_dir = persona_dir / "roles"
        if roles_dir.is_dir():
            for yaml_file in sorted(roles_dir.glob("*.yaml")):
                try:
                    p = Persona.from_yaml(yaml_file)
                    personas[p.name] = p
                except Exception:
                    pass
    if not personas:
        demo_path = Path("personas/demo.yaml")
        if demo_path.exists():
            p = Persona.from_yaml(demo_path)
            personas[p.name] = p
    return personas


@app.command()
def serve(
    workflows_dir: Path = typer.Option(
        Path("workflows"),
        "--workflows-dir",
        help="Directory containing workflow YAML files",
    ),
    personas_dir: Path = typer.Option(
        Path("personas"),
        "--personas-dir",
        help="Directory containing persona YAML files",
    ),
    workers: int = typer.Option(4, "--workers", help="Number of parallel agent workers"),
    workdir: Path = typer.Option(Path("."), "--workdir", "-w", help="Base working directory"),
) -> None:
    """Start the apathy daemon -- autonomous agents watching, scheduling and acting."""
    from rich.console import Console

    from agent_framework.core.runtime import AgentRuntime
    from agent_framework.core.tool import ToolRegistry
    from agent_framework.core.workflow import Workflow
    from agent_framework.interfaces.cli.daemon import run_dashboard
    from agent_framework.tools import register_builtin_tools

    console = Console()

    workflows = Workflow.load_dir(workflows_dir)
    if not workflows:
        console.print(f"[yellow]No workflows found in {workflows_dir}[/yellow]")

    personas = _load_personas(personas_dir)
    if not personas:
        console.print("[red]No personas found. Cannot start daemon.[/red]")
        raise typer.Exit(1)

    registry = ToolRegistry()
    register_builtin_tools(registry, task_personas=personas)

    runtime = AgentRuntime(
        workflows=workflows,
        personas=personas,
        base_tools=registry,
        num_workers=workers,
        workdir=str(workdir),
    )

    console.print(
        f"[bold cyan]apathy serve[/bold cyan] -- "
        f"{len(workflows)} workflows, {workers} workers, workdir={workdir}"
    )

    async def _run() -> None:
        await runtime.start()
        await run_dashboard(runtime)

    asyncio.run(_run())


@app.command()
def ps() -> None:
    """Show status of running agents (requires daemon to be running)."""
    from rich.console import Console

    console = Console()
    console.print(
        "[yellow]No daemon state found.[/yellow] "
        "Start the daemon first with: [bold]apathy serve[/bold]"
    )


@app.command(name="trigger")
def trigger_workflow(
    workflow_name: str = typer.Argument(..., help="Name of the workflow to trigger"),
    workdir: Path = typer.Option(Path("."), "--workdir", "-w", help="Base working directory"),
    workflows_dir: Path = typer.Option(
        Path("workflows"), "--workflows-dir", help="Directory containing workflow YAML files"
    ),
    personas_dir: Path = typer.Option(
        Path("personas"), "--personas-dir", help="Directory containing persona YAML files"
    ),
) -> None:
    """Manually trigger a workflow once (runs to completion without the daemon)."""
    from rich.console import Console

    from agent_framework.core.runtime import AgentRuntime
    from agent_framework.core.tool import ToolRegistry
    from agent_framework.core.workflow import Workflow
    from agent_framework.tools import register_builtin_tools

    console = Console()

    workflows = Workflow.load_dir(workflows_dir)
    wf_map = {w.name: w for w in workflows}

    if workflow_name not in wf_map:
        console.print(f"[red]Workflow '{workflow_name}' not found in {workflows_dir}[/red]")
        available = ", ".join(wf_map.keys()) if wf_map else "none"
        console.print(f"Available: {available}")
        raise typer.Exit(1)

    personas = _load_personas(personas_dir)
    if not personas:
        console.print("[red]No personas found.[/red]")
        raise typer.Exit(1)

    registry = ToolRegistry()
    register_builtin_tools(registry, task_personas=personas)

    runtime = AgentRuntime(
        workflows=workflows,
        personas=personas,
        base_tools=registry,
        num_workers=1,
        workdir=str(workdir),
    )

    async def _run() -> None:
        await runtime.start()
        job_id = await runtime.trigger_manual(workflow_name)
        console.print(f"[green]Triggered workflow '{workflow_name}' -- job {job_id}[/green]")
        # Wait for all queued jobs to complete (max 5 min)
        deadline = asyncio.get_event_loop().time() + 300
        while asyncio.get_event_loop().time() < deadline:
            pending = [
                j for j in runtime.jobs.values()
                if j.status.value in ("queued", "running", "waiting_perm")
            ]
            if not pending:
                break
            await asyncio.sleep(0.5)
        await runtime.stop()
        for job in runtime.jobs.values():
            status_color = "green" if job.status.value == "done" else "red"
            console.print(
                f"  [{status_color}]{job.status.value}[/{status_color}] "
                f"{job.step_name}: {job.result or job.error or ''}"
            )

    asyncio.run(_run())


@app.command(name="workflows-list")
def workflows_list(
    workflows_dir: Path = typer.Option(
        Path("workflows"), "--workflows-dir", help="Directory containing workflow YAML files"
    ),
) -> None:
    """List available workflows."""
    from rich.console import Console
    from rich.table import Table

    from agent_framework.core.workflow import Workflow

    console = Console()
    workflows = Workflow.load_dir(workflows_dir)

    if not workflows:
        console.print(f"[yellow]No workflows found in {workflows_dir}[/yellow]")
        return

    table = Table(title=f"Workflows in {workflows_dir}")
    table.add_column("Name", style="cyan")
    table.add_column("Enabled", justify="center")
    table.add_column("Triggers")
    table.add_column("Steps")
    table.add_column("Permission")
    table.add_column("Description")

    for wf in workflows:
        enabled = "[green]yes[/green]" if wf.enabled else "[dim]no[/dim]"
        trigger_names = ", ".join(t.type.value for t in wf.triggers)
        step_names = ", ".join(s.name for s in wf.steps)
        table.add_row(
            wf.name, enabled, trigger_names, step_names, wf.permission.value, wf.description
        )

    console.print(table)


def main() -> None:
    app()
