#!/usr/bin/env python3
"""
pipeline/enrich.py

Buys Double Agent's x402 ecosystem company data and cross-references it
with our well-known endpoint crawl data to produce premium grouped datasets.

Local outputs (dated, archive):
  pipeline/cache/{da-filename}              — cached DA purchases (max one per day)
  data/x402-agent-cards-{date}.jsonl        — agent-card hits from x402 companies
  data/x402-mcp-infrastructure-{date}.jsonl — MCP/oauth hits from x402 companies
  data/x402-wellknown-overview-{date}.jsonl — all 7 endpoint types for x402 companies

Uploads use stable filenames so each PUT atomically upserts the same slot on
the resolved.sh listing — no dated files accumulate, no cap pressure, no
cleanup logic needed:
  x402-agent-cards-latest.jsonl
  x402-mcp-infrastructure-latest.jsonl
  x402-wellknown-overview-latest.jsonl

Exits non-zero if any upload fails so the caller (post-crawl.sh) can emit an
honest `success: true/false` Pulse event.
"""

import base64
import json
import logging
import os
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

REPO_ROOT    = Path(__file__).parent.parent
DATA_DIR     = REPO_ROOT / "data"
LOG_FILE     = DATA_DIR / "state" / "enrich.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("enrich")

# Env vars — actual names used in this repo's .env
RESOLVED_API_KEY = os.environ.get("RESOLVED_API_KEY", "")
RESOURCE_ID      = os.environ.get("RESOLVED_RESOURCE_ID", "ef9f56ad-11a4-43e7-9171-fd108d194ad8")
EVM_PRIVATE_KEY  = os.environ.get("EVM_PRIVATE_KEY", "")
EVM_PUBLIC_ADDR  = os.environ.get("EVM_PUBLIC_ADDRESS", "")

# Double Agent — source of x402 ecosystem company data
DOUBLE_AGENT_BASE = "https://agentagent.resolved.sh"
DOUBLE_AGENT_FILE = "x402_ecosystem_full_index.jsonl"  # full company index, $2.00
DA_DELTA_FILE     = "x402_new_activity_feed.jsonl"     # optional delta feed (~$0.50)

# Daily-max-one-purchase cache for Double Agent.
# Index format: {"<filename>": "YYYY-MM-DD"} — date of last purchase per dataset.
CACHE_DIR   = REPO_ROOT / "pipeline" / "cache"
CACHE_INDEX = CACHE_DIR / "da_last_purchased.json"

# Stable upload filenames — re-PUT each run is an atomic upsert.
X402_AGENT_CARDS_UPLOAD = "x402-agent-cards-latest.jsonl"
X402_MCP_INFRA_UPLOAD   = "x402-mcp-infrastructure-latest.jsonl"
X402_OVERVIEW_UPLOAD    = "x402-wellknown-overview-latest.jsonl"

# USDC on Base Mainnet
USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BASE_CHAIN_ID = 8453

# resolved.sh API
RESOLVED_BASE = "https://resolved.sh"


# ── x402 Payment ──────────────────────────────────────────────────────────────

