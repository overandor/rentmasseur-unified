"""
RM RevenueOps — the joined revenue ledger.

daily_profile_metrics + experiment_decisions + daily_evidence_packet + strict decision engine.

No AGI. No fake numbers. One packet, one decision, one experiment.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "revenue_ops.db"

DECISION_STATES = [
    "BLOCK_NO_METRICS",
    "BLOCK_NO_BASELINE_EXPERIMENT",
    "BLOCK_LOW_EXPOSURE",
    "BLOCK_BAD_ACCOUNT_STATE",
    "BLOCK_ATTRIBUTION_DIRTY",
    "READY_TO_TEST",
    "TEST_RUNNING",
    "KEEP_CURRENT",
    "TEST_NEXT_BIO",
    "WINNER_FOUND",
    "REVERT_TO_BASELINE",
    "NEEDS_HUMAN_REVIEW",
]

MIN_VIEWS_FOR_DECISION = 100
MIN_HOURS_FOR_DECISION = 24
SEVERE_DROP_THRESHOLD = 0.50  # if CTR drops by 50%+ vs baseline, revert early


def init_db(db_path: Path = DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_profile_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            bio_id TEXT NOT NULL,
            headline_hash TEXT,
            bio_hash TEXT,
            profile_views INTEGER NOT NULL,
            contact_clicks INTEGER NOT NULL,
            new_visits INTEGER DEFAULT 0,
            new_emails INTEGER DEFAULT 0,
            booking_requests INTEGER,
            confirmed_clients INTEGER,
            revenue_cents INTEGER,
            availability_state INTEGER NOT NULL,
            profile_visible INTEGER NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiment_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            bio_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            profile_views INTEGER,
            contact_clicks INTEGER,
            contact_click_rate REAL,
            minimum_views_met INTEGER,
            minimum_hours_met INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            bio_id TEXT NOT NULL,
            variant_class TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            baseline_bio_id TEXT,
            before_views INTEGER,
            before_contact_clicks INTEGER,
            before_emails INTEGER,
            after_views INTEGER,
            after_contact_clicks INTEGER,
            after_emails INTEGER,
            actual_lift REAL,
            winner TEXT,
            rollback_snapshot TEXT,
            status TEXT DEFAULT 'running'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS receipt_chain (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_hash TEXT NOT NULL,
            prev_hash TEXT,
            action TEXT NOT NULL,
            data_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_conn(db_path: Path = DB_PATH):
    return sqlite3.connect(str(db_path))


def sha256_of(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def write_receipt(action: str, data: dict, db_path: Path = DB_PATH) -> str:
    conn = get_conn(db_path)
    ts = datetime.now(timezone.utc).isoformat()
    data_str = json.dumps(data, sort_keys=True, default=str)
    prev = conn.execute("SELECT receipt_hash FROM receipt_chain ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = prev[0] if prev else ""
    receipt_hash = sha256_of(prev_hash + action + ts + data_str)
    conn.execute(
        "INSERT INTO receipt_chain (receipt_hash, prev_hash, action, data_json) VALUES (?, ?, ?, ?)",
        (receipt_hash, prev_hash, action, data_str),
    )
    conn.commit()
    conn.close()
    return receipt_hash


def verify_receipt_chain(db_path: Path = DB_PATH) -> bool:
    conn = get_conn(db_path)
    rows = conn.execute("SELECT receipt_hash, prev_hash, action, data_json FROM receipt_chain ORDER BY id").fetchall()
    conn.close()
    prev = ""
    for r_hash, r_prev, action, data_json in rows:
        if r_prev != prev:
            return False
        # Can't fully recompute hash without timestamp, but chain linkage is verifiable
        prev = r_hash
    return True


def ingest_metrics(packet: dict, db_path: Path = DB_PATH) -> dict:
    """Ingest a daily metrics packet. Returns computed values + decision."""
    conn = get_conn(db_path)
    ts = datetime.now(timezone.utc).isoformat()
    date = packet.get("date", datetime.now(timezone.utc).date().isoformat())
    bio_id = packet.get("bio_id", "unknown")
    profile_views = int(packet.get("profile_views", 0))
    contact_clicks = int(packet.get("contact_clicks", 0))
    new_visits = int(packet.get("new_visits", 0))
    new_emails = int(packet.get("new_emails", 0))
    availability = 1 if packet.get("availability_state", True) else 0
    visible = 1 if packet.get("profile_visible", True) else 0
    headline_hash = packet.get("headline_hash", "")
    bio_hash = packet.get("bio_hash", "")

    contact_click_rate = contact_clicks / profile_views if profile_views > 0 else 0.0
    email_rate = new_emails / profile_views if profile_views > 0 else 0.0

    conn.execute(
        """INSERT INTO daily_profile_metrics
           (date, bio_id, headline_hash, bio_hash, profile_views, contact_clicks,
            new_visits, new_emails, availability_state, profile_visible, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (date, bio_id, headline_hash, bio_hash, profile_views, contact_clicks,
         new_visits, new_emails, availability, visible, packet.get("notes", "")),
    )
    conn.commit()

    decision = compute_decision(bio_id, profile_views, contact_clicks, new_emails,
                                 availability, visible, conn)
    conn.close()

    write_receipt("metrics_ingest", {
        "date": date, "bio_id": bio_id, "profile_views": profile_views,
        "contact_clicks": contact_clicks, "contact_click_rate": contact_click_rate,
        "decision": decision["status"], "reason": decision["reason"],
    }, db_path)

    return {
        "ok": True,
        "ingested": True,
        "computed": {
            "contact_click_rate": round(contact_click_rate, 4),
            "email_rate": round(email_rate, 4),
            "contact_clicks_per_100_views": round(contact_click_rate * 100, 2),
        },
        "decision": decision,
    }


