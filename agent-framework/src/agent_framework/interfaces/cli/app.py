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
    """Run a scripted offline demo — proves the full agent loop with NO API key."""
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

    table = Table(title="apathy — built-in tools")
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
    workers: int = typer.Option(4, "--workers", "-w", help="Number of parallel worker agents"),
) -> None:
    """Start the apathy daemon — persistent multi-agent runtime with Rich dashboard."""
    from agent_framework.core.runtime import AgentRuntime
    from agent_framework.interfaces.cli.daemon import run_dashboard

    runtime = AgentRuntime(
        workflows_dir=str(workflows_dir),
        personas_dir=str(personas_dir),
        num_workers=workers,
    )
    asyncio.run(run_dashboard(runtime))


@app.command(name="trigger")
def trigger_workflow(
    workflow_name: str = typer.Argument(..., help="Name of the workflow to trigger"),
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
) -> None:
    """Trigger a workflow once and run it to completion (non-daemon mode)."""
    from rich.console import Console

    from agent_framework.core.runtime import AgentRuntime
    from agent_framework.core.workflow import Workflow

    console = Console()
    wfs = Workflow.load_all(workflows_dir)
    wf = next((w for w in wfs if w.name == workflow_name), None)
    if wf is None:
        console.print(f"[red]Workflow {workflow_name!r} not found in {workflows_dir}[/red]")
        raise typer.Exit(1)

    runtime = AgentRuntime(
        workflows_dir=str(workflows_dir),
        personas_dir=str(personas_dir),
        num_workers=min(4, len(wf.steps)),
    )

    async def _run() -> None:
        await runtime.start()
        job_id = await runtime.trigger_manual(workflow_name)
        console.print(
            f"[green]Triggered[/green] workflow [cyan]{workflow_name}[/cyan] (job {job_id})"
        )
        # Wait until all queued jobs finish (up to timeout)
        for _ in range(wf.timeout_seconds * 2):
            await asyncio.sleep(0.5)
            if runtime.queued_count == 0 and not runtime.active_jobs:
                break
        await runtime.stop()

    asyncio.run(_run())
    done = [j for j in runtime.jobs.values() if j.status.value == "done"]
    failed = [j for j in runtime.jobs.values() if j.status.value == "failed"]
    console.print(f"[bold]Done:[/bold] {len(done)} step(s) completed, {len(failed)} failed")
    if failed:
        for j in failed:
            console.print(f"  [red]FAILED[/red] {j.step_name}: {j.error}")


@app.command(name="workflows-list")
def workflows_list(
    workflows_dir: Path = typer.Option(
        Path("workflows"),
        "--workflows-dir",
        help="Directory containing workflow YAML files",
    ),
) -> None:
    """List all available workflows."""
    from rich.console import Console
    from rich.table import Table

    from agent_framework.core.workflow import Workflow

    console = Console()
    wfs = Workflow.load_all(workflows_dir)
    if not wfs:
        console.print(f"[dim]No workflows found in {workflows_dir}[/dim]")
        return

    table = Table(title="apathy workflows")
    table.add_column("Name", style="cyan")
    table.add_column("Triggers", style="yellow")
    table.add_column("Steps", justify="center")
    table.add_column("Permission")
    table.add_column("Description")
    for wf in wfs:
        trigger_str = ", ".join(
            f"{t.type.value}({t.interval or t.path or ''})" for t in wf.triggers
        )
        table.add_row(
            wf.name,
            trigger_str,
            str(len(wf.steps)),
            wf.permission.value,
            wf.description.strip().splitlines()[0][:60] if wf.description else "",
        )
    console.print(table)


def main() -> None:
    app()
