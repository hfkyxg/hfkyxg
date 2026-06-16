"""Tests for PermissionGate: all decision paths, rules, predicates, callbacks."""
from __future__ import annotations

import pytest

from agent_framework.core.permissions import (
    PermissionDecision,
    PermissionGate,
    PermissionRule,
    always_allow,
)
from agent_framework.tools.files import ListDirTool, ReadFileTool, WriteFileTool
from agent_framework.tools.shell import BashTool

# Convenience aliases for cleaner tests
ALLOW = PermissionDecision.ALLOW
DENY = PermissionDecision.DENY
ASK = PermissionDecision.ASK


async def yes_callback(tool, args) -> bool:
    return True


async def no_callback(tool, args) -> bool:
    return False


class TestAutopilotMode:
    @pytest.mark.asyncio
    async def test_autopilot_allows_everything(self):
        gate = PermissionGate(autopilot=True)
        assert await gate.check(WriteFileTool(), {"path": "/etc/passwd"}) == ALLOW
        assert await gate.check(BashTool(), {"command": "rm -rf /"}) == ALLOW

    @pytest.mark.asyncio
    async def test_always_allow_convenience(self):
        gate = always_allow()
        assert await gate.check(WriteFileTool(), {}) == ALLOW


class TestDefaultPolicy:
    """No rules set. Default: read-only tools auto-allow, mutating tools ask (→deny without callback)."""

    @pytest.mark.asyncio
    async def test_read_only_tool_auto_allowed(self):
        gate = PermissionGate()
        # ReadFileTool.requires_permission = False
        assert await gate.check(ReadFileTool(), {"path": "/tmp/x"}) == ALLOW

    @pytest.mark.asyncio
    async def test_list_dir_auto_allowed(self):
        gate = PermissionGate()
        assert await gate.check(ListDirTool(), {"path": "."}) == ALLOW

    @pytest.mark.asyncio
    async def test_mutating_tool_denied_without_callback(self):
        gate = PermissionGate()
        # WriteFileTool.requires_permission = True, no ask_callback → deny
        assert await gate.check(WriteFileTool(), {"path": "/tmp/x", "content": "hi"}) == DENY

    @pytest.mark.asyncio
    async def test_mutating_tool_allowed_when_callback_returns_true(self):
        gate = PermissionGate(ask_callback=yes_callback)
        assert await gate.check(WriteFileTool(), {"path": "/tmp/x", "content": "hi"}) == ALLOW

    @pytest.mark.asyncio
    async def test_mutating_tool_denied_when_callback_returns_false(self):
        gate = PermissionGate(ask_callback=no_callback)
        assert await gate.check(WriteFileTool(), {}) == DENY


class TestExplicitRules:
    @pytest.mark.asyncio
    async def test_explicit_allow_rule_overrides_default(self):
        rule = PermissionRule(tool_name="write_file", decision=ALLOW)
        gate = PermissionGate(rules=[rule])
        assert await gate.check(WriteFileTool(), {}) == ALLOW

    @pytest.mark.asyncio
    async def test_explicit_deny_rule(self):
        rule = PermissionRule(tool_name="bash", decision=DENY)
        gate = PermissionGate(rules=[rule], ask_callback=yes_callback)
        assert await gate.check(BashTool(), {"command": "pwd"}) == DENY

    @pytest.mark.asyncio
    async def test_wildcard_rule_catches_unmatched_tools(self):
        wildcard = PermissionRule(tool_name="*", decision=ALLOW)
        gate = PermissionGate(rules=[wildcard])
        assert await gate.check(WriteFileTool(), {}) == ALLOW
        assert await gate.check(BashTool(), {}) == ALLOW

    @pytest.mark.asyncio
    async def test_specific_rule_beats_wildcard(self):
        specific = PermissionRule(tool_name="bash", decision=DENY)
        wildcard = PermissionRule(tool_name="*", decision=ALLOW)
        gate = PermissionGate(rules=[specific, wildcard])
        assert await gate.check(BashTool(), {}) == DENY
        assert await gate.check(WriteFileTool(), {}) == ALLOW  # falls through to wildcard

    @pytest.mark.asyncio
    async def test_ask_rule_delegates_to_callback_allow(self):
        rule = PermissionRule(tool_name="bash", decision=ASK)
        gate = PermissionGate(rules=[rule], ask_callback=yes_callback)
        assert await gate.check(BashTool(), {}) == ALLOW

    @pytest.mark.asyncio
    async def test_ask_rule_delegates_to_callback_deny(self):
        rule = PermissionRule(tool_name="bash", decision=ASK)
        gate = PermissionGate(rules=[rule], ask_callback=no_callback)
        assert await gate.check(BashTool(), {}) == DENY


class TestArgumentPredicate:
    @pytest.mark.asyncio
    async def test_predicate_match_applies_rule(self):
        rule = PermissionRule(
            tool_name="bash",
            decision=ALLOW,
            argument_predicate=lambda a: a.get("command", "").startswith("echo"),
        )
        gate = PermissionGate(rules=[rule])
        assert await gate.check(BashTool(), {"command": "echo hi"}) == ALLOW

    @pytest.mark.asyncio
    async def test_predicate_no_match_skips_rule(self):
        rule = PermissionRule(
            tool_name="bash",
            decision=ALLOW,
            argument_predicate=lambda a: a.get("command", "").startswith("echo"),
        )
        gate = PermissionGate(rules=[rule])
        # No match → falls through to default policy (requires_permission=True, no callback → deny)
        assert await gate.check(BashTool(), {"command": "rm -rf /"}) == DENY
