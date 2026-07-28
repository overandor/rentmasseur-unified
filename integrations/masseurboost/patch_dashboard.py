#!/usr/bin/env python3
"""Apply small, idempotent runtime wiring updates to the static dashboard."""
from __future__ import annotations

import argparse
from pathlib import Path


def patch(path: Path) -> None:
    source = path.read_text()
    old = "const result=await api('/api/metrics/ingest',{method:'POST',body:payload,timeout:18000});"
    new = "const result=await api('/api/trials',{method:'POST',body:payload,timeout:18000});"
    if new not in source:
        if old not in source:
            raise SystemExit("Could not find trial submission endpoint")
        source = source.replace(old, new, 1)
    source = source.replace(
        "This sends a `trial_signup` event to the live optimizer.",
        "This creates a dedicated trial record in the live optimizer."
    )
    path.write_text(source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    patch(args.path)
    print(f"patched {args.path}")


if __name__ == "__main__":
    main()
