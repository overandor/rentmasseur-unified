#!/usr/bin/env python3
"""
Daily Promotion Script — the bridge between rm_traffic and the runtime.

rm_traffic/profileops.db → sanitize → hash → compact → daily_evidence_packet.json

Usage:
    python3 daily_promotion.py [--traffic-db PATH] [--out PATH] [--ingest-url URL]
"""

import argparse
import json
import os
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from rm_revenue_engine.revenue_ops import (
    init_db, generate_daily_evidence_packet, ingest_metrics, write_receipt
)

DEFAULT_TRAFFIC_DB = Path(__file__).resolve().parent.parent / "rm_traffic" / "profileops.db"
DEFAULT_OUT = Path(__file__).resolve().parent / "content" / "daily_evidence_packet.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traffic-db", default=str(DEFAULT_TRAFFIC_DB))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--ingest-url", default=None, help="POST packet to this URL if set")
    ap.add_argument("--bio-id", default="karpathian_wolf_live")
    args = ap.parse_args()

    init_db()

    print(f"Generating daily evidence packet from {args.traffic_db}...")
    packet = generate_daily_evidence_packet(args.traffic_db, bio_id=args.bio_id)
    if "error" in packet:
        print(f"ERROR: {packet['error']}")
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(packet, indent=2, default=str))
    print(f"Packet written: {out_path}")
    print(f"  packet_id: {packet['packet_id']}")
    print(f"  profile_views: {packet['metrics']['profile_views']}")
    print(f"  contact_clicks: {packet['metrics']['contact_clicks']}")
    print(f"  contact_click_rate: {packet['derived']['contact_click_rate']}")
    print(f"  decision: {packet['decision']['status']}")
    print(f"  reason: {packet['decision']['reason']}")

    # Also ingest locally
    result = ingest_metrics({
        "date": packet["date"],
        "bio_id": args.bio_id,
        "profile_views": packet["metrics"]["profile_views"],
        "contact_clicks": packet["metrics"]["contact_clicks"],
        "new_visits": packet["metrics"]["new_visits"],
        "new_emails": packet["metrics"]["new_emails"],
        "availability_state": packet["account"]["is_available"],
        "profile_visible": packet["account"]["profile_visible"],
        "headline_hash": packet["bio"]["bio_hash"],
        "bio_hash": packet["bio"]["bio_hash"],
        "notes": "Daily promotion script ingestion.",
    })
    print(f"\nLocal ingest: {result['decision']['status']} — {result['decision']['reason']}")
    print(f"  computed CTR: {result['computed']['contact_click_rate']}")
    print(f"  clicks/100 views: {result['computed']['contact_clicks_per_100_views']}")

    # Optionally POST to remote runtime
    if args.ingest_url:
        import requests
        print(f"\nPOSTing to {args.ingest_url}...")
        try:
            r = requests.post(args.ingest_url, json=packet, timeout=15)
            print(f"  Response: {r.status_code} — {r.json()}")
        except Exception as e:
            print(f"  POST failed: {e}")

    write_receipt("daily_promotion", {
        "packet_id": packet["packet_id"],
        "decision": packet["decision"]["status"],
        "out_path": str(out_path),
    })
    print("\nReceipt written.")


if __name__ == "__main__":
    main()
