# apathy

**Framework Python para agentes de IA autônomos com execução multi-agente paralela.**

Apathy não tem opinião sobre qual LLM você usa, como você organiza suas ferramentas ou onde roda seus agentes. Ele se preocupa com uma coisa: pegar seu objetivo e executar — silenciosamente, eficientemente, em paralelo quando possível.

```bash
# Conversa com um agente que usa ferramentas de verdade
apathy chat --persona personas/default.yaml

# Um time de agentes construindo um projeto inteiro, em paralelo
apathy build "API REST com FastAPI e frontend em HTML/JS" --workspace ./output
```

---

## Sumário

- [Por que apathy](#por-que-apathy)
- [Instalação](#instalação)
- [Início rápido](#início-rápido)
- [Comandos](#comandos)
  - [chat — agente conversacional](#chat--agente-conversacional)
  - [build — time de agentes em paralelo](#build--time-de-agentes-em-paralelo)
- [Personas](#personas)
- [Ferramentas](#ferramentas)
- [Arquitetura](#arquitetura)
- [Testes](#testes)
- [Roadmap e melhorias planejadas](#roadmap-e-melhorias-planejadas)

---

## Por que apathy

A maioria dos frameworks de agentes exige que você aprenda a abstração deles antes de fazer qualquer coisa. Apathy inverte isso: você descreve o que quer em YAML, escolhe o provedor de LLM, e o framework some.

**Sem lock-in de provedor.** A camada `ModelProvider` normaliza tool-calling para qualquer LLM — troca de modelo é uma linha no YAML. O parser de argumentos tenta reparar JSON malformado antes de falhar, o que importa ao usar modelos menores ou locais.

**Controle real sobre permissões.** Leitura é liberada automaticamente. Escrita, shell e requests HTTP passam pelo `PermissionGate` — no modo interativo, você aprova; no modo autônomo (`build`), uma política define o que roda sem interrupção.

**Multi-agente sem mágica.** `ProjectCrew` monta um DAG de tarefas, executa as independentes com `asyncio.gather`, e cada agente roda em contexto completamente isolado. Não há estado compartilhado entre agentes — só o workspace em disco.

**Personas são YAML.** Nenhum código Python para criar um agente diferente. System prompt, modelo, ferramentas permitidas, política de permissão — tudo num arquivo.

---

## Instalação

Requer **Python 3.11+** e [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/hfkyxg/hfkyxg
cd hfkyxg/agent-framework
uv sync --extra dev
cp .env.example .env
```

Configure ao menos uma chave de API:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OLLAMA_API_BASE=http://localhost:11434
```

---

## Início rápido

```bash
# Agente conversacional com ferramentas de arquivo e shell
apathy chat

# O agente lê arquivos de verdade, não alucina o conteúdo:
# you › leia o pyproject.toml e me diga o nome do projeto
#   ✓ read_file — [project]\nname = "apathy"...
# O projeto se chama "apathy", versão 0.1.0.

# Time de agentes construindo um projeto (requer API key)
apathy build "uma CLI de lista de tarefas em Python com SQLite" --workspace ./todo-cli
```

---

## Comandos

### `chat` — agente conversacional

Loop interativo com qualquer LLM. O agente usa ferramentas para agir no sistema real.

```bash
apathy chat --persona personas/default.yaml --workdir /meu/projeto
apathy chat --persona personas/researcher.yaml   # sem escrita/shell
```

Ações destrutivas (escrever arquivos, executar shell) pedem confirmação antes de rodar. Leitura e busca são liberadas automaticamente.

### `build` — time de agentes em paralelo

Para objetivos maiores que cabem em um único agente.

```bash
apathy build "backend FastAPI com auth JWT e frontend React" --workspace ./projeto
apathy build "script de scraping com exportação CSV e README" --workspace ./scraper
apathy build "..." --dry-run   # mostra o plano sem executar
```

**Fluxo interno do `build`:**

```
1. Planner decompõe o objetivo em tarefas JSON com dependências
2. TaskGraph identifica quais tarefas podem rodar em paralelo
3. asyncio.gather executa todas as tarefas prontas simultaneamente
4. Reviewer verifica cada entrega; se falhar → retrabalho (máx. 2 ciclos)
5. Integrator verifica que as partes funcionam juntas e escreve o resumo final
```

Progresso em tempo real no terminal:

```
╭─ apathy build ──────────────────────────────────╮
│  backend FastAPI com auth JWT e frontend React  │
╰──────────────────────────────────────────────────╯

  Plano de tarefas:
  ┌──────────┬──────────┬──────────────────────────────────┬────────────┐
  │ ID       │ Role     │ Descrição                        │ Depends on │
  ├──────────┼──────────┼──────────────────────────────────┼────────────┤
  │ setup_db │ backend  │ Criar modelos SQLAlchemy e DB    │ —          │
  │ setup_ui │ frontend │ Scaffold React + Vite            │ —          │
  │ auth_api │ backend  │ Endpoints JWT login/register     │ setup_db   │
  │ docker   │ infra    │ Dockerfile e docker-compose      │ auth_api   │
  └──────────┴──────────┴──────────────────────────────────┴────────────┘

  started    [backend]  setup_db
  started    [frontend] setup_ui     ← paralelo
  done       [backend]  setup_db
  done       [frontend] setup_ui
  started    [backend]  auth_api
  done       [backend]  auth_api
  started    [infra]    docker
  done       [infra]    docker

╭─ Build complete — SUCCESS ───────────────────────╮
│ Projeto criado em ./projeto/                     │
│  • backend/  FastAPI + SQLAlchemy + JWT          │
│  • frontend/ React + Vite                        │
│  • docker-compose.yml                            │
│ Para rodar: docker compose up                    │
╰──────────────────────────────────────────────────╯
```

---

## Personas

Um agente é completamente definido em YAML — sem código Python.

```yaml
# personas/researcher.yaml
name: researcher
system_prompt: |
  Você é um pesquisador cuidadoso. Investiga tópicos usando web e arquivos locais.
  Nunca modifica arquivos nem executa código. Sempre cita as fontes.
provider: "anthropic/claude-sonnet-4-6"
enabled_tools: [read_file, list_dir, grep, glob, web_fetch, http_request]
permission_overrides:
  - tool: http_request
    decision: ask
max_iterations: 15
temperature: 0.1
```

**Trocar de modelo é uma linha:**

```yaml
provider: "openai/gpt-4o"          # OpenAI
provider: "ollama/llama3.2"         # local via Ollama
provider: "groq/llama-3.3-70b"     # Groq (ultra-rápido)
provider: "mistral/mistral-large"   # Mistral
```

### Personas de papel — usadas pelo `build`

```
personas/roles/
├── planner.yaml      # decompõe o objetivo em JSON de tarefas
├── backend.yaml      # APIs, banco de dados, lógica de servidor
├── frontend.yaml     # UI, HTML/CSS/JS, React/Vue
├── infra.yaml        # Dockerfile, CI/CD, scripts de deploy
├── reviewer.yaml     # revisa entregas → {"ok": bool, "feedback": "..."}
└── integrator.yaml   # verifica integração, testa, escreve resumo final
```

Cada papel pode usar um modelo diferente — ex: planner num modelo forte de raciocínio, implementadores num modelo mais rápido e barato.

---

## Ferramentas

| Ferramenta    | O que faz                                              | Pede permissão? |
|---------------|--------------------------------------------------------|:---------------:|
| `read_file`   | Lê arquivo com offset/limit e numeração de linhas      | Não             |
| `list_dir`    | Lista um diretório                                     | Não             |
| `grep`        | Busca regex via ripgrep com filtro por extensão        | Não             |
| `glob`        | Encontra arquivos por padrão glob                      | Não             |
| `web_fetch`   | Busca URL e extrai texto limpo (remove HTML/scripts)   | Não             |
| `write_file`  | Cria ou sobrescreve arquivo (cria diretórios pai)      | **Sim**         |
| `edit_file`   | Substituição exata e única em arquivo existente        | **Sim**         |
| `bash`        | Executa comando shell (asyncio, timeout configurável)  | **Sim**         |
| `http_request`| HTTP com método, headers e body arbitrários            | **Sim**         |
| `task`        | Delega subtarefa a um subagente especialista isolado   | Não             |

---

## Arquitetura

```
src/agent_framework/
├── core/
│   ├── agent.py         # Agent.run_turn() — async generator de eventos
│   ├── provider.py      # ModelProvider: litellm + reparo de JSON malformado
│   ├── orchestrator.py  # Orchestrator.spawn_subagent() — contexto isolado
│   ├── project.py       # TaskGraph + ProjectCrew — execução paralela
│   ├── permissions.py   # PermissionGate: allow / deny / ask por ferramenta
│   ├── persona.py       # Persona: Pydantic + carregamento de YAML
│   ├── session.py       # Session: histórico imutável da conversa
│   ├── messages.py      # Message / ToolCall / ToolResult (agnóstico de provedor)
│   └── tool.py          # Tool (Protocol) + ToolRegistry + ToolContext
├── tools/               # 10 ferramentas prontas para uso
├── interfaces/
│   ├── cli/             # Typer + Rich: chat REPL + build command
│   ├── discord/         # stub
│   ├── slack/           # stub
│   └── telegram/        # stub
├── mcp_server/          # stub — expõe tools via MCP
├── mcp_client/          # stub — consome servidores MCP externos
└── config/              # pydantic-settings + .env
```

### O loop do agente

```
Entrada do usuário
      │
      ▼
 Agent.run_turn()                ← async generator; as interfaces consomem os eventos
      │
      ├──► provider.complete()  ──► LLM (qualquer via litellm)
      │           │
      │           ▼
      │     stop_reason == "end_turn"  ──► TurnCompleteEvent → encerra
      │     stop_reason == "tool_calls"
      │           │
      │           ▼
      │     para cada ToolCall (sequencialmente):
      │       ├── PermissionGate.check()
      │       │     allow → tool.run()    ──► resultado real
      │       │     deny  → ToolResult(is_error=True, "Permission denied")
      │       │     ask   → ask_callback() → allow ou deny
      │       └── ToolResultEvent
      │
      └──► loop (até persona.max_iterations)
```

---

## Testes

```bash
uv run pytest            # 136 testes sem chamadas de API (provider fake)
uv run ruff check .      # lint
```

Cobertura: serialização de mensagens, reparo de JSON, todas as decisões do `PermissionGate`, loop de agente (negação, erro de ferramenta, max_iterations, múltiplos tool calls simultâneos), spawn de subagentes, DAG de tarefas, execução paralela, ciclo de revisão/retrabalho, todas as 10 ferramentas concretas, pipeline end-to-end.

---

## Roadmap e melhorias planejadas

### Em andamento

- [ ] **MCP Server** — expor o `ToolRegistry` como servidor MCP via FastMCP (stdio + HTTP), permitindo que VS Code, Cursor e Claude Desktop usem as ferramentas do apathy nativamente sem extensão customizada
- [ ] **MCP Client** — consumir servidores MCP externos como ferramentas locais, expandindo o toolkit sem escrever código

### Próxima versão (v0.2)

- [ ] **Streaming de respostas** — fazer `Agent.run_turn()` emitir tokens conforme chegam em vez de esperar a resposta completa; necessário para UX responsiva no chat e para modelos com respostas longas
- [ ] **Memória persistente** — `Session` atual é efêmera; adicionar backend opcional (SQLite, JSON, Redis) para agentes que lembram de conversas anteriores e de artefatos já criados
- [ ] **Ferramenta de busca na web** — integrar DuckDuckGo/Brave/Serper como `WebSearchTool` com parsing de resultados, complementando o `web_fetch` que já existe
- [ ] **Execução paralela de tool calls** — quando o modelo retorna múltiplas tool calls numa resposta, executá-las com `asyncio.gather` em vez de sequencialmente (requer cuidado com dependências implícitas entre calls)

### v0.3 — Integrações de chat

- [ ] **Discord** — adaptador fino: evento de mensagem do bot → `Agent.run_turn()`, thread do Discord → `Session`; cada canal pode ter persona diferente
- [ ] **Telegram** — mesmo padrão; bot token, sem processo de aprovação para uso privado
- [ ] **Slack** — Socket Mode para evitar servidor público; OAuth scopes mínimos

### v0.4 — Observabilidade e controle

- [ ] **Traces estruturados** — emitir spans OpenTelemetry a partir dos eventos do loop; ver quanto tempo cada tool call levou, qual modelo foi chamado, quantos tokens consumiu
- [ ] **Modo dry-run global** — flag `--dry-run` que registra todas as intenções de ferramenta sem executar nenhuma; útil para auditar o que um agente faria antes de deixar rodar
- [ ] **Limite de custo** — interromper o loop quando o custo estimado (tokens × preço do modelo) ultrapassar um threshold configurável na persona
- [ ] **Dashboard de sessão** — view Rich ao vivo mostrando mensagens, tool calls e resultados de forma compacta durante execuções longas

### v0.5 — ProjectCrew avançado

- [ ] **Comunicação entre agentes** — canal de mensagens opcional para que subagentes possam consultar uns aos outros durante a execução (ex: frontend pergunta ao backend qual é o contrato da API)
- [ ] **Checkpoint e retomada** — salvar o estado do `TaskGraph` em disco; se o `build` falhar na metade, poder retomar do ponto onde parou sem refazer tarefas já concluídas
- [ ] **Workspace sandboxado por tarefa** — cada agente escreve apenas no próprio subdiretório (`workspace/<task_id>/`), merge feito pelo integrator; reduz conflitos em builds paralelos grandes
- [ ] **Tarefas dinâmicas** — permitir que agentes durante a execução adicionem novas tarefas ao DAG (ex: backend descobre que precisa de uma tarefa de migrations não prevista pelo planner)

### Melhorias de qualidade

- [ ] **Hardening com modelos locais** — testar e ajustar o parser de tool-calling com Ollama (Llama 3, Qwen, Mistral) e registrar quirks conhecidos por modelo; possível fallback para formato ReAct quando function-calling não está disponível
- [ ] **Validação de schema de ferramentas** — validar os argumentos contra o `input_schema` antes de chamar `tool.run()`, retornando erro descritivo em vez de stack trace quando o modelo passa tipos errados
- [ ] **Retry com backoff** — retentar automaticamente chamadas de API que falham por rate limit ou erro temporário, com backoff exponencial e limite de tentativas configurável
- [ ] **Compressão de contexto** — quando a sessão cresce demais, sumarizar as mensagens mais antigas para caber no context window sem perder o fio da conversa

### Ideias em exploração

- [ ] **Interface de voz** — transcrição (Whisper) → `Agent.run_turn()` → TTS; permitir conversar com o agente por áudio
- [ ] **Computer use** — capturar screenshot, enviar para modelo com capacidade de visão, executar cliques/teclas via ferramenta; permitir agentes que operam interfaces gráficas
- [ ] **Plugin system** — carregar ferramentas de pacotes externos via entry points, sem modificar o core; `apathy plugins list/install`
- [ ] **API server mode** — wrapper FastAPI que expõe `Agent.run_turn()` como endpoint HTTP/SSE, transformando qualquer persona em microserviço de agente

---

## Licença

MIT
