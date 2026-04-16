#!/usr/bin/env bash
# Full operating cycle: fetch domains → crawl → generate → upload → enrich
# Usage: bash scripts/cycle.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$REPO_ROOT/.env" 2>/dev/null || true

API_KEY="${RESOLVED_API_KEY:-}"
if [ -z "$API_KEY" ]; then
  echo "ERROR: RESOLVED_API_KEY not set in .env"
  exit 1
fi

echo "=== Well Knowns Full Cycle ==="
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

echo "--- Step 1: Fetch latest Tranco domain list ---"
cd "$REPO_ROOT"
python3 well_knowns/fetch_domains.py

echo ""
echo "--- Step 2: Crawl well-known endpoints ---"
python3 well_knowns/crawl_improved.py

echo ""
echo "--- Step 3: Generate datasets + upload + patch + enrich ---"
bash "$REPO_ROOT/post-crawl.sh"

echo ""
echo "=== Cycle complete ==="
echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
