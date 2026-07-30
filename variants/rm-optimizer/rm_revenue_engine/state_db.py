"""
StateDB — SQLite state logger for RentMasseur account.

Logs every dashboard snapshot, ad statistics, visibility state,
availability window, search rank, and experiment receipt.

No mock data. No estimates. Only real API responses.
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,
    data_json TEXT NOT NULL,
    source TEXT DEFAULT 'api'
);

CREATE TABLE IF NOT EXISTS stats_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    total_views INTEGER,
    total_contact_clicks INTEGER,
    new_visits INTEGER,
    new_emails INTEGER,
    online_bookmarks INTEGER,
    ctr REAL,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS visibility_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    is_ad_hidden INTEGER NOT NULL,
    source TEXT DEFAULT 'api'
);

CREATE TABLE IF NOT EXISTS availability_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    option INTEGER,
    countdown INTEGER,
    selected TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS search_rank (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    city TEXT,
    own_rank INTEGER,
    total_results INTEGER,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    description TEXT,
    data_json TEXT,
    prev_hash TEXT,
    hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_stats_ts ON stats_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_visibility_ts ON visibility_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_receipts_ts ON receipts(timestamp);
"""


class StateDB:
    """SQLite-backed state logger. Thread-safe via per-connection."""

    def __init__(self, db_path: str = "rm_revenue_engine/state.db"):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        conn = self._conn()
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ─── Snapshots ───

    def log_snapshot(self, snapshot_type: str, data: dict, source: str = "api"):
        conn = self._conn()
        conn.execute(
            "INSERT INTO snapshots (timestamp, snapshot_type, data_json, source) VALUES (?, ?, ?, ?)",
            (self._ts(), snapshot_type, json.dumps(data, default=str), source),
        )
        conn.commit()
        conn.close()

    def get_snapshots(self, snapshot_type: str = None, limit: int = 20) -> list:
        conn = self._conn()
        if snapshot_type:
            rows = conn.execute(
                "SELECT * FROM snapshots WHERE snapshot_type=? ORDER BY timestamp DESC LIMIT ?",
                (snapshot_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─── Stats ───

    def log_stats(self, stats: dict):
        total_views = stats.get("totalPageViews") or stats.get("total_views") or 0
        total_clicks = stats.get("totalContactClicks") or stats.get("total_contact_clicks") or 0
        new_visits = stats.get("newVisits") or stats.get("new_visits") or 0
        new_emails = stats.get("newEmails") or stats.get("new_emails") or 0
        bookmarks = stats.get("onlineBookmarks") or stats.get("online_bookmarks") or 0
        ctr = (total_clicks / total_views) if total_views else 0.0

        conn = self._conn()
        conn.execute(
            "INSERT INTO stats_log (timestamp, total_views, total_contact_clicks, new_visits, new_emails, online_bookmarks, ctr, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self._ts(), total_views, total_clicks, new_visits, new_emails, bookmarks, ctr, json.dumps(stats, default=str)),
        )
        conn.commit()
        conn.close()

    def get_latest_stats(self) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM stats_log ORDER BY timestamp DESC LIMIT 1").fetchone()
        conn.close()
        return dict(row) if row else None

    def get_stats_history(self, limit: int = 50) -> list:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM stats_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─── Visibility ───

    def log_visibility(self, is_ad_hidden: bool, source: str = "api"):
        conn = self._conn()
        conn.execute(
            "INSERT INTO visibility_log (timestamp, is_ad_hidden, source) VALUES (?, ?, ?)",
            (self._ts(), 1 if is_ad_hidden else 0, source),
        )
        conn.commit()
        conn.close()

    def get_latest_visibility(self) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM visibility_log ORDER BY timestamp DESC LIMIT 1").fetchone()
        conn.close()
        return dict(row) if row else None

    # ─── Availability ───

    def log_availability(self, avail: dict):
        conn = self._conn()
        conn.execute(
            "INSERT INTO availability_log (timestamp, option, countdown, selected, raw_json) VALUES (?, ?, ?, ?, ?)",
            (self._ts(), avail.get("option"), avail.get("countdown"), avail.get("selected"), json.dumps(avail, default=str)),
        )
        conn.commit()
        conn.close()

    def get_latest_availability(self) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM availability_log ORDER BY timestamp DESC LIMIT 1").fetchone()
        conn.close()
        return dict(row) if row else None

    # ─── Search Rank ───

    def log_search_rank(self, city: str, own_rank: int, total_results: int, raw: dict):
        conn = self._conn()
        conn.execute(
            "INSERT INTO search_rank (timestamp, city, own_rank, total_results, raw_json) VALUES (?, ?, ?, ?, ?)",
            (self._ts(), city, own_rank, total_results, json.dumps(raw, default=str)),
        )
        conn.commit()
        conn.close()

    def get_rank_history(self, limit: int = 20) -> list:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM search_rank ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─── Receipts (SHA-256 chained) ───

    def add_receipt(self, action: str, description: str, data: dict) -> dict:
        import hashlib
        conn = self._conn()
        prev = conn.execute("SELECT hash FROM receipts ORDER BY id DESC LIMIT 1").fetchone()
        prev_hash = prev["hash"] if prev else "0" * 64
        ts = self._ts()
        entry = {
            "timestamp": ts,
            "action": action,
            "description": description,
            "data_json": json.dumps(data, default=str, sort_keys=True),
            "prev_hash": prev_hash,
        }
        entry_str = json.dumps(entry, sort_keys=True)
        entry["hash"] = hashlib.sha256(entry_str.encode()).hexdigest()
        conn.execute(
            "INSERT INTO receipts (timestamp, action, description, data_json, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, action, description, entry["data_json"], prev_hash, entry["hash"]),
        )
        conn.commit()
        conn.close()
        return entry

    def get_receipts(self, limit: int = 50) -> list:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM receipts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def verify_receipt_chain(self) -> bool:
        import hashlib
        conn = self._conn()
        rows = conn.execute("SELECT * FROM receipts ORDER BY id ASC").fetchall()
        conn.close()
        prev_hash = "0" * 64
        for r in rows:
            if r["prev_hash"] != prev_hash:
                return False
            entry = {
                "timestamp": r["timestamp"],
                "action": r["action"],
                "description": r["description"],
                "data_json": r["data_json"],
                "prev_hash": r["prev_hash"],
            }
            expected = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
            if r["hash"] != expected:
                return False
            prev_hash = r["hash"]
        return True

    # ─── Summary ───

    def summary(self) -> dict:
        conn = self._conn()
        snap_count = conn.execute("SELECT COUNT(*) as c FROM snapshots").fetchone()["c"]
        stats_count = conn.execute("SELECT COUNT(*) as c FROM stats_log").fetchone()["c"]
        vis_count = conn.execute("SELECT COUNT(*) as c FROM visibility_log").fetchone()["c"]
        avail_count = conn.execute("SELECT COUNT(*) as c FROM availability_log").fetchone()["c"]
        rank_count = conn.execute("SELECT COUNT(*) as c FROM search_rank").fetchone()["c"]
        receipt_count = conn.execute("SELECT COUNT(*) as c FROM receipts").fetchone()["c"]
        chain_valid = self.verify_receipt_chain() if receipt_count > 0 else True
        conn.close()
        return {
            "snapshots": snap_count,
            "stats_log": stats_count,
            "visibility_log": vis_count,
            "availability_log": avail_count,
            "search_rank": rank_count,
            "receipts": receipt_count,
            "chain_valid": chain_valid,
        }
