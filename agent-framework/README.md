# NEXO

> **O ponto de conexão entre sua intenção e a execução inteligente.**

NEXO é um framework Python para construir agentes de IA que realmente fazem coisas — leem arquivos, rodam código, navegam na web, e quando o objetivo é grande demais para um agente só, formam um **time de especialistas que trabalha em paralelo**.

```bash
# Um agente conversacional
nexo chat --persona personas/default.yaml

# Um time de agentes construindo um projeto inteiro
nexo build "uma API REST de tarefas com FastAPI e frontend em HTML/JS" --workspace ./saida
```

---

## Por que NEXO existe

A maioria dos frameworks de agentes te força a escolher: ou você usa um único provedor de LLM, ou aceita uma camada de abstração opaca que "funciona na demo mas falha na prática". NEXO resolve isso de outra forma:

**Uma camada de normalização real.** O `ModelProvider` traduz a resposta de qualquer LLM — cloud ou local — para um formato interno único. Troca de modelo é uma linha no YAML. Tool-calling quebrado em algum modelo menor? O parser de argumentos tenta reparar o JSON antes de desistir.

**Controle total sobre permissões.** Cada ação arriscada (escrever arquivos, rodar shell, fazer requests HTTP) passa por um `PermissionGate` configurável. No modo interativo, o usuário aprova. No modo autônomo, uma política define o que é liberado automaticamente.

**Subagentes de verdade.** Um agente pode delegar subtarefas a outros agentes isolados via ferramenta `task`. Cada subagente tem contexto zerado, conjunto de ferramentas restrito e retorna apenas o resultado — sem vazar o histórico da conversa pai.

**Execução paralela.** O comando `build` monta um DAG de tarefas, identifica quais podem rodar ao mesmo tempo e as executa com `asyncio.gather`. Backend e frontend sendo escritos simultaneamente, não em série.

---

## Instalação

