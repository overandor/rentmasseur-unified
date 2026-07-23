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

BUNDLE_B64 = "H4sICG2bXmoC/3RyYW5zcG9ydF9jYXBzdWxlX2Vwb2NoXzEudGFyAO1bS3PcNhLWWb8CNXtJqswRngThLVdtNnvwcStbe0q5WE2gqWE8Q86SHMXelP77ApyHpLGcRKtIcjz9HYZDogE0SeDrbgI9v5hf/O2f8OEtQsD+7EnAt/jckXOlb/6n64JLIc/Yh7NnwGYYoY/dn50mZMFWY7PCN8IW2hSG526undbWFOdnhK8eHtbDZokXT9lHmtTWmO0x3x65vDvnhZHSGmFMkhNC2Tj/zXPOf1ji+tfkolhdf33vf078T/z/Cf8rzYn/T4r/q2Xn3w8XTzb/H8b/MteW+P90+F99yv+C+P9Z+N/ex/9Ca0H0f4L8L8zF08z/h/G/4lYT/5P/T/z/Iv5/kf5rMgAnyf/CgAhCBV1V0haK82CcsFBwUWjtnCniISgTuEKDaH0wlRR1nSMXBrVw98//XOvP8r+J8/8O/0ulZJz//Dnn/4ny/y/njM3gEtuxbMLsNZstAvTZgBiydeezqWT2ahLajIuub8aPUSrVipfqZonDx2HEVaoZcNWxn7v+/bAGj6xrlx+nmlGwxTEVJKm2a5H1+J9N02PYlw/oexyHQzmuKgwhlsfi66n3Fj+MJfix6dok1eMwdn3qhL3thpH9nUEbGKzXmA7Md+3YtBtI4gyvDvfQVT9hbOMKUxvfb4WQbdq6aZthgWFSn0E9Yr9t9zvWb9rEjyzEHvvNpMB821gcEeNm0nnYDKljDGXXlotYr4TZ+fWfgj/J/pP9/zT+k4Wzhuz/6dl/5b+M+E8Yiv+I/4n/Xyj+K6wtaP3nNPlfeeWE4kJo5TliLSsITklvPQhwwWuhg5OonQcV6sARdAwZ0daWV+BMeHj8J7Q9iv+04pbiv+dAwJrdiq2++fb1FJHFaGzTt4c46xDXVLPz86ZmZdnCCsuSvXnDZmW5gqYty9m26rpv2vGbO21+S1RC9p/s/58o/uO6oPjvBO2/UV/K+l9O8R/xP/H/C8V/wnBa/ztN/jfKWBkMKiPB1cEWWAmolYheQcVROAClTVUVsjaGBw8BKi4KATwAd85VD4//5CfrfzqaAIr/ngO/zLbLY6/ZzPcI4501rFdsNv1bQoXLaXEwnmWQxbECy2wFPkkcrcwNCEu2G1XToty0cNZ9ZIs762mpZjrGx7pax3pH2w+sLa6Jf8j+k/1/kfhPWeNymn+nZ//r4gtZ/8tp/Y/4n/j/peI/wx3Ff6fJ/3URpAUreM01IHKJhc+Rg6qMzSsvK+s1QFFrb5SAQnsZrFIyjhiMcaBRD4//1DH/S2WVofjvOfAX9u+b3Y9v//HdD2yE4f35ecZ+/PCOfT+FhCxseqhiOOcX6N+vu6Yd50mAvWM/HO/D3BccNleOC5yavH9XZTOwy67Ffa1/peBx2HiPw9D1hzDy52ZcsDX0MVBlK2ibOvbKFjAs5sRRZP/J/v/h8Z9W2iqaWydk//e0Ov9p6NonmP+/Yv+lleoo/tPc0v6fZ8Hvz/+4nVNRTk5AEt/Z8/TVNzoQGOssmPjrPiljFZ8u2+dqTBka4Qpaj2zdd5fx+jBfdpe7dIr952cYjz4HO83zYhKZmk+l09l+yJbJE0i6cKur3HgUvlJOoASZF2AVQJ4XxtdeeVdr4TkKFVRe1RK90VBwri3PZQVPkCOydVrKY1XbzXK5zSGJLtUK9s99PvbQDuuuH7P9vLzic7FLN2kuWxg3PZarLkzKdatmjE8sa9os1UkuWpaScLLNgFl8wmGrSoZBGiNctoZxkdXd9vXuGu02vcfyt77yJ9Er7Ju68dv3v1dhWIA0eZbGRrzPDEJIbzXqlG40O6QAzQ5pQYdHcZRFFE9/nE7Z7vJUtOtGS/7q5mKPyzLdSup/O3JTJg5OzDW7JbfVLUk9NqXtTqvNf5NKShe7a9ev/g+9b4//+3V+7DLcPToLkz9G56H3F+k9Yj9ff7xf6cfuHb1Paa4eo/TYhW6+Cver+9hQ9z51ndyrOx3f7TLc+q67ISoV3SsvnBPgRe7BS5vzSFhKuVrVqQcXmSme2GDROZRFyEX0ko31tauikdynzY3dCMty17N1LmXLnV+T/0/+/2P9f2NySf7/Cfn/PXps1k/i/v/m9z8bJ/vR+o+VnPz/L8v/v+t83+wa2Q6gchsBzJ7SM9+N0UOrBUafKEQ/TgQQ1vmgfIFFVWkLQUL0NDQGX8SfyvEiRItd5Jw7yBXUwYedi3Tsgu86ue14/34f+XM7WpxW1h45wn+sR/BAs08gEAgEAoFAIBAIBAKBQCAQCAQCgUAgEAgEAuErwv8AKusgzQB4AAA="
BUNDLE_SHA256 = "7f0581093409982e442196e32a86605d7d5b5bc60c7d852940c77309d86a8c52"
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


def safe_extract_tar(tf: tarfile.TarFile, dest: Path) -> None:
    try:
        tf.extractall(dest, filter="data")
    except TypeError:
        tf.extractall(dest)


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
        safe_extract_tar(tf, out_dir)

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
