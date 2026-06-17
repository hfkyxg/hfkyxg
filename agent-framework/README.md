<p align="center">
  <img src="assets/apathy-icon.svg" width="120" alt="apathy logo"/>
</p>

<h1 align="center">apathy</h1>

<p align="center"><b>Framework Python para agentes de IA autônomos com execução multi-agente paralela.</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/testes-252%20passando-brightgreen" alt="252 testes"/>
  <img src="https://img.shields.io/badge/ferramentas-14-blueviolet" alt="14 ferramentas"/>
  <img src="https://img.shields.io/badge/provedores-12+-orange" alt="12+ provedores"/>
  <img src="https://img.shields.io/badge/API%20key-opcional-yellow" alt="API key opcional"/>
  <img src="https://img.shields.io/badge/licença-MIT-lightgrey" alt="MIT"/>
</p>

```bash
# Gera um projeto FastAPI completo — SEM nenhuma API key
apathy create fastapi --name minha-api --workspace ./projeto --yes

# Chat interativo com qualquer LLM
apathy chat --persona personas/default.yaml

# Daemon autônomo: monitora arquivos, roda schedules, orquestra agentes
apathy serve --workflows ./workflows

# Time de agentes constrói um sistema inteiro em paralelo
apathy build "API REST com FastAPI e auth JWT" --workspace ./output
```

---

## O que o apathy consegue fazer hoje

### ✅ Funciona 100% offline (sem API key)

O `MockProvider` transforma linguagem natural em chamadas de ferramentas reais — não é simulação, é execução real:

- **Cria arquivos com conteúdo funcional** detectando tipo de arquivo e contexto (FastAPI, pytest, Dockerfile…)
- **Executa comandos shell** (`bash`) e retorna o output real
- **Lê, lista e busca** no disco de verdade
- **Delega subtarefas a subagentes** com contexto isolado

```bash
# Gera 9 arquivos de um projeto FastAPI completo:
apathy create fastapi --name demo-api --workspace /tmp/demo --yes

# Conteúdo gerado (real, funcional):
#   main.py          — FastAPI CRUD + Pydantic
#   Dockerfile       — Python slim, healthcheck, non-root
#   Makefile         — install/test/lint/run/clean
#   requirements.txt — fastapi, uvicorn, pydantic
#   ...
```

### ✅ Runtime autônomo com daemon (`apathy serve`)

O `AgentRuntime` é um daemon assíncrono que orquestra múltiplos agentes em paralelo:

```
┌─────────────────────────────────────────────────────────┐
│  apathy serve  (Rich Live dashboard)                    │
│                                                         │
│  WORKFLOWS  heartbeat(✓)  code_monitor(✓)  web_research │
│  WORKERS    4 workers  |  2 running  |  1 queued        │
│                                                         │
│  JOBS ─────────────────────────────────────────────────│
│  abc123  heartbeat/ping    DONE    2.1s                 │
│  def456  code_monitor/lint RUNNING 5.3s                 │
│  ghi789  web_research/srch WAITING_PERM                 │
│                                                         │
│  PERMISSÕES PENDENTES ──────────────────────────────── │
│  [ghi789] bash: pytest -q   [a]provar  [d]eniar        │
│                                                         │
│  LOG ──────────────────────────────────────────────────│
│  14:32:01 heartbeat concluído em 2.1s                  │
│  14:32:06 code_monitor/lint iniciando                  │
└─────────────────────────────────────────────────────────┘

Comandos: [q]uit  [a]llow <id>  [d]eny <id>  [t]rigger <nome>
```

**Tipos de trigger suportados:**
| Trigger | Exemplo | Descrição |
|---------|---------|-----------|
| `schedule` | `interval: 5m` | Roda periodicamente (s/m/h/d) |
| `watch` | `path: ./src/*.py` | Monitora arquivos via polling |
| `manual` | `apathy trigger nome` | Disparo único sob demanda |
| `event` | `topic: deploy.done` | Pub/sub interno via EventBus |

### ✅ 14 ferramentas integradas