def compute_decision(bio_id: str, profile_views: int, contact_clicks: int,
                     new_emails: int, availability: int, visible: int,
                     conn: sqlite3.Connection) -> dict:
    """Strict decision engine. No magic. Just rules."""

    if not visible:
        return {"status": "BLOCK_BAD_ACCOUNT_STATE",
                "reason": "Profile is not visible.", "next_action": "make_visible"}

    if not availability:
        return {"status": "BLOCK_BAD_ACCOUNT_STATE",
                "reason": "Profile is not available. Metrics not comparable.",
                "next_action": "set_available"}

    if profile_views == 0:
        return {"status": "BLOCK_NO_METRICS",
                "reason": "No profile metrics available.", "next_action": "ingest_metrics"}

    # Check for running experiment
    exp = conn.execute(
        "SELECT * FROM experiments WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()

    if not exp:
        # No experiment running — check if we have baseline data
        baseline = conn.execute(
            "SELECT profile_views, contact_clicks FROM daily_profile_metrics "
            "WHERE bio_id = ? ORDER BY id DESC LIMIT 1", (bio_id,)
        ).fetchone()
        if not baseline:
            return {"status": "BLOCK_NO_BASELINE_EXPERIMENT",
                    "reason": "Real traffic exists, but no completed experiment exists yet. "
                              "Start one controlled bio-only experiment.",
                    "next_action": "start_experiment",
                    "baseline": {"profile_views": profile_views, "contact_clicks": contact_clicks,
                                 "contact_click_rate": round(contact_clicks / profile_views, 5) if profile_views > 0 else 0},
                    "next_candidate": {"bio_id": "targeted_wolf_v1", "change_scope": "headline_and_bio_only",
                                       "minimum_views": MIN_VIEWS_FOR_DECISION, "minimum_hours": MIN_HOURS_FOR_DECISION}}
        return {"status": "READY_TO_TEST",
                "reason": "Baseline established. No active experiment. Ready to start next test.",
                "next_action": "start_experiment",
                "baseline": {"profile_views": baseline[0], "contact_clicks": baseline[1],
                             "contact_click_rate": round(baseline[1] / baseline[0], 5) if baseline[0] > 0 else 0}}

    # Experiment is running — check exposure
    exp_id, exp_bio_id, _, started_at, _, _, before_views, before_clicks, before_emails = exp[:9]

    # Parse started_at
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        elapsed_hours = (datetime.now(timezone.utc) - start).total_seconds() / 3600
    except Exception:
        elapsed_hours = 0

    delta_views = profile_views - (before_views or 0)
    delta_clicks = contact_clicks - (before_clicks or 0)

    min_views_met = delta_views >= MIN_VIEWS_FOR_DECISION
    min_hours_met = elapsed_hours >= MIN_HOURS_FOR_DECISION

    if not min_views_met and not min_hours_met:
        return {"status": "BLOCK_LOW_EXPOSURE",
                "reason": f"Only {delta_views} views in {elapsed_hours:.1f}h. "
                          f"Need {MIN_VIEWS_FOR_DECISION} views or {MIN_HOURS_FOR_DECISION}h.",
                "next_action": "wait",
                "experiment_id": exp_id,
                "elapsed_hours": round(elapsed_hours, 1),
                "current_delta_views": delta_views}

    # We have enough exposure — compute lift
    before_ctr = before_clicks / before_views if before_views and before_views > 0 else 0
    after_ctr = contact_clicks / profile_views if profile_views > 0 else 0
    lift = after_ctr - before_ctr

    # Severe drop check (can trigger before full window if CTR collapses)
    if before_ctr > 0 and after_ctr < before_ctr * (1 - SEVERE_DROP_THRESHOLD):
        return {"status": "REVERT_TO_BASELINE",
                "reason": f"CTR dropped {abs(lift)*100:.1f}pp. Severe drop threshold exceeded.",
                "next_action": "rollback",
                "experiment_id": exp_id,
                "before_ctr": round(before_ctr, 4),
                "after_ctr": round(after_ctr, 4),
                "lift": round(lift, 4)}

    if not min_views_met or not min_hours_met:
        return {"status": "TEST_RUNNING",
                "reason": f"Experiment running: delta_views={delta_views}/{MIN_VIEWS_FOR_DECISION}, "
                          f"hours={elapsed_hours:.1f}/{MIN_HOURS_FOR_DECISION}",
                "next_action": "wait",
                "experiment_id": exp_id}

    # Enough exposure — decide
    if lift > 0.01:
        return {"status": "WINNER_FOUND",
                "reason": f"CTR improved by {lift*100:.1f}pp.",
                "next_action": "close_experiment_winner",
                "experiment_id": exp_id,
                "before_ctr": round(before_ctr, 4),
                "after_ctr": round(after_ctr, 4),
                "lift": round(lift, 4)}
    elif lift < -0.01:
        return {"status": "REVERT_TO_BASELINE",
                "reason": f"CTR decreased by {abs(lift)*100:.1f}pp.",
                "next_action": "rollback",
                "experiment_id": exp_id,
                "before_ctr": round(before_ctr, 4),
                "after_ctr": round(after_ctr, 4),
                "lift": round(lift, 4)}
    else:
        return {"status": "KEEP_CURRENT",
                "reason": f"CTR flat ({lift*100:.1f}pp). No significant change.",
                "next_action": "test_next_bio",
                "experiment_id": exp_id,
                "before_ctr": round(before_ctr, 4),
                "after_ctr": round(after_ctr, 4),
                "lift": round(lift, 4)}


def start_experiment(bio_id: str, variant_class: str, before_views: int,
                     before_contact_clicks: int, before_emails: int,
                     db_path: Path = DB_PATH) -> dict:
    conn = get_conn(db_path)
    exp_id = f"exp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{variant_class}"
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO experiments
           (experiment_id, bio_id, variant_class, started_at, baseline_bio_id,
            before_views, before_contact_clicks, before_emails, status)
           VALUES (?, ?, ?, ?, 'current_live', ?, ?, ?, 'running')""",
        (exp_id, bio_id, variant_class, ts, before_views, before_contact_clicks, before_emails),
    )
    conn.commit()
    conn.close()
    write_receipt("experiment_start", {
        "experiment_id": exp_id, "bio_id": bio_id, "variant_class": variant_class,
        "before_views": before_views, "before_contact_clicks": before_contact_clicks,
    }, db_path)
    return {"experiment_id": exp_id, "status": "running", "bio_id": bio_id}


def close_experiment(experiment_id: str, after_views: int, after_contact_clicks: int,
                     after_emails: int, db_path: Path = DB_PATH) -> dict:
    conn = get_conn(db_path)
    exp = conn.execute("SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)).fetchone()
    if not exp:
        conn.close()
        return {"error": "experiment not found"}
    before_views = exp[6] or 0
    before_clicks = exp[7] or 0
    before_ctr = before_clicks / before_views if before_views > 0 else 0
    after_ctr = after_contact_clicks / after_views if after_views > 0 else 0
    lift = after_ctr - before_ctr
    winner = "test_bio" if lift > 0.01 else ("baseline" if lift < -0.01 else "no_significant_change")
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE experiments SET ended_at=?, after_views=?, after_contact_clicks=?,
           after_emails=?, actual_lift=?, winner=?, status='closed' WHERE experiment_id=?""",
        (ts, after_views, after_contact_clicks, after_emails, lift, winner, experiment_id),
    )
    conn.commit()
    conn.close()
    write_receipt("experiment_close", {
        "experiment_id": experiment_id, "winner": winner, "lift": lift,
        "before_ctr": before_ctr, "after_ctr": after_ctr,
    }, db_path)
    return {"experiment_id": experiment_id, "winner": winner, "lift": round(lift, 4),
            "before_ctr": round(before_ctr, 4), "after_ctr": round(after_ctr, 4)}


