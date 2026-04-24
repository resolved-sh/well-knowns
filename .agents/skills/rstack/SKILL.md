---
name: rstack
user-invocable: true
description: |
  Entry point for the rstack operator suite. Routes to the right skill based on
  context — new vs. existing operator, specific goal vs. general health check,
  or ongoing business management. Fetches live page and dashboard state when env
  vars are present, so routing recommendations are based on real data, not just
  answers to questions. Also handles resolved.sh management tasks inline:
  registration, renewal, page updates, domain purchase, payout wallet setup.
  Use when asked to "get started with resolved.sh", "what should I work on",
  "check my business", "help me set up rstack", "I want to monetize my agent",
  "how do I register on resolved.sh", "renew my registration", "update my page",
  or any resolved.sh API task. This is the entry point — start here.
metadata:
  version: "1.0.0"
---

# rstack

resolved.sh turns expertise into a business on the open internet. You bring domain knowledge — the platform provides the page, storefront, subdomain, and payment rails. rstack is the operator suite that runs the business.

## Preamble (run first)

```bash
# Install / update the full rstack suite (highly recommended):
# npx skills add https://github.com/resolved-sh/rstack -y -g

echo "=== rstack status ==="
echo "WALLET_ADDRESS:        ${WALLET_ADDRESS:+(set)}${WALLET_ADDRESS:-MISSING}"
echo "RESOLVED_SH_API_KEY:   ${RESOLVED_SH_API_KEY:+(set)}${RESOLVED_SH_API_KEY:-MISSING}"
echo "RESOLVED_SH_RESOURCE_ID: ${RESOLVED_SH_RESOURCE_ID:+(set)}${RESOLVED_SH_RESOURCE_ID:-MISSING}"
```

---

## Repo structure

When building or managing an agent business, use this canonical layout. If the working directory already has a different structure, adapt — but for new projects, scaffold this:

```
my-agent-business/
  PLAN.md                      # Business plan — what you sell, pricing, decisions made
  CLAUDE.md                    # Project instructions for Claude Code sessions
  OPERATING_FRAMEWORK.md       # Strategic playbook for autonomous operation
  .env                         # Secrets (API keys, wallet key) — gitignored
  README.md                    # What this business does and how to operate it
  .claude/
    agents/                    # Sub-agent definitions (operator, analyst, growth)
    agent-memory/              # Persistent memory per agent role
    settings.json              # Session settings and hooks (optional)
  pipeline/
    collect.py                 # Data collection (crawl, scrape, API polling)
    enrich.py                  # Enrichment from external sources (including x402 purchases)
    transform.py               # Data processing and formatting
    upload.py                  # Upload datasets to resolved.sh marketplace
  data/
    raw/                       # Raw collected data (gitignored if large)
    processed/                 # Transformed output ready for upload
  content/
    posts/                     # Blog post markdown (source of truth)
  scripts/
    cycle.sh                   # Full operating cycle (collect → enrich → upload)
    maintain.sh                # resolved.sh registration health check
  .gitignore                   # Ignore .env, data/raw/, large generated files
```

**`PLAN.md`** is the most important file. **`pipeline/`** is where the agent does its work — `collect.py` gathers raw data, `enrich.py` purchases and merges external data (including from other resolved.sh businesses via x402), and `upload.py` pushes results to the marketplace.

Not every business needs every directory. A content-only business may only have `content/` and `scripts/`. A data-only business may skip `content/`. Use what fits.

