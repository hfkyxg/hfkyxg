from __future__ import annotations

from typing import Any

import httpx

from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext


class WebFetchTool:
    name = "web_fetch"
    description = "Fetch a URL and return its text content (HTML stripped to readable text)."
    requires_permission = False
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_chars": {"type": "integer", "default": 8000},
        },
        "required": ["url"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        url = arguments["url"]
        max_chars = arguments.get("max_chars", 8000)
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "agent-framework/0.1"})
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "html" in content_type:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "header", "footer"]):
                        tag.decompose()
                    text = soup.get_text(separator="\n", strip=True)
                else:
                    text = resp.text
        except httpx.HTTPError as exc:
            raise ToolError(self.name, f"HTTP error fetching {url}: {exc}") from exc
        return text[:max_chars]


class HttpRequestTool:
    name = "http_request"
    description = "Make an HTTP request to any URL with any method, headers, and body."
    requires_permission = True
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "default": "GET",
            },
            "headers": {"type": "object", "description": "Request headers"},
            "body": {"type": "string", "description": "Request body (for POST/PUT/PATCH)"},
        },
        "required": ["url"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        method = arguments.get("method", "GET").upper()
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.request(
                    method,
                    arguments["url"],
                    headers=arguments.get("headers") or {},
                    content=arguments.get("body"),
                )
        except httpx.HTTPError as exc:
            raise ToolError(self.name, f"HTTP error: {exc}") from exc
        return f"[{resp.status_code}]\n{resp.text[:4000]}"
