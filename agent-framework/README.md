<p align="center">
  <img src="assets/apathy-icon.svg" width="120" alt="apathy mask icon"/>
</p>

<h1 align="center">apathy</h1>

<p align="center"><b>Framework Python para agentes de IA autônomos com execução multi-agente paralela.</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/testes-175%20passando-brightgreen" alt="175 testes"/>
  <img src="https://img.shields.io/badge/API%20key-opcional-orange" alt="API key opcional"/>
  <img src="https://img.shields.io/badge/licença-MIT-lightgrey" alt="MIT"/>
</p>

```bash
# Gera um projeto FastAPI completo — SEM nenhuma API key
apathy run "escreva o arquivo app.py — fastapi com CRUD" --persona personas/demo.yaml --yes

# Loop REPL com qualquer LLM
apathy chat --persona personas/default.yaml

# Time de agentes constrói um sistema inteiro em paralelo
apathy build "API REST com FastAPI e frontend HTML/JS" --workspace ./output
```

---

## O que o apathy consegue fazer hoje

### ✅ Funciona 100% offline (sem API key)

O `MockProvider` transforma linguagem natural em chamadas de ferramentas reais. Não é um LLM — é um motor heurístico determinístico que:

- **Cria arquivos com conteúdo real e funcional** baseado no tipo do arquivo e contexto da tarefa
- **Executa comandos shell** (`bash`) e entrega o output real
- **Lê, lista e busca** arquivos de verdade no disco
- **Delega subtarefas a subagentes** — spawna um agente filho isolado em tempo real

```bash
# Cria um FastAPI app completo com rotas CRUD:
apathy run "escreva o arquivo main.py — fastapi app com CRUD para items" \
  --persona personas/demo.yaml --yes

# Gerado: 56 linhas de FastAPI funcional:
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# app = FastAPI(title="Main", version="0.1.0")
# @app.get("/items") ... @app.post("/items") ... etc.
```

### ✅ Gera código real para 14+ tipos de arquivo

O `ContentGenerator` produz templates prontos para uso:

| Arquivo | Conteúdo gerado |
|---------|----------------|
| `main.py` + FastAPI | App completo com rotas CRUD, Pydantic, uvicorn |
| `main.py` + CLI | argparse com subcomandos, verbose, output |
| `test_*.py` | Pytest: 8 testes, parametrize, fixtures |
| `analysis.py` | Leitura CSV, estatísticas, geração de dataset de exemplo |
| `Dockerfile` | Python slim, non-root, healthcheck, COPY/RUN |
| `Makefile` | install / test / lint / format / run / clean |
| `requirements.txt` | Deps FastAPI ou genéricas (detectado pelo contexto) |
| `config.json` / `.yaml` | Seções server / database / logging / features |
| `index.html` | Dark theme, CSS inline, JS com fetch wrapper |
| `README.md` | Seções Overview, Getting Started, estrutura |
| `.env.example` | Template comentado com DATABASE_URL, API keys |
| `.gitignore` | Padrões Python completos |
| `.sh` | Bash com set -euo pipefail, log(), trap EXIT |
| `TODO.txt` | Checklist por prioridade |

**Detecção automática de contexto:** quando você diz "fastapi" na descrição, gera código FastAPI. "teste" → pytest. "docker" → Dockerfile. O motor escolhe o template certo.

### ✅ Subagentes com visibilidade em tempo real

O `Orchestrator` spawna agentes filhos com sessão isolada, toolset filtrado e transmite cada evento para o pai:

```bash
apathy run "delegue ao subagente: escreva o arquivo relatorio.md com conteúdo # Relatório" \
  --persona personas/demo.yaml --yes
```

```
╭─ Tool: task ─────────────────────────────────────────╮
│ {'prompt': 'escreva o arquivo relatorio.md ...'}     │
╰──────────────────────────────────────────────────────╯
  ✓ Allowed: task
    └─ subagente:demo usa write_file {'path': 'relatorio.md', ...}
    └─ subagente:demo ✓ Wrote 969 characters to relatorio.md
  ✓ task: arquivo criado com sucesso
```

O subagente roda em contexto completamente isolado e devolve apenas o resultado ao pai.

### ✅ Script de projeto completo (offline)

```bash
./examples/build_fastapi_project.sh         # cria 9 arquivos de um projeto FastAPI
./examples/run_tasks.sh                      # 5 tarefas variadas: write/read/bash/grep/delegate
```

