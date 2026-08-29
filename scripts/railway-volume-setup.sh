#!/usr/bin/env bash
# railway-volume-setup.sh
# One-shot volume provisioning for the PersonalOpenSourceWebsite service on Railway.
#
# WHY: Django settings.py resolves the SQLite DB as BASE_DIR/'db.sqlite3' by
# default, or DATABASE_PATH if set. The Dockerfile WORKDIR is /app, so
# BASE_DIR == /app. Railway containers are ephemeral; the only writable,
# persistent storage is a mounted volume. We therefore mount a volume at
# /data and point Django at /data/db.sqlite3 via the DATABASE_PATH env var
# (settings.py change lives in the modernization track, t_17b40095 "Deploy:
# rewrite Dockerfile for Railway").
#
# Prerequisites:
#   - railway CLI (installed at ~/.local/bin/railway, v5.30.4+)
#   - authenticated: RAILWAY_TOKEN env var, or `railway login` (browser)
#   - linked to the project: run from the repo root after `railway link`
#
# Usage:
#   ./railway-volume-setup.sh [SERVICE_NAME]
#
# Idempotent: safe to re-run; existing volume is detected and kept.

set -euo pipefail

RAILWAY="${RAILWAY_BIN:-$HOME/.local/bin/railway}"
SERVICE="${1:-PersonalOpenSourceWebsite}"
VOLUME_MOUNT_PATH="/data"

echo "== railway-volume-setup =="
echo "service:          $SERVICE"
echo "volume mount:     $VOLUME_MOUNT_PATH"
echo

# --- sanity checks ----------------------------------------------------------
if ! "$RAILWAY" whoami >/dev/null 2>&1; then
    echo "ERROR: not authenticated. Set RAILWAY_TOKEN or run 'railway login'." >&2
    exit 1
fi

if ! "$RAILWAY" status >/dev/null 2>&1; then
    echo "ERROR: not linked to a Railway project. Run 'railway link' from the repo root first." >&2
    exit 1
fi

echo "Auth OK, project linked:"
"$RAILWAY" status
echo

# --- volume creation --------------------------------------------------------
# Railway volumes are per-service. The CLI (v5) exposes volume management via
# `railway volume` subcommands; if the installed build lacks them, fall back
# to the GraphQL API with the session token.
if "$RAILWAY" volume list --service "$SERVICE" 2>/dev/null | grep -q "$VOLUME_MOUNT_PATH"; then
    echo "Volume already mounted at $VOLUME_MOUNT_PATH on $SERVICE - nothing to do."
else
    echo "Creating volume mounted at $VOLUME_MOUNT_PATH on $SERVICE ..."
    if "$RAILWAY" volume --help >/dev/null 2>&1; then
        "$RAILWAY" volume add --service "$SERVICE" --mount-path "$VOLUME_MOUNT_PATH"
    else
        echo "ERROR: this railway CLI build lacks 'volume' subcommands." >&2
        echo "Either upgrade the CLI or create the volume in the dashboard:" >&2
        echo "  Project -> $SERVICE -> Settings -> Volumes -> + New Volume" >&2
        echo "  Mount path: $VOLUME_MOUNT_PATH" >&2
        exit 2
    fi
fi

echo
echo "Volume state after run:"
"$RAILWAY" volume list --service "$SERVICE" || true

cat <<EOF

Next steps (not automated here on purpose):
1. Set DATABASE_PATH=/data/db.sqlite3 on the Railway service.
2. Seed the volume from the LOCAL sanitized copy at
   /home/slab/sandboxes/hermes-wren/work/prod-import/db.seed.sqlite3
   That file is intentionally NOT in git (PII hygiene). Do not invent a
   repo path for it. If the file is missing, stop; do not ship an empty DB.
   After the 2026-08-17 repair, contactme tables exist again. If you still
   have an older seed, fake-unapply contactme then migrate before copy.
3. Required env: SECRET_KEY, ALLOWED_HOSTS=mslevin.dev,www.mslevin.dev,
   DEBUG=False, plus DJANGO_SUPERUSER_* if you want a fresh admin user.
4. Redeploy the service so the mount takes effect: railway up / redeploy.
EOF
