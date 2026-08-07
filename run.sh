#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Erstelle venv…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi

if [ ! -f .env ]; then
  echo "FEHLER: .env fehlt — 'cp .env.example .env' und ausfüllen." >&2
  exit 1
fi

exec ./.venv/bin/python -m bot.main