O `build_fastapi_project.sh` gera num workspace temporário:
```
main.py          56 linhas  — FastAPI CRUD completo
requirements.txt  4 linhas  — fastapi, uvicorn, pydantic
config.json      22 linhas  — server/database/logging/features
Dockerfile       26 linhas  — Python slim, healthcheck
.env.example     20 linhas  — DATABASE_URL, API keys
.gitignore       37 linhas  — padrões Python
Makefile         20 linhas  — install/test/lint/run/clean
tests/test_app.py 56 linhas — pytest com 8 testes
README.md        62 linhas  — documentação completa
```
Total: ~9 arquivos, ~360 linhas de código real em **< 30 segundos**, sem API key.

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
      │       │     auto   → tool.run() direto
      │       │     ask    → ask_callback() → usuário decide
      │       │     deny   → ToolResult(is_error=True)
      │       └── ToolResultEvent → volta para complete() → próximo passo
      │
      └──► loop até stop_reason == "end_turn" ou max_iterations
```

### ✅ Multi-provedor sem lock-in

Trocar o LLM é **uma linha** no YAML da persona:

```yaml
provider: "anthropic/claude-opus-4-8"    # Claude via Anthropic
provider: "openai/gpt-4o"                # OpenAI
provider: "ollama/llama3.2"              # local via Ollama
provider: "groq/llama-3.3-70b"          # Groq (ultra-rápido)
provider: "mock/demo"                    # offline — sem API key
```

O `ModelProvider` normaliza o tool-calling para qualquer provedor. Inclui reparo de JSON malformado — importante para modelos locais que às vezes geram JSON quebrado.

### ✅ 175 testes — tudo roda sem API key

```bash
uv run pytest       # 175 testes, nenhuma chamada de rede
```

Cobertura: mensagens e serialização, reparo de JSON, PermissionGate (todas as decisões), loop de agente (negação, erro de ferramenta, max_iterations), spawn de subagentes, DAG de tarefas, execução paralela, ciclo de revisão, todas as 10 ferramentas, pipeline end-to-end, content generator (14+ tipos).

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
# edite .env:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# OLLAMA_API_BASE=http://localhost:11434
```

Sem chaves: tudo funciona com a persona `mock/demo`.

---

## Início rápido

### Sem API key (offline)

```bash
# Demonstração completa do loop de agente
uv run apathy demo

# Gerar um arquivo com código real
uv run apathy run "escreva o arquivo app.py — fastapi com CRUD" \
  --persona personas/demo.yaml --yes

# Criar um projeto completo (9 arquivos)
./examples/build_fastapi_project.sh

# Agente delega para subagente
uv run apathy run \
  "delegue ao subagente: escreva o arquivo sub.txt com conteúdo feito-pelo-sub" \
  --persona personas/demo.yaml --yes

# Introspecção
uv run apathy tools
uv run apathy version
```

### Com API key

```bash
# Chat interativo com qualquer LLM
uv run apathy chat --persona personas/default.yaml

# Time de agentes constrói um sistema inteiro
uv run apathy build "API REST com FastAPI e auth JWT" --workspace ./projeto
```

---

## Comandos

### `demo` — prova offline completa

Sequência de 5 passos que exercita o loop inteiro: write → read → list → bash → grep. Tudo em workspace temporário, tudo real.

```bash
apathy demo
```

### `run` — tarefa única (scriptável)

```bash
# Gera código com contexto automático
apathy run "escreva o arquivo api.py — fastapi" --persona personas/demo.yaml --yes
apathy run "escreva o arquivo tests/test_api.py" --persona personas/demo.yaml --yes
apathy run "rode: pytest -q" --yes

# Delegação a subagente
apathy run "delegue ao subagente: escreva o arquivo nota.txt com conteúdo olá" \
  --persona personas/demo.yaml --yes
```

`--yes` (`-y`) aprova todas as ações automaticamente — ideal para CI e scripts.

### `chat` — REPL conversacional

```bash
apathy chat                                  # persona padrão
apathy chat --persona personas/researcher.yaml
apathy chat --workdir /meu/projeto
```

Ações de leitura liberadas automaticamente. Escrita, shell e HTTP pedem confirmação.

### `build` — time de agentes em paralelo

Para objetivos grandes demais para um único agente. Requer LLM real.

```bash
apathy build "backend FastAPI com auth JWT e frontend React" --workspace ./projeto
apathy build "..." --dry-run   # mostra plano sem executar
```

