#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -f backend/app.py ]; then
  exec gunicorn --chdir backend app:app --bind "0.0.0.0:${PORT:-10000}"
fi
exec gunicorn app:app --bind "0.0.0.0:${PORT:-10000}"
