"""Backfill missing RentMasseur profile views by scraping public profile pages.

This script reads a JSONL of profiles missing views, fetches each public
profile page, and extracts:
  - visits           (total profile views)
  - member_since     (registration date string like "Mar 25, 2014")
  - days_online      (days since registration)
  - views_per_day    (visits / days_online)

Output is written as JSONL and merged into the base file.

NOTE: This makes HTTP requests to rentmasseur.com. Use responsibly and
respect rate limits / robots.txt / Terms of Service.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_member_since(html: str) -> str:
    """Extract Member Since date from profile page HTML."""
    match = re.search(r'Member Since:</div><div class="value">([^<]+)</div>', html)
    if match:
        return match.group(1).strip()
    # Fallback variants
    match = re.search(r'Member Since[^<]*<[^>]*value[^>]*>([^<]+)</', html, re.I)
    return match.group(1).strip() if match else ""


def parse_visits(html: str) -> int:
    """Extract profile visit count from page HTML/JSON."""
    # Primary: JSON "visits":N (skip 0 which is often the viewer's own stat)
    vals = [int(v) for v in re.findall(r'"visits":(\d+)', html) if v != "0"]
    if vals:
        return max(vals)

    # Fallback text patterns
    m = re.search(r'(\d[\d,]*)\s+profile\s+views', html, re.I)
    if m:
        return int(m.group(1).replace(",", ""))

    m = re.search(r'Profile Views\s*</[^>]*>\s*<[^>]*>([\d,]+)', html, re.I)
    if m:
        return int(m.group(1).replace(",", ""))

    return 0


def days_since(date_str: str) -> int:
    """Calculate days since date string like 'Mar 25, 2014'."""
    if not date_str:
        return 0
    try:
        joined = datetime.strptime(date_str, "%b %d, %Y")
        return max(1, (datetime.now() - joined).days)
    except ValueError:
        return 0


def fetch_profile_views(username: str, delay: float = 0.25) -> dict:
    """Fetch and parse views for one username."""
    if not username:
        return _empty_views()
    url = f"https://rentmasseur.com/{username}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return _empty_views(error=f"HTTP {resp.status_code}")
        member_since = parse_member_since(resp.text)
        visits = parse_visits(resp.text)
        days = days_since(member_since)
        views_per_day = round(visits / days, 4) if days else 0
        time.sleep(delay)
        return {
            "visits": visits,
            "member_since": member_since,
            "days_online": days,
            "views_per_day": views_per_day,
            "_fetch_ok": True,
        }
    except Exception as e:
        return _empty_views(error=str(e))


def _empty_views(error: str = "") -> dict:
    return {
        "visits": 0,
        "member_since": "",
        "days_online": 0,
        "views_per_day": 0,
        "_fetch_ok": False,
        "_error": error,
    }


def backfill(
    missing_path: Path,
    base_path: Path | None = None,
    workers: int = 8,
    delay: float = 0.25,
) -> Path:
    """Fetch views for all profiles in missing file and merge into base file."""
    out_dir = missing_path.parent
    date_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    missing: list[dict] = []
    with open(missing_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                missing.append(json.loads(line))

    print(f"Backfilling views for {len(missing):,} profiles with {workers} workers...")

    results: list[dict] = []
    fetched = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_rec = {
            pool.submit(fetch_profile_views, rec.get("username", ""), delay): rec
            for rec in missing
        }
        for future in as_completed(future_to_rec):
            rec = future_to_rec[future]
            try:
                views = future.result()
            except Exception as e:
                views = _empty_views(error=str(e))

            rec["visits"] = views["visits"]
            rec["member_since"] = views["member_since"]
            rec["days_online"] = views["days_online"]
            rec["views_per_day"] = views["views_per_day"]
            rec["_fetch_ok"] = views["_fetch_ok"]
            if views.get("_error"):
                rec["_fetch_error"] = views["_error"]
                errors += 1
            if views["_fetch_ok"]:
                fetched += 1
            results.append(rec)

    backfill_path = out_dir / f"backfilled_views_{date_stamp}.jsonl"
    with open(backfill_path, "w", encoding="utf-8") as f:
        for rec in results:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    print(f"Backfilled {fetched:,} profiles, {errors:,} errors -> {backfill_path}")

    if base_path and base_path.exists():
        # Merge back into base
        base_records: list[dict] = []
        with open(base_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    base_records.append(json.loads(line))

        backfill_by_id = {r["id"]: r for r in results if "id" in r}
        backfill_by_user = {r["username"]: r for r in results if r.get("username")}

        for rec in base_records:
            patch = backfill_by_id.get(rec.get("id")) or backfill_by_user.get(rec.get("username"))
            if patch:
                for fld in ["visits", "member_since", "days_online", "views_per_day"]:
                    rec[fld] = patch.get(fld, 0)

        complete_path = out_dir / f"real_bios_complete_{date_stamp}.jsonl"
        with open(complete_path, "w", encoding="utf-8") as f:
            for rec in base_records:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        print(f"Complete merged dataset -> {complete_path}")
        return complete_path

    return backfill_path


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    candidates = [
        here / ".." / "data" / "backups",
        here / "data" / "backups",
        Path("/Users/alep/Downloads/data/backups"),
    ]

    missing_path = None
    base_path = None
    for cand in candidates:
        mp = cand / "missing_views_20260625_183110.jsonl"
        if mp.exists():
            missing_path = mp
            base_path = cand / "real_bios_merged_20260625_183110.jsonl"
            break

    if missing_path is None:
        # Use most recent missing file in same dir
        files = sorted(
            Path("/Users/alep/Downloads/data/backups").glob("missing_views_*.jsonl")
        )
        if files:
            missing_path = files[-1]
            base_path = missing_path.parent / f"real_bios_merged_{missing_path.stem.split('_')[-1]}.jsonl"

    if missing_path is None:
        raise FileNotFoundError("No missing_views JSONL found. Run merge_bios.py first.")

    backfill(missing_path, base_path=base_path)
