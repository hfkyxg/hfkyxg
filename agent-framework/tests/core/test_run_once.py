"""Tests for the single-shot `apathy run` execution and content extraction."""
from __future__ import annotations

import pytest

from agent_framework.core.mock_provider import MockProvider
from agent_framework.core.persona import Persona
from agent_framework.interfaces.cli.run_once import run_once


def demo_persona() -> Persona:
    return Persona(
        name="demo",
        system_prompt="demo",
        provider="mock/demo",
        enabled_tools=["read_file", "write_file", "list_dir", "bash", "grep"],
        max_iterations=6,
    )


def specs(*names: str) -> list[dict]:
    return [
        {"type": "function", "function": {"name": n, "description": "", "parameters": {}}}
        for n in names
    ]


class TestContentExtraction:
    @pytest.mark.asyncio
    async def test_write_extracts_content_after_com_conteudo(self):
        p = MockProvider()
        from agent_framework.core.messages import Message

        msgs = [Message(role="user", content="escreva o arquivo a.txt com conteúdo olá mundo")]
        resp = await p.complete(msgs, specs("write_file"))
        args = resp.message.tool_calls[0].arguments
        assert args["content"].strip() == "olá mundo"

    @pytest.mark.asyncio
    async def test_write_falls_back_to_default_content(self):
        p = MockProvider()
        from agent_framework.core.messages import Message

        msgs = [Message(role="user", content="crie o arquivo b.txt")]
        resp = await p.complete(msgs, specs("write_file"))
        args = resp.message.tool_calls[0].arguments
        assert args["content"]  # non-empty default


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_run_once_writes_real_file(self, tmp_path):
        target = tmp_path / "out.txt"
        await run_once(
            demo_persona(),
            f"escreva o arquivo {target} com conteúdo conteudo-real",
            str(tmp_path),
            auto_approve=True,
        )
        assert target.exists()
        assert "conteudo-real" in target.read_text()

    @pytest.mark.asyncio
    async def test_run_once_runs_real_command(self, tmp_path, capsys):
        await run_once(
            demo_persona(),
            "rode: echo apathy-ran-this",
            str(tmp_path),
            auto_approve=True,
        )
        out = capsys.readouterr().out
        assert "apathy-ran-this" in out
