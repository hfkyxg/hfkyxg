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
                # Avoid stacking "(mock) Resultado..." when the result already
                # came from a subagent (which itself produced a mock summary).
                snippet = snippet.replace("(mock) Resultado da ferramenta:", "").strip()
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

        # delegate to a subagent (checked first — the subtask text may itself
        # contain other keywords like "escreva" that we must not match here).
        # Require a real delegation directive — an imperative verb, or a
        # "sub-agent" mention introduced by a delegation preposition — so the
        # bare word "subagente" inside content does not trigger delegation.
        delegation = re.search(r"\b(delegue|delega|delegate)\b", lower) or re.search(
            r"\b(?:ao|à|para|pro|use|usar|usando|com|to|using)\s+"
            r"(?:o\s+|um\s+|a\s+)?sub-?agent(?:e)?\b",
            lower,
        )
        if delegation:
            # The subtask is whatever follows the first colon; e.g.
            # "delegue ao subagente: escreva X" -> subtask "escreva X".
            if ":" in text:
                subtask = text.split(":", 1)[1].strip()
            else:
                subtask = re.sub(
                    r"^.*?\b(?:delegue|delega|subagente|subagent|delegate)\b[\s:]*"
                    r"(?:(?:para|ao|to)\s+(?:o\s+)?(?:subagente|subagent)?\s*)?",
                    "",
                    text,
                    flags=re.IGNORECASE,
                ).strip()
            # Guard against recursive delegation: strip only LEADING delegation
            # keywords (not ones inside the content), so the child does real work.
            subtask = re.sub(
                r"^(?:\b(?:delegue|delega|subagente|subagent|delegate)\b[:\s]*)+",
                "",
                subtask,
                flags=re.IGNORECASE,
            ).strip()
            if not subtask:
                subtask = "liste o diretório ."
            return call("task", {"prompt": subtask, "persona": "demo"})

        # bash / run command
        if re.search(r"\b(rode|execute|run|bash|shell|comando)\b", lower):
            m = re.search(
                r"(?:rode|execute|run|comando|bash|shell)[:\s]+(.+)$", text, re.IGNORECASE
            )
            cmd = m.group(1).strip().strip("'\"") if m else "echo hello-from-apathy"
            return call("bash", {"command": cmd})

        # write file — try to extract explicit content after a separator
        if any(k in lower for k in ("escreva", "crie", "write", "salve")):
            path = _extract_path(text, "apathy-demo.txt")
            content = "criado pelo apathy demo\n"
            cm = re.search(
                r"(?:com\s+conte[uú]do|contendo|content|with\s+content|:)\s+(.+)$",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if cm:
                extracted = cm.group(1).strip().strip("'\"")
                # don't mistake the filename for content
                if extracted and extracted != path:
                    content = extracted + ("\n" if not extracted.endswith("\n") else "")
            return call("write_file", {"path": path, "content": content})

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
