from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum

from agent_framework.core.tool import Tool


class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


AskCallback = Callable[[Tool, dict], Awaitable[bool]]


@dataclass
class PermissionRule:
    tool_name: str  # exact tool name, or "*" for default
    decision: PermissionDecision
    argument_predicate: Callable[[dict], bool] | None = None


class PermissionGate:
    def __init__(
        self,
        rules: list[PermissionRule] | None = None,
        *,
        ask_callback: AskCallback | None = None,
        autopilot: bool = False,
        workspace_root: str | None = None,
    ) -> None:
        self._rules = rules or []
        self._ask_callback = ask_callback
        self._autopilot = autopilot
        self._workspace_root = workspace_root

    async def check(self, tool: Tool, arguments: dict) -> PermissionDecision:
        # Autopilot mode (project/crew execution): allow anything inside workspace
        if self._autopilot:
            return PermissionDecision.ALLOW

        # Check explicit rules (most specific first, then wildcard)
        for rule in self._rules:
            if rule.tool_name not in (tool.name, "*"):
                continue
            if rule.argument_predicate and not rule.argument_predicate(arguments):
                continue
            if rule.decision == PermissionDecision.ASK:
                return await self._ask(tool, arguments)
            return rule.decision

        # Default policy: read-only tools (requires_permission=False) auto-allow,
        # everything else asks
        if not tool.requires_permission:
            return PermissionDecision.ALLOW
        return await self._ask(tool, arguments)

    async def _ask(self, tool: Tool, arguments: dict) -> PermissionDecision:
        if self._ask_callback is None:
            return PermissionDecision.DENY
        allowed = await self._ask_callback(tool, arguments)
        return PermissionDecision.ALLOW if allowed else PermissionDecision.DENY


def always_allow() -> PermissionGate:
    """Convenience gate for tests and non-interactive contexts that need to skip all gates."""
    gate = PermissionGate(autopilot=True)
    return gate


def workspace_gate(
    workspace_root: str,
    ask_callback: AskCallback | None = None,
) -> PermissionGate:
    """Auto-allow all tool calls whose path argument stays inside *workspace_root*.

    Any path-using tool call that escapes the workspace sandbox still asks the user.
    Non-path tools (e.g. bash) are auto-allowed inside daemon/project execution.
    """

    workspace_abs = os.path.realpath(os.path.expanduser(workspace_root))

    def _inside_workspace(arguments: dict) -> bool:
        for v in arguments.values():
            if not isinstance(v, str):
                continue
            # Only check values that look like paths
            if "/" not in v and "\\" not in v:
                continue
            real = os.path.realpath(os.path.expanduser(v))
            if not real.startswith(workspace_abs):
                return False
        return True

    rules = [
        PermissionRule(
            tool_name="*",
            decision=PermissionDecision.ALLOW,
            argument_predicate=_inside_workspace,
        ),
        PermissionRule(
            tool_name="*",
            decision=PermissionDecision.ASK,
        ),
    ]
    return PermissionGate(rules=rules, ask_callback=ask_callback)
