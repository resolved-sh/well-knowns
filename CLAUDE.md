# CLAUDE.md

## What this is

Well Knowns is a data business on resolved.sh that crawls the internet's `/.well-known/` endpoints across the Tranco top 100k domains and sells the resulting datasets. The products cover OIDC providers, A2A agent cards, MCP infrastructure, and full catalogs — all agent-consumable and purchasable via x402/USDC.

This repo is also a **demonstration of resolved.sh** — showing how an autonomous agent business operates on the platform, including cross-business enrichment with the [Double Agent](https://agentagent.resolved.sh) project.

## resolved.sh identity

- **Subdomain:** well-knowns.resolved.sh
- **Custom domain:** well-knowns.com
- **Resource ID:** `ef9f56ad-11a4-43e7-9171-fd108d194ad8`
- **Inbox:** jollylight927@agentmail.to
- **Registration status:** active (paid)

## Agent team

This business is run by a 4-agent team. The **CEO** is the default entry point.

| Agent | File | Role |
|-------|------|------|
| CEO | `.claude/agents/wellknowns-ceo.md` | Strategic leadership, prioritization, delegation |
| Operator | `.claude/agents/wellknowns-operator.md` | Pipeline ops, uploads, health checks |
| Analyst | `.claude/agents/wellknowns-analyst.md` | Data analysis, blog posts, trends |
| Growth | `.claude/agents/wellknowns-growth.md` | Page optimization, distribution |

Agent memory persists at `.claude/agent-memory/{agent-name}/`.

## Repo structure

```
well_knowns/           # Core pipeline code (crawl, generate, upload)
pipeline/              # Cross-business enrichment (buys from Double Agent)
data/                  # Generated datasets (mostly gitignored)
distribution/          # External platform listings (HuggingFace, etc.)
scripts/               # Operational scripts (cycle, maintain)
.claude/agents/        # Agent team definitions (CEO, operator, analyst, growth)
.claude/agent-memory/  # Persistent memory per agent role
```

## How to operate

### Full pipeline (crawl → generate → upload → enrich)
```bash
bash scripts/cycle.sh
```

### Individual steps
```bash
# 1. Fetch latest Tranco domain list
python3 well_knowns/fetch_domains.py

# 2. Crawl well-known endpoints
python3 well_knowns/crawl_improved.py

# 3. Generate datasets from raw crawl
python3 well_knowns/generate_improved.py

# 4. Upload to resolved.sh
python3 well_knowns/upload.py --api-key "$RESOLVED_API_KEY" --replace

# 5. Post-crawl: generate + upload + patch descriptions + enrich
bash post-crawl.sh

# 6. Cross-business enrichment (buy Double Agent data, produce grouped datasets)
python3 pipeline/enrich.py
```

### Health check
```bash
bash scripts/maintain.sh
```

## Environment variables (.env)

| Variable | Purpose |
|----------|---------|
| `RESOLVED_API_KEY` | resolved.sh API key |
| `RESOLVED_RESOURCE_ID` | Listing resource ID |
| `EVM_PRIVATE_KEY` | x402 wallet private key (Base mainnet) |
| `EVM_PUBLIC_ADDRESS` | Wallet public address |
| `EVM_CHAIN_ID` | 8453 (Base) |
| `AGENTMAIL_API_KEY` | AgentMail API key (for sending email from the agent inbox) |
| `AGENT_EMAIL_ADDRESS` | This business's inbox (`jollylight927@agentmail.to`) |
| `RESOLVED_SH_DEVELOPER_EMAIL` | The resolved.sh / rstack developer's inbox — see "Contacting the developer" below |

## Contacting the developer

The human behind resolved.sh/rstack can be reached at the email in `RESOLVED_SH_DEVELOPER_EMAIL` (stored in `.env`, never in the repo). Send email via the AgentMail API using `AGENTMAIL_API_KEY` and the `AGENT_EMAIL_ADDRESS` inbox.

**When to email the developer:**
- Feedback on rstack skills (what works, what's missing, adoption friction)
- Bugs or unexpected behavior in the resolved.sh API, x402 flow, or marketplace features
- Strategic questions about the platform that affect this business
- Notable milestones worth reporting (first sale, schema changes, cross-business commerce events)
- Anything ambiguous where we'd otherwise guess — ask rather than assume

Don't email for routine operational events (pipeline runs, uploads, normal cron output); those belong in Pulse events and agent memory.

## Key decisions

- **JSONL for full catalog** — DuckDB handles nested fields better than CSV; agents can stream line-by-line.
- **Seven endpoint types crawled:** agent-card.json, mcp.json, oauth-protected-resource, openid-configuration, oauth-authorization-server, security.txt, host-meta.
- **Cross-business enrichment with Double Agent** — We buy their x402 ecosystem company data and cross-reference it with our crawl to produce premium grouped datasets. This demonstrates resolved.sh's agent-to-agent commerce.
- **Pricing:** Full catalog at $1.00-$3.00, individual products $0.10-$1.50. Query pricing lower than download pricing.
- **Data files use date suffixes** (e.g., `full-catalog-2026-04-16.jsonl`) — upload with `--replace` to keep only the latest.

## What not to do

- **Never commit .env** — it contains private keys and API credentials.
- **Never upload PII** — crawl data is public endpoint metadata only.
- **Don't change pricing without reviewing PLAN.md** — pricing decisions are documented there.
- **Don't delete data files from resolved.sh** — update by uploading replacements with `--replace`.
- **Don't skip the description patching step** — file descriptions drive discoverability.
- **No personal information in committed files** — this repo is a public demonstration.

## Double Agent integration

The [Double Agent](https://agentagent.resolved.sh) project maintains an index of x402 ecosystem companies. Our enrichment pipeline (`pipeline/enrich.py`) purchases their data via x402 and cross-references it with our crawl results to produce:
- `x402-agent-cards-{date}.jsonl` — agent-card hits from x402 companies
- `x402-mcp-infrastructure-{date}.jsonl` — MCP/oauth hits from x402 companies
- `x402-wellknown-overview-{date}.jsonl` — all endpoint types for x402 companies

This two-way commerce is the core demonstration of how resolved.sh businesses interact.
