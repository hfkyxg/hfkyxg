"""MockProvider — a scripted, offline LLM provider.

This lets `apathy` run end-to-end (full agent loop: tool calls, permissions,
results, final answer) WITHOUT any API key. It uses simple keyword heuristics
to decide which tool to call based on the user's request, then summarizes the
tool result on the next turn.

It is NOT an LLM. It exists so the framework is runnable and testable out of
the box, for demos, smoke tests and CI.
"""
from __future__ import annotations

import re
import uuid

from agent_framework.core.messages import Message, ToolCall
from agent_framework.core.provider import ModelProvider, ProviderResponse

# Heuristic intent → tool mapping. Each entry: (compiled regex, tool name, arg builder).
_PATH_RE = re.compile(r"([\w./\-]+\.\w+|[\w./\-]+/)")


def _extract_path(text: str, default: str = ".") -> str:
    m = _PATH_RE.search(text)
    return m.group(1) if m else default


class MockProvider(ModelProvider):
    """Deterministic, offline provider driven by keyword heuristics."""

    def __init__(self, model: str = "mock/demo", **kw) -> None:
        super().__init__(model=model, **kw)

    async def complete(self, messages, tools, **kw) -> ProviderResponse:
        available = {
            spec["function"]["name"] for spec in (tools or [])
        }
        last = messages[-1] if messages else None

        # If the previous step produced tool results, summarize them and finish.
        if last is not None and last.role == "tool":
            lines = []
            for tr in last.tool_results:
                tag = "✗ erro" if tr.is_error else "✓ ok"
                snippet = tr.content.strip()
                if len(snippet) > 500:
                    snippet = snippet[:500] + "…"
                lines.append(f"[{tag}] {snippet}")
            body = "\n".join(lines)
            text = f"(mock) Resultado da ferramenta:\n{body}"
            return ProviderResponse(
                message=Message(role="assistant", content=text),
                stop_reason="end_turn",
            )

        # Otherwise look at the most recent user request.
        user_text = ""
        for m in reversed(messages):
            if m.role == "user" and m.content:
                user_text = m.content
                break

        tool_call = self._decide_tool(user_text, available)
        if tool_call is not None:
            return ProviderResponse(
                message=Message(role="assistant", content=None, tool_calls=[tool_call]),
                stop_reason="tool_calls",
            )

        # No tool matched — answer in plain text.
        return ProviderResponse(
            message=Message(
                role="assistant",
                content=(
                    "(mock) Sou o provider de demonstração offline do apathy. "
                    "Peça para eu 'ler <arquivo>', 'listar <dir>', 'rodar <comando>', "
                    "'buscar <termo>' ou 'escrever <arquivo>' para ver o loop de "
                    "ferramentas funcionando sem nenhuma API key."
                ),
            ),
            stop_reason="end_turn",
        )

    def _decide_tool(self, text: str, available: set[str]) -> ToolCall | None:
        lower = text.lower()

        def call(name: str, args: dict) -> ToolCall | None:
            if name not in available:
                return None
            return ToolCall(id=uuid.uuid4().hex, name=name, arguments=args)

        # bash / run command
        if re.search(r"\b(rode|execute|run|bash|shell|comando)\b", lower):
            m = re.search(
                r"(?:rode|execute|run|comando|bash|shell)[:\s]+(.+)$", text, re.IGNORECASE
            )
            cmd = m.group(1).strip().strip("'\"") if m else "echo hello-from-apathy"
            return call("bash", {"command": cmd})

        # write file
        if any(k in lower for k in ("escreva", "crie", "write", "salve")):
            path = _extract_path(text, "apathy-demo.txt")
            return call("write_file", {"path": path, "content": "criado pelo apathy demo\n"})

        # read file
        if any(k in lower for k in ("leia", "read", "mostre o arquivo", "conteúdo de")):
            path = _extract_path(text, "README.md")
            return call("read_file", {"path": path})

        # list dir
        if any(k in lower for k in ("liste", "list", "ls ", "diretório", "directory", "pasta")):
            path = _extract_path(text, ".")
            if "." in path and "/" not in path:  # looks like a file, fall back to cwd
                path = "."
            return call("list_dir", {"path": path})

        # grep / search
        if any(k in lower for k in ("busque", "procure", "search", "grep", "encontre")):
            m = re.search(
                r"(?:busque|procure|search|grep|encontre)[:\s]+(\S+)", text, re.IGNORECASE
            )
            pattern = m.group(1) if m else "TODO"
            return call("grep", {"pattern": pattern, "path": "."})

        # web fetch
        url_m = re.search(r"https?://\S+", text)
        if url_m and ("web" in lower or "fetch" in lower or "busque" in lower or "url" in lower):
            return call("web_fetch", {"url": url_m.group(0)})

        return None
