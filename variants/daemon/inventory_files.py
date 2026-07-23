"""Inventory all RentMasseur-related files across known project directories.

Outputs a JSON manifest of every relevant file with size, type, and location.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

# Roots referenced by the user
ROOTS = [
    Path("/Users/alep/Downloads/data"),
    Path("/Users/alep/Downloads/rentmasseur-optimizer"),
    Path("/Users/alep/Downloads/sellable-repos/glyphos-bundle/systems/rm_traffic"),
    Path("/Users/alep/Downloads/sellable-repos/glyphos-bundle/systems/masseuros"),
    Path("/Users/alep/Downloads/sellable-repos/glyphos-bundle/systems/shadowshard_mforge/data/masseuros"),
    Path("/Users/alep/Downloads/windsurf-smoke/masseuros"),
    Path("/Users/alep/Downloads/windsurf-smoke/shadowshard_mforge/data/masseuros"),
    Path("/Users/alep/Downloads/windsurf-smoke/browser_bridge"),
    Path("/Users/alep/Downloads/windsurf-smoke/data"),
    Path("/Users/alep/Downloads/5647dea192a8fdead8a74eb82d153046ed7592c63060567522be3b98db6be49a-2026-07-10-22-21-58-1d1b9fd0aea44fbaa622927667d9830a/restored_files"),
    Path("/Users/alep/Downloads/_worktree_rescue/sad-kalam-fc097a/MEMBRA_VAULT_COLD/01_SYSTEMS/MEMBRA_DEPRECATED_VAULT/rentmasseur_scraper"),
    Path("/Users/alep/Downloads/MEMBRA::VAULT=CONFIG@FROZEN/MEMBRA_VAULT_COLD/01_SYSTEMS/MEMBRA_DEPRECATED_VAULT/rentmasseur_scraper"),
]

# Patterns that identify RentMasseur-related files
PATTERNS = [
    "*rentmasseur*",
    "*masseur*",
    "*masseuro*",
    "*rm_*",
    "*bio*",
    "*profile*",
    "*view*",
    "*traffic*",
    "*revenue*",
    "*.jsonl",
    "*.xlsx",
    "*.csv",
    "*.html",
    "*.db",
    "*.sqlite",
    "*.log",
]

RELEVANT_EXTENSIONS = {
    ".py", ".js", ".ts", ".cpp", ".h", ".swift", ".json", ".jsonl",
    ".csv", ".xlsx", ".html", ".db", ".sqlite", ".log", ".txt",
    ".zip", ".png", ".jpg", ".jpeg",
}


def is_relevant(path: Path) -> bool:
    """Quick relevance filter."""
    name = path.name.lower()
    if any(k in name for k in ["rentmasseur", "masseur", "masseuro", "rm_", "bios", "views"]):
        return True
    ext = path.suffix.lower()
    if ext in {".jsonl", ".xlsx", ".csv", ".db", ".sqlite"}:
        return True
    if ext in {".py", ".js", ".ts", ".cpp", ".h", ".swift"}:
        if any(k in name for k in ["rent", "masseur", "bio", "profile", "traffic", "view", "revenue"]):
            return True
    return False


def walk(root: Path) -> list[dict]:
    items = []
    if not root.exists():
        return items
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        # Prune irrelevant deep dirs
        if any(x in dp.parts for x in ["__pycache__", ".git", "node_modules", ".venv"]):
            continue
        for fname in filenames:
            fpath = dp / fname
            try:
                if not is_relevant(fpath):
                    continue
                stat = fpath.stat()
                items.append({
                    "path": str(fpath),
                    "relative": str(fpath.relative_to(root) if fpath.is_relative_to(root) else fpath),
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "type": fpath.suffix.lower() or "noext",
                    "root": str(root),
                })
            except (OSError, PermissionError):
                continue
    return items


def inventory() -> Path:
    out_dir = Path("/Users/alep/Downloads/data/backups")
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"rentmasseur_inventory_{timestamp}.json"

    all_items = []
    for root in ROOTS:
        print(f"Scanning {root} ...")
        items = walk(root)
        all_items.extend(items)

    all_items.sort(key=lambda x: x["path"])

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "roots": [str(r) for r in ROOTS],
        "total_files": len(all_items),
        "files": all_items,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nInventory: {len(all_items):,} files -> {out_path}")

    # Print summary by extension
    by_ext: dict[str, int] = {}
    by_root: dict[str, int] = {}
    for it in all_items:
        by_ext[it["type"]] = by_ext.get(it["type"], 0) + 1
        by_root[it["root"]] = by_root.get(it["root"], 0) + 1

    print("\nBy extension:")
    for ext, cnt in sorted(by_ext.items(), key=lambda x: -x[1])[:15]:
        print(f"  {ext}: {cnt}")

    print("\nBy root:")
    for root, cnt in sorted(by_root.items(), key=lambda x: -x[1]):
        print(f"  {Path(root).name}: {cnt}")

    return out_path


if __name__ == "__main__":
    inventory()
