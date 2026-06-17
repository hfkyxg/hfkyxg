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


def main() -> None:
    app()
