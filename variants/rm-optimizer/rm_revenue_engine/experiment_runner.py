"""
ExperimentRunner — before/after measurement, lift computation, rollback.

Never applies without approval. Never claims success without measurement.
Every experiment produces a receipt with before/after snapshots.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .state_db import StateDB
from rm_pri.py.api_client import RentMasseurAPI


class ExperimentRunner:
    """Run controlled profile experiments with before/after measurement."""

    def __init__(self, api: RentMasseurAPI, db: StateDB, experiments_dir: str = "rm_pri/data/experiments"):
        self.api = api
        self.db = db
        self.experiments_dir = Path(experiments_dir)
        self.experiments_dir.mkdir(parents=True, exist_ok=True)

    def snapshot_dashboard(self) -> dict:
        """Take a full dashboard snapshot."""
        dashboard = self.api.get_dashboard()
        stats = self.api.get_ad_statistics()
        keeponline = self.api.get_keeponline()
        about = self.api.get_about()

        keep = keeponline.get("keeponline", {}) if isinstance(keeponline, dict) else {}
        stats_data = stats.get("adStatistics", stats) if isinstance(stats, dict) else {}
        about_data = about.get("about", about) if isinstance(about, dict) else {}

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "profile_views": stats_data.get("totalPageViews") or dashboard.get("profileViews", 0),
            "contact_clicks": stats_data.get("totalContactClicks", 0),
            "new_visits": keep.get("newVisits", 0),
            "new_emails": keep.get("newEmails", 0),
            "online_bookmarks": dashboard.get("onlineBookmarks", 0),
            "is_ad_hidden": keep.get("isAdHidden", 0),
            "headline": about_data.get("headline", ""),
            "description_len": len(about_data.get("description", "")),
            "raw_dashboard": dashboard,
            "raw_stats": stats,
            "raw_keeponline": keeponline,
        }

        ctr = (snapshot["contact_clicks"] / snapshot["profile_views"]) if snapshot["profile_views"] else 0.0
        snapshot["ctr"] = round(ctr, 6)

        return snapshot

    def start_experiment(self, variant_id: str, bio_file: str, content_type: str = "bio",
                         headline: str = "", description: str = "") -> dict:
        """Start an experiment: snapshot before, apply variant, return experiment record."""
        before = self.snapshot_dashboard()
        self.db.log_snapshot("experiment_before", before)

        exp_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        applied = False
        apply_error = None
        if headline or description:
            try:
                self.api.set_about(headline=headline, description=description)
                applied = True
            except Exception as e:
                apply_error = str(e)

        experiment = {
            "experiment_id": exp_id,
            "variant_id": variant_id,
            "bio_file": bio_file,
            "content_type": content_type,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "live" if applied else "failed",
            "before": before,
            "applied": applied,
            "apply_error": apply_error,
            "headline": headline,
            "description": description[:200] if description else "",
        }

        exp_path = self.experiments_dir / f"{exp_id}.json"
        exp_path.write_text(json.dumps(experiment, indent=2, default=str))

        self.db.add_receipt("experiment_start", f"Experiment {exp_id} started with {variant_id}", experiment)

        return experiment

    def close_experiment(self, experiment_id: str) -> dict:
        """Close an experiment: snapshot after, compute lift, write receipt."""
        exp_path = self.experiments_dir / f"{experiment_id}.json"
        if not exp_path.exists():
            return {"error": f"Experiment {experiment_id} not found"}

        experiment = json.loads(exp_path.read_text())
        after = self.snapshot_dashboard()
        self.db.log_snapshot("experiment_after", after)

        lift = self._compute_lift(experiment.get("before", {}), after)

        result = {
            "experiment_id": experiment_id,
            "variant_id": experiment.get("variant_id"),
            "started_at": experiment.get("started_at"),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "before": experiment.get("before", {}),
            "after": after,
            "lift": lift,
            "result_label": "winner" if lift["ctr_lift"] > 0 else ("loser" if lift["ctr_lift"] < 0 else "inconclusive"),
            "status": "closed",
        }

        result_path = self.experiments_dir / f"{experiment_id}_result.json"
        result_path.write_text(json.dumps(result, indent=2, default=str))

        self.db.add_receipt("experiment_close", f"Experiment {experiment_id} closed: {result['result_label']}", result)

        return result

    def rollback_experiment(self, experiment_id: str, original_headline: str = "", original_description: str = "") -> dict:
        """Rollback: restore original profile content."""
        exp_path = self.experiments_dir / f"{experiment_id}.json"
        if not exp_path.exists():
            return {"error": f"Experiment {experiment_id} not found"}

        experiment = json.loads(exp_path.read_text())
        before = experiment.get("before", {})
        headline = original_headline or before.get("headline", "")
        description = original_description or before.get("description", "")

        try:
            self.api.set_about(headline=headline, description=description)
            rolled_back = True
        except Exception as e:
            rolled_back = False
            error = str(e)

        after_rollback = self.snapshot_dashboard()

        result = {
            "experiment_id": experiment_id,
            "action": "rollback",
            "rolled_back": rolled_back,
            "restored_headline": headline[:80],
            "after_rollback": after_rollback,
        }

        self.db.add_receipt("experiment_rollback", f"Rolled back experiment {experiment_id}", result)
        return result

    def _compute_lift(self, before: dict, after: dict) -> dict:
        """Compute real lift between before/after snapshots."""
        bv = before.get("profile_views", 0) or 0
        av = after.get("profile_views", 0) or 0
        bc = before.get("contact_clicks", 0) or 0
        ac = after.get("contact_clicks", 0) or 0
        be = before.get("new_emails", 0) or 0
        ae = after.get("new_emails", 0) or 0
        bn = before.get("new_visits", 0) or 0
        an = after.get("new_visits", 0) or 0

        before_ctr = bc / bv if bv > 0 else 0.0
        after_ctr = ac / av if av > 0 else 0.0

        return {
            "lift_views": av - bv,
            "lift_clicks": ac - bc,
            "lift_emails": ae - be,
            "lift_new_visits": an - bn,
            "before_ctr": round(before_ctr, 6),
            "after_ctr": round(after_ctr, 6),
            "ctr_lift": round(after_ctr - before_ctr, 6),
            "ctr_lift_pct": round(((after_ctr - before_ctr) / before_ctr * 100) if before_ctr > 0 else 0, 2),
        }
