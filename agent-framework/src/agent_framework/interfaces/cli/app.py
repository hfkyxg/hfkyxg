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
