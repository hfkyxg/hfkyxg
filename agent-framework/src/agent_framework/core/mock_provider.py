"""MockProvider — a scripted, offline LLM provider.

This lets `apathy` run end-to-end (full agent loop: tool calls, permissions,
results, final answer) WITHOUT any API key. It uses simple keyword heuristics
to decide which tool to call based on the user's request, then summarizes the
tool result on the next turn.

It is NOT an LLM. It exists so the framework is runnable and testable out of
the box, for demos, smoke tests and CI.
"""
from __future__ import annotations

import os
import re
import uuid

from agent_framework.core.content_generator import generate_content, make_project_plan
from agent_framework.core.messages import Message, ToolCall
from agent_framework.core.provider import ModelProvider, ProviderResponse

# Heuristic intent → tool mapping. Each entry: (compiled regex, tool name, arg builder).
# Order: absolute paths (with or without extension) > relative paths with ext > dir paths.
_PATH_RE = re.compile(
    r"(/[\w./\-]+)"            # absolute path (handles Dockerfile, Makefile, etc.)
    r"|([\w./\-]+\.\w+)"       # relative path with extension
    r"|([\w./\-]+/)"           # directory path ending in /
)

# Well-known extensionless filenames that should be treated as file paths.
_EXTENSIONLESS = frozenset({
    "Dockerfile", "Makefile", "makefile", "Jenkinsfile",
    ".env", ".gitignore", ".gitattributes", ".dockerignore",
})


def _extract_path(text: str, default: str = ".") -> str:
    # Prefer absolute paths first
    m = _PATH_RE.search(text)
    if m:
        return next(g for g in m.groups() if g is not None)
    # Fallback: check for well-known extensionless filenames in the text
    for token in text.split():
        clean = token.strip("'\",:;")
        if clean in _EXTENSIONLESS or os.path.basename(clean) in _EXTENSIONLESS:
            return clean
    return default


