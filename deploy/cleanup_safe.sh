#!/usr/bin/env bash
set -euo pipefail

# Safe cleanup: do NOT delete Docker volumes.
# Run from repo root (e.g. /opt/financial-expert)

if [ -f ./.env ]; then
  set -a
  . ./.env
  set +a
fi

echo "[cleanup] stopping compose (if running)"
docker compose down || true

echo "[cleanup] remove stopped containers"
docker container prune -f

echo "[cleanup] remove unused networks"
docker network prune -f

echo "[cleanup] remove unused images (no volumes)"
docker image prune -af

echo "[cleanup] remove build cache"
docker builder prune -af

echo "[cleanup] done (volumes preserved)"
