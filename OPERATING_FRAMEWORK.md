# Operating Framework — Well Knowns

## Current State

- **Live at:** well-knowns.com (well-knowns.resolved.sh)
- **Products:** 5 data products + 1 free manifest on resolved.sh marketplace
- **Pipeline:** Functional end-to-end (crawl → generate → upload → enrich)
- **Domain coverage:** ~100k (Tranco top list)
- **Revenue:** Pre-revenue — data quality and discoverability are the blockers
- **Cross-business enrichment:** Active — buys from Double Agent, produces 3 grouped datasets
- **Purpose:** Demonstration of resolved.sh platform capabilities and agent-to-agent commerce

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
- Updating PLAN.md with current metrics

### Ask the human first:
- Pricing changes
- Adding new data sources or endpoint types
- Changes to the Double Agent integration
- Public-facing page content changes
- Anything involving private keys or wallet operations
- Structural changes to the repo

## Operating Cadence

### Each session:
1. Check registration health (`bash scripts/maintain.sh`)
2. Review data freshness — when was the last crawl?
3. Run the pipeline if data is stale (>7 days for full, >1 day for priority)
4. Upload and patch descriptions
5. Run enrichment pipeline (buy from Double Agent)
6. Emit Pulse events for completed operations

### Weekly:
1. Full 100k-domain crawl
2. Run complete enrichment cycle
3. Update PLAN.md current state section
4. Check for schema changes — post changelog if any

### As needed:
- Update distribution listings (HuggingFace, etc.) when data format changes
- Review and respond to marketplace inquiries

## Anti-Patterns

- Don't build new features when the pipeline isn't running cleanly
- Don't optimize pricing before there are buyers
- Don't skip the health check at session start
- Don't skip description patching — it's what makes products discoverable
- Don't commit personal information — this is a public demonstration repo
- Don't manually run steps that `scripts/cycle.sh` covers
