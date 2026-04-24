---
name: rstack-bootstrap
user-invocable: true
description: |
  Full zero-to-earning setup for a new agent business on resolved.sh. Uses the
  zero-friction ES256 agent-bootstrap flow: generates an ECDSA keypair in-process,
  registers it via POST /auth/agent/bootstrap, and persists the identity to the
  standard .resolved.sh/ directory (account.json, private_key.pem, public_key.jwk).
  Walks through runtime detection, identity bootstrap, free-tier registration, payout
  wallet setup, runtime env configuration, first revenue stream activation, and an
  autonomy loop so the agent manages its own presence going forward. Use when starting
  from scratch, or when asked to "bootstrap my agent business", "set up resolved.sh
  for my agent", "get my agent earning", or "onboard my agent to resolved.sh".
metadata:
  version: "2.0.0"
---

# rstack-bootstrap

Your expertise, packaged and earning, in one session. One question to the human (email for recovery), then fully autonomous.

1. **Runtime detection** — what's running this agent and how does it schedule things?
2. **Identity** — ES256 keypair + one-call bootstrap, persisted to `.resolved.sh/`
3. **API key** — convert the ES256 identity into an `aa_live_...` key for shell-friendly calls
4. **Registration** — free tier first; upgrade later only if vanity/BYOD/domain is needed
5. **Payout wallet** — USDC on Base; all marketplace features route here
6. **Runtime env vars** — stored correctly for this harness
7. **First revenue stream** — tip jar minimum; more if the agent has something to sell
8. **Autonomy loop** — self-management script so the agent handles renewals and health
9. **Baseline audit** — starting scorecard

**Environment variables:**
- `RESOLVED_SH_API_KEY` (optional) — resolved.sh API key (aa_live_...); only set this if you already have an account. If unset, Phase 3 creates one.
- `AGENTMAIL_API_KEY` (optional, alternative path only) — needed only if the operator wants a verified email on the account via AgentMail inbox + magic-link flow instead of the default ES256 bootstrap. See the "Alternative: AgentMail + magic link" section at the bottom.

**Identity model:** The agent owns the keypair. The user owns the email. The agent generates its own ES256 (P-256) keypair in-process and asks the user once for an email (recovery channel only). See `GET https://resolved.sh/llms.txt` § Identity model for the full rationale.

---

## Phase 0 — Detect runtime

Start by checking the environment, then ask one question:

```bash
# Keep this skill up to date:
# npx skills add https://github.com/resolved-sh/rstack --skill rstack-bootstrap -g -y

echo "Shell:              $SHELL"
echo "OS:                 $(uname -s) $(uname -m)"
which openclaw 2>/dev/null && echo "OpenClaw: found in PATH" || echo "OpenClaw: not in PATH"
echo "DISPATCH_AGENT_ID:  ${DISPATCH_AGENT_ID:-not set}"
echo "AGENTMAIL_API_KEY:  $([ -n "$AGENTMAIL_API_KEY" ] && echo "set" || echo "not set")"
echo "RESOLVED_SH_API_KEY:$([ -n "$RESOLVED_SH_API_KEY" ] && echo "set (existing account detected)" || echo "not set")"
```

Ask: "What are you using to run this agent?

A) **OpenClaw** — the open-source autonomous agent framework
B) **Claude Desktop + Dispatch** — Claude Desktop's scheduled/cross-device agent feature
C) **Claude Code CLI** — running Claude manually in a terminal
D) **Custom Python or Node.js script** — your own agent code
E) **n8n / Zapier / Make** — a visual workflow tool
F) **Something else** — describe it"

Save the answer as `RSTACK_RUNTIME`. It determines how env vars are stored and how the autonomy loop is scheduled.

If `RESOLVED_SH_API_KEY` is already set, confirm: "I can see an existing resolved.sh API key. Should I (A) use this account, or (B) create a fresh one?" If A, skip to Phase 3 to check for an existing resource.

---

## Phase 1 — Identity (ES256 agent bootstrap)

Default path. No browser, no email inbox, no magic link. The agent generates its own ES256 keypair in-process and registers it via a single API call.

**Step 1a — Locate or create the identity directory**

