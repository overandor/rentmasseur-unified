#!/usr/bin/env python3
"""
Daily Operations — unified Selenium + API automation for RentMasseur.

Combines four pillars into a single daily run:
  1. Reciprocal visits (Selenium visit-back via rm_engagement_engine)
  2. Bio automation (push winning bio variant via push_bio.py)
  3. Daily stats / KPI extraction (pull all dashboard metrics via API)
  4. Full telemetry (visitor polling, online count, messages, Rebrandly clicks)

Output:
  - content/daily_kpis.json       — full KPI snapshot
  - content/telemetry_latest.json  — latest telemetry
  - content/telemetry.jsonl       — telemetry log
  - receipts/daily_ops_*.json      — receipt for the full run
  - artifacts/engagement/engagement.db — visitor tracking DB

Usage:
  python3 daily_ops.py                          # full run
  python3 daily_ops.py --skip-visits             # skip reciprocal visits
  python3 daily_ops.py --skip-bio               # skip bio push
  python3 daily_ops.py --skip-telemetry          # skip telemetry polling
  python3 daily_ops.py --visit-limit 10          # limit reciprocal visits
  python3 daily_ops.py --telemetry-duration 300  # 5 min telemetry poll
  python3 daily_ops.py --dry-run                # show what would happen
"""

import argparse
import json
import os
import subprocess
import sys
import time
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Add rm_pri to path
sys.path.insert(0, str(Path(__file__).parent / "rm_pri" / "py"))
from api_client import RentMasseurAPI

try:
    from rebrandly_client import RebrandlyClient
    HAS_REBRANDLY = True
except ImportError:
    HAS_REBRANDLY = False

from dotenv import load_dotenv

# Paths
EXT_DIR = Path(__file__).parent
CONTENT_DIR = EXT_DIR / "content"
RECEIPTS_DIR = EXT_DIR / "receipts"
EVIDENCE_DIR = CONTENT_DIR / "evidence"
ENGAGEMENT_DB = EXT_DIR / "artifacts" / "engagement" / "engagement.db"
BIO_EXPERIMENTS_DB = EXT_DIR / "artifacts" / "engagement" / "bio_experiments.db"
KPI_PATH = CONTENT_DIR / "daily_kpis.json"
KPI_HISTORY_PATH = CONTENT_DIR / "kpi_history.jsonl"
TELEMETRY_LATEST = CONTENT_DIR / "telemetry_latest.json"
TELEMETRY_LOG = CONTENT_DIR / "telemetry.jsonl"
LEDGER_PATH = CONTENT_DIR / "experiment_ledger.json"

BOOKING_URL = os.environ.get("BOOKING_URL", "https://calendly.com/carpathianwolf/clone?back=1&month=2024-08")
REBRANDLY_LINK = os.environ.get("REBRANDLY_LINK", "rebrand.ly/carpathianwolf")

for d in (CONTENT_DIR, RECEIPTS_DIR, EVIDENCE_DIR):
    d.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env():
    load_dotenv(EXT_DIR / ".env")
    load_dotenv()


def write_receipt(action: str, status: str, data: dict):
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    receipt = {
        "action": action,
        "status": status,
        "timestamp": now_iso(),
        **data,
    }
    path = RECEIPTS_DIR / f"daily_ops_{action}_{ts}.json"
    path.write_text(json.dumps(receipt, indent=2))
    print(f"  Receipt: {path}")
    return path


# ═════════════════════════════════════════════════════════════════════
# PILLAR 1: Reciprocal Visits (Selenium)
# ═════════════════════════════════════════════════════════════════════

def run_reciprocal_visits(limit: int = 0, dry_run: bool = False) -> dict:
    """Run reciprocal visit-back via rm_engagement_engine.py."""
    print("\n" + "=" * 60)
    print("PILLAR 1: RECIPROCAL VISITS (Selenium)")
    print("=" * 60)

    cmd = [sys.executable, "rm_engagement_engine.py", "--login", "--visit-back", "--max-load-more", "20"]
    if limit > 0:
        cmd += ["--limit", str(limit)]
    if dry_run:
        cmd += ["--dry-run"]

    print(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(EXT_DIR), capture_output=True, text=True, timeout=1800)

    # Parse output for summary
    visited = 0
    blocked = 0
    for line in result.stdout.splitlines():
        if "VISIT BACK:" in line:
            print(f"  {line.strip()}")
        if "visited" in line.lower() and "summary" in line.lower():
            print(f"  {line.strip()}")

    print(f"  Exit code: {result.returncode}")
    if result.stderr:
        print(f"  Stderr (last 500): {result.stderr[-500:]}")

    summary = {
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-1000:],
        "limit": limit,
        "dry_run": dry_run,
    }
    write_receipt("reciprocal_visits", "pass" if result.returncode == 0 else "fail", summary)
    return summary


