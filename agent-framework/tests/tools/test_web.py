"""Tests for WebFetchTool and HttpRequestTool using httpx mock transport."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_framework.core.errors import ToolError
from agent_framework.core.permissions import always_allow
from agent_framework.core.session import Session
from agent_framework.core.tool import ToolContext
from agent_framework.tools.web import HttpRequestTool, WebFetchTool


def ctx() -> ToolContext:
    return ToolContext(workdir=Path("."), session=Session(), permission_gate=always_allow())


def make_httpx_response(content: str, status_code: int = 200, content_type: str = "text/plain") -> MagicMock:
    resp = MagicMock()
    resp.text = content
    resp.status_code = status_code
    resp.headers = {"content-type": content_type}
    resp.raise_for_status = MagicMock()
    return resp


class TestWebFetchTool:
    @pytest.mark.asyncio
    async def test_fetches_and_returns_text(self):
        mock_resp = make_httpx_response("Hello, world!")
        with patch("agent_framework.tools.web.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await WebFetchTool().run({"url": "http://example.com"}, context=ctx())

        assert "Hello, world!" in result

    @pytest.mark.asyncio
    async def test_strips_html_tags(self):
        html = "<html><body><script>bad</script><p>Good content</p></body></html>"
        mock_resp = make_httpx_response(html, content_type="text/html")
        with patch("agent_framework.tools.web.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await WebFetchTool().run({"url": "http://example.com"}, context=ctx())

        assert "Good content" in result
        assert "<script>" not in result
        assert "<p>" not in result

    @pytest.mark.asyncio
    async def test_truncates_to_max_chars(self):
        long_text = "x" * 10_000
        mock_resp = make_httpx_response(long_text)
        with patch("agent_framework.tools.web.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await WebFetchTool().run(
                {"url": "http://example.com", "max_chars": 100}, context=ctx()
            )

        assert len(result) <= 100

    @pytest.mark.asyncio
    async def test_http_error_raises_tool_error(self):
        import httpx

        with patch("agent_framework.tools.web.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPError("connection refused")
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(ToolError, match="HTTP error"):
                await WebFetchTool().run({"url": "http://bad.invalid"}, context=ctx())


class TestHttpRequestTool:
    @pytest.mark.asyncio
    async def test_get_request_returns_status_and_body(self):
        mock_resp = make_httpx_response('{"ok": true}', status_code=200)
        with patch("agent_framework.tools.web.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await HttpRequestTool().run(
                {"url": "http://api.example.com/data", "method": "GET"},
                context=ctx(),
            )

        assert "[200]" in result
        assert '{"ok": true}' in result

    @pytest.mark.asyncio
    async def test_post_with_body(self):
        mock_resp = make_httpx_response("created", status_code=201)
        captured: dict = {}
        with patch("agent_framework.tools.web.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture_request(method, url, **kwargs):
                captured.update({"method": method, "body": kwargs.get("content")})
                return mock_resp

            mock_client.request = capture_request
            mock_client_cls.return_value = mock_client

            result = await HttpRequestTool().run(
                {"url": "http://api.example.com/items", "method": "POST", "body": '{"name":"test"}'},
                context=ctx(),
            )

        assert captured["method"] == "POST"
        assert captured["body"] == '{"name":"test"}'
        assert "[201]" in result

    @pytest.mark.asyncio
    async def test_http_error_raises_tool_error(self):
        import httpx

        with patch("agent_framework.tools.web.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(side_effect=httpx.HTTPError("timeout"))
            mock_client_cls.return_value = mock_client

            with pytest.raises(ToolError, match="HTTP error"):
                await HttpRequestTool().run({"url": "http://bad.invalid"}, context=ctx())

    @pytest.mark.asyncio
    async def test_custom_headers_passed_through(self):
        mock_resp = make_httpx_response("ok")
        captured: dict = {}
        with patch("agent_framework.tools.web.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture(method, url, **kwargs):
                captured["headers"] = kwargs.get("headers", {})
                return mock_resp

            mock_client.request = capture
            mock_client_cls.return_value = mock_client

            await HttpRequestTool().run(
                {"url": "http://x.com", "headers": {"Authorization": "Bearer token123"}},
                context=ctx(),
            )

        assert captured["headers"].get("Authorization") == "Bearer token123"
