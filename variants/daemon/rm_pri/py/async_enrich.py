#!/usr/bin/env python3
"""Async public-profile enricher for RM-PRI. High throughput with captcha detection."""

import argparse
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")


def extract_phone(text: str) -> str:
    phones = PHONE_RE.findall(text)
    if not phones:
        return ""
    digits = re.sub(r"\D", "", phones[0])
    if len(digits) == 10:
        return digits
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return ""


def parse_profile_page(username: str, text: str) -> dict:
    if "CrowdSec" in text:
        return {"username": username, "error": "captcha"}

    m = re.search(r'Member Since:</div><div class="value">([^<]+)</div>', text)
    member_since = m.group(1).strip() if m else ""

    visit_values = [int(v) for v in re.findall(r'"visits":(\d+)', text) if v != "0"]
    visits = max(visit_values) if visit_values else 0

    days_online = 0
    if member_since:
        try:
            joined = datetime.strptime(member_since, "%b %d, %Y")
            days_online = max(1, (datetime.now() - joined).days)
        except ValueError:
            pass

    views_per_day = visits / days_online if days_online > 0 else 0.0
    phone = extract_phone(text)

    return {
        "username": username,
        "visits": visits,
        "member_since": member_since,
        "days_online": days_online,
        "views_per_day": views_per_day,
        "phone": phone,
    }


async def fetch_one(session: aiohttp.ClientSession, username: str, sem: asyncio.Semaphore, min_delay: float) -> dict:
    async with sem:
        url = f"https://rentmasseur.com/{username}"
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                text = await resp.text()
                if "CrowdSec" in text:
                    return {"username": username, "error": "captcha"}
                return parse_profile_page(username, text)
        except Exception as e:
            return {"username": username, "error": str(e)}
        finally:
            await asyncio.sleep(min_delay)


async def enrich(input_path: Path, output_path: Path, concurrency: int = 100, min_delay: float = 0.01):
    bios = [json.loads(l) for l in input_path.open() if l.strip()]
    total = len(bios)

    existing = {}
    if output_path.exists():
        for line in output_path.open():
            if line.strip():
                row = json.loads(line)
                if row.get("views_per_day", 0) > 0 and row.get("phone", None) is not None:
                    existing[row.get("username")] = row
        print(f"Resuming: {len(existing)} profiles already enriched")

    # Only fetch those not already enriched
    todo = [b for b in bios if b.get("username") not in existing]
    print(f"Total: {total} | Already enriched: {len(existing)} | To fetch: {len(todo)}")

    connector = aiohttp.TCPConnector(limit=concurrency * 2, limit_per_host=concurrency * 2)
    sem = asyncio.Semaphore(concurrency)

    captcha_hit = False
    results = {}

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_one(session, b.get("username"), sem, min_delay) for b in todo]
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            r = await coro
            if r.get("error") == "captcha":
                captcha_hit = True
                print(f"\nCAPTCHA detected at {r['username']}. Stopping.")
                break
            results[r.get("username")] = r
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i+1}/{len(todo)} fetched")

    # Merge and write
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
                # Not fetched (captcha hit)
                b.update({"visits": 0, "member_since": "", "days_online": 0, "views_per_day": 0, "phone": "", "scraped_at": datetime.now(timezone.utc).isoformat()})
                out.write(json.dumps(b, ensure_ascii=False) + "\n")

    print(f"\nDone. Fetched: {len(results)} | Captcha: {captcha_hit}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="rm_pri/data/real_bios_raw.jsonl")
    ap.add_argument("--output", default="rm_pri/data/real_bios_with_views.jsonl")
    ap.add_argument("--concurrency", type=int, default=100)
    ap.add_argument("--delay", type=float, default=0.01)
    args = ap.parse_args()
    asyncio.run(enrich(Path(args.input), Path(args.output), args.concurrency, args.delay))


if __name__ == "__main__":
    main()
