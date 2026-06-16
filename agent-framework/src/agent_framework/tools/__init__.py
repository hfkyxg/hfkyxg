from agent_framework.core.tool import ToolRegistry
from agent_framework.tools.files import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from agent_framework.tools.search import GlobTool, GrepTool
from agent_framework.tools.shell import BashTool
from agent_framework.tools.task import TaskTool
from agent_framework.tools.web import HttpRequestTool, WebFetchTool


def register_builtin_tools(
    registry: ToolRegistry,
    *,
    include: set[str] | None = None,
    task_personas: dict | None = None,
) -> None:
    all_tools = [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        ListDirTool(),
        BashTool(),
        GrepTool(),
        GlobTool(),
        WebFetchTool(),
        HttpRequestTool(),
        TaskTool(personas=task_personas or {}),
    ]
    for tool in all_tools:
        if include is None or tool.name in include:
            registry.register(tool)
