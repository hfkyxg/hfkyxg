from __future__ import annotations

import asyncio
from typing import Any

from agent_framework.config.settings import settings
from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext


class BashTool:
    name = "bash"
    description = (
        "Execute a shell command in the workspace directory. "
        "Returns combined stdout+stderr. Times out after the configured limit."
    )
    requires_permission = True
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
        },
        "required": ["command"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        command = arguments["command"]
        timeout = min(arguments.get("timeout", settings.max_bash_timeout), settings.max_bash_timeout)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(context.workdir),
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise ToolError(self.name, f"Command timed out after {timeout}s: {command!r}")
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(self.name, f"Failed to run command: {exc}") from exc

        output = stdout.decode(errors="replace").strip()
        rc = proc.returncode or 0
        if rc != 0:
            return f"[exit code {rc}]\n{output}" if output else f"[exit code {rc}]"
        return output or "(no output)"