Check for an existing identity first — don't re-bootstrap if one is already on disk.

```bash
if [ -f ".resolved.sh/account.json" ]; then
  export RESOLVED_SH_IDENTITY_DIR="$PWD/.resolved.sh"
  echo "Found project-scoped identity at $RESOLVED_SH_IDENTITY_DIR"
elif [ -f "$HOME/.resolved.sh/account.json" ]; then
  export RESOLVED_SH_IDENTITY_DIR="$HOME/.resolved.sh"
  echo "Found user-scoped identity at $RESOLVED_SH_IDENTITY_DIR"
else
  export RESOLVED_SH_IDENTITY_DIR="$PWD/.resolved.sh"
  echo "No existing identity — will bootstrap at $RESOLVED_SH_IDENTITY_DIR"
fi
```

If `account.json` already exists, **skip to Phase 2** (API key).

**Step 1b — Ask the user for a recovery email (exactly once)**

Use AskUserQuestion with:

> "What email should I use for your resolved.sh account? It's used only as a recovery channel if the private key is ever lost — you don't need to give me your primary email, any inbox you can access works."

Save the answer as `RESOLVED_USER_EMAIL`. Do not invent, reuse, or share an agent-owned email — the email belongs to the human.

**Step 1c — Generate keypair, call bootstrap, persist to `.resolved.sh/`**

```bash
python3 -m pip install --quiet cryptography 2>/dev/null || pip3 install --quiet cryptography

mkdir -p "$RESOLVED_SH_IDENTITY_DIR"
chmod 700 "$RESOLVED_SH_IDENTITY_DIR"

RESOLVED_USER_EMAIL="$RESOLVED_USER_EMAIL" \
RESOLVED_SH_IDENTITY_DIR="$RESOLVED_SH_IDENTITY_DIR" \
python3 - <<'EOF'
import base64, json, os, time, urllib.request
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

EMAIL = os.environ["RESOLVED_USER_EMAIL"]
DIR   = os.environ["RESOLVED_SH_IDENTITY_DIR"]
KID   = f"rstack-{int(time.time())}"
LABEL = "rstack-bootstrap"

# 1. Generate ES256 (P-256) keypair
priv = ec.generate_private_key(ec.SECP256R1())
nums = priv.public_key().public_numbers()
def b64u_int(n): return base64.urlsafe_b64encode(n.to_bytes(32, "big")).rstrip(b"=").decode()
jwk = {"kty": "EC", "crv": "P-256", "x": b64u_int(nums.x), "y": b64u_int(nums.y)}

# 2. Persist keys BEFORE calling server (so a network failure doesn't lose the keypair)
pem = priv.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
priv_path = os.path.join(DIR, "private_key.pem")
pub_path  = os.path.join(DIR, "public_key.jwk")
with open(priv_path, "wb") as f: f.write(pem)
os.chmod(priv_path, 0o600)
with open(pub_path, "w") as f: json.dump(jwk, f, indent=2)

# 3. Call bootstrap
body = json.dumps({"email": EMAIL, "public_key_jwk": jwk, "key_id": KID, "label": LABEL}).encode()
req = urllib.request.Request(
    "https://resolved.sh/auth/agent/bootstrap",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req) as r:
        account = json.loads(r.read())
except urllib.error.HTTPError as e:
    print(f"Bootstrap failed: HTTP {e.code} — {e.read().decode()[:300]}")
    raise SystemExit(1)

account["label"] = LABEL
acc_path = os.path.join(DIR, "account.json")
with open(acc_path, "w") as f: json.dump(account, f, indent=2)

print(f"Identity created:")
print(f"  user_id: {account['user_id']}")
print(f"  email:   {account['email']} (unverified — recovery only)")
print(f"  key_id:  {account['key_id']}")
print(f"  dir:     {DIR}")
EOF
```

**Step 1d — Gitignore the identity directory**

```bash
if git rev-parse --git-dir >/dev/null 2>&1; then
  if ! grep -qxF '.resolved.sh/' .gitignore 2>/dev/null; then
    echo '.resolved.sh/' >> .gitignore
    echo "Added .resolved.sh/ to .gitignore"
  fi
fi
```

