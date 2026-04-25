#!/usr/bin/env bash
# Post-crawl pipeline: generate datasets + upload to resolved.sh + patch descriptions
# Run after crawl_improved.py finishes.
# Usage: bash post-crawl.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$REPO_ROOT/.env" 2>/dev/null || true

API_KEY="${RESOLVED_API_KEY:-}"
RESOURCE_ID="${RESOLVED_RESOURCE_ID:-ef9f56ad-11a4-43e7-9171-fd108d194ad8}"

if [ -z "$API_KEY" ]; then
  echo "ERROR: RESOLVED_API_KEY not set in .env"
  exit 1
fi

echo "=== Step 1: Generate datasets ==="
cd "$REPO_ROOT"
python3 well_knowns/generate_improved.py

echo ""
echo "=== Step 2: Upload to resolved.sh ==="
python3 well_knowns/upload.py --api-key "$API_KEY" --replace

echo ""
echo "=== Step 3: Patch descriptions on uploaded files ==="
DATE=$(date +%Y-%m-%d)

# Get file IDs
FILES_JSON=$(curl -sf "https://resolved.sh/listing/$RESOURCE_ID/data" \
  -H "Authorization: Bearer $API_KEY")

patch_description() {
  local FILENAME="$1"
  local DESCRIPTION="$2"
  local QUERY_PRICE="$3"
  local DOWNLOAD_PRICE="$4"

  FILE_ID=$(echo "$FILES_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for f in d.get('files', []):
    if f['filename'] == '$FILENAME':
        print(f['id'])
        break
" 2>/dev/null)

  if [ -z "$FILE_ID" ]; then
    echo "  WARN: $FILENAME not found in listing"
    return
  fi

  RESP=$(curl -s -X PATCH "https://resolved.sh/listing/$RESOURCE_ID/data/$FILE_ID" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"description\": \"$DESCRIPTION\", \"query_price_usdc\": $QUERY_PRICE, \"download_price_usdc\": $DOWNLOAD_PRICE}")
  if echo "$RESP" | grep -q '"detail"'; then
    echo "  FAIL $FILENAME: $RESP" | head -c 300
    echo ""
  else
    echo "  OK $FILENAME"
  fi
}

patch_description "full-catalog-${DATE}.jsonl" \
  "Complete /.well-known/ catalog across the Tranco top 100k domains. Seven endpoint types: agent-card.json, mcp.json, oauth-protected-resource, openid-configuration, oauth-authorization-server, security.txt, host-meta. One row per (domain, endpoint) hit. Columns: domain, rank, endpoint, raw_content, http_status, crawled_at. Use cases: agent infra research, security auditing, OAuth landscape mapping. Updated weekly." \
  0.10 1.00

patch_description "oidc-providers-${DATE}.json" \
  "OpenID Connect provider index from the top 100k domains. Columns: domain, rank, issuer, authorization_endpoint, token_endpoint, jwks_uri, scopes_supported, grant_types_supported, crawled_at. ~3,000-8,000 records expected. Use cases: pre-flight auth discovery for agent OAuth flows, OIDC issuer mapping, identity provider landscape research. Source: Tranco top 100k crawl. Updated weekly." \
  0.05 0.25

patch_description "agent-index-${DATE}.json" \
  "Index of domains publishing agent-card.json (A2A protocol). Columns: domain, rank, name, description, url, skills, capabilities, auth_schemes, crawled_at. Every publicly discoverable A2A agent across the top 100k domains. Use cases: find agents by capability, audit A2A adoption rates, build agent discovery tools. Source: Tranco top 100k crawl. Updated weekly." \
  0.05 0.10

patch_description "mcp-infrastructure-${DATE}.json" \
  "MCP server discovery index: domains publishing mcp.json or oauth-protected-resource endpoints. Columns: domain, rank, endpoint_type, tool_names, capabilities, auth_servers, bearer_methods, crawled_at. The only commercial catalog of MCP-discoverable services. Use cases: find MCP servers by tool name, audit oauth-protected-resource deployments, monitor Shopify mcp.json rollout. Source: Tranco top 100k crawl. Updated weekly." \
  0.05 0.10

patch_description "delta-${DATE}.jsonl" \
  "Daily change log of /.well-known/ endpoint changes across top 100k domains. Columns: domain, endpoint (e.g. agent-card.json), change_type (new/removed/updated), previous_status, current_status, crawled_at. Use cases: monitor when domains add/drop agent cards, track MCP server rollouts, detect OIDC endpoint changes. Updated daily." \
  0.01 0.05

echo ""
echo "=== Step 4: Cross-business enrichment (buy Double Agent data + produce grouped datasets) ==="
python3 pipeline/enrich.py

echo ""
echo "=== Done! ==="
echo "Fresh data from $(date +%Y-%m-%d) 100k-domain crawl is now live on resolved.sh"
