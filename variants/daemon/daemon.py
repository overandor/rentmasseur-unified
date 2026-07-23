#!/usr/bin/env python3
"""
RentMasseur Optimizer Daemon

Runs all subsystems as one long-lived process:
  - FastAPI revenue OS server
  - rm_traffic engine cycles (availability, stats, search position)
  - daily promotion / evidence packet generation
  - bio view backfill
  - health reporting

Environment:
  RM_USERNAME, RM_PASSWORD        RentMasseur credentials
  ADMIN_TOKEN                     Required for mutation endpoints
  HF_SPACE / SPACE_NAME           HF Space identifier
  DAEMON_INTERVAL                 Main loop interval in seconds (default 60)
  TRAFFIC_CYCLE_MINUTES           Traffic engine cycle interval (default 5)
  DAILY_PROMOTION_HOUR            Hour of day for daily promotion (default 6 UTC)
  BACKFILL_VIEWS_DAILY            If "1", run view backfill once per day

Usage:
  python daemon.py                  # run daemon in foreground
  python daemon.py --once           # single cycle, then exit
  python daemon.py --server-only    # only run FastAPI server
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "daemon.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("rm_daemon")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class Config:
    username: str = os.getenv("RM_USERNAME", "")
    password: str = os.getenv("RM_PASSWORD", "")
    admin_token: str = os.getenv("ADMIN_TOKEN", "")
    hf_space: str = os.getenv("SPACE_NAME", os.getenv("HF_SPACE", "rentmasseur-optimizer"))
    interval: int = int(os.getenv("DAEMON_INTERVAL", "60"))
    traffic_cycle_minutes: int = int(os.getenv("TRAFFIC_CYCLE_MINUTES", "5"))
    daily_promotion_hour: int = int(os.getenv("DAILY_PROMOTION_HOUR", "6"))
    backfill_views_daily: bool = os.getenv("BACKFILL_VIEWS_DAILY", "1") == "1"

# ---------------------------------------------------------------------------
# Subsystem discovery helpers
# ---------------------------------------------------------------------------

def module_available(module_path: str) -> bool:
    """Check if a module/package is importable."""
    try:
        return importlib.util.find_spec(module_path) is not None
    except Exception:
        return False


def run_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
    """Run a subprocess command and return exit code + output."""
    log.info("Running subprocess: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=APP_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return -9, e.stdout or "", e.stderr or ""
    except Exception as e:
        return 1, "", str(e)


# ---------------------------------------------------------------------------
# Server thread
# ---------------------------------------------------------------------------

def run_server(host: str = "0.0.0.0", port: int = 7860):
    """Run the FastAPI server in the current thread."""
    import uvicorn
    log.info("Starting FastAPI server on %s:%d", host, port)
    uvicorn.run("server:app", host=host, port=port, log_level="info")


def start_server_thread(host: str = "0.0.0.0", port: int = 7860) -> threading.Thread:
    t = threading.Thread(target=run_server, args=(host, port), daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# Traffic engine integration
# ---------------------------------------------------------------------------

def run_traffic_cycle() -> dict:
    """Run one rm_traffic engine cycle."""
    if not module_available("rm_traffic.engine"):
        return {"status": "skipped", "reason": "rm_traffic.engine not installed"}
    if not Config.username or not Config.password:
        return {"status": "skipped", "reason": "RM_USERNAME/RM_PASSWORD not set"}

    try:
        sys.path.insert(0, str(APP_DIR))
        from rm_traffic.engine import run_cycle
        result = run_cycle()
        return {"status": "success", "result": result}
    except Exception as e:
        log.error("Traffic cycle failed: %s", e)
        return {"status": "error", "error": str(e), "trace": traceback.format_exc()}


# ---------------------------------------------------------------------------
# Daily promotion
# ---------------------------------------------------------------------------

def run_daily_promotion() -> dict:
    """Generate daily evidence packet and ingest metrics."""
    script = APP_DIR / "daily_promotion.py"
    if not script.exists():
        return {"status": "skipped", "reason": "daily_promotion.py not found"}

    code, out, err = run_subprocess([sys.executable, str(script)])
    return {
        "status": "success" if code == 0 else "error",
        "exit_code": code,
        "stdout": out[-2000:],
        "stderr": err[-2000:],
    }


# ---------------------------------------------------------------------------
# View backfill
# ---------------------------------------------------------------------------

def run_view_backfill() -> dict:
    """Backfill missing profile views."""
    script = APP_DIR / "backfill_views.py"
    if not script.exists():
        return {"status": "skipped", "reason": "backfill_views.py not found"}

    code, out, err = run_subprocess([sys.executable, str(script)], timeout=7200)
    return {
        "status": "success" if code == 0 else "error",
        "exit_code": code,
        "stdout": out[-2000:],
        "stderr": err[-2000:],
    }


# ---------------------------------------------------------------------------
# Bio merge / data maintenance
# ---------------------------------------------------------------------------

def run_bio_merge() -> dict:
    """Merge bios with views if merge script exists."""
    script = APP_DIR / "merge_bios.py"
    if not script.exists():
        return {"status": "skipped", "reason": "merge_bios.py not found"}

    code, out, err = run_subprocess([sys.executable, str(script)])
    return {
        "status": "success" if code == 0 else "error",
        "exit_code": code,
        "stdout": out[-2000:],
        "stderr": err[-2000:],
    }


# ---------------------------------------------------------------------------
# Health / status
# ---------------------------------------------------------------------------

def write_daemon_state(state: dict):
    state_path = APP_DIR / "content" / "daemon_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, default=str))


def get_health() -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "space": Config.hf_space,
        "subsystems": {
            "rm_traffic.engine": module_available("rm_traffic.engine"),
            "rm_revenue_engine.revenue_ops": module_available("rm_revenue_engine.revenue_ops"),
            "server": True,
        },
        "credentials_set": bool(Config.username and Config.password),
    }


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    def __init__(self):
        self.last_traffic: Optional[float] = None
        self.last_daily_promotion: Optional[str] = None
        self.last_view_backfill: Optional[str] = None
        self.last_bio_merge: Optional[str] = None
        self.history: list[dict] = []

    def should_run_traffic(self) -> bool:
        if self.last_traffic is None:
            return True
        return (time.time() - self.last_traffic) >= Config.traffic_cycle_minutes * 60

    def should_run_daily_promotion(self) -> bool:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now_hour = datetime.now(timezone.utc).hour
        return today != self.last_daily_promotion and now_hour >= Config.daily_promotion_hour

    def should_run_view_backfill(self) -> bool:
        if not Config.backfill_views_daily:
            return False
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return today != self.last_view_backfill

    def should_run_bio_merge(self) -> bool:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return today != self.last_bio_merge

    def record(self, name: str, result: dict):
        entry = {
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
        self.history.append(entry)
        if len(self.history) > 1000:
            self.history = self.history[-1000:]


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_once(scheduler: Scheduler) -> dict:
    results = {}

    if scheduler.should_run_bio_merge():
        log.info("Running bio merge")
        results["bio_merge"] = run_bio_merge()
        if results["bio_merge"]["status"] != "error":
            scheduler.last_bio_merge = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        scheduler.record("bio_merge", results["bio_merge"])

    if scheduler.should_run_view_backfill():
        log.info("Running view backfill")
        results["view_backfill"] = run_view_backfill()
        if results["view_backfill"]["status"] != "error":
            scheduler.last_view_backfill = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        scheduler.record("view_backfill", results["view_backfill"])

    if scheduler.should_run_traffic():
        log.info("Running traffic cycle")
        results["traffic_cycle"] = run_traffic_cycle()
        if results["traffic_cycle"]["status"] != "error":
            scheduler.last_traffic = time.time()
        scheduler.record("traffic_cycle", results["traffic_cycle"])

    if scheduler.should_run_daily_promotion():
        log.info("Running daily promotion")
        results["daily_promotion"] = run_daily_promotion()
        if results["daily_promotion"]["status"] != "error":
            scheduler.last_daily_promotion = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        scheduler.record("daily_promotion", results["daily_promotion"])

    state = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "health": get_health(),
        "scheduler": {
            "last_traffic": scheduler.last_traffic,
            "last_daily_promotion": scheduler.last_daily_promotion,
            "last_view_backfill": scheduler.last_view_backfill,
            "last_bio_merge": scheduler.last_bio_merge,
        },
        "latest_results": results,
        "history_tail": scheduler.history[-10:],
    }
    write_daemon_state(state)
    return results


def main():
    ap = argparse.ArgumentParser(description="RentMasseur Optimizer Daemon")
    ap.add_argument("--once", action="store_true", help="Run one cycle and exit")
    ap.add_argument("--server-only", action="store_true", help="Only run the FastAPI server")
    ap.add_argument("--host", default="0.0.0.0", help="Server host")
    ap.add_argument("--port", type=int, default=7860, help="Server port")
    args = ap.parse_args()

    if args.server_only:
        run_server(args.host, args.port)
        return

    log.info("RentMasseur Optimizer Daemon starting")
    log.info("Health: %s", get_health())

    # Start FastAPI server in background thread
    server_thread = start_server_thread(args.host, args.port)
    time.sleep(2)  # give server a moment to bind

    scheduler = Scheduler()

    if args.once:
        log.info("Running one daemon cycle")
        run_once(scheduler)
        return

    log.info("Entering main loop (interval=%ds)", Config.interval)
    while True:
        try:
            run_once(scheduler)
        except Exception as e:
            log.error("Main loop error: %s\n%s", e, traceback.format_exc())
        time.sleep(Config.interval)


if __name__ == "__main__":
    main()
