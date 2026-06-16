from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from agent_framework.core.orchestrator import Orchestrator
    from agent_framework.core.permissions import PermissionGate
    from agent_framework.core.session import Session


@dataclass
class ToolContext:
    workdir: Path
    session: Session
    permission_gate: PermissionGate
    orchestrator: Orchestrator | None = None


ToolSpec = dict[str, Any]  # JSON Schema object for the tool


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]
    requires_permission: bool

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Tool '{name}' not found in registry. Available: {list(self._tools)}")

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def specs(self) -> list[ToolSpec]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in self._tools.values()
        ]

    def filtered(
        self,
        allowed_names: set[str] | None = None,
        denied_names: set[str] | None = None,
    ) -> ToolRegistry:
        new = ToolRegistry()
        for tool in self._tools.values():
            if denied_names and tool.name in denied_names:
                continue
            if allowed_names is not None and tool.name not in allowed_names:
                continue
            new.register(tool)
        return new
