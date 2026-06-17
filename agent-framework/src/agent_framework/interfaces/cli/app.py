from __future__ import annotations

import asyncio
from pathlib import Path

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