**Fluxo do `build`:**
1. **Planner** decompõe o objetivo em tarefas JSON com dependências
2. **TaskGraph** identifica quais tarefas rodam em paralelo
3. **asyncio.gather** executa todas as tarefas prontas simultaneamente
4. **Reviewer** verifica cada entrega → retrabalho se necessário (máx. 2 ciclos)
5. **Integrator** verifica que as partes conversam e gera o resumo final

### `tools` / `version`

```bash
apathy tools     # tabela: 10 ferramentas com policy de permissão
apathy version   # apathy 0.1.0
```

---

## Ferramentas (10 disponíveis)

| Ferramenta    | O que faz                                              | Permissão |
|---------------|--------------------------------------------------------|:---------:|
| `read_file`   | Lê arquivo com offset/limit e numeração de linhas      | auto      |
| `list_dir`    | Lista diretório (tamanhos, tipos)                      | auto      |
| `grep`        | Busca regex em arquivos (via ripgrep)                  | auto      |
| `glob`        | Encontra arquivos por padrão glob                      | auto      |
| `web_fetch`   | Busca URL, extrai texto limpo (remove HTML/scripts)    | auto      |
| `write_file`  | Cria ou sobrescreve arquivo (cria diretórios pai)      | **ask**   |
| `edit_file`   | Substituição exata e única em arquivo existente        | **ask**   |
| `bash`        | Executa comando shell com timeout                      | **ask**   |
| `http_request`| HTTP com método, headers e body arbitrários            | **ask**   |
| `task`        | Delega subtarefa a um subagente em contexto isolado    | auto      |

---

## Personas

Cada agente é definido inteiramente em YAML.

```yaml
# personas/demo.yaml — agente offline para demos e CI
name: demo
system_prompt: "Agente de demonstração offline."
provider: "mock/demo"
enabled_tools: [read_file, write_file, list_dir, bash, grep, task]
max_iterations: 30
temperature: 0.0
```

```yaml
# personas/researcher.yaml — pesquisador sem permissão de escrita
name: researcher
system_prompt: |
  Você é um pesquisador cuidadoso. Investiga usando web e arquivos locais.
  Nunca modifica arquivos nem executa código. Sempre cita as fontes.
provider: "anthropic/claude-sonnet-4-6"
enabled_tools: [read_file, list_dir, grep, glob, web_fetch, http_request]
permission_overrides:
  - tool: http_request
    decision: ask
max_iterations: 15
temperature: 0.1
```

### Personas de papel (usadas pelo `build`)

```
personas/roles/
├── planner.yaml      # decompõe o objetivo em JSON de tarefas
├── backend.yaml      # APIs, banco de dados, lógica de servidor
├── frontend.yaml     # UI, HTML/CSS/JS
├── infra.yaml        # Dockerfile, CI/CD, scripts de deploy
├── reviewer.yaml     # verifica entregas → {"ok": bool, "feedback": "..."}
└── integrator.yaml   # integração final, testa o sistema, escreve resumo
```

---

## Arquitetura

```
agent-framework/
├── pyproject.toml                   # apathy 0.1.0, entry: apathy = "...cli.app:main"
├── personas/                        # YAMLs: demo, default, researcher, roles/
├── assets/apathy-icon.svg           # máscara dark com mira — identidade visual
├── examples/
│   ├── run_tasks.sh                 # 5 tarefas offline: write/read/bash/grep/delegate
│   └── build_fastapi_project.sh     # cria projeto FastAPI completo offline (9 arquivos)
└── src/agent_framework/
    ├── core/
    │   ├── agent.py                 # Agent.run_turn() — async generator de eventos
    │   ├── provider.py              # ModelProvider: litellm + reparo de JSON
    │   ├── mock_provider.py         # MockProvider: heurístico offline determinístico
    │   ├── content_generator.py     # templates para 14+ tipos de arquivo
    │   ├── orchestrator.py          # spawn_subagent() + subagent_event_hook
    │   ├── project.py               # TaskGraph + ProjectCrew — DAG paralelo
    │   ├── permissions.py           # PermissionGate: auto / ask / deny
    │   ├── persona.py               # Persona: Pydantic + YAML loader
    │   ├── session.py               # Session: histórico imutável da conversa
    │   ├── messages.py              # Message / ToolCall / ToolResult
    │   └── tool.py                  # Tool (Protocol) + ToolRegistry + ToolContext
    ├── tools/
    │   ├── files.py                 # read_file, write_file, edit_file, list_dir
    │   ├── search.py                # grep, glob
    │   ├── shell.py                 # bash
    │   ├── web.py                   # web_fetch, http_request
    │   └── task.py                  # task (delega ao Orchestrator)
    ├── interfaces/
    │   ├── cli/                     # Typer + Rich: chat, build, run, demo, tools
    │   ├── discord/                 # stub
    │   ├── slack/                   # stub
    │   └── telegram/                # stub
    ├── mcp_server/                  # stub — expõe tools via MCP (FastMCP)
    └── mcp_client/                  # stub — consome servidores MCP externos
```

