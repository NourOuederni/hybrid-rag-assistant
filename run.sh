#!/usr/bin/env bash
# Start the web app on http://localhost:8000
set -e
cd "$(dirname "$0")"
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 "$@"
