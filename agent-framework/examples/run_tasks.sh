#!/usr/bin/env bash
# Reproducible demonstration of apathy executing real tasks — NO API key needed.
# Each call drives one full agent turn (tool call -> permission -> real execution).
set -euo pipefail
cd "$(dirname "$0")/.."

PERSONA=personas/demo.yaml
WORK=$(mktemp -d -t apathy-tasks-XXXX)
echo "workspace: $WORK"

echo "== task 1: write a file with real content =="
uv run apathy run "escreva o arquivo $WORK/hello.md com conteúdo # Hello from apathy" \
  --persona "$PERSONA" --yes

echo "== task 2: read it back =="
uv run apathy run "leia o arquivo $WORK/hello.md" --persona "$PERSONA" --yes

echo "== task 3: run a real shell command =="
uv run apathy run "rode: echo apathy executed this" --persona "$PERSONA" --yes

echo "== task 4: search the project =="
uv run apathy run "busque MockProvider src" --persona "$PERSONA" --yes

echo "done. artifacts in: $WORK"
