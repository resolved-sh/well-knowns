#!/usr/bin/env python3
"""
well_knowns/upload.py
Uploads data products to resolved.sh listing.

Filenames are date-stamped (e.g. agent-index-2026-04-28.json). resolved.sh
supports true upsert via PUT — re-uploading a same-named file replaces it
atomically without consuming a slot in the file cap. After uploads finish,
this script runs a cleanup pass that DELETEs older dated versions of each
dataset, keeping only the most recent KEEP_VERSIONS per dataset.
"""

import json
import logging
import re
import sys
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

RESOURCE_ID = "ef9f56ad-11a4-43e7-9171-fd108d194ad8"
BASE_URL    = "https://resolved.sh"
DATA_DIR    = Path(__file__).parent.parent / "data"

# Dataset patterns. The `{date}` placeholder is interpolated to today at upload
# time; cleanup matches it as YYYY-MM-DD when sweeping old dated versions.
PRODUCTS = [
    {"pattern": "agent-index-{date}.json",        "price": "0.10"},
    {"pattern": "oidc-providers-{date}.json",     "price": "0.25"},
    {"pattern": "mcp-infrastructure-{date}.json", "price": "0.10"},
    {"pattern": "full-catalog-{date}.jsonl",      "price": "1.00"},
    {"pattern": "delta-{date}.jsonl",             "price": "0.01"},
    # catalog-manifest.json is published directly on the listing page for free
    # (not uploaded as a paid file)
]

# Most-recent dated versions to keep per dataset (today + KEEP_VERSIONS-1 older).
KEEP_VERSIONS = 2

DATE_RE = r"\d{4}-\d{2}-\d{2}"

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


def upload_file(client: httpx.Client, filepath: Path, price_usdc: str) -> dict:
    """PUT a data file to resolved.sh under its on-disk filename (atomic upsert)."""
    filename = filepath.name
    url = f"{BASE_URL}/listing/{RESOURCE_ID}/data/{filename}"
    # Minimum price is 0.01 — set free files to 0.01
    price_val = max(0.01, float(price_usdc)) if price_usdc else 0.01
    params = {"price_usdc": str(price_val)}
    headers = {"Content-Type": content_type_for(filename)}
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
            log.info("Uploaded %s @ $%s — %s", filename, price_usdc, result.get("id", ""))
            return result
        log.error("Upload failed for %s: %d %s", filename, r.status_code, r.text[:200])
        return {"error": f"{r.status_code}: {r.text[:200]}"}
    except Exception as e:
        log.error("Request error uploading %s: %s", filename, e)
        return {"error": str(e)}


def list_files(client: httpx.Client) -> list:
    """List current files on the listing."""
    r = client.get(f"{BASE_URL}/listing/{RESOURCE_ID}/data")
    if r.status_code == 200:
        return r.json().get("files", []) or []
    return []


def delete_file(client: httpx.Client, file_id: str) -> bool:
    """Delete a file by ID."""
    r = client.delete(f"{BASE_URL}/listing/{RESOURCE_ID}/data/{file_id}")
    if r.status_code == 204:
        log.info("Deleted file %s", file_id)
        return True
    log.warning("Failed to delete %s: %d %s", file_id, r.status_code, r.text[:200])
    return False


def cleanup_old_versions(client: httpx.Client, patterns: list,
                         keep: int = KEEP_VERSIONS) -> int:
    """
    GET the listing's files and DELETE old dated versions of each dataset
    pattern, keeping the `keep` most recent (sorted by embedded YYYY-MM-DD
    desc). Returns the number of deletions performed.
    """
    files = list_files(client)
    deleted = 0
    for pattern in patterns:
        if "{date}" not in pattern:
            continue
        prefix, ext = pattern.split("{date}", 1)
        rx = re.compile(r"^" + re.escape(prefix) + r"(" + DATE_RE + r")" + re.escape(ext) + r"$")
        matches = []
        for f in files:
            m = rx.match(f.get("filename", ""))
            if m:
                matches.append((m.group(1), f["filename"], f["id"]))
        matches.sort(key=lambda x: x[0], reverse=True)
        for date_str, filename, file_id in matches[keep:]:
            log.info("Cleanup: deleting old %s (id=%s, date=%s)",
                     filename, file_id, date_str)
            if delete_file(client, file_id):
                deleted += 1
    return deleted


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Upload data products to resolved.sh")
    parser.add_argument("--date",    default=None, help="Date string for filename interpolation (YYYY-MM-DD)")
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

    # Show current files
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
        pattern = product["pattern"]
        price   = product["price"]
        filename = pattern.replace("{date}", date) if "{date}" in pattern else pattern
        filepath = DATA_DIR / filename
        if not filepath.exists():
            log.info("Skipping (not found): %s", filepath)
            continue

        result = upload_file(client, filepath, price)
        if "error" in result:
            errors.append({"file": filename, "error": result["error"]})
        else:
            uploaded.append({"file": filename, "price": price, "id": result.get("id")})

    log.info("\n=== Upload Summary ===")
    log.info("Uploaded:  %d", len(uploaded))
    log.info("Errors:    %d", len(errors))
    if errors:
        for e in errors:
            log.error("  %s: %s", e["file"], e["error"])

    # Cleanup: keep only the KEEP_VERSIONS most recent dated versions per dataset.
    # One pass at the end is equivalent to per-upload cleanup but does a single GET.
    if uploaded:
        log.info("\n=== Cleanup ===")
        patterns = [p["pattern"] for p in PRODUCTS]
        deleted = cleanup_old_versions(client, patterns, keep=KEEP_VERSIONS)
        log.info("Deleted %d old dated version(s) (kept %d per dataset)",
                 deleted, KEEP_VERSIONS)

    client.close()


if __name__ == "__main__":
    main()
