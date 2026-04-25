#!/usr/bin/env python3
"""
scripts/daily_signals.py

Diff the latest WK crawl output against the previously-published signal state
and write a delta of new/changed/removed `.well-known/` endpoint hits.

Reads:  data/raw-crawl.jsonl          — latest crawl (streamed, large)
Reads:  data/signals_checkpoint.json  — previously-published state (may be absent)
Writes: data/signals_delta.jsonl      — delta records (overwritten each run)
Writes: data/signals_checkpoint.json  — updated checkpoint

A signal is fingerprinted as `{domain}:{endpoint}` → 12-char SHA-256 of the
endpoint's `data` field. Only successful (status=200) endpoint hits count.

The first run on an existing crawl bootstraps the checkpoint and emits an
empty delta — that crawl state becomes the baseline for future diffs.

Delta record schema (one row per change):
  {
    "domain": str,
    "rank": int | null,
    "endpoint": str,
    "change_type": "new" | "changed" | "removed",
    "current_status": int | null,
    "content_signature": str | null,
    "crawled_at": str | null,
    "detected_at": str          # ISO timestamp of this diff run
  }
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT  = Path(__file__).parent.parent
DATA_DIR   = REPO_ROOT / "data"
CRAWL_PATH = DATA_DIR / "raw-crawl.jsonl"
CHECKPOINT = DATA_DIR / "signals_checkpoint.json"
DELTA_PATH = DATA_DIR / "signals_delta.jsonl"


def signature(endpoint_data) -> str:
    """Stable 12-char hash of an endpoint's `data` field."""
    serialized = json.dumps(endpoint_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:12]


def build_current_state(crawl_path: Path) -> dict:
    """
    Stream raw-crawl.jsonl and build a dict of successful hits keyed by
    `{domain}:{endpoint}` → {signature, rank, crawled_at, status}.
    """
    state = {}
    with crawl_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            domain = rec.get("domain")
            if not domain:
                continue
            for endpoint, ep in (rec.get("endpoints") or {}).items():
                if not isinstance(ep, dict):
                    continue
                if ep.get("status") != 200 or ep.get("data") is None:
                    continue
                state[f"{domain}:{endpoint}"] = {
                    "signature":  signature(ep["data"]),
                    "rank":       rec.get("rank"),
                    "crawled_at": rec.get("crawled_at"),
                    "status":     ep.get("status"),
                }
    return state


def load_checkpoint():
    if not CHECKPOINT.exists():
        return None
    try:
        return json.loads(CHECKPOINT.read_text())
    except json.JSONDecodeError:
        return None


def write_checkpoint(current_state: dict, detected_at: str):
    CHECKPOINT.write_text(json.dumps({
        "last_published_at": detected_at,
        "signal_count":      len(current_state),
        "signatures":        {k: v["signature"] for k, v in current_state.items()},
    }, indent=2))


def main():
    if not CRAWL_PATH.exists():
        print(f"ERROR: {CRAWL_PATH} not found — run the crawl first", file=sys.stderr)
        sys.exit(1)

    detected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print(f"Reading crawl from {CRAWL_PATH}")
    current = build_current_state(CRAWL_PATH)
    print(f"  {len(current)} successful endpoint hits in current crawl")

    checkpoint = load_checkpoint()
    if checkpoint is None:
        DELTA_PATH.write_text("")
        write_checkpoint(current, detected_at)
        print(f"Bootstrapped checkpoint with {len(current)} signals — empty delta written")
        return

    previous       = checkpoint.get("signatures", {})
    last_published = checkpoint.get("last_published_at", "unknown")

    deltas = []
    for key, info in current.items():
        prev_sig = previous.get(key)
        if prev_sig is None:
            change_type = "new"
        elif prev_sig != info["signature"]:
            change_type = "changed"
        else:
            continue
        domain, endpoint = key.split(":", 1)
        deltas.append({
            "domain":            domain,
            "rank":              info["rank"],
            "endpoint":          endpoint,
            "change_type":       change_type,
            "current_status":    info["status"],
            "content_signature": info["signature"],
            "crawled_at":        info["crawled_at"],
            "detected_at":       detected_at,
        })

    for key in previous:
        if key not in current:
            domain, endpoint = key.split(":", 1)
            deltas.append({
                "domain":            domain,
                "rank":              None,
                "endpoint":          endpoint,
                "change_type":       "removed",
                "current_status":    None,
                "content_signature": None,
                "crawled_at":        None,
                "detected_at":       detected_at,
            })

    with DELTA_PATH.open("w") as f:
        for d in deltas:
            f.write(json.dumps(d) + "\n")

    write_checkpoint(current, detected_at)

    counts = {"new": 0, "changed": 0, "removed": 0}
    for d in deltas:
        counts[d["change_type"]] += 1
    print(
        f"{len(deltas)} new/changed signals since {last_published} "
        f"(new={counts['new']} changed={counts['changed']} removed={counts['removed']})"
    )


if __name__ == "__main__":
    main()
