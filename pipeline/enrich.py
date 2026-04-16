#!/usr/bin/env python3
"""
pipeline/enrich.py

Buys Double Agent's x402 ecosystem company data and cross-references it
with our well-known endpoint crawl data to produce premium grouped datasets.

Outputs:
  data/double-agent-companies-{date}.jsonl  — cached copy of purchased data
  data/x402-agent-cards-{date}.jsonl        — agent-card hits from x402 companies
  data/x402-mcp-infrastructure-{date}.jsonl — MCP/oauth hits from x402 companies
  data/x402-wellknown-overview-{date}.jsonl — all 7 endpoint types for x402 companies

Uploads the three grouped datasets to resolved.sh and patches their descriptions.
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


def x402_download(url: str, cache_path: Path) -> list[dict]:
    """
    Download a file via x402 payment. Returns list of parsed JSONL records.
    Uses cache_path if already downloaded today.
    """
    if cache_path.exists():
        log.info("Using cached file: %s", cache_path)
        records = []
        with cache_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        log.info("Loaded %d records from cache", len(records))
        return records

    if not EVM_PRIVATE_KEY or not EVM_PUBLIC_ADDR:
        log.error("EVM_PRIVATE_KEY and EVM_PUBLIC_ADDRESS are required for x402 payments")
        sys.exit(1)

    # Check balance before attempting payment
    balance = check_usdc_balance(EVM_PUBLIC_ADDR)
    if balance >= 0:
        log.info("Wallet USDC balance: $%.4f", balance)
        if balance < 2.05:  # rough threshold covering the $2.00 full index + small buffer
            log.error(
                "Insufficient USDC balance: $%.4f in %s. "
                "Need at least ~$2.10 to purchase Double Agent full index ($2.00). "
                "Fund the wallet with USDC on Base and retry.",
                balance, EVM_PUBLIC_ADDR
            )
            sys.exit(1)

    log.info("Attempting x402 purchase: %s", url)
    with httpx.Client(timeout=30.0) as client:
        # Step 1: probe (expect 402)
        r = client.get(url)
        if r.status_code != 402:
            log.error("Expected 402, got %d: %s", r.status_code, r.text[:200])
            sys.exit(1)

        payment_req = r.json()
        accepts = payment_req.get("accepts", [])
        if not accepts:
            log.error("No accepts in 402 response: %s", payment_req)
            sys.exit(1)

        accept = accepts[0]
        amount_usdc = int(accept["amount"]) / 1_000_000
        log.info("Payment required: $%.2f USDC to %s", amount_usdc, accept["payTo"])

        # Step 2: sign and pay
        proof_b64 = sign_x402_payment(accept)
        log.info("Signed payment, sending...")

        r2 = client.get(url, headers={"PAYMENT-SIGNATURE": proof_b64})
        if r2.status_code != 200:
            log.error("Payment failed: %d %s", r2.status_code, r2.text[:400])
            sys.exit(1)

        log.info("Payment accepted! Downloaded %d bytes", len(r2.content))

        # Save to cache
        cache_path.write_bytes(r2.content)
        log.info("Saved to %s", cache_path)

        records = []
        for line in r2.text.splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        log.info("Parsed %d records", len(records))
        return records


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
    Tries common field names for the domain/URL.
    """
    index = {}
    for rec in records:
        # Double Agent records likely have domain or website field
        raw = (
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

def upload_file(client: httpx.Client, path: Path, price_usdc: float,
                query_price: float, download_price: float, description: str):
    """Upload a JSONL file to resolved.sh and patch its description."""
    filename = path.name
    url = f"{RESOLVED_BASE}/listing/{RESOURCE_ID}/data/{filename}"

    with path.open("rb") as f:
        body = f.read()

    r = client.put(
        url,
        content=body,
        params={"price_usdc": str(price_usdc)},
        headers={"Content-Type": "application/jsonl"},
    )
    if r.status_code not in (200, 201):
        log.error("Upload failed for %s: %d %s", filename, r.status_code, r.text[:200])
        return

    file_id = r.json().get("id")
    log.info("Uploaded %s (id: %s)", filename, file_id)

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
        log.info("Patched description for %s", filename)
    else:
        log.warning("Patch failed for %s: %d", filename, patch.status_code)


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

    # ── Step 1: Download Double Agent company data ────────────────────────────
    cache_path = DATA_DIR / f"double-agent-companies-{date}.jsonl"
    download_url = f"{DOUBLE_AGENT_BASE}/data/{DOUBLE_AGENT_FILE}"
    log.info("=== Purchasing Double Agent company data ===")
    company_records = x402_download(download_url, cache_path)

    if not company_records:
        log.error("No company data received from Double Agent")
        sys.exit(1)

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
    with httpx.Client(headers=auth_headers, timeout=60.0) as client:
        upload_file(
            client, agent_cards_path,
            price_usdc=0.10, query_price=0.10, download_price=0.25,
            description=(
                f"agent-card.json results filtered to x402 ecosystem companies only "
                f"({len(agent_cards)} records). Cross-referenced with Double Agent company "
                f"intelligence. Columns: domain, rank, name, description, url, skills, "
                f"capabilities, x402_company_name, x402_category, x402_status. "
                f"Source: Tranco top 100k crawl + Double Agent. Updated weekly."
            )
        )
        upload_file(
            client, mcp_infra_path,
            price_usdc=0.10, query_price=0.10, download_price=0.25,
            description=(
                f"MCP server and oauth-protected-resource endpoints from x402 ecosystem "
                f"companies ({len(mcp_infra)} records). Cross-referenced with Double Agent. "
                f"Columns: domain, rank, mcp_json, oauth_protected_resource, x402_company_name, "
                f"x402_category, x402_status. Source: Tranco top 100k crawl + Double Agent. "
                f"Updated weekly."
            )
        )
        upload_file(
            client, overview_path,
            price_usdc=0.15, query_price=0.15, download_price=0.50,
            description=(
                f"All 7 well-known endpoint types for x402 ecosystem companies "
                f"({len(overview)} rows, one per endpoint hit). Combines crawl data with "
                f"Double Agent business intelligence. Columns: domain, rank, endpoint, "
                f"raw_content, x402_company_name, x402_category, x402_status, "
                f"x402_has_agent_card. Source: Tranco top 100k crawl + Double Agent. "
                f"Updated weekly."
            )
        )

    log.info("=== Enrichment complete ===")
    log.info("Agent Cards:       %d records", len(agent_cards))
    log.info("MCP Infrastructure:%d records", len(mcp_infra))
    log.info("WK Overview:       %d rows",    len(overview))
    log.info("Double Agent data cached at: %s", cache_path)


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