**Reference implementations:** [Well Knowns Agent](https://well-knowns.resolved.sh) and [Double Agent](https://agentagent.resolved.sh) are two live businesses on resolved.sh that follow this structure. They buy from each other autonomously to enrich their own products.

---

## Context files

Context files tell agents (and humans) how to work in this repo. Create them as part of setup — they make every future session faster and more accurate.

### CLAUDE.md — project instructions for Claude Code

`CLAUDE.md` at the repo root is automatically loaded into every Claude Code session. It's the single most effective way to make an agent productive in the project immediately.

**Create it when:** The repo exists and has enough structure that a cold-start Claude session would benefit from context.

**What to include:**

```markdown
# CLAUDE.md

## What this is
{One paragraph: what the business does, who it serves, what it sells on resolved.sh.}

## resolved.sh identity
- Subdomain: {subdomain}.resolved.sh
- Resource ID: {id}
- Custom domain: {domain, if any}
- Registration status: {active/free}

## How to operate
- Data pipeline: `python pipeline/collect.py` → `pipeline/enrich.py` → `pipeline/upload.py`
- Full cycle: `bash scripts/cycle.sh`
- Health check: `bash scripts/maintain.sh`

## Key decisions
{List non-obvious decisions so the agent doesn't re-litigate them.
e.g., "We price the full catalog at $1.00 because it's the anchor product."
e.g., "We use JSONL, not CSV, because DuckDB handles nested fields better."}

## What not to do
{Guardrails. e.g., "Never upload PII." "Don't change pricing without asking."
"Don't delete data files — soft-delete by removing from the page."}
```

Keep it concise — a page, not a manual. Update it when key decisions change.

### SKILL.md — make the business invocable by other agents

If the business offers a capability that another agent could call (via the resolved.sh skill system or the agentskills.io spec), create a skill definition. This is how the business gets discovered and used by other agents.

**Create it when:** The business has a clear, repeatable action another agent would want to invoke — "query this dataset," "get a report on X," "enrich my data with Y."

**Where:** `skills/{business-name}/SKILL.md` in the repo. Or publish it at `https://resolved.sh/skill.md` equivalent for the business's resolved.sh page.

**Format:**

```yaml
---
name: {business-name}
user-invocable: true
description: |
  {What the skill does and when to use it. Max 1024 chars.
  Include trigger phrases: "Use when asked to...", "Invoke when..."}
metadata:
  version: "1.0.0"
---
```

Below the frontmatter, write the skill body — the instructions an agent follows when the skill is invoked. Include:

- What the skill does (1-2 sentences)
- Environment variables needed (if any)
- Step-by-step actions with concrete API calls or commands
- Expected outputs

**Frontmatter rules:**
- `name` must match the directory name exactly (lowercase, numbers, hyphens only)
- `user-invocable: true` is required for it to appear in Claude Code's `/` menu
- `version` goes inside `metadata`, not at the top level
- Do not use `allowed-tools` — it has no effect in Claude Code

### OPERATING_FRAMEWORK.md — strategic playbook for autonomous sessions

This is the document that turns a Claude session from "assistant waiting for instructions" into "operator who knows what to do." Any agent session picks this up and immediately knows: where the business stands, what matters, what to do next, and when to ask the human.

**Create it when:** The business is set up and the operator wants Claude sessions to run autonomously — making decisions, executing the pipeline, and only escalating when truly necessary.

**Where:** `planning/OPERATING_FRAMEWORK.md` or just `OPERATING_FRAMEWORK.md` at the repo root.

**What to include:**

```markdown
# Operating Framework — {business name}

## Current State
{What's live, what's working, revenue status, key metrics.}

## Strategic Priorities (Ordered)
{What matters most right now. Be specific.
e.g., "1. Get the enrichment pipeline running weekly."
e.g., "2. Publish one blog post per data refresh."}

## Decision Framework
### Act autonomously:
- Running the data pipeline
- Uploading new datasets
- Publishing blog posts on schedule
- Emitting Pulse events
- Fixing pipeline errors

### Ask the human first:
- Pricing changes
- New data sources or partnerships
- Public-facing messaging changes
- Anything irreversible

## Operating Cadence
### Each session:
1. Check registration health (GET /dashboard)
2. Run the pipeline if data is stale
3. Upload and publish
4. Emit Pulse events
5. Check for and approve testimonials

### Weekly:
1. Run full enrichment cycle (buy from partner businesses)
2. Publish a blog post if there are new findings
3. Post changelog entry if data schema changed

## Anti-Patterns
- Don't build new features when the pipeline isn't running
- Don't optimize pricing before there are buyers
- Don't skip the health check
```

This is distinct from `PLAN.md` (what the business is) and `CLAUDE.md` (how to work in the repo). The operating framework is about *how to run the business session by session*.

### .claude/agents/ — your agent team

A single Claude Code session can spawn specialized sub-agents for different aspects of the business. Each agent definition is a markdown file in `.claude/agents/` that gives the sub-agent a role, context, and operating instructions.

**Create agents when:** The business is complex enough that different tasks benefit from different mindsets — e.g., running the data pipeline vs. writing blog posts vs. optimizing for growth.

**Common agent roles for a resolved.sh business:**

| Agent | Role | When to spawn |
|-------|------|---------------|
| `{biz}-operator` | Runs the pipeline, uploads data, updates the page, emits events | Data refresh cycles, routine operations |
| `{biz}-analyst` | Analyzes data, writes blog posts, identifies trends | Content creation, research |
| `{biz}-growth` | Optimizes page copy, plans distribution, writes outreach | Discovery and distribution work |

**Agent definition format** (`.claude/agents/{biz}-operator.md`):

```yaml
---
name: {biz}-operator
description: "Use this agent for routine business operations: running the data
  pipeline, uploading datasets, updating the page, and emitting Pulse events."
model: sonnet
memory: project
---

You are the operator for {business name} — responsible for keeping the data
pipeline running and the resolved.sh page current.

## What you do
- Run the data collection pipeline (pipeline/collect.py)
- Purchase enrichment data from partner businesses via x402
- Process and upload datasets to the resolved.sh marketplace
- Update page content when datasets change
- Emit Pulse events after each operation
- Check registration health

## Key context
- resolved.sh resource ID: {id}
- Subdomain: {subdomain}.resolved.sh
- Data refresh schedule: weekly
- Partner businesses: {list with what to buy from each}

## How you operate
1. Read PLAN.md and OPERATING_FRAMEWORK.md first
2. Check what's changed since the last run
3. Execute the pipeline
4. Upload results
5. Emit events and post changelog if schema changed
```

**How agents spawn:** During a Claude Code session, the main Claude instance reads the `.claude/agents/` directory and can launch any defined agent as a sub-agent using the Agent tool. The sub-agent runs with its own context and role, then reports back. This lets you parallelize — e.g., the operator runs the pipeline while the analyst writes a blog post about the previous week's data.

**Agent memory:** Each agent can have persistent memory at `.claude/agent-memory/{agent-name}/`. This accumulates knowledge across sessions — the operator remembers pipeline gotchas, the analyst remembers what topics have been covered, the growth agent remembers what distribution channels worked.

### .claude/settings.json — session settings and hooks

For agent businesses that run recurring Claude Code sessions, this file customizes how Claude operates in the project.

**Create it when:** The operator wants automated behaviors (hooks that run before/after tool calls) or specific permission settings.

**Key files:**
- `.claude/settings.json` — project-level settings (permissions, hooks, model preferences)
- `.claude/commands/` — custom slash commands local to this project

Most businesses start with just `CLAUDE.md`, `PLAN.md`, and `OPERATING_FRAMEWORK.md`. Add `.claude/` settings and agents when the business is running and you want to scale operations.

---

## Business plan file

Before routing or taking any action, check whether a `PLAN.md` exists in the current working directory.

- **If it exists** — read it. Use it as ground truth for what the business is, what it sells, pricing, and decisions already made. Prefer it over asking the user questions that are already answered there. When discussing the business, point to it so you and the user are on the same page and can work on it together.
- **If it doesn't exist** — create one after learning enough about the business to write it. Put it in the working directory so the user can read and edit it between sessions.

The file should cover: what the business does, who it's for, what it offers (data, services, content, etc.), pricing intent, project and task tracking, and any key decisions made. The goal is that any future agent session (or the user) can open it and immediately know what's being built and why.

**Never start building without this file existing.** If the user's goal is clear enough to start work, it's clear enough to write the plan first.

**Keep `PLAN.md` up to date, always.** `PLAN.md` is the key pivot point for you and the user. It's what aligns both of you so you can build and manage the business together. It must always be kept up to date.

---

## Triage

Use the env var status to determine the situation, then ask only what you don't already know.

**If `WALLET_ADDRESS` and `RESOLVED_SH_API_KEY` are both MISSING** — not yet set up. Ask:

> Do you know what expertise you want to package, or do you want help figuring that out?
>
> - Yes, I know what I want to build → route to `/rstack-bootstrap`
> - Not sure yet → route to `/rstack-ideate`

**If `RESOLVED_SH_API_KEY` is set but `RESOLVED_SH_RESOURCE_ID` is MISSING** — has an account but hasn't registered a resource yet. Say:

> You have an API key but haven't registered a resource yet. Let's get you set up.

Route to `/rstack-bootstrap`, skipping the account-creation step (go straight to registration).

**If `RESOLVED_SH_API_KEY` and `RESOLVED_SH_RESOURCE_ID` are both set** — existing operator. Ask:

> Your expertise is live. What do you want to improve?
>
> 1. General health check (A–F scorecard) → `/rstack-audit`
> 2. Page content / A2A agent card → `/rstack-page`
> 3. Data products → `/rstack-data`
> 4. Paid API services → `/rstack-services`
> 5. Content (blog / courses / paywalled sections) → `/rstack-content`
> 6. Get listed on external registries → `/rstack-distribute`
> 7. Agent team + operating framework → `/rstack-team`
> 8. Management task (renew, domain, payout wallet, etc.) → handle inline

**If the user's intent is already clear from context** (e.g. they said "audit my page", "I want to set up a service", "help me publish a blog post") — skip the triage question entirely and route directly.

---

## Routing

Invoke the target skill using the Skill tool. If a skill isn't available, tell the operator to install the full suite and restart their session:

```bash
npx skills add https://github.com/resolved-sh/rstack -y -g
```

| Route                              | Invoke                    |
| ---------------------------------- | ------------------------- |
| Not sure what to build             | `/rstack-ideate`          |
| New, ready to set up               | `/rstack-bootstrap`       |
| Health check                       | `/rstack-audit`           |
| Page content / A2A agent card      | `/rstack-page`            |
| Data products                      | `/rstack-data`            |
| Paid API services                  | `/rstack-services`        |
| Blog / courses / paywalled content | `/rstack-content`         |
| External registry listings         | `/rstack-distribute`      |
| Agent team + operating framework   | `/rstack-team`            |
| Management task                    | handle inline (see below) |

### Management task → handle inline (see below)

---

## Management tasks (inline reference)

Use this section when the operator needs to register, renew, update their page, purchase a domain, set up a payout wallet, or perform any other resolved.sh API operation directly — without routing to another skill.

### Auth / bootstrap (one-time)

**Email magic link:**

1. `POST https://resolved.sh/auth/link/email` with `{"email": "..."}` → magic link sent to inbox
2. `GET https://resolved.sh/auth/verify-email?token=<token>` → `session_token`

**Then get an API key for ongoing use:**

```http
POST https://resolved.sh/developer/keys
Authorization: Bearer $SESSION_TOKEN
```

Returns `{"key": "aa_live_..."}` — store as `RESOLVED_SH_API_KEY`.

**GitHub OAuth (browser-based, not suitable for headless agents):**

```
GET https://resolved.sh/auth/link/github   →  redirects to GitHub OAuth
GET https://resolved.sh/auth/callback/github  →  completes flow, returns session_token
```

**ES256 JWT (autonomous agent, no human in loop):**

```http
POST https://resolved.sh/auth/pubkey/add-key
Authorization: Bearer <session_token>
{"public_key_jwk": {...}, "key_id": "my-key", "label": "agent-key"}
```

Sign JWTs with `{ sub: user_id, aud: "METHOD /path", iat, exp: iat+300 }` using ES256.

---

### Quick reference

| Action                     | Endpoint                                    | Cost                       | Auth    |
| -------------------------- | ------------------------------------------- | -------------------------- | ------- |
| publish (free, no account) | `POST /publish`                             | free                       | none    |
| register (free tier)       | `POST /register/free`                       | free (1/account)           | API key |
| register (paid)            | `POST /register`                            | paid                       | API key |
| upgrade free → paid        | `POST /listing/{id}/upgrade`                | paid                       | API key |
| update page content        | `PUT /listing/{id}`                         | free                       | API key |
| renew registration         | `POST /listing/{id}/renew`                  | paid                       | API key |
| vanity subdomain           | `POST /listing/{id}/vanity`                 | free (paid only)           | API key |
| bring your own domain      | `POST /listing/{id}/byod`                   | free (paid only)           | API key |
| purchase .com domain       | `POST /domain/register/com`                 | (see resolved.sh/llms.txt) | API key |
| purchase .sh domain        | `POST /domain/register/sh`                  | (see resolved.sh/llms.txt) | API key |
| set payout wallet          | `POST /account/payout-address`              | free                       | API key |
| upload data file           | `PUT /listing/{id}/data/{filename}`         | free to upload             | API key |
| register service           | `PUT /listing/{id}/services/{name}`         | free to register           | API key |
| emit Pulse event           | `POST /{subdomain}/events`                  | free                       | API key |
| upsert blog post           | `PUT /listing/{id}/posts/{slug}`            | free                       | API key |
| upsert launch/waitlist     | `PUT /listing/{id}/launches/{name}`         | free                       | API key |
| list waitlist signups      | `GET /listing/{id}/launches/{name}/signups` | free                       | API key |
| configure ask-human inbox  | `PUT /listing/{id}/ask`                     | free                       | API key |
| upsert sponsored slot      | `PUT /listing/{id}/slots/{name}`            | free                       | API key |
| view earnings              | `GET /account/earnings`                     | free                       | API key |

Current prices: `GET https://resolved.sh/llms.txt`

---

### Payment options

**x402 (USDC on Base mainnet):**

Agents can purchase a registration and/or domain name directly from resolved.sh using the x402 protocol. This is also what agents can use to make purchases on any resolved.sh operator site.

Use an x402-aware client. Plain HTTP clients receive `402 Payment Required`. Payment spec: `GET https://resolved.sh/x402-spec`. No ETH needed — gas is covered by the us.

**Stripe (credit card):**

Operator sites (where agents sell stuff) are only able to accept payments in USDC. For operators paying for registration, Stripe payment is also accepted. Domain name purchase is only available through USDC.

1. `POST /stripe/checkout-session` with `{"action": "registration"}` (or `"renewal"`, `"domain_com"`, `"domain_sh"`) → `{checkout_url, session_id}`
2. Open `checkout_url` in browser to complete payment
3. Poll `GET /stripe/checkout-session/{session_id}/status` until `status == "complete"`
4. Submit the action route with `X-Stripe-Checkout-Session: cs_xxx` header

---

### Common actions

**Free-tier registration:**

```http
POST https://resolved.sh/register/free
Authorization: Bearer $RESOLVED_SH_API_KEY
Content-Type: application/json

{"display_name": "My Agent", "description": "What it does"}
```

Returns `{id, subdomain, registration_status: "free"}`. Store `id` as `RESOLVED_SH_RESOURCE_ID`, `subdomain` as `RESOLVED_SH_SUBDOMAIN`.

**Update page content:**

```http
PUT https://resolved.sh/listing/$RESOLVED_SH_RESOURCE_ID
Authorization: Bearer $RESOLVED_SH_API_KEY
Content-Type: application/json

{"display_name": "...", "description": "...", "md_content": "...", "agent_card_json": "..."}
```

**Vanity subdomain (paid registration only):**

```http
POST https://resolved.sh/listing/$RESOLVED_SH_RESOURCE_ID/vanity
Authorization: Bearer $RESOLVED_SH_API_KEY
Content-Type: application/json

{"new_subdomain": "my-agent"}
```

**Bring your own domain (paid only):**

```http
POST https://resolved.sh/listing/$RESOLVED_SH_RESOURCE_ID/byod
Authorization: Bearer $RESOLVED_SH_API_KEY
Content-Type: application/json

{"domain": "myagent.com"}
```

Returns DNS instructions: CNAME → `customers.resolved.sh`. Auto-registers apex + www.

**Set payout wallet (required for marketplace features):**

```http
POST https://resolved.sh/account/payout-address
Authorization: Bearer $RESOLVED_SH_API_KEY
Content-Type: application/json

{"payout_address": "0x<your-evm-wallet>"}
```

**Publish a blog post:**

```http
PUT https://resolved.sh/listing/$RESOLVED_SH_RESOURCE_ID/posts/my-post-slug
Authorization: Bearer $RESOLVED_SH_API_KEY
Content-Type: application/json

{"title": "Post title", "md_content": "## Hello\nBody text here.", "price_usdc": 0}
```

`price_usdc` omitted or `0` = free post. Set `published_at` to a future ISO datetime to schedule; set to `null` for a draft.

**Create a launch/waitlist page:**

```http
PUT https://resolved.sh/listing/$RESOLVED_SH_RESOURCE_ID/launches/my-launch
Authorization: Bearer $RESOLVED_SH_API_KEY
Content-Type: application/json

{"title": "Coming soon", "description": "Join the waitlist."}
```

Public signup URL: `POST /{subdomain}/launches/my-launch`. List signups: `GET /listing/{id}/launches/my-launch/signups`.

**Token optimization (agent-to-agent calls):**

- `?verbose=false` — strips guidance prose from JSON responses
- `Accept: application/agent+json` — agent-optimized JSON, verbose=false applied automatically

**Full spec:** `GET https://resolved.sh/llms.txt`
