#!/usr/bin/env python3
"""RM Revenue Engine CLI — brutal, honest, receipt-backed.

Commands:
    status              Show honest system status (DB, API, corpus, experiments)
    visibility on       Unhide profile (requires credentials)
    availability set    Set availability --duration 6 (requires credentials)
    stats snapshot      Pull and log dashboard stats (requires credentials)
    market scan         Scan real bios --cities manhattan-ny --pages 10
    market rank         Rank enriched bios by views/day
    drafts import       Import top candidates from C++ output
    drafts approve      Approve a candidate variant
    profile apply       Apply approved variant (requires credentials)
    experiment close    Close experiment and write receipt
    receipts            Show receipt ledger
    api-check           Test API connectivity

Usage:
    python3 -m rm_revenue_engine.cli status
    python3 -m rm_revenue_engine.cli visibility on
    python3 -m rm_revenue_engine.cli stats snapshot
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rm_revenue_engine.state_db import StateDB
from rm_revenue_engine.market_scan import MarketScanner
from rm_revenue_engine.experiment_runner import ExperimentRunner
from rm_revenue_engine.daemon import run_loop
from rm_pri.py.api_client import RentMasseurAPI
from rm_pri.py.auth import AuthSession


def _get_api() -> RentMasseurAPI:
    api = RentMasseurAPI()
    auth = AuthSession(api, session_file=str(ROOT / "rm_pri" / "data" / "session.json"))
    if not auth.login():
        print("ERROR: Login failed. Set RM_USER and RM_PASS env vars.")
        sys.exit(1)
    return api


def cmd_status(args):
    print("RM REVENUE ENGINE — Status")
    print("=" * 60)

    db = StateDB()
    s = db.summary()
    print(f"\nState DB: {db.path}")
    print(f"  Snapshots:     {s['snapshots']}")
    print(f"  Stats logs:    {s['stats_log']}")
    print(f"  Visibility:    {s['visibility_log']}")
    print(f"  Availability:  {s['availability_log']}")
    print(f"  Search ranks:  {s['search_rank']}")
    print(f"  Receipts:      {s['receipts']}  chain_valid={s['chain_valid']}")

    latest_vis = db.get_latest_visibility()
    if latest_vis:
        hidden = latest_vis["is_ad_hidden"]
        print(f"\n  Latest visibility: {'HIDDEN' if hidden else 'VISIBLE'} ({latest_vis['timestamp'][:19]})")
        if hidden:
            print("  ⚠ WARNING: Profile is HIDDEN. Traffic suppressed. Fix: visibility on")
    else:
        print("\n  Visibility: NO DATA — run 'stats snapshot' to check")

    latest_stats = db.get_latest_stats()
    if latest_stats:
        print(f"\n  Latest stats: views={latest_stats['total_views']} clicks={latest_stats['total_contact_clicks']} ctr={latest_stats['ctr']:.4f}")
    else:
        print("\n  Stats: NO DATA — run 'stats snapshot'")

    raw = ROOT / "rm_pri" / "data" / "real_bios_raw.jsonl"
    enriched = ROOT / "rm_pri" / "data" / "real_bios_with_views.jsonl"
    print(f"\nCorpus:")
    print(f"  Raw bios:      {sum(1 for _ in raw.open()) if raw.exists() else 'MISSING'}")
    if enriched.exists():
        rows = [json.loads(l) for l in enriched.open() if l.strip()]
        has_vpd = [r for r in rows if r.get("views_per_day", 0) > 0]
        print(f"  Enriched:      {len(has_vpd)}/{len(rows)} with views/day")
    else:
        print(f"  Enriched:      NOT STARTED")

    cpp = ROOT / "rm_pri" / "cpp" / "rm_pri"
    print(f"\nC++ Engine: {'compiled' if cpp.exists() else 'NOT COMPILED'}")

    print("\nHonest assessment:")
    if not s["stats_log"]:
        print("  BLIND — no stats logged. Run 'stats snapshot'.")
    if latest_vis and latest_vis["is_ad_hidden"]:
        print("  CRITICAL — profile hidden. Run 'visibility on'.")
    if not enriched.exists():
        print("  STAGE 1 — corpus loaded, enrichment not started.")
    print("  Not AGI. Not revenue oracle. Execution-and-measurement engine.")


def cmd_visibility(args):
    api = _get_api()
    db = StateDB()

    if args.state == "on":
        result = api.set_visibility(visible=True)
        db.log_visibility(False, source="api_command")
        db.add_receipt("visibility_on", "Profile visibility set to VISIBLE", result)
        print("OK: Profile is now VISIBLE")
    elif args.state == "off":
        result = api.set_visibility(visible=False)
        db.log_visibility(True, source="api_command")
        db.add_receipt("visibility_off", "Profile visibility set to HIDDEN", result)
        print("OK: Profile is now HIDDEN")
    else:
        print(f"ERROR: state must be 'on' or 'off', got '{args.state}'")
        sys.exit(1)


def cmd_availability(args):
    api = _get_api()
    db = StateDB()

    if args.action == "set":
        duration = args.duration
        result = api.set_availability(option=1, duration=duration)
        db.log_availability(result)
        db.add_receipt("availability_set", f"Availability set: option=1 duration={duration}h", result)
        print(f"OK: Availability set for {duration}h")
    elif args.action == "check":
        result = api.get_availability()
        db.log_availability(result)
        print(json.dumps(result, indent=2, default=str))


def cmd_stats(args):
    api = _get_api()
    db = StateDB()

    if args.action == "snapshot":
        dashboard = api.get_dashboard()
        stats = api.get_ad_statistics()
        keeponline = api.get_keeponline()

        db.log_snapshot("dashboard", dashboard)
        db.log_stats(stats.get("adStatistics", stats))
        db.log_visibility(bool(keeponline.get("keeponline", {}).get("isAdHidden", 0)))

        keep = keeponline.get("keeponline", {})
        stats_data = stats.get("adStatistics", stats)

        print("Dashboard Snapshot:")
        print(f"  Views:          {stats_data.get('totalPageViews', '?')}")
        print(f"  Contact clicks: {stats_data.get('totalContactClicks', '?')}")
        print(f"  New visits:     {keep.get('newVisits', '?')}")
        print(f"  New emails:     {keep.get('newEmails', '?')}")
        print(f"  Hidden:         {bool(keep.get('isAdHidden', 0))}")

        db.add_receipt("stats_snapshot", "Dashboard stats logged", {
            "views": stats_data.get("totalPageViews"),
            "clicks": stats_data.get("totalContactClicks"),
            "new_visits": keep.get("newVisits"),
            "new_emails": keep.get("newEmails"),
            "is_ad_hidden": bool(keep.get("isAdHidden", 0)),
        })
    elif args.action == "history":
        history = db.get_stats_history(limit=args.limit or 20)
        for h in history:
            print(f"  {h['timestamp'][:19]}  views={h['total_views']} clicks={h['total_contact_clicks']} ctr={h['ctr']:.4f}")


def cmd_market(args):
    if args.action == "scan":
        api = _get_api()
        db = StateDB()
        scanner = MarketScanner(api, db)
        cities = args.cities.split(",") if args.cities else ["manhattan-ny"]
        own = os.environ.get("RM_USERNAME", "")
        results = scanner.scan_cities(cities, pages=args.pages or 5, own_username=own)
        for r in results:
            print(f"  {r['city']}: {r['bios_collected']} bios, own_rank={r['own_rank']}")
    elif args.action == "rank":
        db = StateDB()
        scanner = MarketScanner(None, db)
        result = scanner.rank_by_views_per_day()
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(f"Ranked {result['ranked_bios']}/{result['total_bios']} bios by views/day")
            for b in result.get("top_5", []):
                print(f"  {b['username']}: {b['views_per_day']:.1f} v/day — {b['headline'][:50]}")


def cmd_drafts(args):
    if args.action == "import":
        path = Path(args.file) if args.file else ROOT / "data" / "top_25.jsonl"
        if not path.exists():
            print(f"ERROR: {path} not found")
            sys.exit(1)
        db = StateDB()
        imported = 0
        for line in path.open():
            if line.strip():
                c = json.loads(line)
                db.add_receipt("draft_import", f"Imported candidate {c.get('id', '?')}", c)
                imported += 1
        print(f"Imported {imported} candidates")
    elif args.action == "approve":
        if not args.variant_id:
            print("ERROR: --variant-id required")
            sys.exit(1)
        db = StateDB()
        db.add_receipt("draft_approve", f"Approved variant {args.variant_id}", {"variant_id": args.variant_id})
        print(f"Approved: {args.variant_id}")


def cmd_profile(args):
    if args.action == "apply":
        if not args.variant_id:
            print("ERROR: --variant-id required")
            sys.exit(1)
        api = _get_api()
        db = StateDB()
        runner = ExperimentRunner(api, db)

        bio_path = Path(args.bio_file) if args.bio_file else None
        headline = ""
        description = ""
        if bio_path and bio_path.exists():
            content = bio_path.read_text()
            lines = content.split("\n", 1)
            headline = lines[0].strip()
            description = content.strip()

        exp = runner.start_experiment(
            variant_id=args.variant_id,
            bio_file=str(bio_path) if bio_path else "",
            content_type="bio",
            headline=headline,
            description=description,
        )
        print(f"Experiment started: {exp['experiment_id']}")
        print(f"  Applied: {exp['applied']}")
        if exp.get("apply_error"):
            print(f"  Error: {exp['apply_error']}")
    elif args.action == "current":
        api = _get_api()
        about = api.get_about()
        print(json.dumps(about, indent=2, default=str))


def cmd_experiment(args):
    if args.action == "close":
        if not args.exp_id:
            print("ERROR: --exp-id required")
            sys.exit(1)
        api = _get_api()
        db = StateDB()
        runner = ExperimentRunner(api, db)
        result = runner.close_experiment(args.exp_id)
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(f"Experiment closed: {result['result_label']}")
            lift = result["lift"]
            print(f"  Views lift:     {lift['lift_views']}")
            print(f"  Clicks lift:    {lift['lift_clicks']}")
            print(f"  CTR before:     {lift['before_ctr']:.6f}")
            print(f"  CTR after:      {lift['after_ctr']:.6f}")
            print(f"  CTR lift:       {lift['ctr_lift_pct']}%")
    elif args.action == "rollback":
        if not args.exp_id:
            print("ERROR: --exp-id required")
            sys.exit(1)
        api = _get_api()
        db = StateDB()
        runner = ExperimentRunner(api, db)
        result = runner.rollback_experiment(args.exp_id)
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(f"Rolled back: {result['rolled_back']}")


def cmd_receipts(args):
    db = StateDB()
    receipts = db.get_receipts(limit=args.limit or 20)
    if not receipts:
        print("No receipts yet")
        return
    print(f"{'ID':>4}  {'Timestamp':<22}  {'Action':<22}  Description")
    print("-" * 80)
    for r in receipts:
        print(f"{r['id']:>4}  {r['timestamp'][:19]:<22}  {r['action']:<22}  {r['description'][:40]}")
    print(f"\nChain valid: {db.verify_receipt_chain()}")


def cmd_api_check(args):
    import requests
    h = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://rentmasseur.com", headers=h, timeout=10)
        captcha = "CrowdSec" in r.text
        print(f"GET / status: {r.status_code}")
        print(f"CrowdSec captcha: {captcha}")
        if captcha:
            print("RESULT: BLOCKED — rotate IP or wait for ban to clear")
        else:
            print("RESULT: CLEAR")
    except Exception as e:
        print(f"ERROR: {e}")


def cmd_daemon(args):
    print("Starting RM Revenue Engine 24/7 daemon...")
    print("Mutations disabled by default (mode=0). Set RM_CONTROL_MODE=2 to enable approved mutations.")
    run_loop(once=args.once)


def main():
    parser = argparse.ArgumentParser(prog="rm-revenue-engine", description="RentMasseur API Revenue Engine")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="Show honest system status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("visibility", help="Set profile visibility")
    p.add_argument("state", choices=["on", "off"])
    p.set_defaults(func=cmd_visibility)

    p = sub.add_parser("availability", help="Set or check availability")
    p.add_argument("action", choices=["set", "check"])
    p.add_argument("--duration", type=int, default=5, help="Hours available (1-6)")
    p.set_defaults(func=cmd_availability)

    p = sub.add_parser("stats", help="Pull or view dashboard stats")
    p.add_argument("action", choices=["snapshot", "history"])
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("market", help="Scan market or rank profiles")
    p.add_argument("action", choices=["scan", "rank"])
    p.add_argument("--cities", default="manhattan-ny")
    p.add_argument("--pages", type=int, default=5)
    p.set_defaults(func=cmd_market)

    p = sub.add_parser("drafts", help="Import or approve candidates")
    p.add_argument("action", choices=["import", "approve"])
    p.add_argument("--file", default=None)
    p.add_argument("--variant-id", default=None)
    p.set_defaults(func=cmd_drafts)

    p = sub.add_parser("profile", help="Apply variant or view current profile")
    p.add_argument("action", choices=["apply", "current"])
    p.add_argument("--variant-id", default=None)
    p.add_argument("--bio-file", default=None)
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("experiment", help="Close or rollback experiments")
    p.add_argument("action", choices=["close", "rollback"])
    p.add_argument("--exp-id", default=None)
    p.set_defaults(func=cmd_experiment)

    p = sub.add_parser("receipts", help="Show receipt ledger")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_receipts)

    p = sub.add_parser("api-check", help="Check API connectivity")
    p.set_defaults(func=cmd_api_check)

    p = sub.add_parser("daemon", help="Run 24/7 daemon loop")
    p.add_argument("--once", action="store_true", help="Run one loop then exit")
    p.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
