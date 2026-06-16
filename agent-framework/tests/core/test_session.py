"""Tests for Session: creation, message append, transcript export."""
from __future__ import annotations

import json

from agent_framework.core.messages import Message
from agent_framework.core.session import Session


def test_default_session_is_empty():
    s = Session()
    assert s.messages == []
    assert s.session_id  # non-empty generated id


def test_session_ids_are_unique():
    ids = {Session().session_id for _ in range(20)}
    assert len(ids) == 20


def test_with_system_prompt_seeds_first_message():
    s = Session.with_system_prompt("You are a bot.")
    assert len(s.messages) == 1
    assert s.messages[0].role == "system"
    assert s.messages[0].content == "You are a bot."


def test_append_adds_message():
    s = Session()
    s.append(Message(role="user", content="hello"))
    assert len(s.messages) == 1
    assert s.messages[0].content == "hello"


def test_to_transcript_json_is_valid_json():
    s = Session.with_system_prompt("sys")
    s.append(Message(role="user", content="hi"))
    text = s.to_transcript_json()
    data = json.loads(text)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["role"] == "system"
    assert data[1]["role"] == "user"


def test_to_transcript_json_round_trips_content():
    s = Session()
    s.append(Message(role="user", content="what is 2+2?"))
    s.append(Message(role="assistant", content="4"))
    data = json.loads(s.to_transcript_json())
    assert data[1]["content"] == "4"
