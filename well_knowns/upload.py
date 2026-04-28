#!/usr/bin/env python3
"""
well_knowns/upload.py
Uploads data products to resolved.sh listing.

Local files in data/ are date-stamped (archive). Uploads use stable filenames
(`*-latest.*`) so each PUT is an atomic upsert against the same slot — no
dated files accumulate on the listing, the file cap is never approached, and
no cleanup logic is needed.

Exits non-zero if any upload fails so callers (post-crawl.sh) can decide
whether to emit a `success: true` Pulse event.
"""

import json
import logging
import sys
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

RESOURCE_ID = "ef9f56ad-11a4-43e7-9171-fd108d194ad8"
BASE_URL    = "https://resolved.sh"
DATA_DIR    = Path(__file__).parent.parent / "data"

# Each product: dated local archive name (with `{date}`) + stable upload name.
PRODUCTS = [
    {"local": "agent-index-{date}.json",        "upload": "agent-index-latest.json",        "price": "0.10"},
    {"local": "oidc-providers-{date}.json",     "upload": "oidc-providers-latest.json",     "price": "0.25"},
    {"local": "mcp-infrastructure-{date}.json", "upload": "mcp-infrastructure-latest.json", "price": "0.10"},
    {"local": "full-catalog-{date}.jsonl",      "upload": "full-catalog-latest.jsonl",      "price": "1.00"},
    {"local": "delta-{date}.jsonl",             "upload": "delta-latest.jsonl",             "price": "0.01"},
    # catalog-manifest.json is published directly on the listing page for free
    # (not uploaded as a paid file)
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("upload")


# ── Upload helpers ─────────────────────────────────────────────────────────────

def content_type_for(filename: str) -> str:
    ext = filename.lower().split(".")[-1]
    return {
        "json": "application/json",
        "jsonl": "application/jsonl",
        "csv":  "text/csv",
    }.get(ext, "application/octet-stream")


def upload_file(client: httpx.Client, filepath: Path, upload_filename: str,
                price_usdc: str) -> dict:
    """PUT a local data file to resolved.sh under upload_filename (atomic upsert)."""
    url = f"{BASE_URL}/listing/{RESOURCE_ID}/data/{upload_filename}"
    # Minimum price is 0.01 — set free files to 0.01
    price_val = max(0.01, float(price_usdc)) if price_usdc else 0.01
    params = {"price_usdc": str(price_val)}
    headers = {"Content-Type": content_type_for(upload_filename)}
    try:
        with filepath.open("rb") as f:
            body = f.read()
    except Exception as e:
        log.error("Failed to read %s: %s", filepath, e)
        return {"error": str(e)}

    try:
        r = client.put(url, content=body, params=params, headers=headers)
        if r.status_code == 201:
            result = r.json()
            log.info("Uploaded %s (from %s) @ $%s — %s",
                     upload_filename, filepath.name, price_usdc, result.get("id", ""))
            return result
        log.error("Upload failed for %s: %d %s",
                  upload_filename, r.status_code, r.text[:200])
        return {"error": f"{r.status_code}: {r.text[:200]}"}
    except Exception as e:
        log.error("Request error uploading %s: %s", upload_filename, e)
        return {"error": str(e)}


def list_files(client: httpx.Client) -> list:
    """List current files on the listing."""
    r = client.get(f"{BASE_URL}/listing/{RESOURCE_ID}/data")
    if r.status_code == 200:
        return r.json().get("files", []) or []
    return []


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Upload data products to resolved.sh")
    parser.add_argument("--date",    default=None, help="Date string for local filename interpolation (YYYY-MM-DD)")
    parser.add_argument("--api-key", required=True, help="resolved.sh API key (aa_live_...)")
    parser.add_argument("--check",   action="store_true", help="Only list current files, don't upload")
    parser.add_argument("--replace", action="store_true", help="(no-op; PUT is now an atomic upsert)")
    args = parser.parse_args()

    date = args.date
    if date is None:
        from datetime import datetime, timezone
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    headers = {"Authorization": f"Bearer {args.api_key}"}
    client  = httpx.Client(headers=headers, timeout=30.0)

    existing = list_files(client)
    if existing:
        log.info("Current files on listing (%d):", len(existing))
        for f in existing:
            log.info("  [%s] %s — $%s — %s bytes — %d downloads",
                     f["id"], f["filename"], f.get("price_usdc", "?"),
                     f.get("size_bytes", "?"), f.get("download_count", 0))

    if args.check:
        return

    uploaded = []
    errors   = []

    for product in PRODUCTS:
        local_pattern   = product["local"]
        upload_filename = product["upload"]
        price           = product["price"]

        local_filename = (
            local_pattern.replace("{date}", date) if "{date}" in local_pattern
            else local_pattern
        )
        filepath = DATA_DIR / local_filename
        if not filepath.exists():
            log.info("Skipping (not found): %s", filepath)
            continue

        result = upload_file(client, filepath, upload_filename, price)
        if "error" in result:
            errors.append({"file": upload_filename, "error": result["error"]})
        else:
            uploaded.append({"file": upload_filename, "price": price, "id": result.get("id")})

    log.info("\n=== Upload Summary ===")
    log.info("Uploaded:  %d", len(uploaded))
    log.info("Errors:    %d", len(errors))
    if errors:
        for e in errors:
            log.error("  %s: %s", e["file"], e["error"])

    client.close()
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