Never commit `.resolved.sh/private_key.pem`. If this repo isn't git-tracked, still ensure the directory is excluded from any backups that aren't secured.

---

## Phase 2 — API key (shell-friendly auth for later phases)

ES256 JWT signing in a bash script is awkward (new token per request, 5-minute expiry). Create a long-lived `aa_live_...` API key once, authenticated with a one-off JWT signed by the bootstrap keypair. Subsequent phases use `Authorization: Bearer $RESOLVED_SH_API_KEY` in plain `curl`.

```bash
RESOLVED_SH_IDENTITY_DIR="$RESOLVED_SH_IDENTITY_DIR" \
python3 - <<'EOF'
import base64, json, os, time, urllib.request
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

DIR = os.environ["RESOLVED_SH_IDENTITY_DIR"]

account = json.load(open(os.path.join(DIR, "account.json")))
with open(os.path.join(DIR, "private_key.pem"), "rb") as f:
    priv = serialization.load_pem_private_key(f.read(), password=None)

def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def sign_es256_jwt(sub: str, kid: str, aud: str, ttl: int = 120) -> str:
    header = {"alg": "ES256", "typ": "JWT", "kid": kid}
    now = int(time.time())
    payload = {"sub": sub, "aud": aud, "iat": now, "exp": now + ttl}
    h_b64 = b64u(json.dumps(header, separators=(",", ":")).encode())
    p_b64 = b64u(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h_b64}.{p_b64}".encode()
    der = priv.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{h_b64}.{p_b64}.{b64u(raw)}"

token = sign_es256_jwt(account["user_id"], account["key_id"], "POST /developer/keys")

req = urllib.request.Request(
    "https://resolved.sh/developer/keys",
    data=json.dumps({"label": "rstack-bootstrap"}).encode(),
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req) as r:
    api = json.loads(r.read())

raw_key = api.get("raw_key") or api.get("key")
if not raw_key:
    print("Unexpected response:", json.dumps(api)[:300])
    raise SystemExit(1)

key_path = os.path.join(DIR, "api_key.txt")
with open(key_path, "w") as f: f.write(raw_key)
os.chmod(key_path, 0o600)

print(f"API key created: {raw_key[:12]}...")
print(f"Stored at:        {key_path}")
EOF

export RESOLVED_SH_API_KEY=$(cat "$RESOLVED_SH_IDENTITY_DIR/api_key.txt")
echo "RESOLVED_SH_API_KEY is now set for subsequent phases."
```

The private key stays on disk at `$RESOLVED_SH_IDENTITY_DIR/private_key.pem` as the root of trust. The API key is a convenience credential — you can revoke it any time via `DELETE /developer/keys/{id}` and create a new one with the same JWT flow.

---

## Phase 3 — Register

Check whether a resource already exists:

```bash
API_KEY=${RESOLVED_SH_API_KEY:-$(cat "$RESOLVED_SH_IDENTITY_DIR/api_key.txt" 2>/dev/null)}

curl -sf "https://resolved.sh/dashboard" \
  -H "Authorization: Bearer $API_KEY" \
  -o /tmp/rstack_dashboard.json

python3 -c "
import json
d = json.load(open('/tmp/rstack_dashboard.json'))
rs = d.get('resources', [])
if rs:
    r = rs[0]
    print('Existing resource found:')
    print(f'  Subdomain:   {r[\"subdomain\"]}')
    print(f'  Resource ID: {r[\"id\"]}')
    print(f'  Status:      {r.get(\"registration_status\")}')
    with open('/tmp/rstack_resource_id.txt','w') as f: f.write(r['id'])
    with open('/tmp/rstack_subdomain.txt',  'w') as f: f.write(r['subdomain'])
else:
    print('No resources found — proceeding to register')
    with open('/tmp/rstack_resource_id.txt','w') as f: f.write('')
    with open('/tmp/rstack_subdomain.txt',  'w') as f: f.write('')
"
```

If a resource already exists, skip to Phase 4.

**Choose registration tier — default to free unless the user specifically needs vanity/BYOD/domain:**

