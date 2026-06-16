# agent-framework

Framework Python reutilizável para construir seus próprios agentes de IA — combinando o
melhor de **Claude Code**, sistemas multi-agente estilo **Cowork**, o tool-calling robusto
da família **Hermes** e bots de ação autônoma estilo **Clawbot**.

A ideia: um único núcleo que funciona com **vários provedores de LLM** (Claude, OpenAI,
modelos locais/abertos via Ollama), expõe **várias ferramentas** e pode ser integrado em
**vários sistemas e apps** (terminal, bots de chat, editores via MCP).

## Por que existe

- **Multi-provedor de verdade**: a camada `ModelProvider` (sobre o `litellm`) normaliza
  tool-calling para que o comportamento seja o mesmo, seja Claude, GPT ou um modelo
  Hermes local — você troca o modelo numa linha do YAML, sem mexer no código.
- **Estilo Claude Code**: loop agente com uso de ferramentas, gate de permissão antes de
  ações arriscadas (ler é liberado, escrever/rodar shell pedem confirmação) e uma CLI
  interativa agradável.
- **Multi-agente (Cowork)**: um orquestrador pode delegar subtarefas a subagentes
  isolados, cada um com seu contexto e seu conjunto restrito de ferramentas.
- **Pluggável**: ferramentas, provedores e interfaces são todos intercambiáveis. Defina
  "personas" em YAML para criar agentes diferentes sem escrever Python.

## Estado atual

| Fase | O que entrega | Status |
|------|---------------|--------|
| 0 | Scaffold (pyproject, lint, testes, CI) | ✅ pronto |
| 1 | Núcleo: loop de agente + provider multi-LLM + ferramentas + CLI REPL | ✅ pronto |
| 2 | Permissões completas + mais ferramentas + subagentes | 🔜 planejado |
| 3 | Time de agentes que constrói um sistema inteiro (paralelo) | 🔜 planejado |
| 4 | Servidor/cliente MCP (+ integração VS Code) | 🔜 stub |
| 5–6 | Bots de chat (Discord, Telegram, Slack) | 🔜 stub |

## Instalação

Requer Python 3.11+ e [`uv`](https://docs.astral.sh/uv/).

```bash
cd agent-framework
uv sync --extra dev
cp .env.example .env   # preencha pelo menos ANTHROPIC_API_KEY
```

## Uso

Inicie um chat interativo com a persona padrão (Claude):

```bash
uv run agent-framework --persona personas/default.yaml --workdir .
```

Peça para o agente, por exemplo: *"leia o pyproject.toml e me diga o nome do projeto"* —
ele vai usar a ferramenta `read_file`, receber o conteúdo real e responder com base nele.
Ações que mudam arquivos ou rodam shell pedem sua confirmação antes de executar.

## Estrutura

```
src/agent_framework/
├── core/         # provider (litellm), agent loop, tools, permissões, sessão, persona, orchestrator
├── tools/        # read/write/edit file, bash, grep/glob, web_fetch, http_request
├── interfaces/   # cli (Typer+Rich) — discord/slack/telegram são stubs das próximas fases
├── mcp_server/   # expõe as ferramentas via MCP (stub, Fase 4)
├── mcp_client/   # consome servidores MCP externos (stub, Fase 4)
└── config/       # settings (pydantic-settings)
personas/         # configs YAML de agentes (default, researcher)
tests/            # testes unitários (provider fake — não precisa de API key)
```

## Personas

Um agente é definido em YAML — sem código. Exemplo (`personas/researcher.yaml`):

```yaml
name: researcher
system_prompt: |
  Você é um assistente de pesquisa cuidadoso. Nunca modifica arquivos
  nem roda shell. Sempre cite as URLs usadas.
provider: "anthropic/claude-sonnet-4-6"   # troque por "openai/gpt-4o" ou "ollama/hermes3"
enabled_tools: [read_file, list_dir, grep, glob, web_fetch, http_request]
permission_overrides:
  - tool: web_fetch
    decision: allow
max_iterations: 15
temperature: 0.1
```

Isso prova os três eixos de reusabilidade: trocar `provider` (multi-provedor), trocar
`enabled_tools` (toolset pluggável) e `permission_overrides` (política por ferramenta).

## Testes

```bash
uv run pytest        # 12 testes, sem chamadas de rede (usa um provider fake)
uv run ruff check .  # lint
```
