#!/usr/bin/env python3
"""HDAR portable second-host capsule proof bundle generator.

This creates a minimal host-A capsule, destroys the host-A runtime workspace,
and emits a single Python file that can be executed on an independent Host B.

The generated Host B bundle:
  1. unpacks the transported capsule bytes,
  2. verifies manifest and content-addressed block hashes,
  3. restores the workspace byte-for-byte,
  4. continues the unfinished task by updating durable state,
  5. seals a successor capsule,
  6. writes a machine-readable proof report.

Boundary: this script intentionally uses hash-only verification so it has no
third-party dependencies on Host B. It proves portable cross-host transport,
exact workspace restoration, continuation, and successor sealing. It does not
replace the production Ed25519 owner-signature path.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import time
from pathlib import Path


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
    files: list[dict] = []
    total_size = 0
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel_path = path.relative_to(workspace).as_posix()
        st = path.stat()
        entry = {
            "rel_path": rel_path,
            "sha256": sha256_file(path),
            "size": st.st_size,
            "mode": st.st_mode & 0o777,
        }
        files.append(entry)
        total_size += entry["size"]

    root_material = "\n".join(
        f"{f['rel_path']}|{f['sha256']}|{f['size']}|{f['mode']}" for f in files
    ).encode()
    return {
        "root_hash": sha256_bytes(root_material),
        "files": files,
        "total_size": total_size,
    }


def seal_workspace(
    workspace: Path,
    capsule_dir: Path,
    *,
    epoch: int,
    parent_manifest_hash: str | None,
    source_host_label: str,
    objective: str,
    continuation_point: str,
) -> dict:
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
        "objective": objective,
        "continuation_point": continuation_point,
        "verification_mode": "sha256-content-addressed-hash-only",
        "signature_mode": "omitted-in-portable-demo-use-production-ed25519-path-for-seed",
        "workspace_manifest": workspace_manifest,
    }
    manifest["manifest_hash"] = sha256_bytes(canonical_json({k: v for k, v in manifest.items() if k != "manifest_hash"}))

    (capsule_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    receipt = {
        "schema": "hdar.receipt/v0.1",
        "event": "capsule_sealed",
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


def verify_capsule(capsule_dir: Path) -> dict:
    manifest = json.loads((capsule_dir / "manifest.json").read_text())
    expected_manifest_hash = sha256_bytes(canonical_json({k: v for k, v in manifest.items() if k != "manifest_hash"}))
    problems: list[str] = []
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


def make_capsule_tar(capsule_dir: Path, out_tar: Path) -> dict:
    if out_tar.exists():
        out_tar.unlink()
    with tarfile.open(out_tar, "w:gz") as tf:
        tf.add(capsule_dir, arcname="capsule")
    data = out_tar.read_bytes()
    return {
        "path": str(out_tar),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "base64": base64.b64encode(data).decode(),
    }


REMOTE_TEMPLATE = r'''#!/usr/bin/env python3
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

BUNDLE_B64 = "__BUNDLE_B64__"
BUNDLE_SHA256 = "__BUNDLE_SHA256__"
AGENT_ID = "__AGENT_ID__"
SCHEMA = "__SCHEMA__"
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
'''


def write_host_b_bundle(capsule_tar: dict, bundle_path: Path) -> None:
    script = REMOTE_TEMPLATE
    script = script.replace("__BUNDLE_B64__", capsule_tar["base64"])
    script = script.replace("__BUNDLE_SHA256__", capsule_tar["sha256"])
    script = script.replace("__AGENT_ID__", AGENT_ID)
    script = script.replace("__SCHEMA__", SCHEMA)
    bundle_path.write_text(script)
    os.chmod(bundle_path, 0o755)


def create_demo_workspace(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "src").mkdir(exist_ok=True)
    (workspace / "agent_state.json").write_text(json.dumps({
        "agent_id": AGENT_ID,
        "status": "suspended_on_host_a",
        "objective": "Continue unfinished work after Host A runtime destruction.",
        "next_action": "restore on Host B and append a continuation event",
        "authority": {
            "filesystem": "demo workspace only",
            "network": "none required",
            "secrets": "none embedded",
        },
    }, indent=2, sort_keys=True) + "\n")
    (workspace / "progress.log").write_text(
        json.dumps({
            "event": "created_on_host_a",
            "host_label": "host-a-local-mac",
            "timestamp": time.time(),
            "next_action": "seal capsule and destroy host A runtime",
        }, sort_keys=True) + "\n"
    )
    (workspace / "todo.md").write_text(textwrap.dedent("""\
        # Unfinished HDAR task

        - [x] Create durable checkpoint.
        - [ ] Restore on Host B.
        - [ ] Continue the task after Host A runtime is gone.
        - [ ] Seal successor capsule with parent manifest hash.
        """))
    (workspace / "src" / "worker.py").write_text(textwrap.dedent("""\
        def next_action():
            return "restore_on_host_b"

        if __name__ == "__main__":
            print(next_action())
        """))


def build(args: argparse.Namespace) -> dict:
    run_root = Path(args.out).resolve() if args.out else Path(tempfile.mkdtemp(prefix="hdar-second-host-poc-"))
    run_root.mkdir(parents=True, exist_ok=True)

    host_a_workspace = run_root / "host_a_runtime_workspace"
    capsule_epoch_1 = run_root / "capsule_epoch_1"
    transport_tar = run_root / "transport_capsule_epoch_1.tar.gz"
    host_b_bundle = run_root / "run_on_host_b.py"
    local_host_b_out = run_root / "local_host_b_simulation"

    if host_a_workspace.exists() or capsule_epoch_1.exists() or host_b_bundle.exists():
        raise SystemExit(f"refusing to overwrite existing demo outputs in {run_root}")

    create_demo_workspace(host_a_workspace)
    pre_seal_workspace_hash = hash_workspace(host_a_workspace)["root_hash"]
    manifest = seal_workspace(
        host_a_workspace,
        capsule_epoch_1,
        epoch=1,
        parent_manifest_hash=None,
        source_host_label="host-a-local-mac",
        objective="Continue unfinished work after Host A runtime destruction.",
        continuation_point="Host A sealed epoch 1; Host B must restore and advance progress.log.",
    )
    capsule_verify = verify_capsule(capsule_epoch_1)
    if not capsule_verify["ok"]:
        raise SystemExit(f"host A capsule verification failed: {capsule_verify['problems']}")

    capsule_tar = make_capsule_tar(capsule_epoch_1, transport_tar)
    write_host_b_bundle(capsule_tar, host_b_bundle)

    shutil.rmtree(host_a_workspace)
    host_a_destroyed = not host_a_workspace.exists()

    report = {
        "schema": "hdar.second-host-demo-build/v0.1",
        "claim_boundary": "Generated Host B bundle is ready for a genuine independent host. Local simulation is not a seed-grade second-host proof.",
        "run_root": str(run_root),
        "host_a_platform": platform.platform(),
        "host_a_workspace_hash_before_destroy": pre_seal_workspace_hash,
        "host_a_runtime_destroyed": host_a_destroyed,
        "capsule_epoch_1": capsule_verify,
        "transport_bundle": {
            "path": str(host_b_bundle),
            "bytes": host_b_bundle.stat().st_size,
            "sha256": sha256_file(host_b_bundle),
        },
        "transport_capsule_tar": {
            "path": capsule_tar["path"],
            "bytes": capsule_tar["bytes"],
            "sha256": capsule_tar["sha256"],
        },
        "next_real_seed_step": f"Run python3 {host_b_bundle.name} --out /tmp/hdar-host-b-proof on an independent Host B and return host_b_report.json plus successor_capsule_epoch_2.tar.gz.",
    }

    if args.run_local_simulation:
        completed = subprocess.run(
            [sys.executable, str(host_b_bundle), "--out", str(local_host_b_out), "--host-label", "host-b-local-simulation-not-seed-proof"],
            check=True,
            text=True,
            capture_output=True,
        )
        report["local_simulation"] = json.loads(completed.stdout)

    (run_root / "host_a_build_report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="Output directory. Defaults to a temp directory.")
    ap.add_argument("--run-local-simulation", action="store_true", help="Run the generated Host B bundle locally as a smoke test.")
    args = ap.parse_args()
    report = build(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
