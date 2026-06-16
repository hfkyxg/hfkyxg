class AgentError(Exception): ...


class ToolError(AgentError):
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"[{tool_name}] {message}")


class PermissionDenied(AgentError):
    def __init__(self, tool_name: str):
        super().__init__(f"Permission denied for tool: {tool_name}")


class ProviderError(AgentError): ...


class PlanningError(AgentError): ...
