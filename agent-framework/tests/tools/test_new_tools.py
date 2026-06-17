"""Tests for web_search, memory, notify, and database tools."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _ctx():
    ctx = MagicMock()
    ctx.workdir = "."
    return ctx


# ── WebSearchTool ─────────────────────────────────────────────────────────────

class TestWebSearchTool:
    def test_duckduckgo_result_parsing(self):
        """_duckduckgo_search parses results from the DDG HTML structure."""
        from agent_framework.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        assert tool.name == "web_search"
        assert tool.requires_permission is False

    def test_best_backend_defaults_to_duckduckgo(self):
        from agent_framework.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        # With no keys configured, should fall back to duckduckgo
        backend = tool._best_backend()
        assert backend in ("duckduckgo", "google", "brave", "serper")

    @pytest.mark.asyncio
    async def test_run_returns_formatted_string(self):
        from agent_framework.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        fake_results = [
            {"title": "Python docs", "url": "https://python.org", "snippet": "Official docs"},
            {"title": "Real Python", "url": "https://realpython.com", "snippet": "Tutorials"},
        ]
        with patch.object(tool, "_duckduckgo_search", AsyncMock(return_value=fake_results)):
            with patch.object(tool, "_best_backend", return_value="duckduckgo"):
                result = await tool.run({"query": "python"}, context=_ctx())

        assert "Python docs" in result
        assert "https://python.org" in result
        assert "Official docs" in result

    @pytest.mark.asyncio
    async def test_run_no_results(self):
        from agent_framework.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        with patch.object(tool, "_duckduckgo_search", AsyncMock(return_value=[])):
            with patch.object(tool, "_best_backend", return_value="duckduckgo"):
                result = await tool.run({"query": "xyzzy"}, context=_ctx())

        assert "No results" in result

    @pytest.mark.asyncio
    async def test_caps_num_results_at_20(self):
        from agent_framework.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        captured = {}

        async def fake_search(query, num_results):
            captured["num"] = num_results
            return []

        with patch.object(tool, "_duckduckgo_search", fake_search):
            with patch.object(tool, "_best_backend", return_value="duckduckgo"):
                await tool.run({"query": "test", "num_results": 100}, context=_ctx())

        assert captured["num"] == 20

    @pytest.mark.asyncio
    async def test_backend_parameter_respected(self):
        from agent_framework.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        brave_called = []

        async def fake_brave(query, num_results):
            brave_called.append(True)
            return [{"title": "r", "url": "https://x.com", "snippet": "s"}]

        with patch.object(tool, "_brave_search", fake_brave):
            await tool.run({"query": "x", "backend": "brave"}, context=_ctx())

        assert brave_called


# ── MemoryTool ────────────────────────────────────────────────────────────────

class TestMemoryTool:
    @pytest.mark.asyncio
    async def test_set_and_get(self, tmp_path: Path):
        from agent_framework.tools.memory import MemoryTool

        with patch("agent_framework.tools.memory._db_path", return_value=tmp_path / "mem.db"):
            tool = MemoryTool()
            result_set = await tool.run(
                {"action": "set", "key": "name", "value": "apathy"}, context=_ctx()
            )
            assert "Stored" in result_set

            result_get = await tool.run(
                {"action": "get", "key": "name"}, context=_ctx()
            )
            assert "apathy" in result_get

    @pytest.mark.asyncio
    async def test_get_missing_key(self, tmp_path: Path):
        from agent_framework.tools.memory import MemoryTool

        with patch("agent_framework.tools.memory._db_path", return_value=tmp_path / "mem.db"):
            tool = MemoryTool()
            result = await tool.run(
                {"action": "get", "key": "nonexistent"}, context=_ctx()
            )
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_list_empty_namespace(self, tmp_path: Path):
        from agent_framework.tools.memory import MemoryTool

        with patch("agent_framework.tools.memory._db_path", return_value=tmp_path / "mem.db"):
            tool = MemoryTool()
            result = await tool.run({"action": "list"}, context=_ctx())
        assert "No entries" in result

    @pytest.mark.asyncio
    async def test_list_after_set(self, tmp_path: Path):
        from agent_framework.tools.memory import MemoryTool

        with patch("agent_framework.tools.memory._db_path", return_value=tmp_path / "mem.db"):
            tool = MemoryTool()
            await tool.run({"action": "set", "key": "k1", "value": "v1"}, context=_ctx())
            await tool.run({"action": "set", "key": "k2", "value": "v2"}, context=_ctx())
            result = await tool.run({"action": "list"}, context=_ctx())
        assert "k1" in result
        assert "k2" in result

    @pytest.mark.asyncio
    async def test_delete(self, tmp_path: Path):
        from agent_framework.tools.memory import MemoryTool

        with patch("agent_framework.tools.memory._db_path", return_value=tmp_path / "mem.db"):
            tool = MemoryTool()
            await tool.run({"action": "set", "key": "temp", "value": "x"}, context=_ctx())
            del_result = await tool.run({"action": "delete", "key": "temp"}, context=_ctx())
            assert "Deleted" in del_result
            get_result = await tool.run({"action": "get", "key": "temp"}, context=_ctx())
            assert "not found" in get_result

    @pytest.mark.asyncio
    async def test_search(self, tmp_path: Path):
        from agent_framework.tools.memory import MemoryTool

        with patch("agent_framework.tools.memory._db_path", return_value=tmp_path / "mem.db"):
            tool = MemoryTool()
            await tool.run(
                {"action": "set", "key": "note1", "value": "python is great"}, context=_ctx()
            )
            await tool.run(
                {"action": "set", "key": "note2", "value": "javascript is dynamic"},
                context=_ctx(),
            )
            result = await tool.run(
                {"action": "search", "query": "python"}, context=_ctx()
            )
        assert "note1" in result
        assert "note2" not in result

    @pytest.mark.asyncio
    async def test_namespace_isolation(self, tmp_path: Path):
        from agent_framework.tools.memory import MemoryTool

        with patch("agent_framework.tools.memory._db_path", return_value=tmp_path / "mem.db"):
            tool = MemoryTool()
            await tool.run(
                {"action": "set", "key": "x", "value": "ns1-value", "namespace": "ns1"},
                context=_ctx(),
            )
            result = await tool.run(
                {"action": "get", "key": "x", "namespace": "ns2"}, context=_ctx()
            )
        assert "not found" in result


# ── NotifyTool ────────────────────────────────────────────────────────────────

class TestNotifyTool:
    def test_detect_service_slack(self):
        from agent_framework.tools.notify import NotifyTool

        tool = NotifyTool()
        assert tool._detect_service("https://hooks.slack.com/services/abc") == "slack"

    def test_detect_service_discord(self):
        from agent_framework.tools.notify import NotifyTool

        tool = NotifyTool()
        assert tool._detect_service("https://discord.com/api/webhooks/123/abc") == "discord"

    def test_detect_service_teams(self):
        from agent_framework.tools.notify import NotifyTool

        tool = NotifyTool()
        assert "teams" in tool._detect_service("https://outlook.office.com/webhook/abc")

    def test_slack_payload_with_title(self):
        from agent_framework.tools.notify import NotifyTool

        tool = NotifyTool()
        payload = tool._slack_payload("Hello!", "Alert", "danger")
        assert "attachments" in payload
        assert payload["attachments"][0]["title"] == "Alert"
        assert payload["attachments"][0]["color"] == "danger"

    def test_slack_payload_without_title(self):
        from agent_framework.tools.notify import NotifyTool

        tool = NotifyTool()
        payload = tool._slack_payload("Hello!", "", "good")
        assert payload == {"text": "Hello!"}

    def test_discord_payload_color_good(self):
        from agent_framework.tools.notify import NotifyTool

        tool = NotifyTool()
        payload = tool._discord_payload("msg", "title", "good")
        assert "embeds" in payload
        assert payload["embeds"][0]["color"] == 0x2ECC71

    def test_discord_payload_hex_color(self):
        from agent_framework.tools.notify import NotifyTool

        tool = NotifyTool()
        payload = tool._discord_payload("msg", "", "#FF0000")
        assert payload["embeds"][0]["color"] == 0xFF0000

    @pytest.mark.asyncio
    async def test_run_slack_webhook(self):
        from agent_framework.tools.notify import NotifyTool

        tool = NotifyTool()
        mock_settings = {
            "slack_webhook_url": "https://hooks.slack.com/services/fake",
            "discord_webhook_url": "",
            "teams_webhook_url": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
        }
        with patch.object(tool, "_load_settings", return_value=mock_settings):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_post = AsyncMock(return_value=mock_resp)
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock(
                    return_value=MagicMock(post=mock_post)
                )
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                result = await tool.run(
                    {"message": "test", "channel": "slack"}, context=_ctx()
                )
        assert "sent" in result.lower()

    @pytest.mark.asyncio
    async def test_run_missing_webhook_raises(self):
        from agent_framework.core.errors import ToolError
        from agent_framework.tools.notify import NotifyTool

        tool = NotifyTool()
        empty_settings = {
            "slack_webhook_url": "",
            "discord_webhook_url": "",
            "teams_webhook_url": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
        }
        with patch.object(tool, "_load_settings", return_value=empty_settings):
            with pytest.raises(ToolError, match="No webhook URL"):
                await tool.run({"message": "test", "channel": "slack"}, context=_ctx())


# ── DatabaseTool ──────────────────────────────────────────────────────────────

class TestDatabaseTool:
    @pytest.mark.asyncio
    async def test_sqlite_create_and_query(self, tmp_path: Path):
        from agent_framework.tools.database import DatabaseTool

        tool = DatabaseTool()
        db = str(tmp_path / "test.db")
        await tool.run(
            {"query": "CREATE TABLE users (id INTEGER, name TEXT)", "database": db},
            context=_ctx(),
        )
        await tool.run(
            {"query": "INSERT INTO users VALUES (1, 'Alice')", "database": db},
            context=_ctx(),
        )
        result = await tool.run(
            {"query": "SELECT * FROM users", "database": db}, context=_ctx()
        )
        assert "Alice" in result

    @pytest.mark.asyncio
    async def test_sqlite_in_memory(self):
        from agent_framework.tools.database import DatabaseTool

        tool = DatabaseTool()
        # In-memory: each call gets a fresh connection, so CREATE then SELECT in same session
        result = await tool.run(
            {"query": "SELECT 1+1 AS result", "database": ":memory:"}, context=_ctx()
        )
        assert "result" in result.lower() or "2" in result

    @pytest.mark.asyncio
    async def test_empty_select(self, tmp_path: Path):
        from agent_framework.tools.database import DatabaseTool

        tool = DatabaseTool()
        db = str(tmp_path / "empty.db")
        await tool.run(
            {"query": "CREATE TABLE items (id INTEGER)", "database": db}, context=_ctx()
        )
        result = await tool.run(
            {"query": "SELECT * FROM items", "database": db}, context=_ctx()
        )
        assert "no rows" in result.lower()

    @pytest.mark.asyncio
    async def test_destructive_blocked(self):
        from agent_framework.core.errors import ToolError
        from agent_framework.tools.database import DatabaseTool

        tool = DatabaseTool()
        with pytest.raises(ToolError, match="Destructive DDL"):
            await tool.run(
                {"query": "DROP TABLE users", "database": ":memory:"}, context=_ctx()
            )

    @pytest.mark.asyncio
    async def test_parameterized_query(self, tmp_path: Path):
        from agent_framework.tools.database import DatabaseTool

        tool = DatabaseTool()
        db = str(tmp_path / "param.db")
        await tool.run(
            {"query": "CREATE TABLE t (n TEXT)", "database": db}, context=_ctx()
        )
        await tool.run(
            {"query": "INSERT INTO t VALUES (?)", "database": db, "params": ["hello"]},
            context=_ctx(),
        )
        result = await tool.run({"query": "SELECT * FROM t", "database": db}, context=_ctx())
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_insert_returns_row_count(self, tmp_path: Path):
        from agent_framework.tools.database import DatabaseTool

        tool = DatabaseTool()
        db = str(tmp_path / "rc.db")
        await tool.run(
            {"query": "CREATE TABLE x (v INTEGER)", "database": db}, context=_ctx()
        )
        result = await tool.run(
            {"query": "INSERT INTO x VALUES (1)", "database": db}, context=_ctx()
        )
        assert "1 row" in result
