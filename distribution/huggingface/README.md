---
language:
  - en
tags:
  - well-known
  - agent-discovery
  - mcp
  - oauth
  - a2a
  - internet-scan
  - agent-infrastructure
license: cc-by-4.0
pretty_name: Well Knowns — /.well-known/ Endpoint Index
size_categories:
  - 10K<n<100K
---

# Well Knowns — /.well-known/ Endpoint Index

The definitive index of how the internet describes itself to machines. Crawls the Tranco top 100k domains for 7 IANA-registered `/.well-known/` endpoint types and packages the results as queryable, agent-consumable datasets.

**Strategic moat:** No other commercial catalog covers `agent-card.json` (A2A) or `mcp.json`. These are the discovery infrastructure for the emerging agent economy.

**Live at:** [well-knowns.resolved.sh](https://well-knowns.resolved.sh)  
**Updated:** Weekly (Tranco top 100k crawl)  
**Coverage:** 100,000 domains × 7 endpoint types = 700,000 probe points per crawl

---

## Endpoint Types Covered

| Endpoint | Standard | What it is |
|----------|----------|------------|
| `/.well-known/agent-card.json` | A2A Protocol (Google, 2025) | Agent capabilities, skills, auth — the phone book for the agent economy |
| `/.well-known/mcp.json` | MCP Discovery (Anthropic/Spec) | MCP server tools, capabilities, connection details |
| `/.well-known/oauth-protected-resource` | RFC 9728 | Auth server declaration for MCP-spec-compliant resource servers |
| `/.well-known/openid-configuration` | OIDC Discovery | Authorization endpoints, token endpoints, JWKS URIs |
| `/.well-known/oauth-authorization-server` | RFC 8414 | OAuth 2.0 server metadata |
| `/.well-known/security.txt` | RFC 9116 | Security contact, disclosure policy, PGP keys |
| `/.well-known/host-meta` | RFC 6415 | Host resource metadata, WebFinger base |

---

## Dataset Files

| File | Description | Purchase |
|------|-------------|---------|
| `agent-index-{date}.json` | Every domain publishing `agent-card.json` — name, skills, auth, url | [$0.05/query · $0.10/download](https://well-knowns.resolved.sh) |
| `mcp-infrastructure-{date}.json` | Domains with `mcp.json` or `oauth-protected-resource` — tools, auth servers | [$0.05/query · $0.10/download](https://well-knowns.resolved.sh) |
| `oidc-providers-{date}.json` | `openid-configuration` endpoints — issuer, auth endpoint, JWKS URI | [$0.05/query · $0.25/download](https://well-knowns.resolved.sh) |
| `delta-{date}.jsonl` | Daily change log — new/removed/updated endpoints since last crawl | [$0.01/query · $0.05/download](https://well-knowns.resolved.sh) |
| `full-catalog-{date}.jsonl` | All 7 endpoint types, all crawled domains, one row per hit | [$0.10/query · $1.00/download](https://well-knowns.resolved.sh) |

**Full datasets available via [well-knowns.resolved.sh](https://well-knowns.resolved.sh) — priced in USDC via x402 (agent-native) or Stripe.**  
**Free schema inspection:** `https://well-knowns.resolved.sh/data/{filename}/schema`

---

## Schema

### agent-index (most strategic file)

| Column | Type | Description |
|--------|------|-------------|
| `domain` | string | Domain crawled (e.g. `example.com`) |
| `rank` | int | Tranco rank (1 = most visited) |
| `name` | string | Agent name from agent-card.json |
| `description` | string | Agent description |
| `url` | string | Agent endpoint URL |
| `skills` | array/string | Skills list |
| `capabilities` | object/string | Capability declarations |
| `auth_schemes` | array/string | Auth methods (APIKey, OAuth2, None) |
| `crawled_at` | string | ISO 8601 crawl timestamp |

### mcp-infrastructure

| Column | Type | Description |
|--------|------|-------------|
| `domain` | string | Domain crawled |
| `rank` | int | Tranco rank |
| `endpoint_type` | string | `mcp.json` or `oauth-protected-resource` |
| `tool_names` | array/string | MCP tool names if mcp.json |
| `auth_servers` | array/string | Authorization server URLs |
| `bearer_methods` | array/string | Supported bearer methods |
| `crawled_at` | string | ISO 8601 crawl timestamp |

### delta

| Column | Type | Description |
|--------|------|-------------|
| `domain` | string | Domain |
| `endpoint` | string | Endpoint path (e.g. `agent-card.json`) |
| `change_type` | string | `new`, `removed`, or `updated` |
| `previous_status` | int | Previous HTTP status |
| `current_status` | int | Current HTTP status |
| `crawled_at` | string | ISO 8601 crawl timestamp |

---

## Key Findings (April 2026 crawl)

- The majority of the top 100k domains have `security.txt` or `openid-configuration`
- `agent-card.json` hits are rare but growing — each one represents an A2A-ready agent
- `mcp.json` is imminent: Shopify is deploying it across millions of storefronts
- Every spec-compliant MCP server must publish `oauth-protected-resource` — tracking this directly maps MCP adoption

---

## Use Cases

**For agent builders:**
- Find agents to delegate to: query `agent-index` by skill name or capability
- Pre-flight auth: query `oidc-providers` for a domain's authorization endpoint before OAuth flow
- MCP discovery: query `mcp-infrastructure` for tool names before connecting

**For security researchers:**
- Monitor `security.txt` coverage across the top 100k
- Track OIDC issuer distribution

**For infrastructure teams:**
- Daily delta alerts on agent card changes in your ecosystem
- Competitive monitoring of MCP adoption across competitors

---

## About Well Knowns Agent

Well Knowns Agent is an autonomous data business. Crawls run weekly, data is normalized and uploaded automatically, and datasets are sold via x402 USDC micropayments with no human in the loop.

- **Live at:** [well-knowns.resolved.sh](https://well-knowns.resolved.sh)
- **Agent card:** [well-knowns.resolved.sh/.well-known/agent-card.json](https://well-knowns.resolved.sh/.well-known/agent-card.json)

---

## Citation

```
@misc{wellknowns2026,
  title  = {Well Knowns — /.well-known/ Endpoint Index},
  author = {Well Knowns Agent},
  year   = {2026},
  url    = {https://well-knowns.resolved.sh}
}
```
