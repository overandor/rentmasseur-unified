#!/usr/bin/env python3
"""RM-PRI CLI — RentMasseur Profile Revenue Intelligence.

Commands:
    validate          Gate 1: validate corpus schema
    atomize           Extract structural atoms from bios
    features          Build C++ feature file
    train             Train views/day model (requires enrichment)
    generate          Generate candidate bios
    score             Score candidates with model
    evolve            Run GA over scored candidates
    select            Select top safe candidates
    status            Show honest system status
    api-check         Test API connectivity (requires credentials)
    enrich-views      Enrich bios with public visits/member-since
    rank-real         Rank bios by real views/day
    snapshot          Take dashboard snapshot (requires credentials)
    start-experiment  Apply approved variant and measure (requires credentials)
    close-experiment  Close experiment and write receipt
    receipts          Show receipt ledger

Usage:
    python3 -m rm_pri.py.cli status
    python3 -m rm_pri.py.cli validate
    python3 -m rm_pri.py.cli train --label reviews
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CPP = ROOT / "cpp" / "rm_pri"
RAW = DATA / "real_bios_raw.jsonl"
ENRICHED = DATA / "real_bios_with_views.jsonl"
RECEIPTS = DATA / "receipts" / "ledger.jsonl"


def _run_cpp(args: list) -> subprocess.CompletedProcess:
    if not CPP.exists():
        print("ERROR: C++ engine not compiled. Run: cd rm_pri/cpp && g++ -O3 -std=c++17 rm_pri.cpp -o rm_pri")
        sys.exit(1)
    return subprocess.run([str(CPP)] + args, capture_output=True, text=True)


def _load_jsonl(path: Path):
    rows = []
    if path.exists():
        with path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def cmd_status(args):
    print("RM-PRI — RentMasseur Profile Revenue Intelligence")
    print("=" * 60)

    # Stage 1
    if not RAW.exists():
        print("\nStage 1: Real Corpus — MISSING")
    else:
        rows = _load_jsonl(RAW)
        print(f"\nStage 1: Real Corpus — {len(rows)} bios loaded")

    # Stage 2
    if not ENRICHED.exists():
        print("\nStage 2: Public Views/Day — NOT STARTED")
        print("  Next: run 'enrich-views' (requires fresh IP or credentials)")
    else:
        rows = _load_jsonl(ENRICHED)
        enriched = [r for r in rows if r.get("views_per_day", 0) > 0]
        print(f"\nStage 2: Public Views/Day — {len(enriched)}/{len(rows)} enriched")

    # Stages 3-5
    print("\nStage 3: Dashboard Labels — NOT STARTED")
    print("Stage 4: Controlled Experiments — NOT STARTED")
    print("Stage 5: Validated Online Learner — NOT STARTED")

    # C++ engine
    print(f"\nC++ Engine: {'compiled' if CPP.exists() else 'NOT COMPILED'}")
    if CPP.exists():
        print(f"  Path: {CPP}")

    print("\nHonest assessment: This is Stage 1 — real corpus loaded.")
    print("Not AGI. Not revenue oracle. Not CTR predictor.")
    print("Next real step: enrich with public visits/member-since.")


def cmd_validate(args):
    result = _run_cpp(["validate", str(RAW)])
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)


def cmd_atomize(args):
    result = _run_cpp(["inspect", str(RAW)])
    print(result.stdout)


def cmd_train(args):
    label = args.label or "reviews"
    if not RAW.exists():
        print("ERROR: real_bios_raw.jsonl not found")
        sys.exit(1)
    cmd = [
        "train", str(RAW),
        "--label", label,
        "--epochs", str(args.epochs),
        "--lr", str(args.lr),
        "--hidden", str(args.hidden),
    ]
    if args.cv:
        cmd.append("--cv")
        cmd.append(str(args.cv))
    if args.walk_forward:
        cmd.append("--walk-forward")
    result = _run_cpp(cmd)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


def cmd_generate(args):
    cmd = [
        "generate",
        "--count", str(args.count),
        "--mode", args.mode,
        "--out", args.out,
    ]
    result = _run_cpp(cmd)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


def cmd_api_check(args):
    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed")
        sys.exit(1)
    h = {"User-Agent": "Mozilla/5.0"}
    r = requests.get("https://rentmasseur.com", headers=h, timeout=10)
    captcha = "CrowdSec" in r.text
    print(f"GET / status: {r.status_code}")
    print(f"CrowdSec captcha: {captcha}")
    if captcha:
        print("RESULT: BLOCKED — rotate IP or wait for ban to clear")
    else:
        print("RESULT: CLEAR")


def cmd_enrich_views(args):
    print("Enriching bios with public visits/member-since...")
    # Check if we can reach site
    import requests
    h = {"User-Agent": "Mozilla/5.0"}
    r = requests.get("https://rentmasseur.com", headers=h, timeout=10)
    if "CrowdSec" in r.text:
        print("BLOCKED: CrowdSec captcha active. Cannot enrich.")
        print("Next: rotate IP or wait for ban to clear.")
        return
    print("Site reachable. Enrichment not yet implemented in C++.")
    print("Use Python fallback: python3 -m rm_pri.py.enrich")


def cmd_receipts(args):
    if not RECEIPTS.exists():
        print("No receipts yet")
        return
    with RECEIPTS.open() as f:
        for line in f:
            r = json.loads(line)
            print(f"{r['index']:03d} | {r['timestamp']} | {r['action']:20s} | {r['description']}")


def main():
    parser = argparse.ArgumentParser(prog="rm-pri", description="RentMasseur Profile Revenue Intelligence")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="Show honest system status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("validate", help="Validate corpus schema")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("atomize", help="Extract corpus atoms")
    p.set_defaults(func=cmd_atomize)

    p = sub.add_parser("train", help="Train model on available labels")
    p.add_argument("--label", default="reviews", choices=["reviews", "views_per_day"])
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--lr", type=float, default=0.001)
    p.add_argument("--hidden", type=int, default=64)
    p.add_argument("--cv", type=int, default=None)
    p.add_argument("--walk-forward", action="store_true")
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("generate", help="Generate candidate bios")
    p.add_argument("--count", type=int, default=10000)
    p.add_argument("--mode", default="speech")
    p.add_argument("--out", default="rm_pri/data/candidates/candidates.jsonl")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("api-check", help="Check API connectivity")
    p.set_defaults(func=cmd_api_check)

    p = sub.add_parser("enrich-views", help="Enrich bios with public visits")
    p.set_defaults(func=cmd_enrich_views)

    p = sub.add_parser("receipts", help="Show receipt ledger")
    p.set_defaults(func=cmd_receipts)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
