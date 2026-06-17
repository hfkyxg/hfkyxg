"""Web search tool — DuckDuckGo (free/no key) + Google Custom Search + Brave + Serper."""
from __future__ import annotations

import urllib.parse
from typing import Any

import httpx

from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext


class WebSearchTool:
    name = "web_search"
    description = (
        "Search the web and return a list of results with titles, URLs, and snippets. "
        "Uses DuckDuckGo by default (no API key needed); auto-upgrades to Google, Brave, "
        "or Serper when the corresponding API key is set."
    )
    requires_permission = False
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "num_results": {
                "type": "integer",
                "default": 8,
                "description": "Number of results to return (max 20)",
            },
            "backend": {
                "type": "string",
                "enum": ["auto", "duckduckgo", "google", "brave", "serper"],
                "default": "auto",
                "description": "Search backend to use (auto picks the best available)",
            },
        },
        "required": ["query"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        query = arguments["query"]
        num_results = min(int(arguments.get("num_results", 8)), 20)
        backend = arguments.get("backend", "auto")

        if backend == "auto":
            backend = self._best_backend()

        try:
            if backend == "google":
                results = await self._google_search(query, num_results)
            elif backend == "brave":
                results = await self._brave_search(query, num_results)
            elif backend == "serper":
                results = await self._serper_search(query, num_results)
            else:
                results = await self._duckduckgo_search(query, num_results)
        except httpx.HTTPError as exc:
            raise ToolError(self.name, f"Search request failed: {exc}") from exc

        if not results:
            return f"No results found for: {query!r}"

        lines = [f"Search results for: {query!r}  [backend={backend}]\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   {r['url']}")
            if r.get("snippet"):
                lines.append(f"   {r['snippet']}")
            lines.append("")
        return "\n".join(lines).strip()

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------

    def _best_backend(self) -> str:
        try:
            from agent_framework.config.settings import settings

            if settings.google_api_key and settings.google_cse_id:
                return "google"
            if settings.serper_api_key:
                return "serper"
            if settings.brave_api_key:
                return "brave"
        except Exception:
            pass
        return "duckduckgo"

    # ------------------------------------------------------------------
    # DuckDuckGo (HTML scraping — always free, no key needed)
    # ------------------------------------------------------------------

    async def _duckduckgo_search(
        self, query: str, num_results: int
    ) -> list[dict[str, str]]:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            resp.raise_for_status()

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[dict[str, str]] = []
        for item in soup.select(".result__body")[:num_results]:
            title_el = item.select_one(".result__title a")
            snippet_el = item.select_one(".result__snippet")
            if title_el is None:
                continue
            href = title_el.get("href", "")
            # DDG wraps URLs in a redirect; extract the real URL from query param
            if href.startswith("/"):
                parsed = urllib.parse.urlparse("https://duckduckgo.com" + href)
                qs = urllib.parse.parse_qs(parsed.query)
                href = qs.get("uddg", qs.get("u", [href]))[0]
            results.append(
                {
                    "title": title_el.get_text(strip=True),
                    "url": href,
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                }
            )
        return results

    # ------------------------------------------------------------------
    # Google Custom Search API
    # ------------------------------------------------------------------

    async def _google_search(self, query: str, num_results: int) -> list[dict[str, str]]:
        from agent_framework.config.settings import settings

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.google_api_key,
            "cx": settings.google_cse_id,
            "q": query,
            "num": min(num_results, 10),
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in data.get("items", [])
        ]

    # ------------------------------------------------------------------
    # Brave Search API
    # ------------------------------------------------------------------

    async def _brave_search(self, query: str, num_results: int) -> list[dict[str, str]]:
        from agent_framework.config.settings import settings

        url = "https://api.search.brave.com/res/v1/web/search"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                params={"q": query, "count": num_results},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": settings.brave_api_key,
                },
            )
            resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            }
            for item in data.get("web", {}).get("results", [])[:num_results]
        ]

    # ------------------------------------------------------------------
    # Serper.dev (Google Search proxy)
    # ------------------------------------------------------------------

    async def _serper_search(self, query: str, num_results: int) -> list[dict[str, str]]:
        from agent_framework.config.settings import settings

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": num_results},
                headers={
                    "X-API-KEY": settings.serper_api_key,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        data = resp.json()
        results: list[dict[str, str]] = []
        for item in data.get("organic", [])[:num_results]:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                }
            )
        return results
