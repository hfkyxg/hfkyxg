#!/usr/bin/env bash
# Demonstrates apathy building a complete FastAPI project from scratch.
# No API key required — uses the offline MockProvider.
#
# What it creates:
#   main.py          — FastAPI application with CRUD endpoints
#   models.py        — Pydantic data models
#   config.json      — App configuration
#   requirements.txt — Python dependencies
#   Dockerfile       — Container image
#   .env.example     — Environment variable template
#   .gitignore       — Git ignore patterns
#   Makefile         — Dev shortcuts
#   tests/test_app.py — Pytest test suite
#   README.md        — Project documentation
#
# Usage:
#   ./examples/build_fastapi_project.sh
#   ./examples/build_fastapi_project.sh /tmp/my-custom-workspace
set -euo pipefail
cd "$(dirname "$0")/.."

PERSONA=personas/demo.yaml
WORK="${1:-$(mktemp -d -t apathy-fastapi-XXXX)}"
mkdir -p "$WORK" "$WORK/tests"
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        apathy  ·  FastAPI Project Builder Demo               ║"
echo "║        workspace: $WORK"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

run() {
  local step="$1" task="$2"
  echo "── step $step ──────────────────────────────────────────────────────────"
  uv run apathy run "$task" --persona "$PERSONA" --yes
  echo ""
}

run 1  "escreva o arquivo $WORK/main.py — uma aplicação fastapi com rotas CRUD para items"
run 2  "escreva o arquivo $WORK/requirements.txt para um projeto fastapi com uvicorn e pydantic"
run 3  "escreva o arquivo $WORK/config.json — configuração do app fastapi"
run 4  "escreva o arquivo $WORK/Dockerfile — imagem Docker para fastapi"
run 5  "escreva o arquivo $WORK/.env.example — variáveis de ambiente do projeto"
run 6  "escreva o arquivo $WORK/.gitignore — padrões git para projeto python"
run 7  "escreva o arquivo $WORK/Makefile — targets: install test lint run clean"
run 8  "escreva o arquivo $WORK/tests/test_app.py — testes pytest para o app fastapi"
run 9  "escreva o arquivo $WORK/README.md — documentação do projeto fastapi"
run 10 "liste o diretório $WORK"
run 11 "rode: echo '--- verificando arquivos gerados ---' && wc -l $WORK/*.py $WORK/*.txt $WORK/*.json $WORK/Makefile $WORK/Dockerfile $WORK/README.md $WORK/tests/*.py 2>/dev/null | tail -1"
run 12 "busque FastAPI $WORK/main.py"

echo "═══════════════════════════════════════════════════════════════"
echo " Projeto gerado em: $WORK"
echo " Arquivos criados:"
ls -la "$WORK"/*.py "$WORK"/*.txt "$WORK"/*.json "$WORK"/Makefile "$WORK"/Dockerfile "$WORK"/README.md "$WORK"/.env.example "$WORK"/.gitignore "$WORK"/tests/ 2>/dev/null || true
echo ""
echo " Para usar com uma API key real:"
echo "   export ANTHROPIC_API_KEY=sk-..."
echo "   cp personas/default.yaml personas/real.yaml  # edit provider:"
echo "   uv run apathy chat --persona personas/real.yaml"
echo "═══════════════════════════════════════════════════════════════"