| Ferramenta     | O que faz                                                | Permissão  |
|----------------|----------------------------------------------------------|:----------:|
| `read_file`    | Lê arquivo com offset/limit e numeração de linhas        | auto       |
| `write_file`   | Cria ou sobrescreve arquivo (cria diretórios pai)        | **ask**    |
| `edit_file`    | Substituição exata e única em arquivo existente          | **ask**    |
| `list_dir`     | Lista diretório (tamanhos, tipos)                        | auto       |
| `bash`         | Executa comando shell com timeout configurável           | **ask**    |
| `grep`         | Busca regex em arquivos                                  | auto       |
| `glob`         | Encontra arquivos por padrão glob                        | auto       |
| `web_fetch`    | Busca URL, extrai texto limpo (remove HTML/scripts)      | auto       |
| `web_search`   | Pesquisa web: DuckDuckGo (grátis) / Google / Brave / Serper | auto  |
| `http_request` | HTTP com método, headers e body arbitrários              | **ask**    |
| `memory`       | Memória persistente SQLite: set/get/list/delete/search   | auto       |
| `notify`       | Notificações: Slack / Discord / Teams / Telegram         | **ask**    |
| `database`     | SQL: SQLite local + PostgreSQL (asyncpg)                 | **ask**    |
| `task`         | Delega subtarefa a subagente com contexto isolado        | auto       |

### ✅ Multi-provedor — 12+ LLMs sem lock-in

Trocar o modelo é **uma linha** no YAML da persona:

```yaml
provider: "anthropic/claude-opus-4-8"      # Claude (Anthropic)
provider: "anthropic/claude-sonnet-4-6"    # Claude Sonnet
provider: "openai/gpt-4o"                  # OpenAI GPT-4o
provider: "openai/gpt-4o-mini"             # OpenAI Mini
provider: "azure/gpt-4o"                   # Azure OpenAI
provider: "groq/llama-3.3-70b-versatile"   # Groq (ultra-rápido)
provider: "groq/mixtral-8x7b-32768"        # Groq Mixtral
provider: "google/gemini-2.0-flash"        # Google Gemini Flash
provider: "google/gemini-pro"              # Google Gemini Pro
provider: "mistral/mistral-large-latest"   # Mistral Large
provider: "cohere/command-r-plus"          # Cohere Command R+
provider: "together_ai/meta-llama/..."     # Meta Llama (Together)
provider: "ollama/llama3.2"               # Local via Ollama
provider: "ollama/hermes3"                # Local Hermes (tool-calling)
provider: "mock/demo"                      # Offline — sem API key
```

### ✅ Busca web sem API key

O `web_search` usa DuckDuckGo por padrão (grátis, sem chave), e auto-detecta provedores premium quando as chaves estão configuradas:

```python
# Auto-seleção: Google → Serper → Brave → DuckDuckGo
backend = "auto"   # padrão

# Ou força um backend específico:
backend = "duckduckgo"  # sempre grátis
backend = "google"       # requer GOOGLE_API_KEY + GOOGLE_CSE_ID
backend = "brave"        # requer BRAVE_API_KEY
backend = "serper"       # requer SERPER_API_KEY
```

### ✅ Memória persistente entre sessões

```bash
# Agente salva e recupera informações entre sessões
memory set --key projeto_atual --value "API de e-commerce" --namespace projetos
memory get --key projeto_atual --namespace projetos
memory search --query "API" --namespace projetos
```

O `MemoryTool` usa SQLite em `~/.apathy/memory.db` (configurável via `MEMORY_DB_PATH`). Zero dependências extras — usa `sqlite3` nativo.

### ✅ Notificações para qualquer plataforma

```yaml
# Na persona: habilitar notify
enabled_tools: [notify, ...]

# O agente envia notificações automaticamente:
# notify channel=slack message="Deploy concluído" title="CI/CD" color=good
# notify channel=discord message="Erro detectado" color=danger
# notify channel=telegram message="Tarefa finalizada"
```

### ✅ Loop de agente completo com gate de permissão

```
Entrada do usuário
      │
      ▼
 Agent.run_turn()              ← async generator; interfaces consomem os eventos
      │
      ├──► provider.complete() ──► LLM (qualquer via litellm) ou MockProvider (offline)
      │           │
      │           ▼
      │     stop_reason == "end_turn"  ──► TurnCompleteEvent → encerra
      │     stop_reason == "tool_calls"
      │           │
      │           ▼
      │     para cada ToolCall:
      │       ├── PermissionGate.check()
      │       │     always_allow → tool.run() direto
      │       │     workspace    → auto dentro do workspace, ask fora
      │       │     ask          → ask_callback() → usuário decide
      │       │     deny         → ToolResult(is_error=True)
      │       └── ToolResultEvent → volta para complete() → próximo passo
      │
      └──► loop até stop_reason == "end_turn" ou max_iterations
```

