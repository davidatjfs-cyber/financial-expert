#!/usr/bin/env bash
set -euo pipefail

# Sync local repo contents to server WITHOUT relying on git.
# Defaults are set for this project.

DEPLOY_SSH_HOST="${DEPLOY_SSH_HOST:-root@8.153.95.62}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/financial-expert}"

# Run from local repo root.

echo "[sync] -> ${DEPLOY_SSH_HOST}:${DEPLOY_PATH}"

# Be safe: do NOT delete remote files; do NOT overwrite server .env; do NOT touch persistent data.
rsync -az \
  --info=progress2 \
  --exclude ".git/" \
  --exclude ".env" \
  --exclude "data/" \
  --exclude ".data/" \
  --exclude "hr-management-system/" \
  --exclude "*.tar.gz" \
  ./ "${DEPLOY_SSH_HOST}:${DEPLOY_PATH}/"

echo "[sync] done"
