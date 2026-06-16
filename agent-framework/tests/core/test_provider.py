"""Tests for ModelProvider: message serialization, response parsing, JSON repair."""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent_framework.core.errors import ProviderError
from agent_framework.core.messages import Message, ToolCall, ToolResult
from agent_framework.core.provider import ModelProvider


def make_litellm_resp(
    content: str | None = None,
    finish_reason: str = "stop",
    tool_calls: list | None = None,
) -> MagicMock:
    """Build a minimal litellm-style response object."""
    msg = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
    )
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def make_litellm_tool_call(name: str, arguments: str, call_id: str | None = None) -> SimpleNamespace:
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id or uuid.uuid4().hex, function=fn)


provider = ModelProvider(model="fake/model")


# --- _to_litellm_messages ---

class TestToLitellmMessages:
    def test_simple_user_message(self):
        msgs = [Message(role="user", content="hello")]
        out = provider._to_litellm_messages(msgs)
        assert out == [{"role": "user", "content": "hello"}]

    def test_system_message(self):
        msgs = [Message(role="system", content="you are a bot")]
        out = provider._to_litellm_messages(msgs)
        assert out[0]["role"] == "system"
        assert out[0]["content"] == "you are a bot"

    def test_assistant_with_tool_calls(self):
        tc = ToolCall(id="tc1", name="read_file", arguments={"path": "/tmp/x"})
        msgs = [Message(role="assistant", content=None, tool_calls=[tc])]
        out = provider._to_litellm_messages(msgs)
        assert len(out) == 1
        assert out[0]["role"] == "assistant"
        assert out[0]["tool_calls"][0]["id"] == "tc1"
        assert out[0]["tool_calls"][0]["function"]["name"] == "read_file"
        assert json.loads(out[0]["tool_calls"][0]["function"]["arguments"]) == {"path": "/tmp/x"}

    def test_tool_role_expands_to_individual_results(self):
        results = [
            ToolResult(tool_call_id="a", content="res_a"),
            ToolResult(tool_call_id="b", content="res_b", is_error=True),
        ]
        msgs = [Message(role="tool", tool_results=results)]
        out = provider._to_litellm_messages(msgs)
        assert len(out) == 2
        assert out[0] == {"role": "tool", "tool_call_id": "a", "content": "res_a"}
        assert out[1] == {"role": "tool", "tool_call_id": "b", "content": "res_b"}

    def test_message_with_name_field(self):
        msgs = [Message(role="user", content="hi", name="frank")]
        out = provider._to_litellm_messages(msgs)
        assert out[0]["name"] == "frank"

    def test_none_content_becomes_empty_string_for_plain_messages(self):
        msgs = [Message(role="user", content=None)]
        out = provider._to_litellm_messages(msgs)
        assert out[0]["content"] == ""


# --- _from_litellm_response ---

class TestFromLitellmResponse:
    def test_end_turn(self):
        raw = make_litellm_resp(content="done", finish_reason="stop")
        resp = provider._from_litellm_response(raw)
        assert resp.stop_reason == "end_turn"
        assert resp.message.content == "done"
        assert resp.message.tool_calls == []

    def test_max_tokens(self):
        raw = make_litellm_resp(content="cut", finish_reason="length")
        resp = provider._from_litellm_response(raw)
        assert resp.stop_reason == "max_tokens"

    def test_tool_calls_detected(self):
        ltc = make_litellm_tool_call("bash", '{"command": "echo hi"}', call_id="id1")
        raw = make_litellm_resp(finish_reason="tool_calls", tool_calls=[ltc])
        resp = provider._from_litellm_response(raw)
        assert resp.stop_reason == "tool_calls"
        assert len(resp.message.tool_calls) == 1
        tc = resp.message.tool_calls[0]
        assert tc.id == "id1"
        assert tc.name == "bash"
        assert tc.arguments == {"command": "echo hi"}

    def test_multiple_tool_calls(self):
        ltcs = [
            make_litellm_tool_call("read_file", '{"path": "/a"}'),
            make_litellm_tool_call("list_dir", '{"path": "/b"}'),
        ]
        raw = make_litellm_resp(finish_reason="tool_calls", tool_calls=ltcs)
        resp = provider._from_litellm_response(raw)
        assert len(resp.message.tool_calls) == 2
        assert resp.message.tool_calls[0].name == "read_file"
        assert resp.message.tool_calls[1].name == "list_dir"

    def test_tool_call_with_null_id_gets_generated(self):
        ltc = make_litellm_tool_call("bash", '{"command": "pwd"}', call_id=None)
        raw = make_litellm_resp(finish_reason="tool_calls", tool_calls=[ltc])
        resp = provider._from_litellm_response(raw)
        assert resp.message.tool_calls[0].id  # non-empty generated id


# --- _parse_args ---

class TestParseArgs:
    def test_valid_json(self):
        result = provider._parse_args('{"path": "/tmp/x"}', "read_file")
        assert result == {"path": "/tmp/x"}

    def test_empty_string_returns_empty_dict(self):
        result = provider._parse_args("", "bash")
        assert result == {}

    def test_none_returns_empty_dict(self):
        result = provider._parse_args(None, "bash")
        assert result == {}

    def test_trailing_comma_repair(self):
        result = provider._parse_args('{"cmd": "ls", }', "bash")
        assert result == {"cmd": "ls"}

    def test_nested_trailing_comma(self):
        result = provider._parse_args('{"a": [1, 2,]}', "tool")
        assert result == {"a": [1, 2]}

    def test_json_block_extraction_from_prose(self):
        raw = 'Sure, here are the args: {"path": "/foo"} done.'
        result = provider._parse_args(raw, "read_file")
        assert result == {"path": "/foo"}

    def test_completely_unparseable_raises(self):
        with pytest.raises(ProviderError, match="Could not parse"):
            provider._parse_args("not json at all !!", "tool")
