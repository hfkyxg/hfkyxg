from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext


class ReadFileTool:
    name = "read_file"
    description = "Read the contents of a file. Returns file text."
    requires_permission = False
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or workspace-relative path to the file",
            },
            "offset": {
                "type": "integer",
                "description": "Start reading from this line number (1-indexed)",
                "default": 1,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read",
                "default": 2000,
            },
        },
        "required": ["path"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        path = Path(arguments["path"])
        if not path.is_absolute():
            path = context.workdir / path
        if not path.exists():
            raise ToolError(self.name, f"File not found: {path}")
        if not path.is_file():
            raise ToolError(self.name, f"Not a file: {path}")
        offset = max(1, arguments.get("offset", 1))
        limit = arguments.get("limit", 2000)
        lines = path.read_text(errors="replace").splitlines()
        selected = lines[offset - 1 : offset - 1 + limit]
        numbered = "\n".join(f"{offset + i}\t{line}" for i, line in enumerate(selected))
        return numbered or "(empty file)"


class WriteFileTool:
    name = "write_file"
    description = "Write text content to a file, creating it if it doesn't exist."
    requires_permission = True
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        path = Path(arguments["path"])
        if not path.is_absolute():
            path = context.workdir / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"])
        return f"Wrote {len(arguments['content'])} characters to {path}"


class EditFileTool:
    name = "edit_file"
    description = (
        "Replace an exact string in a file with new content. "
        "Fails if the old_string is not found or is ambiguous (found more than once)."
    )
    requires_permission = True
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string", "description": "Exact text to replace"},
            "new_string": {"type": "string", "description": "Replacement text"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        path = Path(arguments["path"])
        if not path.is_absolute():
            path = context.workdir / path
        if not path.exists():
            raise ToolError(self.name, f"File not found: {path}")
        content = path.read_text()
        old = arguments["old_string"]
        count = content.count(old)
        if count == 0:
            raise ToolError(self.name, f"old_string not found in {path}")
        if count > 1:
            raise ToolError(
                self.name,
                f"old_string found {count} times in {path}; provide more context to make it unique",
            )
        path.write_text(content.replace(old, arguments["new_string"], 1))
        return f"Edited {path}"


class ListDirTool:
    name = "list_dir"
    description = "List files and directories in a given directory path."
    requires_permission = False
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to list"},
        },
        "required": ["path"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        path = Path(arguments["path"])
        if not path.is_absolute():
            path = context.workdir / path
        if not path.exists():
            raise ToolError(self.name, f"Path not found: {path}")
        if not path.is_dir():
            raise ToolError(self.name, f"Not a directory: {path}")
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        lines = []
        for e in entries:
            suffix = "/" if e.is_dir() else ""
            lines.append(f"{e.name}{suffix}")
        return "\n".join(lines) or "(empty directory)"
