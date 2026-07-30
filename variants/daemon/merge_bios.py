"""Merge full bios with existing view data and prepare backfill list.

Inputs:
  real_bios_20260625_183110.jsonl          (full profiles, no views)
  real_bios_with_views_20260625_183110.jsonl (some profiles with views)

Outputs:
  real_bios_merged_YYYYMMDD.jsonl          (all full profiles + views where known)
  missing_views_YYYYMMDD.jsonl           (profiles that still need views fetched)
  merge_report_YYYYMMDD.txt              (summary statistics)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def merge_bios(
    full_path: Path,
    views_path: Path,
    out_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    out_dir = out_dir or full_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    full = load_jsonl(full_path)
    with_views = load_jsonl(views_path)

    # Index by id first, then username fallback
    views_by_id: dict[int, dict] = {}
    views_by_user: dict[str, dict] = {}
    for v in with_views:
        vid = v.get("id")
        vuser = v.get("username")
        if vid is not None:
            views_by_id[int(vid)] = v
        if vuser:
            views_by_user[vuser] = v

    view_fields = ["visits", "member_since", "days_online", "views_per_day"]

    merged: list[dict] = []
    missing: list[dict] = []
    has_views = 0
    missing_views = 0

    for rec in full:
        rid = rec.get("id")
        ruser = rec.get("username")

        view_rec = views_by_id.get(int(rid)) if rid is not None else None
        if not view_rec and ruser:
            view_rec = views_by_user.get(ruser)

        if view_rec:
            for fld in view_fields:
                rec[fld] = view_rec.get(fld)
            has_views += 1
        else:
            for fld in view_fields:
                rec[fld] = 0 if fld != "member_since" else ""
            missing.append(rec)
            missing_views += 1

        merged.append(rec)

    # Profiles in views file but not in full set
    extra_ids = set(views_by_id.keys()) - {r.get("id") for r in full if r.get("id")}
    extra_users = set(views_by_user.keys()) - {r.get("username") for r in full if r.get("username")}
    extras = [views_by_id.get(i) or views_by_user.get(u) for i, u in zip(extra_ids, extra_users)]
    extras = [e for e in extras if e]

    date_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    merged_path = out_dir / f"real_bios_merged_{date_stamp}.jsonl"
    missing_path = out_dir / f"missing_views_{date_stamp}.jsonl"
    report_path = out_dir / f"merge_report_{date_stamp}.txt"

    with open(merged_path, "w", encoding="utf-8") as f:
        for rec in merged:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    with open(missing_path, "w", encoding="utf-8") as f:
        for rec in missing:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("RentMasseur Bio Merge Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Full profiles loaded:        {len(full):,}\n")
        f.write(f"Profiles with views loaded:  {len(with_views):,}\n")
        f.write(f"Overlap by id/username:        {has_views:,}\n")
        f.write(f"Missing views:               {missing_views:,}\n")
        f.write(f"Extra profiles in views file: {len(extras):,}\n\n")
        f.write(f"Output files:\n")
        f.write(f"  Merged:  {merged_path}\n")
        f.write(f"  Missing: {missing_path}\n\n")
        f.write("Sample missing usernames (first 20):\n")
        for rec in missing[:20]:
            f.write(f"  - {rec.get('username')} (id={rec.get('id')}, city={rec.get('city')})\n")

    print(f"Merged {len(merged):,} profiles -> {merged_path}")
    print(f"Missing views for {len(missing):,} profiles -> {missing_path}")
    print(f"Report -> {report_path}")
    return merged_path, missing_path, report_path


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    backups = here / ".." / "data" / "backups"
    # Try common locations
    candidates = [
        backups,
        here / "data" / "backups",
        Path("/Users/alep/Downloads/data/backups"),
    ]
    full_path = None
    views_path = None
    for cand in candidates:
        fp = cand / "real_bios_20260625_183110.jsonl"
        vp = cand / "real_bios_with_views_20260625_183110.jsonl"
        if fp.exists() and vp.exists():
            full_path = fp
            views_path = vp
            break

    if full_path is None:
        raise FileNotFoundError(
            "Could not find real_bios_20260625_183110.jsonl and real_bios_with_views_20260625_183110.jsonl"
        )

    merge_bios(full_path, views_path)
