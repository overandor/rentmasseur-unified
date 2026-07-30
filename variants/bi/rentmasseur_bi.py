#!/usr/bin/env python3
"""
RentMasseur Business Intelligence Artifact.

Computes contact-action density (NOT fake booked revenue) from analytics data.
Produces banker-safe valuation waterfall with honest proof gaps.

DISCIPLINED CLAIMS:
- Screenshots are NOT collateral
- Contact actions are NOT booked revenue
- Booked revenue requires booking + invoice + deposit proof
- Raw private chats are NOT bank-facing evidence
- A hashed minimized lead ledger CAN support underwriting

Output: KPI cards, banker-safe claim cards, revenue scenarios, proof-gap cards.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import sqlite3
from pathlib import Path

SESSION_PRICE = 159.00


@dataclass
class DailyMetric:
    date: str
    unique_visitors: int = 0
    phone_clicks: int = 0
    email_clicks: int = 0
    contact_actions: int = 0  # phone + email clicks

    @property
    def density(self) -> float:
        """Contact-action density = contact_actions / unique_visitors."""
        if self.unique_visitors == 0:
            return 0.0
        return self.contact_actions / self.unique_visitors


@dataclass
class ValuationWaterfall:
    """Banker-safe valuation waterfall with proof gaps."""
    unique_visitors_30d: int = 0
    total_contact_actions: int = 0
    avg_density: float = 0.0
    hot_days: int = 0  # density > 0.15
    zero_conversion_days: int = 0  # 0 contact actions
    weekly_collapse: bool = False  # >30% drop week over week
    weekly_rebound: bool = False  # >30% recovery

    # Revenue surface (NOT booked revenue — potential revenue)
    close_rate_10pct: float = 0.0
    close_rate_20pct: float = 0.0
    close_rate_30pct: float = 0.0
    monthly_potential_10pct: float = 0.0
    monthly_potential_20pct: float = 0.0
    monthly_potential_30pct: float = 0.0

    # 10% density uplift scenario
    uplifted_contacts: int = 0
    uplifted_monthly_10pct_close: float = 0.0

    # Proof gaps
    proof_gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unique_visitors_30d": self.unique_visitors_30d,
            "total_contact_actions": self.total_contact_actions,
            "avg_density": round(self.avg_density, 4),
            "hot_days": self.hot_days,
            "zero_conversion_days": self.zero_conversion_days,
            "weekly_collapse": self.weekly_collapse,
            "weekly_rebound": self.weekly_rebound,
            "revenue_surface": {
                "close_rate_10pct": {
                    "sessions": int(self.total_contact_actions * 0.10),
                    "monthly_potential": round(self.close_rate_10pct, 2),
                },
                "close_rate_20pct": {
                    "sessions": int(self.total_contact_actions * 0.20),
                    "monthly_potential": round(self.close_rate_20pct, 2),
                },
                "close_rate_30pct": {
                    "sessions": int(self.total_contact_actions * 0.30),
                    "monthly_potential": round(self.close_rate_30pct, 2),
                },
            },
            "density_uplift_scenario": {
                "uplifted_contacts": self.uplifted_contacts,
                "monthly_potential_at_10pct_close": round(self.uplifted_monthly_10pct_close, 2),
            },
            "proof_gaps": self.proof_gaps,
            "session_price": SESSION_PRICE,
            "disclaimer": "Contact actions are NOT booked revenue. "
                          "Booked revenue requires booking + invoice + deposit proof. "
                          "Screenshots are NOT collateral.",
        }


class RentMasseurBI:
    """Business intelligence from analytics data."""

    def __init__(self, db_path: str = "rentmasseur_bi.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY,
                unique_visitors INTEGER DEFAULT 0,
                phone_clicks INTEGER DEFAULT 0,
                email_clicks INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS lead_ledger (
                id TEXT PRIMARY KEY,
                date TEXT,
                source TEXT,
                contact_type TEXT,
                contact_hash TEXT,
                status TEXT DEFAULT 'contacted',
                booking_proof TEXT,
                invoice_proof TEXT,
                deposit_proof TEXT
            );
        """)
        self.conn.commit()

    def ingest_daily(self, date: str, unique_visitors: int,
                     phone_clicks: int, email_clicks: int):
        self.conn.execute(
            "INSERT OR REPLACE INTO daily_metrics (date, unique_visitors, phone_clicks, email_clicks) "
            "VALUES (?, ?, ?, ?)",
            (date, unique_visitors, phone_clicks, email_clicks),
        )
        self.conn.commit()

    def ingest_demo_data(self):
        """Ingest 30 days of demo analytics data."""
        import random
        random.seed(42)
        base = datetime(2026, 6, 11, tzinfo=timezone.utc)
        for i in range(30):
            d = base + timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            # Weekend boost
            is_weekend = d.weekday() >= 5
            visitors = random.randint(40, 120) + (30 if is_weekend else 0)
            phone = random.randint(2, 12) + (3 if is_weekend else 0)
            email = random.randint(1, 8) + (2 if is_weekend else 0)
            # Some zero-conversion days
            if random.random() < 0.1:
                phone, email = 0, 0
            self.ingest_daily(date_str, visitors, phone, email)

    def compute_waterfall(self) -> ValuationWaterfall:
        """Compute the full valuation waterfall."""
        rows = self.conn.execute(
            "SELECT * FROM daily_metrics ORDER BY date"
        ).fetchall()

        metrics = []
        for r in rows:
            m = DailyMetric(
                date=r["date"],
                unique_visitors=r["unique_visitors"],
                phone_clicks=r["phone_clicks"],
                email_clicks=r["email_clicks"],
                contact_actions=r["phone_clicks"] + r["email_clicks"],
            )
            metrics.append(m)

        if not metrics:
            return ValuationWaterfall(proof_gaps=["No data ingested"])

        wf = ValuationWaterfall()
        wf.unique_visitors_30d = sum(m.unique_visitors for m in metrics)
        wf.total_contact_actions = sum(m.contact_actions for m in metrics)
        wf.avg_density = wf.total_contact_actions / max(wf.unique_visitors_30d, 1)

        # Hot days: density > 0.15
        wf.hot_days = sum(1 for m in metrics if m.density > 0.15)

        # Zero-conversion days
        wf.zero_conversion_days = sum(1 for m in metrics if m.contact_actions == 0)

        # Weekly collapse/rebound
        if len(metrics) >= 14:
            week1 = sum(m.contact_actions for m in metrics[:7])
            week2 = sum(m.contact_actions for m in metrics[7:14])
            week3 = sum(m.contact_actions for m in metrics[14:21])
            week4 = sum(m.contact_actions for m in metrics[21:28])
            if week2 > 0 and (week2 - week1) / week2 < -0.30:
                wf.weekly_collapse = True
            if week3 > 0 and (week3 - week2) / week3 > 0.30:
                wf.weekly_rebound = True

        # Revenue surface
        contacts = wf.total_contact_actions
        wf.close_rate_10pct = contacts * 0.10 * SESSION_PRICE
        wf.close_rate_20pct = contacts * 0.20 * SESSION_PRICE
        wf.close_rate_30pct = contacts * 0.30 * SESSION_PRICE
        wf.monthly_potential_10pct = wf.close_rate_10pct
        wf.monthly_potential_20pct = wf.close_rate_20pct
        wf.monthly_potential_30pct = wf.close_rate_30pct

        # 10% density uplift
        uplifted_visitors = int(wf.unique_visitors_30d * 1.10)
        wf.uplifted_contacts = int(wf.avg_density * uplifted_visitors)
        wf.uplifted_monthly_10pct_close = wf.uplifted_contacts * 0.10 * SESSION_PRICE

        # Proof gaps
        wf.proof_gaps = [
            "Screenshots are not collateral — need verified analytics export",
            "Contact actions are not booked revenue — need booking confirmation",
            "No invoice proof — need invoice records or system export",
            "No deposit proof — need bank deposit records or payment processor export",
            "Raw private chats are not bank-facing — need hashed minimized lead ledger",
        ]

        return wf

    def generate_widgets(self) -> Dict[str, Any]:
        """Generate chat-native widget cards."""
        wf = self.compute_waterfall()

        kpi_cards = [
            {"type": "kpi", "label": "30-Day Unique Visitors", "value": wf.unique_visitors_30d, "format": "number"},
            {"type": "kpi", "label": "Total Contact Actions", "value": wf.total_contact_actions, "format": "number"},
            {"type": "kpi", "label": "Avg Contact Density", "value": round(wf.avg_density * 100, 1), "format": "percent"},
            {"type": "kpi", "label": "Hot Days (>15% density)", "value": wf.hot_days, "format": "number"},
            {"type": "kpi", "label": "Zero-Conversion Days", "value": wf.zero_conversion_days, "format": "number"},
        ]

        banker_safe_claims = [
            {
                "type": "claim_card",
                "claim": f"30-day unique visitors: {wf.unique_visitors_30d}",
                "evidence": "analytics_daily_metrics",
                "bank_safe": True,
                "note": "Verifiable from analytics platform export",
            },
            {
                "type": "claim_card",
                "claim": f"Total contact actions: {wf.total_contact_actions}",
                "evidence": "phone_clicks + email_clicks",
                "bank_safe": True,
                "note": "Verifiable from analytics platform export",
            },
            {
                "type": "claim_card",
                "claim": f"Monthly potential at 20% close rate: ${wf.monthly_potential_20pct:,.0f}",
                "evidence": "contact_actions * 0.20 * $159",
                "bank_safe": False,
                "note": "POTENTIAL revenue, NOT booked revenue. Requires booking + invoice + deposit proof.",
            },
        ]

        revenue_scenarios = [
            {
                "type": "scenario_card",
                "scenario": "Conservative (10% close rate)",
                "sessions": int(wf.total_contact_actions * 0.10),
                "monthly_potential": wf.monthly_potential_10pct,
                "proof_required": "booking + invoice + deposit",
            },
            {
                "type": "scenario_card",
                "scenario": "Base (20% close rate)",
                "sessions": int(wf.total_contact_actions * 0.20),
                "monthly_potential": wf.monthly_potential_20pct,
                "proof_required": "booking + invoice + deposit",
            },
            {
                "type": "scenario_card",
                "scenario": "Optimistic (30% close rate)",
                "sessions": int(wf.total_contact_actions * 0.30),
                "monthly_potential": wf.monthly_potential_30pct,
                "proof_required": "booking + invoice + deposit",
            },
            {
                "type": "scenario_card",
                "scenario": "10% Density Uplift → 10% close",
                "sessions": int(wf.uplifted_contacts * 0.10),
                "monthly_potential": wf.uplifted_monthly_10pct_close,
                "proof_required": "booking + invoice + deposit",
            },
        ]

        proof_gap_cards = [
            {
                "type": "proof_gap_card",
                "gap": gap,
                "status": "missing",
                "blocking": True,
            }
            for gap in wf.proof_gaps
        ]

        receipt = {
            "receipt_version": "1.0",
            "artifact": "rentmasseur_bi",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": wf.to_dict()["disclaimer"],
            "widget_hash": hashlib.sha256(
                json.dumps(wf.to_dict(), sort_keys=True).encode()
            ).hexdigest(),
        }

        return {
            "kpi_cards": kpi_cards,
            "banker_safe_claim_cards": banker_safe_claims,
            "revenue_scenario_cards": revenue_scenarios,
            "proof_gap_cards": proof_gap_cards,
            "receipt": receipt,
            "waterfall": wf.to_dict(),
        }

    def generate_html_dashboard(self) -> str:
        """Generate HTML dashboard from widgets."""
        w = self.generate_widgets()
        wf = w["waterfall"]

        cards_html = ""
        for card in w["kpi_cards"]:
            val = card["value"]
            if card["format"] == "percent":
                val = f"{val}%"
            elif card["format"] == "number":
                val = f"{val:,}"
            cards_html += f'<div class="kpi"><strong>{card["label"]}</strong><br>{val}</div>\n'

        scenarios_html = ""
        for s in w["revenue_scenario_cards"]:
            scenarios_html += f"""<div class="card">
<h4>{s["scenario"]}</h4>
<p>Sessions: {s["sessions"]}</p>
<p>Monthly potential: ${s["monthly_potential"]:,.0f}</p>
<p class="warning">Proof required: {s["proof_required"]}</p>
</div>\n"""

        gaps_html = ""
        for g in w["proof_gap_cards"]:
            gaps_html += f'<div class="gap">⚠ {g["gap"]}</div>\n'

        return f"""<!DOCTYPE html>
<html>
<head><title>RentMasseur BI Dashboard</title>
<style>
body {{ font-family: system-ui; max-width: 900px; margin: 20px auto; padding: 20px; }}
.kpi {{ display: inline-block; margin: 8px; padding: 16px 24px; background: #f0f4ff; border-radius: 10px; text-align: center; }}
.card {{ border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 12px 0; }}
.gap {{ background: #fff3cd; padding: 8px 12px; margin: 4px 0; border-radius: 6px; border: 1px solid #ffc107; }}
.warning {{ color: #856404; font-size: 0.85em; }}
.disclaimer {{ background: #f8d7da; padding: 12px; border-radius: 8px; font-size: 0.9em; }}
h3 {{ border-bottom: 2px solid #007aff; padding-bottom: 8px; }}
</style>
</head>
<body>
<h1>RentMasseur BI Dashboard</h1>
<div class="disclaimer">
<strong>DISCLAIMER:</strong> {wf["disclaimer"]}
</div>

<h3>KPI Cards</h3>
{cards_html}

<h3>Revenue Scenarios (Potential, NOT Booked)</h3>
{scenarios_html}

<h3>Proof Gaps (Must Close Before Bank-Facing)</h3>
{gaps_html}

<h3>Receipt</h3>
<div class="card">
<pre>Receipt hash: {w["receipt"]["widget_hash"]}
Generated: {w["receipt"]["generated_at"]}
Version: {w["receipt"]["receipt_version"]}</pre>
</div>
</body>
</html>"""

    def close(self):
        self.conn.close()