class MockProvider(ModelProvider):
    """Deterministic, offline provider driven by keyword heuristics."""

    def __init__(self, model: str = "mock/demo", **kw) -> None:
        super().__init__(model=model, **kw)
        self._project_plan: list[dict[str, str]] | None = None
        self._plan_step: int = 0
        self._plan_finishing: bool = False  # True when we issued list_dir, waiting for final result

    async def complete(self, messages, tools, **kw) -> ProviderResponse:
        available = {
            spec["function"]["name"] for spec in (tools or [])
        }
        last = messages[-1] if messages else None

        # If the previous step produced tool results:
        if last is not None and last.role == "tool":
            # --- Project mode: advance through the plan ---
            if self._plan_finishing:
                # We just got the list_dir result — emit rich completion summary
                plan = self._project_plan or []
                workspace = plan[0]["path"].rsplit("/", 1)[0] if plan else "/tmp"
                # Detect project type from first file task
                first_task = plan[0]["task"] if plan else ""
                if "fastapi" in first_task or "api" in first_task:
                    startup = "pip install -r requirements.txt\nuvicorn main:app --reload"
                elif "cli" in first_task or "command line" in first_task:
                    startup = "pip install -r requirements.txt\npython main.py --help"
                elif "html" in first_task or "webapp" in first_task or "css" in first_task:
                    startup = "open index.html\n# or: python -m http.server 8080"
                elif "data" in first_task or "analysis" in first_task:
                    startup = "pip install -r requirements.txt\npython analysis.py"
                else:
                    startup = "python main.py"
                file_list = "\n".join(f"  {s['path']}" for s in plan)
                text = (
                    f"(apathy) Projeto criado com sucesso!\n\n"
                    f"Arquivos gerados:\n{file_list}\n\n"
                    f"Para iniciar:\n  cd {workspace}\n  {startup}\n"
                )
                # Reset state
                self._project_plan = None
                self._plan_step = 0
                self._plan_finishing = False
                return ProviderResponse(
                    message=Message(role="assistant", content=text),
                    stop_reason="end_turn",
                )

            if self._project_plan is not None:
                if self._plan_step < len(self._project_plan):
                    # More files to write — return next tool call
                    step = self._project_plan[self._plan_step]
                    content = generate_content(step["path"], step["task"])
                    self._plan_step += 1
                    tc = ToolCall(id=uuid.uuid4().hex, name="write_file",
                                  arguments={"path": step["path"], "content": content})
                    return ProviderResponse(
                        message=Message(role="assistant", content=None, tool_calls=[tc]),
                        stop_reason="tool_calls",
                    )
                else:
                    # All files written — do a list_dir on the workspace root
                    workspace = self._project_plan[0]["path"].rsplit("/", 1)[0]
                    self._plan_finishing = True
                    tc = ToolCall(id=uuid.uuid4().hex, name="list_dir",
                                  arguments={"path": workspace})
                    return ProviderResponse(
                        message=Message(role="assistant", content=None, tool_calls=[tc]),
                        stop_reason="tool_calls",
                    )

            # Not in project mode — summarize and end_turn (original behavior)
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

        # ── project-creation detection (must run before delegation check) ──────
        _PROJECT_TRIGGERS = (
            "projeto completo", "complete project", "crie um projeto",
            "create a project", "build a complete", "crie o projeto",
            "construa um projeto",
        )
        _TYPE_KEYWORDS = {
            "fastapi": "fastapi", "api": "fastapi", "rest": "fastapi",
            "cli": "cli", "tool": "cli",
            "webapp": "webapp", "web": "webapp", "html": "webapp",
            "data": "data", "analysis": "data",
        }
        # Also match "crie projeto X" where X is a known type
        _CRIE_PROJETO_RE = re.compile(
            r"\bcrie\s+(?:um\s+)?projeto\s+(\w+)", re.IGNORECASE
        )
        _is_project_request = any(t in lower for t in _PROJECT_TRIGGERS)
        _crie_m = _CRIE_PROJETO_RE.search(lower)
        if _crie_m and _crie_m.group(1).lower() in _TYPE_KEYWORDS:
            _is_project_request = True
        if _is_project_request and "write_file" in available:
            # Detect project type
            detected_type = "fastapi"
            for kw, pt in _TYPE_KEYWORDS.items():
                if kw in lower:
                    detected_type = pt
                    break
            # Extract workspace
            workspace_path = _extract_path(text, "/tmp/apathy-project")
            # If extracted path looks like a file (has extension), use parent dir
            if "." in workspace_path.split("/")[-1]:
                workspace_path = "/tmp/apathy-project"
            # Extract name — look for "chamado X" or "named X" or "called X"
            name = "myapp"
            nm = re.search(
                r"(?:chamado|named|called|nome|name)\s+([a-zA-Z0-9_\-]+)",
                text, re.IGNORECASE
            )
            if nm:
                name = nm.group(1)
            # Build the plan and set state
            self._project_plan = make_project_plan(detected_type, workspace_path, name)
            self._plan_step = 0
            self._plan_finishing = False
            # Return the first write_file tool call
            step = self._project_plan[self._plan_step]
            content = generate_content(step["path"], step["task"])
            self._plan_step += 1
            return call("write_file", {"path": step["path"], "content": content})

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

        # write file — checked BEFORE bash so "escreva ... Makefile — targets: ... run ..."
        # does not accidentally route to bash because "run" appears in the description.
        if any(k in lower for k in ("escreva", "crie", "write", "salve")):
            path = _extract_path(text, "apathy-demo.txt")
            content: str | None = None
            cm = re.search(
                r"(?:com\s+conte[uú]do|contendo|with\s+content)\s+(.+)$",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if cm:
                extracted = cm.group(1).strip().strip("'\"")
                # don't mistake the filename for content
                if extracted and extracted != path:
                    content = extracted + ("\n" if not extracted.endswith("\n") else "")
            if content is None:
                content = generate_content(path, text)
            return call("write_file", {"path": path, "content": content})

        # bash / run command — after write so "run" in a file description doesn't hijack.
        # Require the execution keyword before ":" or at a word boundary near a command.
        if re.search(r"\b(rode|execute|bash|shell|comando)\b", lower) or re.search(
            r"\brun\s*:", lower
        ):
            m = re.search(
                r"(?:rode|execute|run|comando|bash|shell)[:\s]+(.+)$", text, re.IGNORECASE
            )
            cmd = m.group(1).strip().strip("'\"") if m else "echo hello-from-apathy"
            return call("bash", {"command": cmd})

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

        # cloud upload / backup (checked before generic organize)
        _cloud_kw = ("nuvem", "cloud", "drive", "rclone", "google drive",
                     "onedrive", "dropbox", "backup", "faça upload", "envie para")
        if any(k in lower for k in _cloud_kw) and "cloud_sync" in available:
            # remote looks like "name:path"
            rm = re.search(r"\b([a-zA-Z0-9_\-]+:[\w./\- ]+)", text)
            remote = rm.group(1).strip() if rm else ""
            src = _extract_path(text, ".")
            cloud_action = "copy"
            if any(k in lower for k in ("mova", "mover", "move ")):
                cloud_action = "move"
            if remote:
                return call(
                    "cloud_sync",
                    {"action": cloud_action, "source": src, "dest": remote},
                )
            return call("cloud_sync", {"action": "remotes"})

        # organize files
        if any(k in lower for k in ("organize", "organizar", "ordene", "classifique", "mova os")):
            path = _extract_path(text, ".")
            mode = "by_type"
            if "vídeo" in lower or "video" in lower or "mídia" in lower or "media" in lower:
                mode = "by_media"
            elif "data" in lower or "date" in lower or "dia" in lower:
                mode = "by_date"
            elif "size" in lower or "tamanho" in lower or "grande" in lower:
                mode = "by_size"
            return call("organize_files", {"path": path, "mode": mode, "dry_run": False})

        # memory
        _mem_set_kw = ("lembre", "memorize", "salve na memória", "memory set", "guarde")
        if any(k in lower for k in _mem_set_kw):
            m = re.search(r"(?:que|that|:)\s+(.+)$", text, re.IGNORECASE)
            value = m.group(1).strip() if m else text
            return call("memory", {"action": "set", "key": "last_task", "value": value})
        _mem_get_kw = ("recall", "lembre-se", "recupere da memória", "memory get")
        if any(k in lower for k in _mem_get_kw):
            return call("memory", {"action": "get", "key": "last_task"})

        # web search
        _search_kw = ("pesquise", "search for", "procure na web", "web search", "busca web")
        if any(k in lower for k in _search_kw):
            _patt = (
                r"(?:pesquise|search for|busque|procure)"
                r"\s+(?:na web\s+)?(?:sobre\s+)?(.+)$"
            )
            m = re.search(_patt, text, re.IGNORECASE)
            query = m.group(1).strip() if m else text
            return call("web_search", {"query": query})

        # web fetch
        url_m = re.search(r"https?://\S+", text)
        if url_m and ("web" in lower or "fetch" in lower or "busque" in lower or "url" in lower):
            return call("web_fetch", {"url": url_m.group(0)})

        return None