# ═════════════════════════════════════════════════════════════════════
# PILLAR 2: Bio Automation
# ═════════════════════════════════════════════════════════════════════

def run_bio_push(dry_run: bool = False) -> dict:
    """Push the current winning bio variant via push_bio.py."""
    print("\n" + "=" * 60)
    print("PILLAR 2: BIO AUTOMATION")
    print("=" * 60)

    # Load ledger to find current variant
    ledger = {}
    if LEDGER_PATH.exists():
        ledger = json.loads(LEDGER_PATH.read_text())

    current_bio = ledger.get("current_bio_id", "unknown")
    print(f"  Current bio: {current_bio}")

    # Determine which variant to push (rotate A → B → C)
    variant_map = {"A": "B", "B": "C", "C": "A"}
    last_pushed = ledger.get("last_pushed_variant", "A")
    next_variant = variant_map.get(last_pushed, "A")
    print(f"  Next variant: {next_variant} (last was {last_pushed})")

    if dry_run:
        print(f"  DRY RUN — would push variant {next_variant}")
        return {"dry_run": True, "variant": next_variant}

    cmd = [sys.executable, "push_bio.py", next_variant]
    print(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(EXT_DIR), capture_output=True, text=True, timeout=300, env=os.environ.copy())

    print(f"  Exit code: {result.returncode}")
    if result.stdout:
        print(f"  Stdout (last 500): {result.stdout[-500:]}")
    if result.stderr:
        print(f"  Stderr (last 500): {result.stderr[-500:]}")

    # Update ledger with pushed variant
    if result.returncode == 0 and ledger:
        ledger["last_pushed_variant"] = next_variant
        LEDGER_PATH.write_text(json.dumps(ledger, indent=2))

    summary = {
        "exit_code": result.returncode,
        "variant": next_variant,
        "stdout_tail": result.stdout[-500:],
    }
    write_receipt("bio_push", "pass" if result.returncode == 0 else "fail", summary)
    return summary


# ═════════════════════════════════════════════════════════════════════
# PILLAR 3: Daily Stats / KPI Extraction
# ═════════════════════════════════════════════════════════════════════