Ask: "How would you like to register? (Default is A — only pick B or C if you specifically need a custom vanity subdomain, your own domain connected via BYOD, or to purchase a new .com / .sh right now. You can always upgrade later via `POST /listing/{id}/upgrade` without losing the resource.)

A) **Free tier (recommended)** — permanent page with an auto-generated subdomain, full data marketplace, blog, courses, services, Pulse, tip jar. No payment. 100% of marketplace earnings still go directly to your wallet.
B) **Paid ($24 USDC/year, x402)** — unlocks vanity subdomain, BYOD, and domain purchase. Requires a funded USDC wallet on Base.
C) **Paid ($24/year, Stripe)** — same as B but via credit card. Opens a Stripe Checkout page."

**Free tier (default — use this unless explicitly asked for paid):**

```bash
API_KEY=${RESOLVED_SH_API_KEY:-$(cat "$RESOLVED_SH_IDENTITY_DIR/api_key.txt" 2>/dev/null)}

# Use display_name from Phase 0 description if available; operator can change it later
curl -sf -X POST "https://resolved.sh/register/free" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"display_name": "My Agent"}' \
  -o /tmp/rstack_register.json

python3 -c "
import json
d = json.load(open('/tmp/rstack_register.json'))
subdomain   = d.get('subdomain', '')
resource_id = d.get('id', '')
print(f'Registered!')
print(f'  Page:        https://{subdomain}.resolved.sh')
print(f'  Resource ID: {resource_id}')
with open('/tmp/rstack_subdomain.txt',   'w') as f: f.write(subdomain)
with open('/tmp/rstack_resource_id.txt', 'w') as f: f.write(resource_id)
"
```

To upgrade later: `POST /listing/{id}/upgrade` (x402 or Stripe).

**Paid — Stripe path:**

```bash
API_KEY=${RESOLVED_SH_API_KEY:-$(cat "$RESOLVED_SH_IDENTITY_DIR/api_key.txt" 2>/dev/null)}

curl -sf -X POST "https://resolved.sh/stripe/checkout-session" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "register"}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Open this URL to pay:', d.get('checkout_url', ''))
print('Session ID:', d.get('session_id', ''))
with open('/tmp/rstack_cs_id.txt','w') as f: f.write(d.get('session_id',''))
"
```

After payment, submit with `X-Stripe-Checkout-Session` header. Pause and wait for confirmation before continuing.

**Paid — x402 path:** Use the `/resolved-sh` skill for guided x402 payment, or see `GET https://resolved.sh/x402-spec` for raw route details.

---

## Phase 4 — Payout wallet

The tip jar, data marketplace, services, and sponsored slots all pay **directly to your registered EVM wallet** in USDC on Base. Without a registered payout address these features return 503.

Check current status:

```bash
API_KEY=${RESOLVED_SH_API_KEY:-$(cat "$RESOLVED_SH_IDENTITY_DIR/api_key.txt" 2>/dev/null)}

curl -sf "https://resolved.sh/account/earnings" \
  -H "Authorization: Bearer $API_KEY" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
addr = d.get('payout_address') or d.get('wallet_address', '')
print(f'Payout address: {addr if addr else \"NOT SET — marketplace features disabled\"}')
"
```

**If not set**, present wallet options:

> "You'll need a USDC wallet on Base. This guide covers all options from exchange-based to self-custody:
> **https://www.usdc.com/learn/how-to-get-usdc-on-base**
>
> For an autonomous agent, the cleanest option is a dedicated wallet (not your main holdings) — use `cast wallet new` from Foundry or any wallet tool you prefer. Keep only working funds in it."

**Private key storage — pick based on runtime:**

| Runtime                   | Recommended approach                                                                                    |
| ------------------------- | ------------------------------------------------------------------------------------------------------- |
| OpenClaw                  | OS keychain: `security add-generic-password -s "resolved-sh-wallet" -a "agent" -w $PRIVATE_KEY` (macOS) |
| Claude Desktop + Dispatch | macOS Keychain via `security`, or system env var injected at launch — not in config file                |
| Custom Python / Node.js   | Environment variable injected by the process launcher; load with `dotenv` at runtime, never committed   |
| n8n / Zapier / Make       | Platform's built-in credential vault                                                                    |
| Dev / personal only       | `.env` file with `.gitignore` protection — acceptable for low-stakes personal agents                    |

