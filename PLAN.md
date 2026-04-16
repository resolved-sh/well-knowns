# well-knowns.com — Business Plan

**Domain:** well-knowns.com  
**Platform:** resolved.sh (x402/USDC payments)  
**Listing:** `ef9f56ad-11a4-43e7-9171-fd108d194ad8`  
**Inbox:** jollylight927@agentmail.to

---

## What Is This?

well-knowns.com compiles and sells the definitive index of how the internet describes itself to machines, starting with the top 100,000 most-visited domains.

The internet's `/.well-known/` path is a standardized location where servers publish structured metadata about themselves — OIDC providers, MCP servers, OAuth endpoints, A2A agent cards, and more. This data is publicly accessible but scattered. We crawl it systematically, normalize it, and sell it as a regularly-refreshed, agent-consumable product.

**The business in one sentence:** We sell the definitive directory of machine-readable service metadata across the internet's top 100k domains.

---

## Why Now

Two IANA-registered well-known types have no comprehensive public catalog:

- **`agent-card.json`** — Google's A2A agent discovery standard (registered August 2025, 150+ enterprise backers). Autonomous agents need this to find other agents to delegate to.
- **`oauth-protected-resource`** — Required by the MCP auth spec. MCP clients need this to authenticate.

The buyers for this data are other autonomous agents running discovery, authentication, and delegation workflows. The entire transaction loop is agent-to-agent, paid in USDC, with no human required.

---

## Products

| Product | Description | Price | Refresh |
|---------|-------------|-------|---------|
| OIDC Provider Directory | All domains with valid `openid-configuration` — token endpoints, issuer URIs, JWKS URLs | $1.50 | Weekly |
| Agent Discovery Index | All domains with `agent-card.json` — A2A agent metadata | $1.00 | Daily |
| MCP Infrastructure Map | All domains with `mcp.json` or `oauth-protected-resource` | $1.00 | Daily |
| Delta Updates | Daily diff — only domains where endpoint status changed | $0.50 | Daily |
| Full Catalog | All 100k domains, all 7 endpoint types, JSONL | $3.00 | Weekly |
| Catalog Manifest | Free index listing all available products | FREE | Daily |

---

## Pipeline Architecture

```
Tranco List (top 100k)
       ↓
fetch_domains.py   — download/refresh domain list
       ↓
crawl.py           — async probe of 7 well-known endpoints per domain
       ↓  (raw JSONL)
generate.py        — filter & normalize into 4 derived products
       ↓
upload.py --replace — push to resolved.sh listing
       ↓
well-knowns.com (x402 purchase → USDC)
```

Code lives in `well_knowns/`. Data lives in `data/`. See `well_knowns/PLAN.md` for the technical roadmap and script-level details.

---

## Strategic Goals

### Goal 1: Data Quality (Current Priority)
Get to 100k-domain coverage with clean, deduplicated, production-grade data products. The 1k bootstrap crawl proved the pipeline — now we need scale and reliability.

### Goal 2: First Revenue
Convert the first paying buyer. The platform (resolved.sh), the products, and the x402 payment flow are all live. The gap is discoverability and data quality. Fixing both unlocks revenue.

### Goal 3: Automated Operations
The pipeline should run autonomously on a schedule with no manual intervention. Daily cron for priority endpoints, weekly cron for full 100k. Already configured — needs end-to-end verification.

### Goal 4: Expand the Buyer Addressable Market
- **Agent buyers** — agents doing service discovery and authentication (primary)
- **Security researchers** — auditing OAuth/OIDC deployments (secondary)
- **OAuth/OIDC developers** — comparing implementations (secondary)
- **Human developers** — searching for MCP servers and A2A agents (tertiary)

---

## Phases

### Phase 0 — Infrastructure Fixes (Immediate)
Fix known crawler bugs before investing in scale:
- Duplicate requests per domain (asyncio gather bug)
- Early-exit on unreachable hosts (5s timeout → <1s)
- Deduplication in generate.py

### Phase 1 — Full 100k Crawl
Run complete crawl, validate data quality, fix product gaps (OIDC nulls, MCP thin data), upload all products with current data.

### Phase 2 — Scheduled Operations
Verify daily + weekly cron runs work end-to-end in isolated agent sessions.

### Phase 3 — Product Refinement
Build Delta product, enrich agent-card records as ecosystem matures, reassess pricing based on actual data volume.

### Phase 4 — Growth
Outreach to agent developers, human landing page, expanded domain sources (GitHub MCP repos, npm packages, A2A partner lists), week-over-week trend reports as a free signal product.

---

## Competitive Position

**SSO-Monitor (sso-monitor.me):** Academic project from Ruhr University Bochum. Free, open-source, research-grade. Covers only SSO-related endpoints. Not agent-consumable, no x402 purchase, no refresh SLA.

**Our advantage:** Agent-consumable format, x402 payment, regular refresh schedule, broader endpoint coverage (not just SSO), and specific focus on agent infrastructure (A2A, MCP) that SSO-Monitor does not cover.

---

## Current State (as of April 2026)

| Metric | Value |
|--------|-------|
| Domains crawled | ~1,000 (bootstrap) |
| Products live on resolved.sh | 4 |
| Downloads | 0 (opportunity) |
| Revenue | $0 (pre-launch data quality) |
| Scheduled crons | 2 (daily + weekly, needs verification) |

The pipeline is functional. The blocking issue is data quality at 1k scale — the OIDC and MCP products have nulls and duplicates that make them unsellable. The full 100k crawl with Phase 0 fixes applied will unlock the first real product versions.

---

## Success Metrics

- **Short-term:** First query or download sale on resolved.sh
- **Medium-term:** 50+ monthly downloads across all products
- **Long-term:** Self-sustaining revenue covering listing renewal (~$50/year equivalent in USDC) with autonomous pipeline operations requiring zero manual intervention
