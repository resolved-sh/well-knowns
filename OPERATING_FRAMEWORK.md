# Operating Framework — Well Knowns

*Last updated: 2026-04-16*

## Current State

- **Live at:** well-knowns.com (well-knowns.resolved.sh)
- **Products:** 5 data products + 1 free manifest on resolved.sh marketplace
- **Pipeline:** Functional end-to-end (crawl → generate → upload → enrich)
- **Domain coverage:** ~100k (Tranco top list)
- **Revenue:** Pre-revenue — data quality and discoverability are the blockers
- **Cross-business enrichment:** Active — buys from Double Agent, produces 3 grouped datasets
- **Purpose:** Demonstration of resolved.sh platform capabilities and agent-to-agent commerce

## Team Structure

The business is run by a 4-agent team. The **CEO** is the default entry point for every session — it assesses state, prioritizes, and delegates.

| Agent | Role | Spawned when |
|-------|------|-------------|
| **wellknowns-ceo** | Strategic leadership, prioritization, delegation | Default session entry point |
| **wellknowns-operator** | Pipeline ops, uploads, health checks, enrichment | Data stale, uploads needed, pipeline errors |
| **wellknowns-analyst** | Data analysis, blog posts, trend reports | Fresh data landed, content needed |
| **wellknowns-growth** | Page optimization, distribution, outreach | Discoverability gaps, new channels to pursue |

Agent memory persists across sessions at `.claude/agent-memory/{agent-name}/`.

## Strategic Priorities (Ordered)

1. **Data quality** — Clean, deduplicated, production-grade products. The pipeline works; the data must be sellable.
2. **Automated operations** — Pipeline runs on schedule with no manual intervention. Daily for priority endpoints, weekly for full 100k.
3. **First revenue** — Convert the first paying buyer. The platform, products, and payment flow are live. The gap is discoverability and data quality.
4. **Demonstration value** — Keep this repo clean and well-documented as a reference implementation for resolved.sh businesses.

## Decision Framework

### Act autonomously:
- Running the data pipeline (crawl → generate → upload)
- Cross-business enrichment (buying from Double Agent)
- Uploading new/refreshed datasets
- Patching file descriptions on resolved.sh
- Fixing pipeline errors and data quality issues
- Emitting Pulse events after operations
- Publishing blog posts about data findings
- Updating PLAN.md with current metrics

### Ask the human first:
- Pricing changes
- Adding new data sources or endpoint types
- Changes to the Double Agent integration
- Public-facing page content changes (beyond blog posts)
- Anything involving private keys or wallet operations
- Structural changes to the repo

## Operating Cadence

### Each session (CEO leads):
1. Check registration health (`bash scripts/maintain.sh`)
2. Review data freshness — when was the last crawl?
3. Decide priorities for this session
4. Spawn operator if data is stale (>7 days for full, >1 day for priority)
5. Spawn analyst if fresh data needs content
6. Spawn growth if discoverability work is needed
7. Write session summary to `.claude/agent-memory/wellknowns-ceo/`

### Weekly:
1. Full 100k-domain crawl (operator)
2. Run complete enrichment cycle (operator)
3. Blog post on notable findings (analyst)
4. Update PLAN.md current state section (CEO)
5. Check for schema changes — post changelog if any (analyst)
6. Review earnings (`GET /account/earnings`) (CEO)

### As needed:
- Update distribution listings (HuggingFace, etc.) when data format changes (growth)
- Review and respond to marketplace inquiries (CEO)

## Key Files

| File | Purpose |
|------|---------|
| `PLAN.md` | What the business is and sells |
| `CLAUDE.md` | Project instructions for Claude sessions |
| `OPERATING_FRAMEWORK.md` | This file — how to run the business |
| `.claude/agents/` | Agent team definitions |
| `.claude/agent-memory/` | Persistent memory per agent role |
| `pipeline/` | Cross-business enrichment code |
| `well_knowns/` | Core pipeline code |
| `scripts/cycle.sh` | Full operating cycle |
| `scripts/maintain.sh` | Health check |

## Anti-Patterns

- Don't build new features when the pipeline isn't running cleanly
- Don't optimize pricing before there are buyers
- Don't skip the health check at session start
- Don't skip description patching — it's what makes products discoverable
- Don't commit personal information — this is a public demonstration repo
- Don't manually run steps that `scripts/cycle.sh` covers
- Don't re-litigate decisions already in PLAN.md
