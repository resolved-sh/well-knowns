#!/usr/bin/env python3
"""
scripts/publish_signals.py

Upload data/signals_delta.jsonl to resolved.sh as the WK delta feed and emit a
Pulse event. No-op (exit 0) when the delta file is empty.

Reads:  data/signals_delta.jsonl
Writes: data/signals_listing_id.txt   — file_id of the uploaded delta dataset

Filename uploaded: x402-daily-signals.jsonl  (stable — replaces prior version on each run)
Pricing: $0.10/query · $0.50/download

Env:
  RESOLVED_API_KEY      — WK's resolved.sh API key (required; NOT RESOLVED_SH_API_KEY)
  RESOLVED_RESOURCE_ID  — WK listing resource ID (default = WK production ID)
"""
import json
import os
import sys
from pathlib import Path

import httpx

REPO_ROOT       = Path(__file__).parent.parent
DATA_DIR        = REPO_ROOT / "data"
DELTA_PATH      = DATA_DIR / "signals_delta.jsonl"
LISTING_ID_FILE = DATA_DIR / "signals_listing_id.txt"

RESOLVED_BASE  = "https://resolved.sh"
WK_SUBDOMAIN   = "well-knowns"
DELTA_FILENAME = "x402-daily-signals.jsonl"
DELTA_DESCRIPTION = (
    "Newly discovered x402-enabled domains and .well-known/ endpoint changes — "
    "delta feed, updated multiple times daily. Each row records a new, changed, "
    "or removed (domain, endpoint) signal since the last publish. "
    "Columns: domain, rank, endpoint, change_type, current_status, "
    "content_signature, crawled_at, detected_at. "
    "Source: Tranco top 100k crawl, diffed against previous publish state."
)
QUERY_PRICE    = 0.10
DOWNLOAD_PRICE = 0.50


def load_dotenv(env_path: Path):
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k, v)


def main():
    load_dotenv(REPO_ROOT / ".env")

    api_key     = os.environ.get("RESOLVED_API_KEY", "")
    resource_id = os.environ.get(
        "RESOLVED_RESOURCE_ID",
        "ef9f56ad-11a4-43e7-9171-fd108d194ad8",
    )

    if not api_key:
        print("ERROR: RESOLVED_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    if not DELTA_PATH.exists() or DELTA_PATH.stat().st_size == 0:
        print("No new signals, skipping")
        return

    body = DELTA_PATH.read_bytes()
    row_count = sum(1 for line in body.splitlines() if line.strip())
    if row_count == 0:
        print("No new signals, skipping")
        return

    print(f"Uploading {row_count} delta records ({len(body)} bytes) → {DELTA_FILENAME}")

    auth = {"Authorization": f"Bearer {api_key}"}
    upload_url = f"{RESOLVED_BASE}/listing/{resource_id}/data/{DELTA_FILENAME}"

    with httpx.Client(timeout=60.0) as client:
        r = client.put(
            upload_url,
            content=body,
            params={"price_usdc": str(DOWNLOAD_PRICE)},
            headers={**auth, "Content-Type": "application/jsonl"},
        )
        if r.status_code not in (200, 201):
            print(f"ERROR: upload failed {r.status_code} {r.text[:300]}", file=sys.stderr)
            sys.exit(1)

        result  = r.json()
        file_id = result.get("id")
        if not file_id:
            print(f"ERROR: no file id in upload response: {result}", file=sys.stderr)
            sys.exit(1)
        print(f"  uploaded — file_id={file_id}")

        LISTING_ID_FILE.write_text(file_id + "\n")

        patch = client.patch(
            f"{RESOLVED_BASE}/listing/{resource_id}/data/{file_id}",
            headers={**auth, "Content-Type": "application/json"},
            json={
                "description":         DELTA_DESCRIPTION,
                "query_price_usdc":    QUERY_PRICE,
                "download_price_usdc": DOWNLOAD_PRICE,
            },
        )
        if patch.status_code != 200:
            print(f"WARN: description patch failed {patch.status_code} {patch.text[:200]}")
        else:
            print("  description + pricing patched")

        event = client.post(
            f"{RESOLVED_BASE}/{WK_SUBDOMAIN}/events",
            headers={**auth, "Content-Type": "application/json"},
            json={
                "event_type": "data_upload",
                "payload": {
                    "file_id":    file_id,
                    "filename":   DELTA_FILENAME,
                    "size_bytes": len(body),
                    "price_usdc": DOWNLOAD_PRICE,
                    "row_count":  row_count,
                },
                "is_public": True,
            },
        )
        if event.status_code == 200:
            event_id = event.json().get("event_id")
            print(f"  Pulse event emitted: data_upload → {event_id}")
        else:
            print(f"WARN: Pulse emit failed {event.status_code} {event.text[:200]}")


if __name__ == "__main__":
    main()