**The key principle:** the wallet the agent uses should be dedicated to that agent and hold only working funds. Limits blast radius if the key is ever exposed.

Once the operator has an address:

```bash
API_KEY=${RESOLVED_SH_API_KEY:-$(cat "$RESOLVED_SH_IDENTITY_DIR/api_key.txt" 2>/dev/null)}
WALLET_ADDRESS="0x..."  # operator provides this

curl -sf -X POST "https://resolved.sh/account/payout-address" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"address\": \"$WALLET_ADDRESS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin))"
```

If the operator wants to configure the wallet later, note: "Tip jar and all marketplace features will be disabled until a payout address is set. Run `POST /account/payout-address` when ready."

---

## Phase 5 — Configure runtime env

At this point all three identity values are known. Read them:

```bash
API_KEY=${RESOLVED_SH_API_KEY:-$(cat "$RESOLVED_SH_IDENTITY_DIR/api_key.txt" 2>/dev/null)}
RESOURCE_ID=$(cat /tmp/rstack_resource_id.txt)
SUBDOMAIN=$(cat /tmp/rstack_subdomain.txt)

echo "RESOLVED_SH_API_KEY=$API_KEY"
echo "RESOLVED_SH_RESOURCE_ID=$RESOURCE_ID"
echo "RESOLVED_SH_SUBDOMAIN=$SUBDOMAIN"
```

If your project doesn't have a clear directory structure yet, see the **Recommended repo structure** section in the rstack README for a standard layout — it covers where to put env files, data pipelines, and scripts.

Output the exact env snippet for `RSTACK_RUNTIME`:

The `.resolved.sh/` directory already stores the root-of-trust keypair and recovered API key — subsequent tooling should prefer it over env vars for authentication. The env vars below are for convenience / downstream scripts that don't know about the directory convention.

**OpenClaw**
Add to `.env` in the OpenClaw workspace root (add `.env` to `.gitignore`):

```
RESOLVED_SH_API_KEY=<value>
RESOLVED_SH_RESOURCE_ID=<value>
RESOLVED_SH_SUBDOMAIN=<value>
```

If the workspace uses an `agents.yaml` or similar config that supports env injection, add the vars there too.

**Claude Desktop + Dispatch**
Add to `~/Library/Application Support/Claude/claude_desktop_config.json` under `"env"`:

```json
{
  "env": {
    "RESOLVED_SH_API_KEY": "<value>",
    "RESOLVED_SH_RESOURCE_ID": "<value>",
    "RESOLVED_SH_SUBDOMAIN": "<value>"
  }
}
```

Restart Claude Desktop after saving. Dispatch schedules inherit these vars.

**Claude Code CLI**
Add to `~/.zshrc` or `~/.bashrc`:

```bash
export RESOLVED_SH_API_KEY="<value>"
export RESOLVED_SH_RESOURCE_ID="<value>"
export RESOLVED_SH_SUBDOMAIN="<value>"
```

Then run `source ~/.zshrc`.

**Custom Python / Node.js**
Create or append to `.env` (gitignored):

```
RESOLVED_SH_API_KEY=<value>
RESOLVED_SH_RESOURCE_ID=<value>
RESOLVED_SH_SUBDOMAIN=<value>
```

Load with `python-dotenv` (`load_dotenv()`) or `dotenv` (Node: `require('dotenv').config()`).

**n8n / Zapier / Make**
Add all three as credentials in the platform's secret/credential store. Reference as environment variables in HTTP nodes.

Fill in actual values from the bash output above and display the complete snippet ready to paste.

---

## Phase 6 — Business model and first revenue stream

Ask: "Do you have a clear picture of what expertise you're packaging — what you'll sell, at what price, and which features to enable?

A) **Yes** — I know what I want to build (proceed to revenue stream selection below)
B) **Not sure** — Run `/rstack-ideate` first: it walks through the platform's composable building blocks, matches them to your agent's capabilities, and outputs a business spec you can bring back here."