def sign_x402_payment(accept: dict) -> str:
    """
    Sign an x402 v2 payment using EIP-712 / EIP-3009 TransferWithAuthorization.
    Returns base64-encoded JSON proof for the PAYMENT-SIGNATURE header.
    """
    try:
        from eth_account import Account
    except ImportError:
        log.error("eth_account not installed. Run: python3 -m pip install eth_account --user")
        sys.exit(1)

    nonce_bytes = secrets.token_bytes(32)
    nonce_hex   = "0x" + nonce_bytes.hex()
    valid_before = int(time.time()) + accept["maxTimeoutSeconds"]

    domain_data = {
        "name":              accept["extra"]["name"],
        "version":           accept["extra"]["version"],
        "chainId":           int(accept["network"].split(":")[1]),
        "verifyingContract": accept["asset"],
    }
    message_types = {
        "TransferWithAuthorization": [
            {"name": "from",        "type": "address"},
            {"name": "to",          "type": "address"},
            {"name": "value",       "type": "uint256"},
            {"name": "validAfter",  "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce",       "type": "bytes32"},
        ]
    }
    # Note: "from" is a Python keyword but valid as a dict key
    message_data = {
        "from":        EVM_PUBLIC_ADDR,
        "to":          accept["payTo"],
        "value":       int(accept["amount"]),
        "validAfter":  0,
        "validBefore": valid_before,
        "nonce":       nonce_bytes,
    }

    account = Account.from_key(EVM_PRIVATE_KEY)
    signed  = account.sign_typed_data(domain_data, message_types, message_data)
    sig_hex = "0x" + signed.signature.hex()

    proof = {
        "x402Version": 2,
        "payload": {
            "authorization": {
                "from":        EVM_PUBLIC_ADDR,
                "to":          accept["payTo"],
                "value":       accept["amount"],
                "validAfter":  "0",
                "validBefore": str(valid_before),
                "nonce":       nonce_hex,
            },
            "signature": sig_hex,
        },
        "accepted": accept,
    }
    return base64.b64encode(json.dumps(proof).encode()).decode()


def check_usdc_balance(wallet_addr: str) -> float:
    """Check USDC balance on Base mainnet. Returns balance in USDC (not microUSDC)."""
    data = "0x70a08231" + "000000000000000000000000" + wallet_addr[2:].lower()
    try:
        r = httpx.post(
            "https://mainnet.base.org",
            json={"jsonrpc": "2.0", "method": "eth_call",
                  "params": [{"to": USDC_CONTRACT, "data": data}, "latest"], "id": 1},
            timeout=10.0,
        )
        hex_val = r.json().get("result", "0x0")
        return int(hex_val, 16) / 1_000_000
    except Exception as e:
        log.warning("Could not check USDC balance: %s", e)
        return -1.0


def x402_download(url: str, save_path: Path, *, allow_missing: bool = False):
    """
    Purchase a file via x402 payment, save to save_path, return parsed JSONL records.
    Always performs a real purchase — caching decisions are made by the caller
    (see fetch_or_load).

    When allow_missing=True, a 404 from the probe returns None instead of
    exiting (used for optional files that DA may not publish).
    """
    if not EVM_PRIVATE_KEY or not EVM_PUBLIC_ADDR:
        log.error("EVM_PRIVATE_KEY and EVM_PUBLIC_ADDRESS are required for x402 payments")
        sys.exit(1)

    log.info("Attempting x402 purchase: %s", url)
    with httpx.Client(timeout=30.0) as client:
        # Step 1: probe (expect 402)
        r = client.get(url)
        if r.status_code == 404 and allow_missing:
            log.info("File not available at %s (404) — skipping", url)
            return None
        if r.status_code != 402:
            log.error("Expected 402, got %d: %s", r.status_code, r.text[:200])
            sys.exit(1)

        accepts = r.json().get("accepts", [])
        if not accepts:
            log.error("No accepts in 402 response")
            sys.exit(1)

        accept      = accepts[0]
        amount_usdc = int(accept["amount"]) / 1_000_000
        log.info("Payment required: $%.4f USDC to %s", amount_usdc, accept["payTo"])

        # Balance check sized to the actual amount required (+ small buffer)
        balance = check_usdc_balance(EVM_PUBLIC_ADDR)
        if balance >= 0:
            log.info("Wallet USDC balance: $%.4f", balance)
            if balance < amount_usdc + 0.05:
                log.error(
                    "Insufficient USDC balance: $%.4f in %s. Need ~$%.4f for this purchase.",
                    balance, EVM_PUBLIC_ADDR, amount_usdc + 0.05,
                )
                sys.exit(1)

        # Step 2: sign and pay
        proof_b64 = sign_x402_payment(accept)
        log.info("Signed payment, sending...")

        r2 = client.get(url, headers={"PAYMENT-SIGNATURE": proof_b64})
        if r2.status_code != 200:
            log.error("Payment failed: %d %s", r2.status_code, r2.text[:400])
            sys.exit(1)

        log.info("Payment accepted! Downloaded %d bytes", len(r2.content))
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(r2.content)
        log.info("Saved to %s", save_path)

        records = _parse_jsonl_text(r2.text)
        log.info("Parsed %d records", len(records))
        return records