# ─── CLI ───
def main():
    import argparse
    parser = argparse.ArgumentParser(description="RentMasseur BI Artifact")
    parser.add_argument("--db", default="rentmasseur_bi.db")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("demo", help="Ingest demo data and compute waterfall")
    sub.add_parser("widgets", help="Generate widget cards as JSON")
    sub.add_parser("dashboard", help="Generate HTML dashboard")
    sub.add_parser("waterfall", help="Compute valuation waterfall")

    p_ingest = sub.add_parser("ingest", help="Ingest one day of data")
    p_ingest.add_argument("--date", required=True)
    p_ingest.add_argument("--visitors", type=int, required=True)
    p_ingest.add_argument("--phone", type=int, required=True)
    p_ingest.add_argument("--email", type=int, required=True)

    args = parser.parse_args()
    bi = RentMasseurBI(db_path=args.db)

    if args.command == "demo":
        bi.ingest_demo_data()
        wf = bi.compute_waterfall()
        print(json.dumps(wf.to_dict(), indent=2))
    elif args.command == "widgets":
        print(json.dumps(bi.generate_widgets(), indent=2))
    elif args.command == "dashboard":
        html = bi.generate_html_dashboard()
        print(html)
    elif args.command == "waterfall":
        wf = bi.compute_waterfall()
        print(json.dumps(wf.to_dict(), indent=2))
    elif args.command == "ingest":
        bi.ingest_daily(args.date, args.visitors, args.phone, args.email)
        print(f"Ingested {args.date}")
    else:
        parser.print_help()

    bi.close()


if __name__ == "__main__":
    main()
