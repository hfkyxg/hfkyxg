from __future__ import annotations

from typing import Any

from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext


class TaskTool:
    """Delegates a subtask to a specialized subagent and returns its result."""

    name = "task"
    description = (
        "Delegate a subtask to a specialized subagent that runs in an isolated context. "
        "The subagent has its own tool set and returns a single result string. "
        "Use this to parallelize work or to call a specialist agent."
    )
    requires_permission = False
    input_schema = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The task description / instructions for the subagent.",
            },
            "persona": {
                "type": "string",
                "description": "Persona name to use (must match a loaded persona key).",
                "default": "default",
            },
            "allowed_tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tool names the subagent may use. Omit to inherit all.",
            },
        },
        "required": ["prompt"],
    }

    def __init__(self, personas: dict | None = None) -> None:
        self._personas = personas or {}

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        if context.orchestrator is None:
            raise ToolError(self.name, "No orchestrator available — cannot spawn subagent.")

        persona_key = arguments.get("persona", "default")
        persona = self._personas.get(persona_key)
        if persona is None:
            available = list(self._personas)
            raise ToolError(
                self.name,
                f"Persona '{persona_key}' not found. Available: {available}",
            )

        allowed: set[str] | None = None
        if raw := arguments.get("allowed_tools"):
            allowed = set(raw)

        return await context.orchestrator.spawn_subagent(
            task_prompt=arguments["prompt"],
            persona=persona,
            allowed_tools=allowed,
        )
