#!/bin/sh
set -eu
export PORT="${PORT:-3000}"
export SQLITE_PATH="${SQLITE_PATH:-/data/one-api.db?_busy_timeout=30000}"
export HF_DATASET_REPO="${HF_DATASET_REPO:-hoshisakihk/new-api-sqlite-backup}"
mkdir -p /data

# Restore latest SQLite backup if local DB does not exist.
python3 /backup-loop.py restore || true

# Start periodic backup loop in background.
python3 /backup-loop.py loop &

exec /new-api
