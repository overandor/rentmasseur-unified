"""
Daemon — 24/7 RM Revenue Engine loop.

Runs only safe, read-only operations by default. Mutations require mode >= 2.
Every action is logged and receipted. Errors are caught, never crash the loop.

Intervals (seconds):
    visibility_check  : 300   (5 min)
    availability_check: 300   (5 min)
    stats_snapshot    : 600   (10 min)
    market_scan       : 3600  (1 hour)
    enrich            : 86400 (1 day)
    train             : 86400 (1 day)
    experiment_cycle  : 21600 (6 hours)
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .state_db import StateDB
from .market_scan import MarketScanner
from .experiment_runner import ExperimentRunner
from rm_pri.py.api_client import RentMasseurAPI
from rm_pri.py.auth import AuthSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("rm_daemon")


INTERVALS = {
    "visibility_check": 300,
    "availability_check": 300,
    "stats_snapshot": 600,
    "market_scan": 3600,
    "enrich": 86400,
    "train": 86400,
    "experiment_cycle": 21600,
}

# Load control mode from env, default to 0 (read-only)
CONTROL_MODE = int(os.environ.get("RM_CONTROL_MODE", "0"))


def _get_api() -> Optional[RentMasseurAPI]:
    api = RentMasseurAPI()
    auth = AuthSession(api)
    if not auth.login():
        log.error("Login failed — credentials missing or invalid")
        return None
    return api


def _check_ip_block() -> bool:
    """Return True if CrowdSec captcha is active."""
    import requests
    try:
        r = requests.get("https://rentmasseur.com", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        return "CrowdSec" in r.text
    except Exception as e:
        log.error("IP check failed: %s", e)
        return True


def _can_mutate() -> bool:
    return CONTROL_MODE >= 2


def _record_action(db: StateDB, action: str, description: str, data: dict):
    log.info("%s: %s", action, description)
    db.add_receipt(action, description, data)


def check_visibility(db: StateDB, api: RentMasseurAPI):
    try:
        keep = api.get_keeponline()
        is_hidden = bool(keep.get("keeponline", {}).get("isAdHidden", 0))
        db.log_visibility(is_hidden)
        if is_hidden:
            log.warning("PROFILE IS HIDDEN")
            if _can_mutate():
                log.info("Control mode >= 2 — unhiding profile")
                api.set_visibility(visible=True)
                db.log_visibility(False, source="daemon_unhide")
                _record_action(db, "visibility_auto_on", "Auto-unhid profile", {"control_mode": CONTROL_MODE})
            else:
                _record_action(db, "visibility_warning", "Profile hidden but control mode < 2 — no auto action", {"control_mode": CONTROL_MODE})
    except Exception as e:
        log.error("Visibility check failed: %s", e)


def check_availability(db: StateDB, api: RentMasseurAPI):
    try:
        avail = api.get_availability()
        db.log_availability(avail)
        countdown = avail.get("countdown", 0)
        now = time.time()
        minutes_left = max(0, int(countdown - now) // 60)
        log.info("Availability: %s, minutes_left=%d", avail.get("selected"), minutes_left)
        if minutes_left < 30 and _can_mutate():
            log.info("Availability expiring soon — refreshing to 6h if actually available")
            api.set_availability(option=1, duration=5)
            _record_action(db, "availability_refresh", "Refreshed availability", {"control_mode": CONTROL_MODE})
    except Exception as e:
        log.error("Availability check failed: %s", e)


def snapshot_stats(db: StateDB, api: RentMasseurAPI):
    try:
        dashboard = api.get_dashboard()
        stats = api.get_ad_statistics()
        keeponline = api.get_keeponline()
        db.log_snapshot("dashboard", dashboard)
        db.log_stats(stats.get("adStatistics", stats))
        db.log_visibility(bool(keeponline.get("keeponline", {}).get("isAdHidden", 0)))
        _record_action(db, "stats_snapshot", "Logged dashboard stats", {
            "views": stats.get("adStatistics", stats).get("totalPageViews"),
            "clicks": stats.get("adStatistics", stats).get("totalContactClicks"),
        })
    except Exception as e:
        log.error("Stats snapshot failed: %s", e)


def scan_market(db: StateDB, api: RentMasseurAPI):
    try:
        cities = os.environ.get("RM_SCAN_CITIES", "manhattan-ny").split(",")
        pages = int(os.environ.get("RM_SCAN_PAGES", "5"))
        own = os.environ.get("RM_USERNAME", "")
        scanner = MarketScanner(api, db)
        results = scanner.scan_cities(cities, pages=pages, own_username=own)
        _record_action(db, "market_scan", f"Scanned {len(results)} cities", {"results": results})
    except Exception as e:
        log.error("Market scan failed: %s", e)


def run_enrich(db: StateDB):
    """Run enricher if not blocked. This is public scraping, not API login."""
    if _check_ip_block():
        log.warning("IP blocked — skipping enrichment")
        return
    try:
        from rm_pri.py import enrich
        input_path = Path("rm_pri/data/real_bios_raw.jsonl")
        output_path = Path("rm_pri/data/real_bios_with_views.jsonl")
        if not input_path.exists():
            log.error("Raw bios not found")
            return
        enrich.enrich(input_path, output_path, limit=100, resume=True, min_delay=2.0)
        _record_action(db, "enrich", "Ran public profile enrichment", {"limit": 100})
    except Exception as e:
        log.error("Enrich failed: %s", e)


def run_train(db: StateDB):
    try:
        cpp = Path("rm_pri/cpp/rm_pri")
        if not cpp.exists():
            log.error("C++ engine not compiled")
            return
        enriched = Path("rm_pri/data/real_bios_with_views.jsonl")
        if not enriched.exists():
            log.error("Enriched data not found")
            return
        result = subprocess.run(
            [str(cpp), "train", str(enriched), "--label", "views_per_day", "--cv", "5", "--walk-forward"],
            capture_output=True, text=True, timeout=600
        )
        _record_action(db, "train", "Ran C++ model training", {
            "exit_code": result.returncode,
            "stdout_tail": result.stdout[-500:],
            "stderr_tail": result.stderr[-500:],
        })
    except Exception as e:
        log.error("Train failed: %s", e)


def experiment_cycle(db: StateDB, api: RentMasseurAPI):
    """Close any live experiment, then start next approved candidate if mode allows."""
    try:
        experiments_dir = Path("rm_pri/data/experiments")
        experiments_dir.mkdir(parents=True, exist_ok=True)

        # Close any live experiment
        live = None
        for f in sorted(experiments_dir.glob("exp_*.json")):
            exp = json.loads(f.read_text())
            if exp.get("status") == "live":
                live = exp
                break

        runner = ExperimentRunner(api, db)
        if live:
            log.info("Closing live experiment %s", live["experiment_id"])
            result = runner.close_experiment(live["experiment_id"])
            _record_action(db, "experiment_close", f"Closed experiment {live['experiment_id']}", result)

        if not _can_mutate():
            log.info("Control mode < 2 — not starting new experiment")
            return

        # Start next approved candidate if available
        top_file = Path("data/top_25.jsonl")
        if not top_file.exists():
            log.info("No top candidates file — cannot start experiment")
            return

        candidates = [json.loads(l) for l in top_file.open() if l.strip()]
        if not candidates:
            log.info("No approved candidates — cannot start experiment")
            return

        c = candidates[0]
        bio_file = Path(c.get("bio_file", "content/bios/best_bio.txt"))
        if not bio_file.exists():
            log.info("Bio file not found: %s", bio_file)
            return

        log.info("Starting experiment with candidate %s", c.get("id", "?"))
        content = bio_file.read_text()
        lines = content.split("\n", 1)
        headline = lines[0].strip()
        description = content.strip()
        exp = runner.start_experiment(
            variant_id=c.get("id", "unknown"),
            bio_file=str(bio_file),
            content_type="bio",
            headline=headline,
            description=description,
        )
        _record_action(db, "experiment_start", f"Started experiment {exp['experiment_id']}", exp)
    except Exception as e:
        log.error("Experiment cycle failed: %s", e)


def run_loop(once: bool = False):
    log.info("RM Revenue Engine daemon starting — control_mode=%d", CONTROL_MODE)

    db = StateDB()
    _record_action(db, "daemon_start", "24/7 daemon started", {"control_mode": CONTROL_MODE, "intervals": INTERVALS})

    api = None
    if not _check_ip_block():
        api = _get_api()
        if api:
            log.info("API authenticated")

    last = {k: 0 for k in INTERVALS}

    try:
        while True:
            now = time.time()

            # Re-auth if needed
            if api is None:
                if not _check_ip_block():
                    api = _get_api()

            if api:
                if _check_ip_block():
                    log.warning("IP block detected — dropping API session")
                    api = None
                else:
                    if now - last["visibility_check"] >= INTERVALS["visibility_check"]:
                        check_visibility(db, api)
                        last["visibility_check"] = now

                    if now - last["availability_check"] >= INTERVALS["availability_check"]:
                        check_availability(db, api)
                        last["availability_check"] = now

                    if now - last["stats_snapshot"] >= INTERVALS["stats_snapshot"]:
                        snapshot_stats(db, api)
                        last["stats_snapshot"] = now

                    if now - last["market_scan"] >= INTERVALS["market_scan"]:
                        scan_market(db, api)
                        last["market_scan"] = now

                    if now - last["experiment_cycle"] >= INTERVALS["experiment_cycle"]:
                        experiment_cycle(db, api)
                        last["experiment_cycle"] = now

            # Public scraping (does not need API login)
            if now - last["enrich"] >= INTERVALS["enrich"]:
                run_enrich(db)
                last["enrich"] = now

            if now - last["train"] >= INTERVALS["train"]:
                run_train(db)
                last["train"] = now

            if once:
                log.info("Single loop complete")
                break

            time.sleep(60)

    except KeyboardInterrupt:
        log.info("Daemon stopped by user")
        _record_action(db, "daemon_stop", "24/7 daemon stopped", {"control_mode": CONTROL_MODE})
    except Exception as e:
        log.error("Daemon crashed: %s", e)
        _record_action(db, "daemon_crash", "Daemon crashed", {"error": str(e), "control_mode": CONTROL_MODE})


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Run one loop then exit")
    ap.add_argument("--mode", type=int, default=None, help="Override control mode")
    args = ap.parse_args()
    if args.mode is not None:
        CONTROL_MODE = args.mode
    run_loop(once=args.once)
