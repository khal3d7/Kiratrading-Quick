#!/usr/bin/env bash
# Local launcher for kira-quick. Forces sqlite for development so it
# doesn't try to reuse the workspace's PostgreSQL DB. On Railway, the
# real env vars (TELEGRAM_BOT_TOKEN, DATABASE_URL=postgres://...) win
# because we only override here in the workspace.
set -e
cd "$(dirname "$0")"

# Local development overrides — applied only if not already set elsewhere.
export DATABASE_URL="${KIRA_DATABASE_URL:-sqlite:///trading.db}"
export PYTHONUNBUFFERED=1

exec python main.py