---

## Estado dos testes

```bash
uv run pytest            # 175 testes, 0 chamadas de rede
uv run ruff check .      # All checks passed
```

| Módulo de teste | O que cobre |
|----------------|-------------|
| `test_messages` | Serialização Message/ToolCall/ToolResult, round-trip |
| `test_provider` | Reparo de JSON, normalização de tool-calling |
| `test_permissions` | Todos os modos: auto, ask, deny, overrides por ferramenta |
| `test_agent` | Loop: negação, erro de ferramenta, max_iterations, múltiplas calls |
| `test_mock_provider` | Seleção heurística de ferramenta, sumarização, end-to-end offline |
| `test_content_generator` | 20 casos: todos os tipos de arquivo, detecção de tópico, substituição |
| `test_subagent_delegation` | Detecção de delegação, loop pai→filho, subagent_event_hook |
| `test_task` | TaskTool: spawn, resultado, erro |
| `test_project` | TaskGraph DAG, execução paralela, ciclo reviewer, integrator |
| `test_tools_*` | Todas as 10 ferramentas concretas |
| `test_run_once` | Pipeline CLI: single-shot, auto-approve |

---

## Roadmap

### ✅ Entregue (v0.1)

- [x] Loop de agente com gate de permissão (auto / ask / deny)
- [x] 10 ferramentas: read, write, edit, list, grep, glob, bash, web_fetch, http_request, task
- [x] Provider offline `MockProvider` — funciona sem API key
- [x] `ContentGenerator` — gera código real para 14+ tipos de arquivo
- [x] Subagentes com contexto isolado e streaming de eventos em tempo real
- [x] CLI completa: `chat`, `run`, `build`, `demo`, `tools`, `version`
- [x] `ProjectCrew` com DAG paralelo, reviewer, integrator
- [x] Personas em YAML: troca de modelo sem código
- [x] 175 testes, ruff limpo

### 🔧 Em andamento

- [ ] **`apathy create <tipo>`** — comando único que cria um projeto completo autonomamente (FastAPI, CLI, webapp, data) com o `MockProvider` guiando o agente por todas as etapas automaticamente
- [ ] **MCP Server** — expor o `ToolRegistry` via FastMCP para VS Code/Cursor/Claude Desktop
- [ ] **MCP Client** — consumir servidores MCP externos como ferramentas locais

### 📅 v0.2

- [ ] **Streaming de tokens** — emitir tokens conforme chegam em vez de esperar a resposta completa
- [ ] **Memória persistente** — backend SQLite/JSON para sessões que lembram de conversas anteriores
- [ ] **Web search** — DuckDuckGo/Brave/Serper como `WebSearchTool`
- [ ] **Tool calls paralelas** — executar múltiplas calls da mesma resposta com `asyncio.gather`
- [ ] **Retry com backoff** — retentar automaticamente erros de rate limit

### 📅 v0.3 — Bots de chat

- [ ] **Discord** — evento de mensagem → `Agent.run_turn()`, thread → `Session`
- [ ] **Telegram** — mesmo padrão, sem processo de aprovação para uso privado
- [ ] **Slack** — Socket Mode, OAuth scopes mínimos

### 📅 v0.4 — Observabilidade

- [ ] **OpenTelemetry spans** — tempo por tool call, modelo chamado, tokens consumidos
- [ ] **Dry-run global** — registra intenções sem executar
- [ ] **Limite de custo** — interromper quando custo estimado ultrapassar threshold
- [ ] **Validação de schema** — validar argumentos contra `input_schema` antes de chamar a ferramenta

### 📅 v0.5 — ProjectCrew avançado

- [ ] **Checkpoint e retomada** — salvar estado do `TaskGraph`; retomar build do ponto onde parou
- [ ] **Workspace sandboxado por tarefa** — cada agente escreve no próprio subdiretório
- [ ] **Tarefas dinâmicas** — agentes podem adicionar novas tarefas ao DAG durante a execução
- [ ] **Comunicação entre agentes** — canal de mensagens entre subagentes

---

## Licença

MIT