Requer **Python 3.11+** e [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/hfkyxg/hfkyxg
cd hfkyxg/agent-framework
uv sync --extra dev
cp .env.example .env
```

Configure pelo menos uma chave de API no `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # opcional
OLLAMA_API_BASE=http://localhost:11434  # para modelos locais
```

---

## Modos de uso

### `nexo chat` — Agente conversacional

Conversa interativa com qualquer LLM. O agente usa ferramentas para responder com dados reais, não alucinados.

```bash
nexo chat --persona personas/default.yaml --workdir /meu/projeto
```

Exemplo de sessão:

```
you › leia o pyproject.toml e me diga as dependências principais
  ✓ read_file: 1  [project]\nname = "nexo"\n...
O projeto chama "nexo" e depende de litellm, pydantic, typer e rich.

you › agora liste os arquivos em src/
  ✓ list_dir: agent_framework/  config/  core/  interfaces/  tools/ ...
```

Ações que modificam arquivos ou executam shell pedem sua confirmação antes de rodar.

### `nexo build` — Time de agentes em paralelo

Para objetivos maiores. Um agente **planejador** decompõe o objetivo em tarefas, um time de **especialistas** as executa em paralelo, um **revisor** verifica cada entrega, e um **integrador** faz a passada final.

```bash
nexo build "um sistema de blog com backend FastAPI e frontend React" \
  --workspace ./blog-project

nexo build "um script Python de scraping com exportação para CSV" \
  --workspace ./scraper \
  --dry-run   # só mostra o plano, não executa
```

O progresso aparece em tempo real:

```
  started              [backend]  setup_api
  started              [frontend] setup_ui      ← rodando ao mesmo tempo
  done                 [backend]  setup_api
  done                 [frontend] setup_ui
  started              [infra]    dockerfile
  done                 [infra]    dockerfile
╭─ Build complete — SUCCESS ──────────────────╮
│ Estrutura criada em ./blog-project:         │
│  • backend/ (FastAPI + SQLite)              │
│  • frontend/ (React + Vite)                 │
│  • docker-compose.yml                       │
│ Para rodar: docker compose up               │
╰─────────────────────────────────────────────╯
```

---

## Personas — agentes sem código

Cada agente é definido em YAML. Nenhum Python necessário para criar comportamentos diferentes.

```yaml
# personas/researcher.yaml
name: researcher
system_prompt: |
  Você é um pesquisador cuidadoso. Nunca modifica arquivos nem executa código.
  Sempre cite as fontes usadas.
provider: "anthropic/claude-sonnet-4-6"
enabled_tools: [read_file, list_dir, grep, web_fetch, http_request]
permission_overrides:
  - tool: http_request
    decision: ask     # pede confirmação para qualquer request
max_iterations: 15
temperature: 0.1
```

Trocar de modelo é uma linha:

```yaml
provider: "openai/gpt-4o"       # GPT-4o
provider: "ollama/llama3.2"     # modelo local via Ollama
provider: "groq/llama-3.3-70b"  # Groq (inferência rápida)
```

### Personas de papel (para `nexo build`)

```
personas/roles/
├── planner.yaml      # decompõe o objetivo em tarefas JSON
├── backend.yaml      # implementa APIs, banco de dados, lógica
├── frontend.yaml     # implementa UI, HTML/CSS/JS, React
├── infra.yaml        # Dockerfile, CI/CD, scripts de deploy
├── reviewer.yaml     # revisa cada entrega e devolve feedback estruturado
└── integrator.yaml   # verifica que as partes funcionam juntas
```

Você pode substituir qualquer papel por um modelo diferente — ex: planner rodando num modelo mais forte enquanto os implementadores usam algo mais rápido e barato.

---

## Arquitetura

```
src/agent_framework/
├── core/
│   ├── provider.py      # ModelProvider: wrapper litellm com reparo de JSON
│   ├── agent.py         # Agent.run_turn(): loop assíncrono gerador de eventos
│   ├── orchestrator.py  # Orchestrator.spawn_subagent(): subagente isolado
│   ├── project.py       # TaskGraph + ProjectCrew: time paralelo de agentes
│   ├── permissions.py   # PermissionGate: allow/deny/ask por ferramenta
│   ├── persona.py       # Persona: carregada de YAML via Pydantic
│   ├── session.py       # Session: histórico da conversa
│   ├── messages.py      # Message / ToolCall / ToolResult (formato interno)
│   └── tool.py          # Tool (Protocol) + ToolRegistry
├── tools/
│   ├── files.py         # read_file, write_file, edit_file, list_dir
│   ├── shell.py         # bash (asyncio subprocess, timeout configurável)
│   ├── search.py        # grep (via ripgrep), glob
│   ├── web.py           # web_fetch (HTML → texto), http_request
│   └── task.py          # task: delega subtarefa a um subagente especialista
├── interfaces/
│   ├── cli/             # Typer + Rich: chat REPL e comando build
│   ├── discord/         # stub — Fase 5
│   ├── slack/           # stub — Fase 5
│   └── telegram/        # stub — Fase 5
├── mcp_server/          # stub — expõe tools via MCP (Fase 4)
├── mcp_client/          # stub — consome servidores MCP externos (Fase 4)
└── config/              # pydantic-settings (.env)
```

### Como o loop funciona

```
Entrada do usuário
      │
      ▼
 Agent.run_turn()           ← async generator de eventos
      │
      ├─ provider.complete() ──► LLM (qualquer provedor via litellm)
      │        │
      │        ▼
      │   ProviderResponse
      │   ├─ end_turn  ──► TurnCompleteEvent → fim
      │   └─ tool_calls
      │        │
      │        ▼
      │   para cada ToolCall:
      │   ├─ PermissionGate.check() ──► allow/deny/ask
      │   ├─ tool.run() ──► resultado real (arquivo, shell, web...)
      │   └─ ToolResultEvent
      │
      └─ loop (até max_iterations)
```

---

## Ferramentas disponíveis

| Ferramenta | O que faz | Pede permissão? |
|---|---|:---:|
| `read_file` | Lê arquivo com offset/limit e numeração de linhas | Não |
| `list_dir` | Lista um diretório | Não |
| `grep` | Busca regex via ripgrep | Não |
| `glob` | Encontra arquivos por padrão | Não |
| `web_fetch` | Busca URL, extrai texto limpo (remove HTML) | Não |
| `write_file` | Cria ou sobrescreve arquivo | **Sim** |
| `edit_file` | Substituição exata e única em arquivo existente | **Sim** |
| `bash` | Executa comando shell (timeout configurável) | **Sim** |
| `http_request` | Request HTTP com método/headers/body | **Sim** |
| `task` | Delega subtarefa a um subagente especialista | Não |

---

## Testes

```bash
uv run pytest           # 136 testes, sem chamadas de API (provider fake)
uv run ruff check .     # lint
```

Os testes cobrem: serialização de mensagens, reparo de JSON malformado, todas as decisões do PermissionGate, loop de agente (denial, erro de ferramenta, max_iterations, multi-tool), spawn de subagentes, DAG de tarefas, execução paralela, loop de revisão, todas as ferramentas concretas.

---

## Roadmap

| Fase | Status |
|------|--------|
| Core: loop de agente + provider multi-LLM + ferramentas + CLI | ✅ Pronto |
| TaskTool + ProjectCrew + execução paralela + `nexo build` | ✅ Pronto |
| Servidor MCP (expõe tools para VS Code/outros clientes) | 🔜 Próxima |
| Cliente MCP (consome servidores externos como tools) | 🔜 Próxima |
| Bots de chat (Discord, Telegram, Slack) | 🔜 Planejado |

---

## Licença

MIT