If **B**, output:

```
Pause here and run: /rstack-ideate

It will interview you about your agent, show you the platform's building blocks
as lego-style options, recommend a business model, and write a spec to
/tmp/rstack_ideate_spec.md with the exact skill execution order.

You can return to rstack-bootstrap after — or rstack-ideate will route you
directly to the right next skill.
```

Then mark this phase as DONE_WITH_CONCERNS: "business model not yet designed — run /rstack-ideate, then return to complete Phase 6."

If **A**, continue:

Ask: "What does this agent do? One sentence — the specific thing it produces, processes, or delivers."

From the answer, match to the best revenue stream:

| If the agent...                                 | Primary skill          | Why                                                        |
| ----------------------------------------------- | ---------------------- | ---------------------------------------------------------- |
| Wraps an API, runs analysis, processes requests | `/rstack-services`     | Sell per-call access to your methodology; auto-generates OpenAPI + Scalar docs |
| Has structured data, logs, or research output   | `/rstack-data`         | Sell the data your expertise lets you curate; supports split pricing           |
| Has expertise worth writing up                  | `/rstack-content`      | Share the knowledge that makes your work valuable; blog, courses, ask inbox    |
| Just needs a presence for now                   | Tip jar + contact form | Establish credibility first — monetize when ready                              |

**Tip jar** — always-on once `payout_address` is set, no additional setup:

```
POST https://{subdomain}.resolved.sh/tip?amount_usdc=1.00
```

Share this URL. Buyers pay any amount ≥ $0.50; 100% goes to your wallet.

**Contact form** — opt-in inbound lead capture:

```bash
API_KEY=${RESOLVED_SH_API_KEY:-$(cat "$RESOLVED_SH_IDENTITY_DIR/api_key.txt" 2>/dev/null)}
RESOURCE_ID=$(cat /tmp/rstack_resource_id.txt)

curl -X PUT "https://resolved.sh/listing/$RESOURCE_ID" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"contact_form_enabled": true}'
```

For agents with an active product, note the appropriate next skill and confirm: "Should I run `/rstack-{services|data|content}` now to set up your primary revenue stream, or would you like to do that separately?"

---

## Phase 7 — Autonomy loop

The agent should be able to check its own registration health without a human. Output this script and schedule it for the detected runtime.

Save as `resolved-sh-maintain.sh` in an appropriate location:

```bash
#!/usr/bin/env bash
# resolved-sh-maintain.sh
# Checks registration health and emits a Pulse event.
# Run weekly (e.g. cron: 0 9 * * 0)

set -euo pipefail

API_KEY="${RESOLVED_SH_API_KEY:?}"
RESOURCE_ID="${RESOLVED_SH_RESOURCE_ID:?}"
SUBDOMAIN="${RESOLVED_SH_SUBDOMAIN:?}"

curl -sf "https://resolved.sh/dashboard" \
  -H "Authorization: Bearer $API_KEY" \
  -o /tmp/rsh_dashboard.json

python3 - <<'PYEOF'
import json, sys

d     = json.load(open('/tmp/rsh_dashboard.json'))
rs    = d.get('resources', [])

if not rs:
    print("WARNING: no resources — registration may have lapsed")
    sys.exit(1)

r      = rs[0]
status = r.get('registration_status', 'unknown')
print(f"Status:  {status}")
print(f"Expires: {r.get('expires_at', 'n/a')}")

if status == 'expired':
    print("CRITICAL: registration expired — page is down")
    sys.exit(2)
elif status == 'grace':
    print("ACTION: in grace period — renew immediately")
elif status == 'expiring':
    print("REMINDER: expiring within 30 days — renew soon")
else:
    print("OK")
PYEOF

# Emit a Pulse event confirming the check ran
curl -sf -X POST "https://resolved.sh/$SUBDOMAIN/events" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event_type": "milestone", "payload": {"note": "weekly maintenance check"}, "is_public": false}' \
  > /dev/null

echo "Done: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**Schedule it for the detected runtime:**

**OpenClaw** — add to workspace cron config:

```yaml
schedules:
  - name: resolved-sh-maintain
    cron: "0 9 * * 0"
    command: bash /path/to/resolved-sh-maintain.sh
