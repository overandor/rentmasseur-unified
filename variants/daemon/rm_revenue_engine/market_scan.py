"""
MarketScanner — search RentMasseur, collect real bios, compute rank.

Uses confirmed API endpoints only. No Selenium. No browser automation.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .state_db import StateDB
from rm_pri.py.api_client import RentMasseurAPI


class MarketScanner:
    """Scan real market bios via API search."""

    def __init__(self, api: RentMasseurAPI, db: StateDB, output_dir: str = "rm_pri/data"):
        self.api = api
        self.db = db
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def scan_city(self, city: str = "manhattan-ny", pages: int = 5,
                  available_only: bool = False, own_username: str = "") -> dict:
        """Search a city and collect real bios."""
        all_bios = []
        own_rank = None

        for page in range(1, pages + 1):
            try:
                result = self.api.search(city=city, available_only=available_only, page=page)
                users = result.get("users") or result.get("data") or []
                if not users:
                    break

                for i, u in enumerate(users):
                    bio = {
                        "id": u.get("id"),
                        "username": u.get("username"),
                        "city": city,
                        "headline": u.get("headline", ""),
                        "description": u.get("description", ""),
                        "ratingAverage": u.get("ratingAverage"),
                        "reviewsCount": u.get("reviewsCount", 0),
                        "isGold": u.get("isGold", False),
                        "isAvailable": u.get("isAvailable", False),
                        "isCertified": u.get("isCertified", False),
                        "services": u.get("services", []),
                        "scanned_at": datetime.now(timezone.utc).isoformat(),
                        "search_page": page,
                        "search_position": (page - 1) * 20 + i + 1,
                    }
                    all_bios.append(bio)

                    if own_username and u.get("username") == own_username:
                        own_rank = bio["search_position"]

                time.sleep(1.0)
            except Exception as e:
                self.db.add_receipt("market_scan_error", f"Page {page} of {city}: {e}", {"city": city, "page": page, "error": str(e)})
                break

        output_path = self.output_dir / f"market_{city}_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with output_path.open("w") as f:
            for b in all_bios:
                f.write(json.dumps(b, ensure_ascii=False, default=str) + "\n")

        self.db.log_search_rank(city, own_rank or 0, len(all_bios), {"city": city, "pages": pages, "collected": len(all_bios)})
        self.db.add_receipt("market_scan", f"Scanned {city}: {len(all_bios)} bios collected", {
            "city": city, "pages": pages, "collected": len(all_bios),
            "own_rank": own_rank, "output": str(output_path),
        })

        return {
            "city": city,
            "bios_collected": len(all_bios),
            "own_rank": own_rank,
            "output": str(output_path),
        }

    def scan_cities(self, cities: list, pages: int = 5, own_username: str = "") -> list:
        """Scan multiple cities."""
        results = []
        for city in cities:
            r = self.scan_city(city=city, pages=pages, own_username=own_username)
            results.append(r)
        return results

    def rank_by_views_per_day(self, enriched_path: str = None) -> dict:
        """Rank enriched bios by views_per_day."""
        path = Path(enriched_path) if enriched_path else self.output_dir / "real_bios_with_views.jsonl"
        if not path.exists():
            return {"error": "Enriched file not found. Run enrich-views first."}

        bios = [json.loads(l) for l in path.open() if l.strip()]
        has_views = [b for b in bios if b.get("views_per_day", 0) > 0]

        if not has_views:
            return {"error": "No bios have views_per_day. Enrichment needed."}

        has_views.sort(key=lambda b: b.get("views_per_day", 0), reverse=True)

        ranked_path = self.output_dir / "ranked_views_per_day.txt"
        with ranked_path.open("w") as f:
            for i, b in enumerate(has_views, 1):
                f.write(
                    f"#{i} | {b.get('username')} | {b.get('city')} | "
                    f"visits={b.get('visits', 0)} | days={b.get('days_online', 0)} | "
                    f"views/day={b.get('views_per_day', 0):.2f} | "
                    f"rating={b.get('ratingAverage')} | reviews={b.get('reviewsCount')}\n"
                )
                f.write(f"  HEADLINE: {b.get('headline', '')}\n\n")

        self.db.add_receipt("rank_profiles", f"Ranked {len(has_views)} bios by views/day", {
            "total": len(bios), "ranked": len(has_views), "output": str(ranked_path),
        })

        return {
            "total_bios": len(bios),
            "ranked_bios": len(has_views),
            "top_5": [{"username": b["username"], "views_per_day": b["views_per_day"],
                        "headline": b.get("headline", "")} for b in has_views[:5]],
            "output": str(ranked_path),
        }
