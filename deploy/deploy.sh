#!/usr/bin/env bash
set -euo pipefail

# Run from repo root (e.g. /opt/financial-expert)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

DEPLOY_SKIP_GIT="${DEPLOY_SKIP_GIT:-0}"

if [ -f ./.env ]; then
  set -a
  . ./.env
  set +a
fi

REV="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
export APP_REV="${APP_REV:-$REV}"

echo "[deploy] git revision: ${REV}"
echo "[deploy] APP_REV: ${APP_REV}"

if [ "${DEPLOY_SKIP_GIT}" != "1" ]; then
  echo "[deploy] sync source"
  git fetch --all
  git reset --hard origin/main
  git clean -fd
else
  echo "[deploy] skip git sync (DEPLOY_SKIP_GIT=1)"
fi

echo "[deploy] build images"
docker compose down

docker compose build --no-cache api frontend

echo "[deploy] start services"
docker compose up -d

echo "[deploy] wait for /api/version"
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1/api/version >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" = "30" ]; then
    echo "[deploy] ERROR: /api/version not healthy after 30s" >&2
    docker compose ps
    exit 1
  fi
done

curl -fsS http://127.0.0.1/api/version || true

echo "[deploy] done"
