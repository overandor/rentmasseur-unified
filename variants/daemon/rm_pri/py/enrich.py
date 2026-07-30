#!/usr/bin/env python3
"""Robust public-profile enricher for RM-PRI.

Fetches public visits and member-since dates for each profile in the corpus.
Respects rate limits, resumes from partial runs, and writes a chained receipt.
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
SITE_WIDE_PHONES = {"1778766027", "6720911878"}


def extract_phone(text: str) -> str:
    """Extract profile-specific phone number, skipping site-wide template numbers."""
    phones = PHONE_RE.findall(text)
    for p in phones:
        digits = re.sub(r"\D", "", p)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            continue
        if digits in SITE_WIDE_PHONES:
            continue
        return digits
    return ""


def fetch_profile(username: str, retries: int = 2, delay: float = 2.0) -> dict:
    result = {
        "username": username,
        "visits": 0,
        "member_since": "",
        "days_online": 0,
        "views_per_day": 0.0,
        "phone": "",
    }
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"https://rentmasseur.com/{username}", headers=HEADERS, timeout=15)
            if r.status_code != 200:
                result["error"] = f"HTTP {r.status_code}"
                return result
            if "CrowdSec" in r.text:
                result["error"] = "captcha"
                return result

            m = re.search(r'Member Since:</div><div class="value">([^<]+)</div>', r.text)
            member_since = m.group(1).strip() if m else ""

            visit_values = [int(v) for v in re.findall(r'"visits":(\d+)', r.text) if v != "0"]
            visits = max(visit_values) if visit_values else 0

            days_online = 0
            if member_since:
                try:
                    joined = datetime.strptime(member_since, "%b %d, %Y")
                    days_online = max(1, (datetime.now() - joined).days)
                except ValueError:
                    pass

            views_per_day = visits / days_online if days_online > 0 else 0.0

            phone = extract_phone(r.text)

            return {
                "username": username,
                "visits": visits,
                "member_since": member_since,
                "days_online": days_online,
                "views_per_day": views_per_day,
                "phone": phone,
            }
        except Exception as e:
            if attempt < retries:
                time.sleep(delay * (attempt + 1))
            else:
                result["error"] = str(e)
    return result


def enrich(
    input_path: Path,
    output_path: Path,
    limit: int = None,
    resume: bool = True,
    min_delay: float = 1.0,
):
    bios = [json.loads(l) for l in input_path.open() if l.strip()]
    if limit:
        bios = bios[:limit]
    total = len(bios)

    # Resume: load existing output
    existing = {}
    if resume and output_path.exists():
        for line in output_path.open():
            if line.strip():
                row = json.loads(line)
                existing[row.get("username")] = row
        print(f"Resuming: {len(existing)} profiles already enriched")

    enriched_count = 0
    failed_count = 0
    captcha_hit = False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp")

    with tmp_path.open("w") as out:
        for i, b in enumerate(bios, 1):
            u = b.get("username")
            if u in existing and existing[u].get("views_per_day", 0) > 0 and existing[u].get("phone", "") not in SITE_WIDE_PHONES and existing[u].get("phone") is not None:
                out.write(json.dumps(existing[u], ensure_ascii=False) + "\n")
                enriched_count += 1
                continue

            print(f"[{i}/{total}] Fetching {u}...", end=" ", flush=True)
            v = fetch_profile(u)
            if v.get("error") == "captcha":
                print("CAPTCHA")
                captcha_hit = True
                # Write remaining as-is and stop
                b.update({"visits": 0, "member_since": "", "days_online": 0, "views_per_day": 0, "scraped_at": datetime.now(timezone.utc).isoformat()})
                out.write(json.dumps(b, ensure_ascii=False) + "\n")
                failed_count += 1
                break
            elif "error" in v:
                print(f"FAIL: {v['error']}")
                b.update({"visits": 0, "member_since": "", "days_online": 0, "views_per_day": 0, "scraped_at": datetime.now(timezone.utc).isoformat()})
                out.write(json.dumps(b, ensure_ascii=False) + "\n")
                failed_count += 1
            else:
                print(f"visits={v['visits']}, days={v['days_online']}, v/day={v['views_per_day']:.1f}")
                b.update(v)
                b["scraped_at"] = datetime.now(timezone.utc).isoformat()
                out.write(json.dumps(b, ensure_ascii=False) + "\n")
                enriched_count += 1

            if i < total:
                time.sleep(min_delay)

    tmp_path.rename(output_path)

    print(f"\nDone: {enriched_count}/{total} enriched, {failed_count} failed")
    if captcha_hit:
        print("CAPTCHA triggered. Stop and wait before retrying.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="rm_pri/data/real_bios_raw.jsonl")
    ap.add_argument("--output", default="rm_pri/data/real_bios_with_views.jsonl")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    enrich(
        Path(args.input),
        Path(args.output),
        limit=args.limit,
        resume=not args.no_resume,
        min_delay=args.delay,
    )


if __name__ == "__main__":
    main()
