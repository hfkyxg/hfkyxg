"""ASCII banner — the apathy mask (inspired by Noro's crosshair-eye mask)."""
from __future__ import annotations

from rich.console import Console

# A pale stitched mask with a crosshair over one eye.
_MASK = r"""
        .-=========-.
      .'   _______   '.
     /   .'       '.   \
    |   /   .---.   \   |
    |  |   / \|/ \   |  |
    |  |   --(+)--   |  |
    |  |   \ /|\ /   |  |
    |   \   '---'   /   |
     \   '._____.'   _ /
      '.   \|/|/   .'
        '-._____.-'
       \\| | | | |//
        `^^^^^^^^^`
"""

_WORDMARK = "[bold white]apathy[/bold white] [dim]- autonomous agent framework[/dim]"


def print_banner(console: Console, subtitle: str | None = None) -> None:
    console.print(f"[bright_cyan]{_MASK}[/bright_cyan]")
    console.print(f"  {_WORDMARK}")
    if subtitle:
        console.print(f"  [dim]{subtitle}[/dim]")
    console.print()