### ✅ 252 testes — tudo roda sem API key

```bash
uv run pytest       # 252 testes, 0 chamadas de rede
uv run ruff check . # All checks passed
```

---

## Instalação

Requer **Python 3.11+** e [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/hfkyxg/hfkyxg
cd hfkyxg/agent-framework
uv sync
```

Para usar com um LLM real, configure as chaves em `.env`:

```bash
cp .env.example .env
```

Edite `.env` com as chaves desejadas (todas são opcionais — sem chaves, tudo funciona com `mock/demo`):

```ini
# ── Anthropic (Claude) ────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ── OpenAI ────────────────────────────────────
OPENAI_API_KEY=sk-...

# ── Google / Gemini ───────────────────────────
GOOGLE_API_KEY=AIza...
GOOGLE_CSE_ID=...        # Custom Search Engine ID (para web_search)
GEMINI_API_KEY=AIza...

# ── Azure OpenAI ──────────────────────────────
AZURE_API_KEY=...
AZURE_API_BASE=https://<resource>.openai.azure.com/
AZURE_API_VERSION=2024-02-01

# ── Groq ──────────────────────────────────────
GROQ_API_KEY=gsk_...

# ── Mistral ───────────────────────────────────
MISTRAL_API_KEY=...

# ── Cohere ────────────────────────────────────
COHERE_API_KEY=...

# ── Together AI ───────────────────────────────
TOGETHER_API_KEY=...

# ── Busca web ─────────────────────────────────
BRAVE_API_KEY=...        # Brave Search API
SERPER_API_KEY=...       # Serper.dev (Google Search proxy)

# ── Notificações ──────────────────────────────
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# ── Ollama (local) ────────────────────────────
OLLAMA_API_BASE=http://localhost:11434

# ── Memória ───────────────────────────────────
MEMORY_DB_PATH=~/.apathy/memory.db  # padrão
```

---

## Início rápido

### Sem API key (offline)

```bash
# Demonstração completa do loop de agente
uv run apathy demo

# Criar projeto completo (FastAPI, CLI, webapp, data)
uv run apathy create fastapi --name minha-api --workspace ./projeto --yes
uv run apathy create cli    --name minha-cli --yes
uv run apathy create webapp --name meu-site  --yes

# Tarefa única com aprovação automática
uv run apathy run "escreva o arquivo app.py — fastapi com CRUD" \
  --persona personas/demo.yaml --yes

# Ver ferramentas disponíveis
uv run apathy tools

# Listar workflows configurados
uv run apathy workflows-list
```

### Com API key

```bash
# Chat interativo com Claude
uv run apathy chat --persona personas/default.yaml

# Chat com GPT-4o
uv run apathy chat --persona personas/providers/gpt4o.yaml

# Chat com modelo local (Ollama)
uv run apathy chat --persona personas/providers/ollama-hermes.yaml

# Daemon autônomo com todos os workflows
uv run apathy serve --workflows ./workflows

# Disparar workflow manualmente
uv run apathy trigger web_research topic="Python 3.13"

# Time de agentes constrói sistema em paralelo
uv run apathy build "API REST com FastAPI e frontend React" --workspace ./output
```

---

## Comandos

### `demo` — prova offline completa

Sequência de 5 passos: write → read → list → bash → grep. Tudo em workspace temporário, tudo real.

```bash
apathy demo
```

### `create` — cria projeto completo autonomamente

```bash
apathy create fastapi --name minha-api --workspace ./projeto --yes
apathy create cli     --name minha-cli --workspace ./cli-app --yes
apathy create webapp  --name meu-site  --workspace ./webapp  --yes
apathy create data    --name analise   --workspace ./data    --yes
```

Cada `create` usa o `MockProvider` para guiar o agente por todas as etapas: scaffold, dependências, testes, Dockerfile, Makefile, README.

### `run` — tarefa única (scriptável)

```bash
# Gera código com detecção automática de contexto
apathy run "escreva o arquivo api.py — fastapi" --persona personas/demo.yaml --yes
apathy run "escreva tests/test_api.py"           --persona personas/demo.yaml --yes
apathy run "rode: pytest -q"                     --yes

# `--yes` / `-y` aprova tudo automaticamente — ideal para CI
```

### `chat` — REPL conversacional

```bash
apathy chat                                       # persona padrão
apathy chat --persona personas/researcher.yaml   # pesquisador (só leitura/web)
apathy chat --persona personas/providers/gpt4o.yaml
apathy chat --workdir /meu/projeto
```

Ações de leitura e memória são liberadas automaticamente. Escrita, shell, HTTP e notificações pedem confirmação.

### `serve` — daemon autônomo

```bash
apathy serve                              # carrega ./workflows/
apathy serve --workflows /caminho/custom
apathy serve --workers 8                  # pool de workers (padrão: 4)
```

Interface Rich com 4 painéis: status geral → tabela de jobs → permissões pendentes → log de eventos.

Comandos interativos:
```
q          — parar o daemon
a <id>     — aprovar permissão pendente
d <id>     — negar permissão pendente
t <nome>   — disparar workflow manualmente
```

### `trigger` — disparo único de workflow

```bash
apathy trigger web_research topic="machine learning"
apathy trigger daily_summary
```

Roda o workflow até completar e imprime o resultado. Sem daemon.

### `workflows-list` — inspecionar workflows

```bash
apathy workflows-list
# Exibe: nome, ativo, triggers, passos, permissão, descrição
```

### `build` — time de agentes em paralelo

Para objetivos grandes demais para um único agente. Requer LLM real.

```bash
apathy build "backend FastAPI com auth JWT e frontend React" --workspace ./projeto
apathy build "..." --dry-run   # mostra plano sem executar
```

**Fluxo do `build`:**
1. **Planner** decompõe o objetivo em tarefas JSON com dependências explícitas
2. **TaskGraph** identifica quais tarefas não têm dependências mútuas
3. **asyncio.gather** executa todas as tarefas prontas simultaneamente
4. **Reviewer** verifica cada entrega → retrabalho se necessário (máx. 2 ciclos)
5. **Integrator** verifica que as partes conversam e gera resumo final

### `tools` / `version` / `ps`

```bash
apathy tools     # tabela: 14 ferramentas com política de permissão
apathy version   # apathy 0.1.0
apathy ps        # status dos agentes em execução
```

---

## Workflows

Workflows são configurados em YAML em `./workflows/`. O daemon os carrega e executa automaticamente.

```yaml
# workflows/web_research.yaml
name: web_research
description: |
  Pesquisa web sobre um tópico e salva relatório estruturado.

triggers:
  - type: manual

steps:
  - name: search
    persona: demo
    task: "pesquise na web sobre: {topic}"
    workspace: "."
  - name: report
    persona: demo
    task: "escreva o arquivo ./reports/research_{topic}.md com relatório sobre {topic}"
    workspace: "."

permission: workspace
parallel: false
timeout_seconds: 120
```

```yaml
# workflows/heartbeat.yaml — roda a cada 1 minuto
name: heartbeat
triggers:
  - type: schedule
    interval: 1m
steps:
  - name: ping
    persona: demo
    task: "rode: echo 'apathy heartbeat at {timestamp}'"
permission: autopilot
```

```yaml
# workflows/code_monitor.yaml — monitora mudanças em .py
name: code_monitor
triggers:
  - type: watch
    path: ./src
    pattern: "*.py"
    events: [modified, created]
steps:
  - name: lint
    persona: demo
    task: "rode: ruff check {changed_file}"
  - name: test
    persona: demo
    task: "rode: pytest -x -q"
permission: workspace
```

**Workflows incluídos:**

| Workflow | Trigger | O que faz |
|----------|---------|-----------|
| `heartbeat` | schedule 1m | Pulso vivo — confirma que o daemon está ativo |
| `code_monitor` | watch `*.py` | Lint + teste a cada mudança no código |
| `daily_summary` | schedule 1h | Escaneia workspace e gera relatório |
| `web_research` | manual | Pesquisa web e salva relatório estruturado |
| `notify_on_error` | watch `*.log` | Detecta erros nos logs e notifica |
| `file_organizer` | watch | Organiza arquivos automaticamente |

---

## Personas

Cada agente é definido inteiramente em YAML.

```yaml
# personas/default.yaml — agente padrão (Claude)
name: default
system_prompt: |
  Você é um assistente de IA especializado em engenharia de software.
  Analise, escreva e refatore código com qualidade profissional.
provider: "anthropic/claude-sonnet-4-6"
enabled_tools:
  - read_file
  - write_file
  - edit_file
  - list_dir
  - bash
  - grep
  - glob
  - web_fetch
  - web_search
  - http_request
  - memory
  - notify
  - database
  - task
max_iterations: 30
temperature: 0.2
```

```yaml
# personas/researcher.yaml — pesquisador sem permissão de escrita
name: researcher
system_prompt: |
  Você é um pesquisador cuidadoso. Investiga usando web e arquivos locais.
  Nunca modifica arquivos nem executa código. Sempre cita as fontes.
provider: "anthropic/claude-sonnet-4-6"
enabled_tools: [read_file, list_dir, grep, glob, web_fetch, web_search, memory]
permission_overrides:
  - tool: http_request
    decision: ask
max_iterations: 15
temperature: 0.1
```

### Personas por provedor (`personas/providers/`)

```
providers/
├── gpt4o.yaml          # OpenAI GPT-4o
├── gpt4o-mini.yaml     # OpenAI GPT-4o Mini
├── azure-gpt4.yaml     # Azure OpenAI
├── groq-llama.yaml     # Groq Llama 3.3 70B
├── groq-mixtral.yaml   # Groq Mixtral 8x7B
├── gemini-pro.yaml     # Google Gemini Pro
├── gemini-flash.yaml   # Google Gemini Flash
├── mistral-large.yaml  # Mistral Large
├── mistral-small.yaml  # Mistral Small
├── cohere.yaml         # Cohere Command R+
├── together-llama.yaml # Meta Llama via Together AI
└── ollama-hermes.yaml  # Hermes 3 local (Ollama)
```

### Personas especializadas

```
personas/
├── demo.yaml           # MockProvider offline — CI e demos
├── default.yaml        # Claude: agente de engenharia completo
├── researcher.yaml     # Pesquisador: web + memória, sem escrita
├── devops.yaml         # DevOps: Docker, CI/CD, infra
├── data-analyst.yaml   # Análise de dados: SQL, CSV, estatísticas
└── roles/              # Usadas pelo comando `build`
    ├── planner.yaml    # Decomposição de objetivos em JSON de tarefas
    ├── backend.yaml    # APIs, banco de dados, lógica de servidor
    ├── frontend.yaml   # UI, HTML/CSS/JS
    ├── infra.yaml      # Dockerfile, CI/CD, scripts de deploy
    ├── reviewer.yaml   # Verifica entregas → {"ok": bool, "feedback": "..."}
    └── integrator.yaml # Integração final, testa sistema, escreve resumo
```

---

## Arquitetura

```
agent-framework/
├── pyproject.toml                        # apathy 0.1.0
├── .env.example                          # 30+ variáveis documentadas
├── personas/                             # YAMLs de agentes
│   ├── demo.yaml / default.yaml / ...
│   ├── providers/                        # 12 provedores prontos
│   └── roles/                            # 6 papéis para o `build`
├── workflows/                            # 6 workflows de exemplo
├── examples/                             # scripts de demonstração
└── src/agent_framework/
    ├── core/
    │   ├── agent.py            # Agent.run_turn() — async generator de eventos
    │   ├── provider.py         # ModelProvider: litellm + reparo de JSON malformado
    │   ├── mock_provider.py    # MockProvider: heurístico offline determinístico
    │   ├── content_generator.py# templates para 14+ tipos de arquivo
    │   ├── orchestrator.py     # spawn_subagent() + subagent_event_hook
    │   ├── project.py          # TaskGraph + ProjectCrew — DAG paralelo + reviewer
    │   ├── runtime.py          # AgentRuntime: daemon com worker pool assíncrono
    │   ├── workflow.py         # Workflow/WorkflowStep: parser + loader de YAML
    │   ├── scheduler.py        # AsyncScheduler: jobs periódicos
    │   ├── watcher.py          # FileWatcher: monitora diretórios por polling
    │   ├── eventbus.py         # EventBus: pub/sub assíncrono entre workflows
    │   ├── permissions.py      # PermissionGate: auto/workspace/ask/deny
    │   ├── persona.py          # Persona: Pydantic + YAML loader
    │   ├── session.py          # Session: histórico imutável da conversa
    │   ├── messages.py         # Message / ToolCall / ToolResult
    │   ├── tool.py             # Tool (Protocol) + ToolRegistry + ToolContext
    │   └── errors.py           # ToolError + AgentError
    ├── tools/
    │   ├── files.py            # read_file, write_file, edit_file, list_dir
    │   ├── search.py           # grep, glob
    │   ├── shell.py            # bash
    │   ├── web.py              # web_fetch, http_request
    │   ├── web_search.py       # web_search (DDG/Google/Brave/Serper)
    │   ├── memory.py           # memory (SQLite ~/.apathy/memory.db)
    │   ├── notify.py           # notify (Slack/Discord/Teams/Telegram)
    │   ├── database.py         # database (SQLite + PostgreSQL)
    │   └── task.py             # task (delega ao Orchestrator)
    ├── interfaces/
    │   ├── cli/
    │   │   ├── app.py          # Typer: todos os comandos
    │   │   ├── daemon.py       # Rich Live dashboard para `serve`
    │   │   ├── repl.py         # REPL interativo para `chat`
    │   │   ├── run_once.py     # Single-shot para `run` e `trigger`
    │   │   ├── crew_runner.py  # Runner para `build`
    │   │   └── demo_runner.py  # Sequência demo para `demo`
    │   ├── discord/bot.py      # Adaptador Discord (bot.py)
    │   ├── slack/bot.py        # Adaptador Slack (bot.py)
    │   └── telegram/bot.py     # Adaptador Telegram (bot.py)
    ├── mcp_server/server.py    # Servidor MCP via FastMCP
    ├── mcp_client/client.py    # Consome servidores MCP externos
    └── config/settings.py      # pydantic-settings: 30+ variáveis de env
```

---

## Integrações de ecossistema

### Anthropic / Claude

```bash
ANTHROPIC_API_KEY=sk-ant-...
# Usar: personas/default.yaml (provider: anthropic/claude-sonnet-4-6)
# Usar: personas/providers/ (claude-opus-4-8, claude-haiku-4-5, ...)
```

### OpenAI

```bash
OPENAI_API_KEY=sk-...
# Usar: personas/providers/gpt4o.yaml
# Usar: personas/providers/gpt4o-mini.yaml
```

### Azure OpenAI

```bash
AZURE_API_KEY=...
AZURE_API_BASE=https://<recurso>.openai.azure.com/
AZURE_API_VERSION=2024-02-01
# Usar: personas/providers/azure-gpt4.yaml
```

### Google (Gemini + Search)

```bash
GOOGLE_API_KEY=AIza...       # para Gemini + Google Custom Search
GOOGLE_CSE_ID=...            # Custom Search Engine ID
GEMINI_API_KEY=AIza...       # alternativa ao GOOGLE_API_KEY para Gemini
# Usar: personas/providers/gemini-pro.yaml
# Usar: personas/providers/gemini-flash.yaml
# Web search automático via Google quando GOOGLE_API_KEY + GOOGLE_CSE_ID configurados
```

### Groq (inferência ultra-rápida)

```bash
GROQ_API_KEY=gsk_...
# Usar: personas/providers/groq-llama.yaml  (Llama 3.3 70B)
# Usar: personas/providers/groq-mixtral.yaml (Mixtral 8x7B)
```

### Mistral AI

```bash
MISTRAL_API_KEY=...
# Usar: personas/providers/mistral-large.yaml
# Usar: personas/providers/mistral-small.yaml
```

### Cohere

```bash
COHERE_API_KEY=...
# Usar: personas/providers/cohere.yaml (Command R+)
```

### Together AI (Meta Llama e outros)

```bash
TOGETHER_API_KEY=...
# Usar: personas/providers/together-llama.yaml
```

### Ollama (modelos locais)

```bash
OLLAMA_API_BASE=http://localhost:11434  # padrão
# Usar: personas/providers/ollama-hermes.yaml (Hermes 3 — excelente em tool-calling)
# Qualquer modelo Ollama: provider: "ollama/<nome-do-modelo>"
```

### Slack / Discord / Teams / Telegram (notificações)

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
# O agente usa a ferramenta `notify` para enviar mensagens a qualquer plataforma
```

### MCP (Model Context Protocol)

```bash
# Servidor MCP — expõe as 14 ferramentas para VS Code / Cursor / Claude Desktop:
uv run python -m agent_framework.mcp_server

# Configuração em .vscode/mcp.json ou claude_desktop_config.json:
# { "mcpServers": { "apathy": { "command": "uv", "args": ["run", "python", "-m", "agent_framework.mcp_server"] } } }
```

---

## Estado dos testes

```bash
uv run pytest            # 252 testes, 0 chamadas de rede
uv run ruff check .      # All checks passed
```

| Módulo de teste | O que cobre |
|----------------|-------------|
| `test_messages` | Serialização Message/ToolCall/ToolResult, round-trip |
| `test_provider` | Reparo de JSON, normalização de tool-calling entre provedores |
| `test_permissions` | Todos os modos: auto, workspace, ask, deny, overrides por ferramenta |
| `test_agent` | Loop: negação, erro de ferramenta, max_iterations, múltiplas calls |
| `test_mock_provider` | Seleção heurística, sumarização, end-to-end offline |
| `test_content_generator` | 20 casos: todos os tipos de arquivo, detecção de tópico |
| `test_subagent_delegation` | Detecção, loop pai→filho, subagent_event_hook |
| `test_task` | TaskTool: spawn, resultado, erro |
| `test_project` | TaskGraph DAG, execução paralela, ciclo reviewer, integrator |
| `test_runtime` | AgentRuntime: jobs, workers, triggers, broker de permissão |
| `test_workflow` | Parser YAML, triggers, enabled flag, load_dir |
| `test_tools_*` | Todas as 14 ferramentas concretas |
| `test_new_tools` | web_search, memory, notify, database |
| `test_run_once` | Pipeline CLI single-shot, auto-approve |

---

## Roadmap

### ✅ Entregue (v0.1)

- [x] Loop de agente com gate de permissão (auto / workspace / ask / deny)
- [x] 14 ferramentas: read, write, edit, list, bash, grep, glob, web_fetch, web_search, http_request, memory, notify, database, task
- [x] `MockProvider` offline — funciona sem API key
- [x] `ContentGenerator` — gera código real para 14+ tipos de arquivo
- [x] Subagentes com contexto isolado e streaming de eventos em tempo real
- [x] CLI completa: `chat`, `run`, `build`, `demo`, `tools`, `version`, `create`, `serve`, `trigger`, `workflows-list`, `ps`
- [x] `AgentRuntime` — daemon autônomo com worker pool assíncrono
- [x] Workflows YAML com 4 tipos de trigger: schedule, watch, manual, event
- [x] `AsyncScheduler` — jobs periódicos com suporte a sufixos s/m/h/d
- [x] `FileWatcher` — monitora diretórios por polling assíncrono
- [x] `EventBus` — pub/sub interno entre workflows
- [x] Dashboard Rich Live para `apathy serve`
- [x] `ProjectCrew` com DAG paralelo, reviewer, integrator
- [x] 12 personas por provedor prontas para usar
- [x] Memória persistente SQLite (`memory`)
- [x] Busca web multi-backend (`web_search`)
- [x] Notificações Slack/Discord/Teams/Telegram (`notify`)
- [x] Banco de dados SQLite + PostgreSQL (`database`)
- [x] Servidor MCP via FastMCP
- [x] Adaptadores Discord / Slack / Telegram
- [x] 252 testes, ruff limpo

### 🔧 Próximas melhorias (v0.2)

- [ ] **Streaming de tokens** — emitir tokens conforme chegam
- [ ] **Tool calls paralelas** — executar múltiplas calls da mesma resposta com `asyncio.gather`
- [ ] **Retry com backoff** — retentar automaticamente erros de rate limit
- [ ] **Checkpoint e retomada** — salvar estado do `TaskGraph`; retomar build do ponto onde parou
- [ ] **Observabilidade OpenTelemetry** — spans por tool call, tokens consumidos, custo estimado
- [ ] **Workspace sandboxado por tarefa** — cada agente escreve no próprio subdiretório
- [ ] **Tarefas dinâmicas** — agentes adicionam novas tarefas ao DAG durante a execução

### 📅 v0.3 — Bots de chat completos

- [ ] **Discord** — evento de mensagem → `Agent.run_turn()`, thread → `Session`
- [ ] **Telegram** — mesmo padrão
- [ ] **Slack** — Socket Mode, OAuth scopes mínimos

---

## Licença

MIT