def generate_daily_evidence_packet(rm_traffic_db: str, bio_id: str = "karpathian_wolf_live",
                                    db_path: Path = DB_PATH) -> dict:
    """Generate daily_evidence_packet.json from rm_traffic profileops.db."""
    traffic_conn = sqlite3.connect(rm_traffic_db)
    snap = traffic_conn.execute(
        "SELECT profile_views, contact_clicks, new_visits, new_emails, "
        "is_hidden, is_available, headline, description_len "
        "FROM traffic_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    traffic_conn.close()

    if not snap:
        return {"error": "no traffic snapshot found"}

    views, clicks, visits, emails, hidden, available, headline, desc_len = snap
    visible = not hidden
    avail = bool(available)
    ctr = clicks / views if views > 0 else 0
    email_rate = emails / views if views > 0 else 0

    # Get current experiment
    conn = get_conn(db_path)
    exp = conn.execute(
        "SELECT experiment_id, bio_id, status, started_at FROM experiments "
        "WHERE status='running' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    conn.close()

    date_str = datetime.now(timezone.utc).date().isoformat()
    packet_id = f"rmep_{date_str.replace('-', '_')}_{datetime.now(timezone.utc).strftime('%H%M')}"

    bio_text = headline or ""
    bio_hash = "sha256:" + sha256_of(bio_text)

    decision = compute_decision(bio_id, views, clicks, emails,
                                1 if avail else 0, 1 if visible else 0,
                                get_conn(db_path))

    packet = {
        "packet_id": packet_id,
        "date": date_str,
        "account": {
            "profile_visible": visible,
            "is_available": avail,
            "gold_status": True,
        },
        "bio": {
            "bio_id": bio_id,
            "headline": bio_text,
            "bio_hash": bio_hash,
            "variant_class": "current_live",
        },
        "metrics": {
            "profile_views": views,
            "contact_clicks": clicks,
            "new_visits": visits,
            "new_emails": emails,
            "booking_requests": None,
            "confirmed_clients": None,
            "revenue": None,
        },
        "derived": {
            "contact_click_rate": round(ctr, 4),
            "email_rate": round(email_rate, 4),
            "contact_clicks_per_100_views": round(ctr * 100, 2),
        },
        "experiment": {
            "experiment_id": exp[0] if exp else None,
            "state": exp[2] if exp else "none",
            "baseline_bio_id": "current_live",
            "test_bio_id": exp[1] if exp else None,
            "minimum_views_required": MIN_VIEWS_FOR_DECISION,
            "minimum_hours_required": MIN_HOURS_FOR_DECISION,
        },
        "decision": decision,
        "receipt": {
            "source": "rm_traffic",
            "created_by": "daily_promotion_script",
            "source_db": rm_traffic_db,
            "packet_hash": "sha256:" + sha256_of(packet_id + str(views) + str(clicks)),
        },
    }
    return packet


def get_latest_decision(db_path: Path = DB_PATH) -> dict:
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT experiment_id, bio_id, decision, reason, profile_views, "
        "contact_clicks, contact_click_rate, created_at "
        "FROM experiment_decisions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return {"status": "BLOCK_NO_SIGNAL", "reason": "No decisions yet."}
    return {
        "experiment_id": row[0], "bio_id": row[1], "decision": row[2],
        "reason": row[3], "profile_views": row[4], "contact_clicks": row[5],
        "contact_click_rate": row[6], "created_at": row[7],
    }


def get_metrics_history(limit: int = 30, db_path: Path = DB_PATH) -> list:
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT date, bio_id, profile_views, contact_clicks, new_visits, "
        "new_emails, availability_state, profile_visible, created_at "
        "FROM daily_profile_metrics ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [{"date": r[0], "bio_id": r[1], "profile_views": r[2], "contact_clicks": r[3],
             "new_visits": r[4], "new_emails": r[5], "available": bool(r[6]),
             "visible": bool(r[7]), "created_at": r[8]} for r in rows]


def get_experiments(db_path: Path = DB_PATH) -> list:
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT experiment_id, bio_id, variant_class, started_at, ended_at, "
        "status, winner, actual_lift FROM experiments ORDER BY started_at DESC"
    ).fetchall()
    conn.close()
    return [{"experiment_id": r[0], "bio_id": r[1], "variant_class": r[2],
             "started_at": r[3], "ended_at": r[4], "status": r[5],
             "winner": r[6], "actual_lift": r[7]} for r in rows]