def extract_kpis(api: RentMasseurAPI) -> dict:
    """Extract all KPIs from the RentMasseur API + Rebrandly API."""
    print("\n" + "=" * 60)
    print("PILLAR 3: DAILY STATS / KPI EXTRACTION")
    print("=" * 60)

    kpis = {
        "timestamp": now_iso(),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    # ── RentMasseur Dashboard ──
    try:
        dash = api.get_dashboard()
        user_settings = dash.get("userSetting", {}) if isinstance(dash, dict) else {}
        availability = user_settings.get("availability", {}) if isinstance(user_settings, dict) else {}
        kpis["profile"] = {
            "visibility": 1 if not user_settings.get("isAdHidden", False) else 0,
            "is_available": availability.get("available", 0) if isinstance(availability, dict) else 0,
            "availability_message": availability.get("message", "") if isinstance(availability, dict) else "",
        }
        print(f"  Visibility: {kpis['profile']['visibility']}")
        print(f"  Available: {kpis['profile']['is_available']}")
    except Exception as e:
        print(f"  Dashboard error: {e}")
        kpis["profile"] = {"error": str(e)}

    # ── Ad Statistics (page views, contact clicks, etc.) ──
    try:
        stats = api.get_ad_statistics()
        profile_stats = stats.get("profileStatistics") if isinstance(stats, dict) else None
        if not isinstance(profile_stats, dict):
            profile_stats = {}
        kpis["ad_statistics"] = {
            "total_page_views": profile_stats.get("totalPageViews", 0) or profile_stats.get("pageViews", 0) or 0,
            "total_contact_clicks": profile_stats.get("totalContactClicks", 0) or profile_stats.get("contactClicks", 0) or 0,
            "new_visits": profile_stats.get("newVisits", 0) or profile_stats.get("visits", 0) or 0,
            "new_emails": profile_stats.get("newEmails", 0) or profile_stats.get("emails", 0) or 0,
            "profile_views_today": profile_stats.get("profileViewsToday", 0) or 0,
            "contact_clicks_today": profile_stats.get("contactClicksToday", 0) or 0,
            "favorites": profile_stats.get("favorites", 0) or 0,
            "reviews": profile_stats.get("reviews", 0) or 0,
            "raw_available": bool(profile_stats),
        }
        print(f"  Total page views: {kpis['ad_statistics']['total_page_views']}")
        print(f"  Total contact clicks: {kpis['ad_statistics']['total_contact_clicks']}")
        print(f"  New visits: {kpis['ad_statistics']['new_visits']}")
        print(f"  New emails: {kpis['ad_statistics']['new_emails']}")
    except Exception as e:
        print(f"  Ad statistics error: {e}")
        kpis["ad_statistics"] = {"error": str(e)}

    # ── About / Bio ──
    try:
        about = api.get_about()
        assets = about.get("userProps", {}).get("assets", {}) if isinstance(about, dict) else {}
        description = assets.get("description", "")
        kpis["bio"] = {
            "headline": assets.get("headline", ""),
            "bio_length": len(description),
            "rebrandly_present": REBRANDLY_LINK in description or "rebrand.ly" in description,
            "bio_preview": description[:200],
        }
        print(f"  Headline: {kpis['bio']['headline'][:60]}")
        print(f"  Bio length: {kpis['bio']['bio_length']} chars")
        print(f"  Rebrandly present: {kpis['bio']['rebrandly_present']}")
    except Exception as e:
        print(f"  About error: {e}")
        kpis["bio"] = {"error": str(e)}

    # ── KeepOnline ──
    try:
        keep = api.get_keeponline()
        kpis["keeponline"] = {
            "enabled": keep.get("enabled", False) if isinstance(keep, dict) else False,
            "status": keep.get("status", "unknown") if isinstance(keep, dict) else "unknown",
        }
        print(f"  KeepOnline: {kpis['keeponline']['enabled']}")
    except Exception as e:
        print(f"  KeepOnline error: {e}")
        kpis["keeponline"] = {"error": str(e)}

    # ── Mailbox ──
    try:
        mailbox = api.get_mailbox(page=1, folder=1)
        messages = mailbox.get("messages", []) if isinstance(mailbox, dict) else []
        unread = sum(1 for m in messages if not m.get("read", False))
        kpis["mailbox"] = {
            "total_messages": len(messages),
            "unread": unread,
        }
        print(f"  Mailbox: {kpis['mailbox']['total_messages']} messages ({unread} unread)")
    except Exception as e:
        print(f"  Mailbox error: {e}")
        kpis["mailbox"] = {"error": str(e)}

    # ── Engagement DB ──
    try:
        if ENGAGEMENT_DB.exists():
            conn = sqlite3.connect(str(ENGAGEMENT_DB))
            conn.row_factory = sqlite3.Row
            total_visitors = conn.execute("SELECT COUNT(*) FROM visitors").fetchone()[0]
            total_visits = conn.execute("SELECT COUNT(*) FROM visit_log").fetchone()[0]
            total_messages = conn.execute("SELECT COUNT(*) FROM message_log").fetchone()[0]
            repeat_3plus = conn.execute("SELECT COUNT(*) FROM visitors WHERE visit_count >= 3").fetchone()[0]
            # Recent activity (last 24h)
            cutoff = (datetime.now(timezone.utc)).isoformat()
            recent_visits = conn.execute(
                "SELECT COUNT(*) FROM visit_log WHERE visited_at >= ?",
                [(datetime.now(timezone.utc)).strftime("%Y-%m-%d") + "T00:00:00"]
            ).fetchone()[0]
            conn.close()
            kpis["engagement"] = {
                "total_visitors": total_visitors,
                "total_visits": total_visits,
                "total_messages_sent": total_messages,
                "repeat_visitors_3plus": repeat_3plus,
                "visits_today": recent_visits,
            }
            print(f"  Engagement: {total_visitors} visitors, {total_visits} visits, {total_messages} messages")
            print(f"  Repeat visitors (3+): {repeat_3plus}")
            print(f"  Visits today: {recent_visits}")
        else:
            kpis["engagement"] = {"error": "no engagement DB"}
            print("  Engagement DB not found")
    except Exception as e:
        print(f"  Engagement DB error: {e}")
        kpis["engagement"] = {"error": str(e)}

    # ── Rebrandly Click Analytics ──
    if HAS_REBRANDLY and os.environ.get("REBRANDLY_API_KEY"):
        try:
            rb = RebrandlyClient()
            main_stats = rb.get_carpathianwolf_stats()
            bio_clicks = rb.get_all_bio_clicks()
            kpis["rebrandly"] = {
                "main_link": {
                    "short_url": main_stats.get("short_url"),
                    "clicks": main_stats.get("clicks", 0),
                    "sessions": main_stats.get("sessions", 0),
                    "last_click": main_stats.get("last_click"),
                },
                "bio_links": bio_clicks,
                "total_clicks": main_stats.get("clicks", 0) + sum(b.get("clicks", 0) for b in bio_clicks),
            }
            print(f"  Rebrandly main: {kpis['rebrandly']['main_link']['clicks']} clicks")
            print(f"  Rebrandly bio links: {len(bio_clicks)} variants")
            print(f"  Rebrandly total clicks: {kpis['rebrandly']['total_clicks']}")
        except Exception as e:
            print(f"  Rebrandly error: {e}")
            kpis["rebrandly"] = {"error": str(e)}
    else:
        kpis["rebrandly"] = {"available": False}
        print("  Rebrandly: API key not set")

    # ── Experiment Ledger ──
    try:
        if LEDGER_PATH.exists():
            ledger = json.loads(LEDGER_PATH.read_text())
            kpis["experiment"] = {
                "current_bio_id": ledger.get("current_bio_id"),
                "current_bio_started_at": ledger.get("current_bio_started_at"),
                "baseline_ctr": ledger.get("baseline_ctr"),
                "current_rebrandly_link_id": ledger.get("current_rebrandly_link_id"),
                "current_rebrandly_clicks_before": ledger.get("current_rebrandly_clicks_before"),
            }
            print(f"  Current bio: {kpis['experiment']['current_bio_id']}")
            print(f"  Baseline CTR: {kpis['experiment']['baseline_ctr']}")
    except Exception as e:
        print(f"  Ledger error: {e}")

    # ── Compute derived KPIs ──
    ad = kpis.get("ad_statistics", {})
    if ad.get("total_page_views", 0) > 0:
        ctr = (ad.get("total_contact_clicks", 0) / ad["total_page_views"]) * 100
        kpis["derived"] = {
            "ctr": round(ctr, 2),
            "visits_to_emails_rate": round(
                (ad.get("new_emails", 0) / ad["total_page_views"]) * 100, 2
            ) if ad["total_page_views"] > 0 else 0,
            "revenue_estimate": round(
                ad.get("total_contact_clicks", 0) * 0.20 * 200 +  # call conversions
                ad.get("new_emails", 0) * 0.05 * 200,  # email conversions
                2
            ),
        }
        print(f"  CTR: {kpis['derived']['ctr']}%")
        print(f"  Revenue estimate: ${kpis['derived']['revenue_estimate']}")

    # Write KPI snapshot
    KPI_PATH.write_text(json.dumps(kpis, indent=2))
    print(f"\n  KPI snapshot: {KPI_PATH}")

    # Append to history
    with open(KPI_HISTORY_PATH, "a") as f:
        f.write(json.dumps(kpis) + "\n")
    print(f"  KPI history: {KPI_HISTORY_PATH}")

    write_receipt("kpi_extraction", "pass", {"kpi_path": str(KPI_PATH), "sections": list(kpis.keys())})
    return kpis


# ═════════════════════════════════════════════════════════════════════
# PILLAR 4: Full Telemetry (Selenium polling)
# ═════════════════════════════════════════════════════════════════════

def run_telemetry(duration: int = 300, interval: int = 60, dry_run: bool = False) -> dict:
    """Run telemetry polling via rm_telemetry_poller.py."""
    print("\n" + "=" * 60)
    print("PILLAR 4: FULL TELEMETRY (Selenium polling)")
    print("=" * 60)

    if dry_run:
        print(f"  DRY RUN — would poll for {duration}s at {interval}s intervals")
        return {"dry_run": True, "duration": duration, "interval": interval}

    cmd = [
        sys.executable, "rm_telemetry_poller.py",
        "--duration", str(duration),
        "--interval", str(interval),
        "--max-load-more", "5",
    ]
    print(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(EXT_DIR), capture_output=True, text=True, timeout=duration + 120, env=os.environ.copy())

    print(f"  Exit code: {result.returncode}")
    if result.stdout:
        print(f"  Stdout (last 800): {result.stdout[-800:]}")
    if result.stderr:
        print(f"  Stderr (last 500): {result.stderr[-500:]}")

    # Read latest telemetry
    telemetry = {}
    if TELEMETRY_LATEST.exists():
        telemetry = json.loads(TELEMETRY_LATEST.read_text())

    summary = {
        "exit_code": result.returncode,
        "duration": duration,
        "interval": interval,
        "latest_telemetry": telemetry,
    }
    write_receipt("telemetry", "pass" if result.returncode == 0 else "fail", summary)
    return summary


# ═════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Daily Operations — unified Selenium + API automation")
    parser.add_argument("--skip-visits", action="store_true", help="Skip reciprocal visits")
    parser.add_argument("--skip-bio", action="store_true", help="Skip bio push")
    parser.add_argument("--skip-kpis", action="store_true", help="Skip KPI extraction")
    parser.add_argument("--skip-telemetry", action="store_true", help="Skip telemetry polling")
    parser.add_argument("--visit-limit", type=int, default=0, help="Max reciprocal visits (0=all)")
    parser.add_argument("--telemetry-duration", type=int, default=300, help="Telemetry duration in seconds")
    parser.add_argument("--telemetry-interval", type=int, default=60, help="Telemetry poll interval in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    args = parser.parse_args()

    load_env()

    username = os.environ.get("RENTMASSEUR_USERNAME")
    password = os.environ.get("RENTMASSEUR_PASSWORD")

    if not username or not password:
        print("ERROR: RENTMASSEUR_USERNAME and RENTMASSEUR_PASSWORD required")
        sys.exit(1)

    print("=" * 60)
    print("DAILY OPERATIONS — Unified Automation")
    print(f"  Visits: {'SKIP' if args.skip_visits else 'RUN'}")
    print(f"  Bio: {'SKIP' if args.skip_bio else 'RUN'}")
    print(f"  KPIs: {'SKIP' if args.skip_kpis else 'RUN'}")
    print(f"  Telemetry: {'SKIP' if args.skip_telemetry else 'RUN'}")
    print(f"  Dry run: {args.dry_run}")
    print("=" * 60)

    results = {
        "timestamp": now_iso(),
        "dry_run": args.dry_run,
    }

    # ── Pillar 1: Reciprocal Visits ──
    if not args.skip_visits:
        results["reciprocal_visits"] = run_reciprocal_visits(
            limit=args.visit_limit, dry_run=args.dry_run
        )

    # ── Pillar 2: Bio Automation ──
    if not args.skip_bio:
        results["bio_push"] = run_bio_push(dry_run=args.dry_run)

    # ── Pillar 3: KPI Extraction (needs API login) ──
    if not args.skip_kpis:
        print("\n" + "=" * 60)
        print("LOGGING IN FOR KPI EXTRACTION")
        print("=" * 60)
        api = RentMasseurAPI(min_request_interval=2.0)
        if not api.login(username, password):
            print("ERROR: Login failed for KPI extraction")
            results["kpi_extraction"] = {"error": "login_failed"}
        else:
            print("Login successful")
            results["kpi_extraction"] = extract_kpis(api)

    # ── Pillar 4: Telemetry ──
    if not args.skip_telemetry:
        results["telemetry"] = run_telemetry(
            duration=args.telemetry_duration,
            interval=args.telemetry_interval,
            dry_run=args.dry_run,
        )

    # ── Final receipt ──
    write_receipt("daily_ops_complete", "pass", {
        "pillars_run": [k for k in results if k != "dry_run"],
        "results_summary": {k: v.get("exit_code", "n/a") if isinstance(v, dict) else "n/a" for k, v in results.items()},
    })

    print("\n" + "=" * 60)
    print("DAILY OPERATIONS COMPLETE")
    print("=" * 60)
    for pillar, result in results.items():
        if pillar == "dry_run":
            continue
        status = "OK" if isinstance(result, dict) and result.get("exit_code", 0) == 0 else "FAIL"
        print(f"  {pillar}: {status}")

    return results


if __name__ == "__main__":
    main()
