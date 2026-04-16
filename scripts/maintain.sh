#!/usr/bin/env bash
# Health check: verify resolved.sh registration, data freshness, and pipeline readiness
# Usage: bash scripts/maintain.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$REPO_ROOT/.env" 2>/dev/null || true

API_KEY="${RESOLVED_API_KEY:-}"
RESOURCE_ID="${RESOLVED_RESOURCE_ID:-ef9f56ad-11a4-43e7-9171-fd108d194ad8}"

echo "=== Well Knowns Health Check ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# Check env vars
echo "--- Environment ---"
if [ -n "$API_KEY" ]; then
  echo "  RESOLVED_API_KEY:    set"
else
  echo "  RESOLVED_API_KEY:    MISSING"
fi
echo "  RESOLVED_RESOURCE_ID: ${RESOURCE_ID:-MISSING}"
echo "  EVM_PRIVATE_KEY:     ${EVM_PRIVATE_KEY:+set}${EVM_PRIVATE_KEY:-MISSING}"
echo "  EVM_PUBLIC_ADDRESS:  ${EVM_PUBLIC_ADDRESS:-MISSING}"
echo ""

# Check registration
echo "--- Registration ---"
if [ -n "$API_KEY" ]; then
  REG_RESPONSE=$(curl -sf "https://resolved.sh/listing/$RESOURCE_ID" \
    -H "Authorization: Bearer $API_KEY" 2>/dev/null || echo "FAILED")
  if [ "$REG_RESPONSE" != "FAILED" ]; then
    echo "  Status: reachable"
    echo "  Listing: https://well-knowns.resolved.sh"
  else
    echo "  Status: UNREACHABLE (check API key and resource ID)"
  fi
else
  echo "  Status: SKIPPED (no API key)"
fi
echo ""

# Check data freshness
echo "--- Data Freshness ---"
DATA_DIR="$REPO_ROOT/data"
if ls "$DATA_DIR"/full-catalog-*.jsonl 1>/dev/null 2>&1; then
  LATEST=$(ls -t "$DATA_DIR"/full-catalog-*.jsonl | head -1)
  LATEST_NAME=$(basename "$LATEST")
  LATEST_DATE=$(echo "$LATEST_NAME" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
  echo "  Latest catalog: $LATEST_NAME"
  echo "  Crawl date:     $LATEST_DATE"

  # Check age
  if command -v gdate &>/dev/null; then
    DATE_CMD="gdate"
  else
    DATE_CMD="date"
  fi
  CRAWL_EPOCH=$($DATE_CMD -d "$LATEST_DATE" +%s 2>/dev/null || echo "0")
  NOW_EPOCH=$($DATE_CMD +%s)
  if [ "$CRAWL_EPOCH" != "0" ]; then
    AGE_DAYS=$(( (NOW_EPOCH - CRAWL_EPOCH) / 86400 ))
    echo "  Age:            ${AGE_DAYS} days"
    if [ "$AGE_DAYS" -gt 7 ]; then
      echo "  ⚠ Data is stale (>7 days). Run: bash scripts/cycle.sh"
    else
      echo "  Data is fresh."
    fi
  fi
else
  echo "  No catalog found. Run: bash scripts/cycle.sh"
fi
echo ""

# Check pipeline readiness
echo "--- Pipeline Readiness ---"
MISSING=""
for f in well_knowns/crawl_improved.py well_knowns/generate_improved.py well_knowns/upload.py pipeline/enrich.py post-crawl.sh; do
  if [ ! -f "$REPO_ROOT/$f" ]; then
    MISSING="$MISSING $f"
  fi
done
if [ -z "$MISSING" ]; then
  echo "  All pipeline scripts present."
else
  echo "  MISSING:$MISSING"
fi

# Check Python deps
if python3 -c "import httpx" 2>/dev/null; then
  echo "  Python httpx: installed"
else
  echo "  Python httpx: MISSING (pip install httpx)"
fi
echo ""

echo "=== Health check complete ==="
