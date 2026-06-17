from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent_framework.core.orchestrator import Orchestrator
from agent_framework.core.permissions import PermissionGate
from agent_framework.core.persona import Persona
from agent_framework.core.project import ProjectCrew, TaskNode
from agent_framework.core.tool import ToolRegistry
from agent_framework.interfaces.cli.banner import print_banner
from agent_framework.tools import register_builtin_tools

console = Console()

_DEFAULT_ROLES = ["planner", "backend", "frontend", "infra", "reviewer", "integrator", "default"]


def _load_personas(personas_dir: Path) -> dict[str, Persona]:
    personas: dict[str, Persona] = {}
    roles_dir = personas_dir / "roles"
    search_dirs = [roles_dir, personas_dir] if roles_dir.exists() else [personas_dir]

    for d in search_dirs:
        for yaml_file in sorted(d.glob("*.yaml")):
            try:
                p = Persona.from_yaml(yaml_file)
                personas[p.name] = p
            except Exception:
                pass

    return personas


def _progress(node: TaskNode | None, event: str) -> None:
    if node is None:
        console.print(f"[dim]{event}[/dim]")
        return
    status_style = {
        "started": "cyan",
        "done": "green",
    }
    color = "yellow"
    for key, s in status_style.items():
        if key in event:
            color = s
            break
    if "failed" in event:
        color = "red"
    if "revision" in event:
        color = "yellow"
    console.print(f"  [{color}]{event:20}[/{color}] [{node.role}] {node.id}")


async def run_build(
    objective: str,
    workspace: Path,
    personas_dir: Path,
    *,
    dry_run: bool = False,
) -> None:
    print_banner(console, subtitle="build — team of agents working in parallel")
    console.print(
        Panel(
            f"[bold white]{objective}[/bold white]",
            title="[bold green]objetivo[/bold green]",
            border_style="green",
        )
    )

    personas = _load_personas(personas_dir)
    if not personas:
        console.print("[red]No personas found. Make sure personas/roles/ directory exists.[/red]")
        raise SystemExit(1)

    console.print(f"  Personas loaded: [cyan]{', '.join(personas)}[/cyan]")
    console.print(f"  Workspace: [dim]{workspace}[/dim]\n")

    registry = ToolRegistry()
    register_builtin_tools(registry)
    gate = PermissionGate(autopilot=True, workspace_root=str(workspace))
    orchestrator = Orchestrator(
        base_tools=registry, base_permission_gate=gate, workdir=str(workspace)
    )

    crew = ProjectCrew(
        orchestrator=orchestrator,
        personas=personas,
        workspace=workspace,
        progress_callback=_progress,
    )

    # Planning phase
    console.print("[bold]Planning...[/bold]")
    try:
        graph = await crew.plan(objective)
    except Exception as exc:
        console.print(f"[red]Planning failed: {exc}[/red]")
        raise SystemExit(1)

    # Show plan
    table = Table(title="Task Plan", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("Role", style="magenta")
    table.add_column("Description")
    table.add_column("Depends on", style="dim")
    for node in graph.nodes:
        table.add_row(
            node.id,
            node.role,
            node.description,
            ", ".join(node.depends_on) or "—",
        )
    console.print(table)

    if dry_run:
        console.print("\n[dim]--dry-run: stopping after planning.[/dim]")
        return

    # Execution phase
    console.print("\n[bold]Executing...[/bold]")
    try:
        result = await crew.execute(graph)
    except Exception as exc:
        console.print(f"[red]Execution error: {exc}[/red]")
        raise SystemExit(1)

    # Final summary
    status = "[green]SUCCESS[/green]" if result.success else "[yellow]PARTIAL[/yellow]"
    console.print(
        Panel(
            result.summary,
            title=f"[bold]Build complete — {status}[/bold]",
            border_style="green" if result.success else "yellow",
        )
    )
    console.print(f"\n  Workspace: [bold]{result.workspace}[/bold]")