# ── Daily-max-one-purchase cache ──────────────────────────────────────────────

def _parse_jsonl_text(text: str) -> list[dict]:
    records = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return _parse_jsonl_text(path.read_text())


def load_cache_index() -> dict:
    if not CACHE_INDEX.exists():
        return {}
    try:
        return json.loads(CACHE_INDEX.read_text())
    except json.JSONDecodeError:
        return {}


def save_cache_index(index: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_INDEX.write_text(json.dumps(index, indent=2))


def fetch_or_load(filename: str, cache_index: dict,
                  *, required: bool = False) -> tuple[list[dict], bool]:
    """
    Get records for a DA file using the daily-max-one-purchase cache. Returns
    (records, was_purchased). Each dataset is purchased at most once per UTC
    day; subsequent calls the same day reuse the on-disk cache file.

    With required=False, a 404 from DA returns ([], False) — the file isn't
    available on DA today (e.g. an optional delta feed not yet published).
    """
    today      = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_path = CACHE_DIR / filename
    last_date  = cache_index.get(filename)

    if last_date == today and cache_path.exists():
        log.info("Cache hit for %s — already purchased today (%s)", filename, today)
        return _read_jsonl(cache_path), False

    if last_date == today:
        log.warning("Index says %s purchased today but file is missing — re-purchasing",
                    filename)
    elif last_date:
        log.info("Last purchase of %s was %s — purchasing again for %s",
                 filename, last_date, today)
    else:
        log.info("First purchase of %s", filename)

    download_url = f"{DOUBLE_AGENT_BASE}/data/{filename}"
    records = x402_download(download_url, cache_path, allow_missing=not required)

    if records is None:
        # File not available on DA today (only possible with required=False).
        return [], False

    cache_index[filename] = today
    save_cache_index(cache_index)
    return records, True


# ── Domain normalization ──────────────────────────────────────────────────────

def extract_domain(value: str) -> str:
    """Normalize a URL or domain string to bare domain (lowercase, no www)."""
    if not value:
        return ""
    # Strip scheme
    v = re.sub(r'^https?://', '', str(value).lower().strip())
    # Strip path and port
    v = v.split("/")[0].split(":")[0].split("?")[0]
    # Strip www.
    if v.startswith("www."):
        v = v[4:]
    return v.strip()


def build_domain_index(records: list[dict]) -> dict[str, dict]:
    """
    Build a domain → company record index from Double Agent data.

    Field-name fallback chain (DA's schema as of 2026-04):
      domain_primary  → canonical
      domain_secondary → secondary domain when set
      domain / website / url / github_url → older field names, kept as
        forward-compat fallbacks
    """
    index = {}
    for rec in records:
        raw = (
            rec.get("domain_primary") or rec.get("domain_secondary") or
            rec.get("domain") or rec.get("website") or
            rec.get("url") or rec.get("github_url") or ""
        )
        domain = extract_domain(raw)
        if domain:
            index[domain] = rec
    return index


# ── Grouped dataset generators ────────────────────────────────────────────────

def find_latest_file(pattern: str):
    """Find the most recently dated file matching data/{pattern}-YYYY-MM-DD.json/jsonl."""
    matches = sorted(DATA_DIR.glob(pattern), reverse=True)
    return matches[0] if matches else None


def load_json_file(path: Path) -> list[dict]:
    if not path or not path.exists():
        return []
    text = path.read_text()
    data = json.loads(text)
    return data if isinstance(data, list) else []


def load_raw_crawl(domain_index: dict[str, dict]) -> list[dict]:
    """
    Load raw-crawl.jsonl and attach x402 enrichment fields where domain matches.
    Returns all crawl records (enriched ones have x402_* fields set).
    """
    raw_path = DATA_DIR / "raw-crawl.jsonl"
    if not raw_path.exists():
        log.warning("raw-crawl.jsonl not found — cannot produce overview dataset")
        return []

    seen, records = set(), []
    with raw_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            domain = rec.get("domain", "")
            if not domain or domain in seen:
                continue
            seen.add(domain)
            company = domain_index.get(domain)
            if company:
                rec["x402_company_name"] = company.get("name") or company.get("company_name") or ""
                rec["x402_category"]     = company.get("category") or company.get("sector") or ""
                rec["x402_status"]       = company.get("status") or company.get("pr_status") or ""
                rec["x402_has_agent_card"] = company.get("has_agent_card", False)
                records.append(rec)
    return records


def generate_x402_agent_cards(crawl_records: list[dict]) -> list[dict]:
    """agent-card.json hits from x402 ecosystem companies."""
    results = []
    for rec in crawl_records:
        ep = rec.get("endpoints", {}).get("agent-card.json", {})
        if ep.get("status") != 200 or not ep.get("data"):
            continue
        data = ep["data"] if isinstance(ep.get("data"), dict) else {}
        results.append({
            "domain":              rec["domain"],
            "rank":                rec.get("rank"),
            "crawled_at":          rec["crawled_at"],
            "name":                data.get("name"),
            "description":         data.get("description"),
            "url":                 data.get("url"),
            "skills":              data.get("skills", []),
            "capabilities":        data.get("capabilities", {}),
            "x402_company_name":   rec.get("x402_company_name", ""),
            "x402_category":       rec.get("x402_category", ""),
            "x402_status":         rec.get("x402_status", ""),
            "x402_has_agent_card": rec.get("x402_has_agent_card", False),
        })
    return sorted(results, key=lambda x: (x.get("rank") or 999999, x.get("domain", "")))


def generate_x402_mcp_infrastructure(crawl_records: list[dict]) -> list[dict]:
    """MCP/oauth-protected-resource hits from x402 ecosystem companies."""
    results = []
    for rec in crawl_records:
        mcp_ep   = rec.get("endpoints", {}).get("mcp.json", {})
        oauth_ep = rec.get("endpoints", {}).get("oauth-protected-resource", {})
        mcp_data   = mcp_ep.get("status") == 200 and mcp_ep.get("data")
        oauth_data = oauth_ep.get("status") == 200 and oauth_ep.get("data")
        if not mcp_data and not oauth_data:
            continue
        entry = {
            "domain":              rec["domain"],
            "rank":                rec.get("rank"),
            "crawled_at":          rec["crawled_at"],
            "x402_company_name":   rec.get("x402_company_name", ""),
            "x402_category":       rec.get("x402_category", ""),
            "x402_status":         rec.get("x402_status", ""),
        }
        if mcp_data:
            entry["mcp_json"] = mcp_ep["data"]
        if oauth_data:
            entry["oauth_protected_resource"] = oauth_ep["data"]
        results.append(entry)
    return results


def generate_x402_wellknown_overview(crawl_records: list[dict]) -> list[dict]:
    """All 7 endpoint types for x402 companies — one row per successful hit."""
    results = []
    for rec in crawl_records:
        for endpoint, ep_data in rec.get("endpoints", {}).items():
            if ep_data.get("status") == 200:
                results.append({
                    "domain":              rec["domain"],
                    "rank":                rec.get("rank"),
                    "crawled_at":          rec["crawled_at"],
                    "endpoint":            endpoint,
                    "raw_content":         ep_data.get("data"),
                    "x402_company_name":   rec.get("x402_company_name", ""),
                    "x402_category":       rec.get("x402_category", ""),
                    "x402_status":         rec.get("x402_status", ""),
                    "x402_has_agent_card": rec.get("x402_has_agent_card", False),
                })
    return results


# ── Upload helpers ────────────────────────────────────────────────────────────

def upload_file(client: httpx.Client, path: Path, upload_filename: str,
                price_usdc: float, query_price: float, download_price: float,
                description: str) -> bool:
    """
    Upload a local JSONL file to resolved.sh under a stable upload filename
    and patch its description+pricing. Returns True on successful upload
    (patch failures are warnings, not failures).
    """
    url = f"{RESOLVED_BASE}/listing/{RESOURCE_ID}/data/{upload_filename}"

    with path.open("rb") as f:
        body = f.read()

    r = client.put(
        url,
        content=body,
        params={"price_usdc": str(price_usdc)},
        headers={"Content-Type": "application/jsonl"},
    )
    if r.status_code != 201:
        log.error("Upload failed for %s: %d %s", upload_filename, r.status_code, r.text[:200])
        return False

    file_id = r.json().get("id")
    log.info("Uploaded %s (from %s) (id: %s)", upload_filename, path.name, file_id)

    # Patch description + pricing
    patch = client.patch(
        f"{RESOLVED_BASE}/listing/{RESOURCE_ID}/data/{file_id}",
        json={
            "description":       description,
            "query_price_usdc":  query_price,
            "download_price_usdc": download_price,
        },
    )
    if patch.status_code == 200:
        log.info("Patched description for %s", upload_filename)
    else:
        log.warning("Patch failed for %s: %d", upload_filename, patch.status_code)
    return True


def write_jsonl(path: Path, records: list[dict]):
    with path.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    log.info("Wrote %d rows → %s", len(records), path)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not RESOLVED_API_KEY:
        log.error("RESOLVED_API_KEY not set")
        sys.exit(1)

    # ── Step 1: Acquire DA data (max one purchase per day, per file) ─────────
    cache_index = load_cache_index()

    log.info("=== Acquiring Double Agent company index ===")
    company_records, purchased_index = fetch_or_load(
        DOUBLE_AGENT_FILE, cache_index, required=True,
    )
    log.info("Company records: %d (purchased=%s)", len(company_records), purchased_index)

    if not company_records:
        log.error("No company data received from Double Agent")
        sys.exit(1)

    # Step 1b: optional delta feed — purchased once per day if DA publishes it
    log.info("=== Acquiring DA delta feed (%s) ===", DA_DELTA_FILE)
    delta_records, purchased_delta = fetch_or_load(
        DA_DELTA_FILE, cache_index, required=False,
    )
    if delta_records:
        log.info("DA delta feed: %d records (purchased=%s) — merging into company index",
                 len(delta_records), purchased_delta)
        company_records.extend(delta_records)

    # Log available fields for debugging
    if company_records:
        sample = company_records[0]
        log.info("Sample company record keys: %s", list(sample.keys()))

    # ── Step 2: Build domain lookup index ────────────────────────────────────
    log.info("=== Building domain index from %d company records ===", len(company_records))
    domain_index = build_domain_index(company_records)
    log.info("Domain index has %d entries", len(domain_index))

    # ── Step 3: Load raw crawl + cross-reference ──────────────────────────────
    log.info("=== Cross-referencing with well-known crawl data ===")
    enriched_records = load_raw_crawl(domain_index)
    log.info("Found %d x402 company domains in crawl data", len(enriched_records))

    if not enriched_records:
        log.warning("No domain overlap found between crawl and Double Agent data.")
        log.warning("Check domain field names in Double Agent data. Sample: %s",
                    company_records[0] if company_records else "empty")

    # ── Step 4: Generate grouped datasets ────────────────────────────────────
    log.info("=== Generating grouped datasets ===")

    agent_cards = generate_x402_agent_cards(enriched_records)
    agent_cards_path = DATA_DIR / f"x402-agent-cards-{date}.jsonl"
    write_jsonl(agent_cards_path, agent_cards)

    mcp_infra = generate_x402_mcp_infrastructure(enriched_records)
    mcp_infra_path = DATA_DIR / f"x402-mcp-infrastructure-{date}.jsonl"
    write_jsonl(mcp_infra_path, mcp_infra)

    overview = generate_x402_wellknown_overview(enriched_records)
    overview_path = DATA_DIR / f"x402-wellknown-overview-{date}.jsonl"
    write_jsonl(overview_path, overview)

    if not any([agent_cards, mcp_infra, overview]):
        log.warning("All grouped datasets are empty — no domain overlap.")
        log.info("Uploading empty files anyway as placeholders.")

    # ── Step 5: Upload to resolved.sh ────────────────────────────────────────
    log.info("=== Uploading grouped datasets to resolved.sh ===")
    auth_headers = {"Authorization": f"Bearer {RESOLVED_API_KEY}"}

    agent_cards_desc = (
        f"agent-card.json results filtered to x402 ecosystem companies only "
        f"({len(agent_cards)} records). Cross-referenced with Double Agent company "
        f"intelligence. Columns: domain, rank, name, description, url, skills, "
        f"capabilities, x402_company_name, x402_category, x402_status. "
        f"Source: Tranco top 100k crawl + Double Agent. Updated weekly."
    )
    mcp_infra_desc = (
        f"MCP server and oauth-protected-resource endpoints from x402 ecosystem "
        f"companies ({len(mcp_infra)} records). Cross-referenced with Double Agent. "
        f"Columns: domain, rank, mcp_json, oauth_protected_resource, x402_company_name, "
        f"x402_category, x402_status. Source: Tranco top 100k crawl + Double Agent. "
        f"Updated weekly."
    )
    overview_desc = (
        f"All 7 well-known endpoint types for x402 ecosystem companies "
        f"({len(overview)} rows, one per endpoint hit). Combines crawl data with "
        f"Double Agent business intelligence. Columns: domain, rank, endpoint, "
        f"raw_content, x402_company_name, x402_category, x402_status, "
        f"x402_has_agent_card. Source: Tranco top 100k crawl + Double Agent. "
        f"Updated weekly."
    )

    upload_results = []
    with httpx.Client(headers=auth_headers, timeout=60.0) as client:
        upload_results.append(upload_file(
            client, agent_cards_path, X402_AGENT_CARDS_UPLOAD,
            price_usdc=0.10, query_price=0.10, download_price=0.25,
            description=agent_cards_desc))
        upload_results.append(upload_file(
            client, mcp_infra_path, X402_MCP_INFRA_UPLOAD,
            price_usdc=0.10, query_price=0.10, download_price=0.25,
            description=mcp_infra_desc))
        upload_results.append(upload_file(
            client, overview_path, X402_OVERVIEW_UPLOAD,
            price_usdc=0.15, query_price=0.15, download_price=0.50,
            description=overview_desc))

    log.info("=== Enrichment complete ===")
    log.info("Agent Cards:       %d records", len(agent_cards))
    log.info("MCP Infrastructure:%d records", len(mcp_infra))
    log.info("WK Overview:       %d rows",    len(overview))
    log.info("Double Agent cache index: %s", CACHE_INDEX)
    log.info("Uploads succeeded: %d/%d", sum(upload_results), len(upload_results))

    if not all(upload_results):
        sys.exit(1)


if __name__ == "__main__":
    # Load .env if present
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key not in os.environ:
                    os.environ[key] = val
        # Re-read after loading .env
        globals()["RESOLVED_API_KEY"] = os.environ.get("RESOLVED_API_KEY", "")
        globals()["RESOURCE_ID"]      = os.environ.get("RESOLVED_RESOURCE_ID", RESOURCE_ID)
        globals()["EVM_PRIVATE_KEY"]  = os.environ.get("EVM_PRIVATE_KEY", "")
        globals()["EVM_PUBLIC_ADDR"]  = os.environ.get("EVM_PUBLIC_ADDRESS", "")
    main()
