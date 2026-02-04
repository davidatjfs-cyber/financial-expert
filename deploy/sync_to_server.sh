#!/usr/bin/env bash
set -euo pipefail

# Sync local repo contents to server WITHOUT relying on git.
# Defaults are set for this project.

DEPLOY_SSH_HOST="${DEPLOY_SSH_HOST:-root@8.153.95.62}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/financial-expert}"

# Run from local repo root.

echo "[sync] -> ${DEPLOY_SSH_HOST}:${DEPLOY_PATH}"

RSYNC_PROGRESS_FLAG="--progress"
if rsync --version 2>/dev/null | head -n 1 | grep -qE "version 3\.[0-9]+\.[0-9]+"; then
  RSYNC_PROGRESS_FLAG="--info=progress2"
fi

# Be safe: do NOT delete remote files; do NOT overwrite server .env; do NOT touch persistent data.
rsync -az \
  ${RSYNC_PROGRESS_FLAG} \
  --exclude ".git/" \
  --exclude ".env" \
  --exclude "data/" \
  --exclude ".data/" \
  --exclude "hr-management-system/" \
  --exclude "*.tar.gz" \
  ./ "${DEPLOY_SSH_HOST}:${DEPLOY_PATH}/"

echo "[sync] done"
