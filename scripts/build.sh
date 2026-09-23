#!/usr/bin/env bash
# SupportIQ production build — everything that belongs to BUILD TIME
# (Fase 6). RUN TIME is gunicorn only: the app never runs npm itself.
#
# Target: Render Web Service → Build Command: `bash scripts/build.sh`
# Requires Node (npm) and Python available in the build image;
# frontend/dist is produced here and stays gitignored.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[build] frontend: npm ci + vite build -> frontend/dist"
command -v npm >/dev/null 2>&1 || {
  echo "[build] ERROR: npm not found — this build image has no Node.js" >&2
  exit 1
}
(
  cd frontend
  npm ci
  npm run build
)

echo "[build] backend: uv sync --frozen (locked by backend/uv.lock)"
(
  cd backend
  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
  fi
  uv sync --frozen
)

echo "[build] done: frontend/dist built, backend dependencies synced"
