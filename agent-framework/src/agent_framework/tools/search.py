from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext


class GrepTool:
    name = "grep"
    description = (
        "Search for a regex pattern in files. "
        "Returns matching lines with file paths and line numbers."
    )
    requires_permission = False
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {
                "type": "string",
                "description": "Directory or file to search in",
                "default": ".",
            },
            "glob": {"type": "string", "description": "File pattern filter, e.g. '*.py'"},
            "case_insensitive": {"type": "boolean", "default": False},
        },
        "required": ["pattern"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        search_path = Path(arguments.get("path", "."))
        if not search_path.is_absolute():
            search_path = context.workdir / search_path
        cmd = ["rg", "--no-heading", "--line-number", "--color=never"]
        if arguments.get("case_insensitive"):
            cmd.append("-i")
        if g := arguments.get("glob"):
            cmd += ["--glob", g]
        cmd += [arguments["pattern"], str(search_path)]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode not in (0, 1):
            # rg exits 2 on error, 1 = no matches (not an error)
            raise ToolError(self.name, stderr.decode().strip())
        return stdout.decode().strip() or "(no matches)"


class GlobTool:
    name = "glob"
    description = "Find files matching a glob pattern."
    requires_permission = False
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'"},
            "path": {
                "type": "string",
                "description": "Root directory to search in",
                "default": ".",
            },
        },
        "required": ["pattern"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        root = Path(arguments.get("path", "."))
        if not root.is_absolute():
            root = context.workdir / root
        matches = sorted(root.glob(arguments["pattern"]))
        if not matches:
            return "(no matches)"
        return "\n".join(str(p.relative_to(root)) for p in matches)