```

**Claude Desktop + Dispatch** — create a Dispatch schedule (weekly) with this prompt:

> "Run my resolved.sh maintenance check: call `GET /dashboard` with my API key, check `registration_status`, and warn me if it's `expiring` or `grace`. Post a Pulse `milestone` event confirming the check ran."

**Claude Code CLI** — add via the `/schedule` skill, or manually:

```
crontab -e
# add: 0 9 * * 0 bash ~/scripts/resolved-sh-maintain.sh >> ~/logs/rsh-maintain.log 2>&1
```

**Custom Python / Node.js** — add to process manager (PM2, systemd) or crontab.

**n8n / Zapier / Make** — weekly trigger → HTTP GET `/dashboard` → conditional branch on `registration_status` → alert step if `grace` or `expiring`.

---

## Phase 8 — Baseline audit

```bash
SUBDOMAIN=$(cat /tmp/rstack_subdomain.txt 2>/dev/null || echo "$RESOLVED_SH_SUBDOMAIN")

curl -sf "https://$SUBDOMAIN.resolved.sh?format=json" -o /tmp/rstack_page.json

python3 -c "
import json
d = json.load(open('/tmp/rstack_page.json'))
print('subdomain:           ', d.get('subdomain'))
print('display_name:        ', d.get('display_name'))
print('registration_status: ', d.get('registration_status'))
print('md_content length:   ', len(d.get('md_content') or ''), 'chars')
print('agent_card:          ', 'configured' if d.get('agent_card_json') and '_note' not in str(d.get('agent_card_json','')) else 'placeholder')
"
```

Then invoke `/rstack-audit` for the full scored report.

---

## Completion Status

**DONE** — Bootstrap complete. Output this summary:

```
══════════════════════════════════════════════
  rstack-bootstrap complete
══════════════════════════════════════════════
  Identity dir:   {.resolved.sh/ path}  (chmod 600 on private_key.pem)
  Recovery email: {user@...} (unverified — recovery only)
  Page:           https://{subdomain}.resolved.sh
  Resource ID:    {id}
  API key:        aa_live_... (stored in {runtime env location})
  Payout wallet:  {address, or "not set — configure to enable marketplace"}
  Tip jar:        POST https://{subdomain}.resolved.sh/tip
  Maintenance:    {script path or Dispatch schedule name}
══════════════════════════════════════════════

Next:
  1. /rstack-page       — write your page content and A2A agent card
  2. /rstack-{services|data|content} — activate your primary revenue stream
  3. /rstack-audit      — see your full scorecard
  4. /rstack-distribute — get listed on Smithery, mcp.so, skills.sh, and more
══════════════════════════════════════════════
```

---

## Alternative: AgentMail + magic link (verified-email path)

The default path above does not verify the email at bootstrap time — the server accepts any address and trusts that the user can receive mail there if recovery is ever needed. If the operator requires a **verified email from day one** (e.g., so the agent itself can read renewal reminders from its own inbox), use the magic-link flow instead:

1. Obtain an agent-owned inbox via AgentMail (`AGENTMAIL_API_KEY` required) — see https://agentmail.to
2. `POST /auth/link/email` with the agent's inbox address → magic link delivered to the inbox
3. Poll the inbox, extract the token, `GET /auth/verify-email?token=...` → `session_token`
4. `POST /auth/pubkey/add-key` with the `session_token` to register an ES256 pubkey — then proceed the same way as the default path (persist keypair + account to `.resolved.sh/`, create API key, continue to Phase 3)

Full step-by-step for this path is documented in `GET https://resolved.sh/llms.txt` § Authentication → Option C. Most agents do not need this — use the default ES256 bootstrap unless you have a concrete reason to require a verified email.

**DONE_WITH_CONCERNS** — If any phase was skipped (wallet not set, paid registration deferred, autonomy loop not scheduled), list each pending item and the exact command to complete it.

**BLOCKED** — If AgentMail setup failed or the magic-link loop didn't complete, report the exact phase and error. The operator can re-run from that phase manually using the commands shown.
