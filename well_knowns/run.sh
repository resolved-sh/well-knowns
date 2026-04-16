#!/bin/bash
# well_knowns/run.sh — wrapper that sets API key from environment then runs the pipeline
# Usage: ./run.sh <phase> [extra args]
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
source .env 2>/dev/null || true
export RESOLVED_SH_API_KEY="${RESOLVED_SH_API_KEY:-$RESOLVED_API_KEY}"
exec python3 well_knowns/pipeline.py "$@"
