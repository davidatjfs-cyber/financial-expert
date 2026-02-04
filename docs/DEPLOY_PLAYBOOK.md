---
description: Deployment playbook (non-git)
---

# Financial Expert — Deployment Playbook (Non-Git)

## Fixed project basics

- Server: `8.153.95.62`
- SSH user: `root`
- Deploy path on server: `/opt/financial-expert`
- Persistent data (DO NOT delete): `/opt/financial-expert/data` (mounted to container `/data`)

## When you do NOT use Git on the server

### A) Local → Server sync (recommended)

Run on your **local machine** from the repo root:

```bash
bash deploy/sync_to_server.sh
```

Notes:

- It **does not** overwrite server `.env`
- It **does not** touch server `data/` or `.data/`
- It excludes `.git/`, `hr-management-system/`, and big `*.tar.gz`

If you need to override target:

```bash
DEPLOY_SSH_HOST=root@8.153.95.62 DEPLOY_PATH=/opt/financial-expert bash deploy/sync_to_server.sh
```

### B) Build & restart on server

Run on the **server**:

```bash
cd /opt/financial-expert
DEPLOY_SKIP_GIT=1 bash ./deploy/deploy.sh
```

Healthcheck:

```bash
curl -sS http://127.0.0.1/api/version
```

## Safe cleanup (NO volume deletion)

Run on the **server**:

```bash
cd /opt/financial-expert
bash ./deploy/cleanup_safe.sh
```

This does **NOT** remove Docker volumes.

## Debug Starbucks/scanned PDF quickly

Temporarily enable debug in server `.env`:

```bash
PDF_TEXT_DEBUG=1
# optional tuning
PDF_TEXT_MIN_CHARS_FOR_NO_OCR=800
OCR_DPI=120
OCR_LANG=eng
OCR_AUTO_MAX_PDF_MB=25
OCR_AUTO_MAX_PAGECOUNT=300
```

Then redeploy:

```bash
cd /opt/financial-expert
DEPLOY_SKIP_GIT=1 bash ./deploy/deploy.sh
```

View logs:

```bash
docker compose logs -n 200 api
```
