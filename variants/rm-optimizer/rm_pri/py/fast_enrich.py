#!/usr/bin/env python3
"""Fast multi-threaded enricher with global rate limiting."""

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
SITE_WIDE_PHONES = {"1778766027", "6720911878"}

rate_lock = Lock()
last_request_time = 0.0


def rate_limited_request(url: str, min_delay: float) -> requests.Response:
    global last_request_time
    with rate_lock:
        elapsed = time.time() - last_request_time
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
        last_request_time = time.time()
    return requests.get(url, headers=HEADERS, timeout=15)


def extract_phone(text: str) -> str:
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


def fetch_profile(username: str, min_delay: float) -> dict:
    try:
        r = rate_limited_request(f"https://rentmasseur.com/{username}", min_delay)
        if r.status_code != 200:
            return {"username": username, "error": f"HTTP {r.status_code}"}
        if "CrowdSec" in r.text:
            return {"username": username, "error": "captcha"}

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
        return {"username": username, "error": str(e)}


def enrich(input_path: Path, output_path: Path, workers: int = 5, min_delay: float = 0.5):
    bios = [json.loads(l) for l in input_path.open() if l.strip()]
    total = len(bios)

    existing = {}
    if output_path.exists():
        for line in output_path.open():
            if line.strip():
                row = json.loads(line)
                if row.get("views_per_day", 0) > 0 and row.get("phone", "") not in SITE_WIDE_PHONES and row.get("phone") is not None:
                    existing[row.get("username")] = row
        print(f"Resuming: {len(existing)} profiles already enriched")

    todo = [b for b in bios if b.get("username") not in existing]
    print(f"Total: {total} | Already enriched: {len(existing)} | To fetch: {len(todo)}")

    results = {}
    captcha_hit = False

    def fetch_one(b):
        nonlocal captcha_hit
        if captcha_hit:
            return None
        u = b.get("username")
        r = fetch_profile(u, min_delay)
        if r.get("error") == "captcha":
            captcha_hit = True
            print(f"\nCAPTCHA at {u}. Stopping.")
        return r

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_one, b): b for b in todo}
        for i, fut in enumerate(futures):
            if captcha_hit:
                break
            r = fut.result()
            if r:
                results[r.get("username")] = r
            if (i + 1) % 50 == 0:
                print(f"  Fetched {i+1}/{len(todo)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as out:
        for b in bios:
            u = b.get("username")
            if u in existing:
                out.write(json.dumps(existing[u], ensure_ascii=False) + "\n")
            elif u in results:
                v = results[u]
                if "error" in v:
                    b.update({"visits": 0, "member_since": "", "days_online": 0, "views_per_day": 0, "phone": "", "error": v["error"], "scraped_at": datetime.now(timezone.utc).isoformat()})
                else:
                    b.update(v)
                    b["scraped_at"] = datetime.now(timezone.utc).isoformat()
                out.write(json.dumps(b, ensure_ascii=False) + "\n")
            else:
                b.update({"visits": 0, "member_since": "", "days_online": 0, "views_per_day": 0, "phone": "", "scraped_at": datetime.now(timezone.utc).isoformat()})
                out.write(json.dumps(b, ensure_ascii=False) + "\n")

    print(f"\nDone. Fetched: {len(results)} | Captcha: {captcha_hit}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="rm_pri/data/real_bios_raw.jsonl")
    ap.add_argument("--output", default="rm_pri/data/real_bios_with_views.jsonl")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()
    enrich(Path(args.input), Path(args.output), args.workers, args.delay)


if __name__ == "__main__":
    main()
