#!/usr/bin/env python3
"""Create and verify a deterministic SQLite database for CI and preview deploys."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY,
    receipt_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    contact TEXT NOT NULL,
    service TEXT NOT NULL,
    timing TEXT NOT NULL,
    budget TEXT NOT NULL,
    location TEXT NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY,
    receipt_id TEXT NOT NULL UNIQUE,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    payload_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deployment_health (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    checked_at TEXT NOT NULL
);
"""

SERVICES = ("Deep tissue", "Swedish", "Sports recovery", "Relaxation")
TIMINGS = ("today", "tomorrow", "week", "flexible")
BUDGETS = ("100-159", "160-249", "250plus")
LOCATIONS = ("Harlem", "Upper West Side", "Chelsea", "Midtown")


def seed(db_path: Path, rows: int) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM receipts")
        conn.execute("DELETE FROM leads")
        conn.execute("DELETE FROM deployment_health")

        base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        for index in range(1, rows + 1):
            created_at = (base + timedelta(minutes=index)).isoformat()
            payload = {
                "name": f"CI Lead {index:03d}",
                "contact": f"ci-lead-{index:03d}@example.invalid",
                "service": SERVICES[(index - 1) % len(SERVICES)],
                "timing": TIMINGS[(index - 1) % len(TIMINGS)],
                "budget": BUDGETS[(index - 1) % len(BUDGETS)],
                "location": LOCATIONS[(index - 1) % len(LOCATIONS)],
                "score": 50 + (index * 7) % 51,
                "status": "qualified" if index % 3 else "review",
                "created_at": created_at,
            }
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            receipt_id = f"ci_{digest[:20]}"
            cursor = conn.execute(
                """INSERT INTO leads
                (receipt_id,name,contact,service,timing,budget,location,score,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (receipt_id, *payload.values()),
            )
            conn.execute(
                "INSERT INTO receipts(receipt_id,lead_id,payload_sha256,created_at) VALUES (?,?,?,?)",
                (receipt_id, cursor.lastrowid, digest, created_at),
            )

        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO deployment_health(provider,status,checked_at) VALUES (?,?,?)",
            ((provider, "ready", now) for provider in ("cloudflare", "vercel", "netlify")),
        )
        conn.commit()

        counts = {
            "leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
            "receipts": conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],
            "deployment_health": conn.execute("SELECT COUNT(*) FROM deployment_health").fetchone()[0],
        }
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok" or counts["leads"] != rows or counts["receipts"] != rows:
            raise RuntimeError(f"database verification failed: integrity={integrity}, counts={counts}")
        return counts
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("artifacts/ci/rentmasseur_ci.sqlite3"))
    parser.add_argument("--rows", type=int, default=50)
    args = parser.parse_args()
    if args.rows < 1:
        raise SystemExit("--rows must be positive")
    counts = seed(args.db, args.rows)
    print(json.dumps({"database": str(args.db), "counts": counts}, sort_keys=True))


if __name__ == "__main__":
    main()
