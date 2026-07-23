#!/usr/bin/env python3
"""Generated HDAR Host B restore/continue/reseal bundle."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import time
from pathlib import Path

BUNDLE_B64 = "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"
BUNDLE_SHA256 = "0b42adb390b9107f47690e75cc32377592fa683bdea3dc3f3a62c939842aabde"
AGENT_ID = "hdar-seed-poc-agent"
SCHEMA = "hdar.transport-capsule/v0.1"
CHUNK_SIZE = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def hash_workspace(workspace: Path) -> dict:
    files = []
    total_size = 0
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel_path = path.relative_to(workspace).as_posix()
        st = path.stat()
        entry = {"rel_path": rel_path, "sha256": sha256_file(path), "size": st.st_size, "mode": st.st_mode & 0o777}
        files.append(entry)
        total_size += entry["size"]
    root_material = "\n".join(f"{f['rel_path']}|{f['sha256']}|{f['size']}|{f['mode']}" for f in files).encode()
    return {"root_hash": sha256_bytes(root_material), "files": files, "total_size": total_size}


def verify_capsule(capsule_dir: Path) -> dict:
    manifest = json.loads((capsule_dir / "manifest.json").read_text())
    expected_manifest_hash = sha256_bytes(canonical_json({k: v for k, v in manifest.items() if k != "manifest_hash"}))
    problems = []
    if expected_manifest_hash != manifest.get("manifest_hash"):
        problems.append("manifest hash mismatch")
    missing = 0
    corrupt = 0
    for entry in manifest["workspace_manifest"]["files"]:
        digest = entry["sha256"]
        blob = capsule_dir / "blocks" / digest[:2] / digest
        if not blob.exists():
            missing += 1
        elif sha256_file(blob) != digest:
            corrupt += 1
    if missing:
        problems.append(f"{missing} content blocks missing")
    if corrupt:
        problems.append(f"{corrupt} content blocks corrupt")
    return {
        "ok": not problems,
        "problems": problems,
        "agent_id": manifest["agent_id"],
        "epoch": manifest["epoch"],
        "manifest_hash": manifest["manifest_hash"],
        "workspace_root_hash": manifest["workspace_manifest"]["root_hash"],
        "file_count": len(manifest["workspace_manifest"]["files"]),
        "total_size": manifest["workspace_manifest"]["total_size"],
    }


def restore_workspace(capsule_dir: Path, dest: Path) -> dict:
    verification = verify_capsule(capsule_dir)
    if not verification["ok"]:
        raise RuntimeError(f"capsule verification failed: {verification['problems']}")
    manifest = json.loads((capsule_dir / "manifest.json").read_text())
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for entry in manifest["workspace_manifest"]["files"]:
        blob = capsule_dir / "blocks" / entry["sha256"][:2] / entry["sha256"]
        out = dest / entry["rel_path"]
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(blob, out)
        os.chmod(out, entry["mode"])
    restored = hash_workspace(dest)
    return {
        "restored_root_hash": restored["root_hash"],
        "expected_root_hash": manifest["workspace_manifest"]["root_hash"],
        "exact": restored["root_hash"] == manifest["workspace_manifest"]["root_hash"],
        "file_count": len(restored["files"]),
        "total_size": restored["total_size"],
    }


def seal_workspace(workspace: Path, capsule_dir: Path, *, epoch: int, parent_manifest_hash: str, source_host_label: str) -> dict:
    capsule_dir.mkdir(parents=True, exist_ok=True)
    blocks_dir = capsule_dir / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)
    workspace_manifest = hash_workspace(workspace)
    for entry in workspace_manifest["files"]:
        src = workspace / entry["rel_path"]
        digest = entry["sha256"]
        dest = blocks_dir / digest[:2] / digest
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    manifest = {
        "schema": SCHEMA,
        "agent_id": AGENT_ID,
        "epoch": epoch,
        "parent_manifest_hash": parent_manifest_hash,
        "created_at": time.time(),
        "source_host_label": source_host_label,
        "objective": "Continue unfinished work after Host A runtime destruction.",
        "continuation_point": "Host B restored the workspace, advanced progress.log, updated agent_state.json, and sealed epoch 2.",
        "verification_mode": "sha256-content-addressed-hash-only",
        "signature_mode": "omitted-in-portable-demo-use-production-ed25519-path-for-seed",
        "workspace_manifest": workspace_manifest,
    }
    manifest["manifest_hash"] = sha256_bytes(canonical_json({k: v for k, v in manifest.items() if k != "manifest_hash"}))
    (capsule_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    receipt = {
        "schema": "hdar.receipt/v0.1",
        "event": "capsule_sealed_after_host_b_continuation",
        "agent_id": AGENT_ID,
        "epoch": epoch,
        "source_host_label": source_host_label,
        "manifest_hash": manifest["manifest_hash"],
        "workspace_root_hash": workspace_manifest["root_hash"],
        "timestamp": time.time(),
    }
    receipt["receipt_hash"] = sha256_bytes(canonical_json(receipt))
    (capsule_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="Output directory. Defaults to a temp directory.")
    ap.add_argument("--host-label", default="host-b-independent")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve() if args.out else Path(tempfile.mkdtemp(prefix="hdar-host-b-proof-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_bytes = base64.b64decode(BUNDLE_B64.encode())
    bundle_hash = sha256_bytes(bundle_bytes)
    if bundle_hash != BUNDLE_SHA256:
        raise SystemExit(f"transport bundle hash mismatch: {bundle_hash} != {BUNDLE_SHA256}")

    bundle_tar = out_dir / "transport_capsule_epoch_1.tar.gz"
    bundle_tar.write_bytes(bundle_bytes)
    with tarfile.open(bundle_tar, "r:gz") as tf:
        tf.extractall(out_dir)

    capsule_epoch_1 = out_dir / "capsule"
    before_verify = verify_capsule(capsule_epoch_1)
    restored_workspace = out_dir / "restored_workspace"
    restore_report = restore_workspace(capsule_epoch_1, restored_workspace)
    if not restore_report["exact"]:
        raise SystemExit("workspace restoration was not exact")

    progress = restored_workspace / "progress.log"
    state_path = restored_workspace / "agent_state.json"
    state = json.loads(state_path.read_text())
    event = {
        "event": "continued_on_host_b",
        "host_label": args.host_label,
        "host_platform": platform.platform(),
        "epoch_from": before_verify["epoch"],
        "epoch_to": before_verify["epoch"] + 1,
        "timestamp": time.time(),
    }
    progress.write_text(progress.read_text() + json.dumps(event, sort_keys=True) + "\n")
    state["status"] = "continued_on_host_b"
    state["host_b_label"] = args.host_label
    state["last_event"] = event
    state["next_action"] = "return successor capsule to Host A or another provider and verify lineage."
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    capsule_epoch_2 = out_dir / "capsule_epoch_2"
    successor_manifest = seal_workspace(
        restored_workspace,
        capsule_epoch_2,
        epoch=before_verify["epoch"] + 1,
        parent_manifest_hash=before_verify["manifest_hash"],
        source_host_label=args.host_label,
    )
    successor_verify = verify_capsule(capsule_epoch_2)
    successor_tar = out_dir / "successor_capsule_epoch_2.tar.gz"
    with tarfile.open(successor_tar, "w:gz") as tf:
        tf.add(capsule_epoch_2, arcname="capsule_epoch_2")

    report = {
        "schema": "hdar.second-host-proof-report/v0.1",
        "claim_boundary": "Hash-only portable Host B proof. Real seed proof still requires production Ed25519 verification and a genuinely independent host run.",
        "host_b_platform": platform.platform(),
        "host_b_label": args.host_label,
        "transport_bundle_sha256": bundle_hash,
        "input_capsule": before_verify,
        "restore": restore_report,
        "continuation_event": event,
        "successor_capsule": successor_verify,
        "lineage_advanced": successor_manifest["parent_manifest_hash"] == before_verify["manifest_hash"] and successor_manifest["epoch"] == before_verify["epoch"] + 1,
        "successor_tar": {
            "path": str(successor_tar),
            "bytes": successor_tar.stat().st_size,
            "sha256": sha256_file(successor_tar),
        },
        "output_dir": str(out_dir),
    }
    (out_dir / "host_b_report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
