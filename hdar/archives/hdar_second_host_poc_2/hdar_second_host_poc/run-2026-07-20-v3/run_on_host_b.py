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
import socket
import sys
import tarfile
import tempfile
import time
from pathlib import Path

BUNDLE_B64 = "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"
BUNDLE_SHA256 = "74827c7eae8694c98d508fad94360d584477eefe7dccf6ff3cae5f4cfe7e9ce0"
# Expected SHA-256 of this runner script itself (for self-verification)
# Computed after generation; set by the build script.
RUNNER_SHA256 = "6ec3164360be68d89b2767d8ddae782b5368a5143c4f182ef9a433f4ed9599a1"
AGENT_ID = "hdar-seed-poc-agent"
SCHEMA = "hdar.transport-capsule/v0.1"
RECEIPT_SCHEMA = "hdar.receipt/v0.1"
CHUNK_SIZE = 1024 * 1024

# Audit issue #7: Deterministic task for continuation proof
# The workspace contains src/worker.py with a partial computation.
# Host B must complete it and the result must be independently verifiable.
TASK_INPUT_N = 100  # sum of primes up to N
TASK_EXPECTED_RESULT = 1060  # sum of primes below 100: 2+3+5+7+11+...+97 = 1060


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


def verify_receipt(capsule_dir: Path, manifest: dict) -> dict:
    """Audit fix #5: Verify the receipt is not decorative.
    Checks receipt_hash, schema, event, epoch, manifest reference, and host label."""
    receipt_path = capsule_dir / "receipt.json"
    if not receipt_path.exists():
        return {"ok": False, "problems": ["receipt.json missing"]}
    receipt = json.loads(receipt_path.read_text())
    problems = []
    # 1. Verify receipt_hash
    expected_hash = sha256_bytes(canonical_json({k: v for k, v in receipt.items() if k != "receipt_hash"}))
    if expected_hash != receipt.get("receipt_hash"):
        problems.append("receipt hash mismatch")
    # 2. Verify schema
    if receipt.get("schema") != RECEIPT_SCHEMA:
        problems.append(f"receipt schema mismatch: expected {RECEIPT_SCHEMA}, got {receipt.get('schema')}")
    # 3. Verify epoch matches manifest
    if receipt.get("epoch") != manifest.get("epoch"):
        problems.append(f"receipt epoch mismatch: expected {manifest.get('epoch')}, got {receipt.get('epoch')}")
    # 4. Verify manifest_hash references the correct manifest
    if receipt.get("manifest_hash") != manifest.get("manifest_hash"):
        problems.append("receipt manifest_hash does not match capsule manifest_hash")
    # 5. Verify workspace_root_hash matches
    if receipt.get("workspace_root_hash") != manifest.get("workspace_manifest", {}).get("root_hash"):
        problems.append("receipt workspace_root_hash does not match manifest")
    # 6. Verify event is a known event type
    valid_events = {"capsule_sealed", "capsule_sealed_after_host_b_continuation"}
    if receipt.get("event") not in valid_events:
        problems.append(f"receipt event unknown: {receipt.get('event')}")
    # 7. Verify source_host_label is present and non-empty
    if not receipt.get("source_host_label"):
        problems.append("receipt source_host_label missing")
    return {
        "ok": not problems,
        "problems": problems,
        "receipt_hash": receipt.get("receipt_hash", ""),
        "event": receipt.get("event", ""),
        "epoch": receipt.get("epoch"),
        "manifest_hash_match": receipt.get("manifest_hash") == manifest.get("manifest_hash"),
    }


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
    # Audit fix #5: Verify receipt is not decorative
    receipt_verify = verify_receipt(capsule_dir, manifest)
    if not receipt_verify["ok"]:
        problems.extend([f"receipt: {p}" for p in receipt_verify["problems"]])
    return {
        "ok": not problems,
        "problems": problems,
        "agent_id": manifest["agent_id"],
        "epoch": manifest["epoch"],
        "manifest_hash": manifest["manifest_hash"],
        "workspace_root_hash": manifest["workspace_manifest"]["root_hash"],
        "file_count": len(manifest["workspace_manifest"]["files"]),
        "total_size": manifest["workspace_manifest"]["total_size"],
        "receipt_verified": receipt_verify,
    }


def _validate_safe_path(rel_path: str, dest: Path) -> Path:
    """Audit fix #4: Validate that rel_path resolves under dest.
    Rejects absolute paths, ../ traversal, symlinks, and duplicate paths."""
    if not rel_path:
        raise ValueError("empty rel_path in manifest")
    if os.path.isabs(rel_path):
        raise ValueError(f"absolute path in manifest: {rel_path}")
    if ".." in Path(rel_path).parts:
        raise ValueError(f"path traversal in manifest: {rel_path}")
    resolved = (dest / rel_path).resolve()
    dest_resolved = dest.resolve()
    if not str(resolved).startswith(str(dest_resolved) + os.sep) and resolved != dest_resolved:
        raise ValueError(f"resolved path escapes workspace root: {rel_path} -> {resolved}")
    return resolved


def restore_workspace(capsule_dir: Path, dest: Path) -> dict:
    verification = verify_capsule(capsule_dir)
    if not verification["ok"]:
        raise RuntimeError(f"capsule verification failed: {verification['problems']}")
    manifest = json.loads((capsule_dir / "manifest.json").read_text())
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    seen_paths = set()
    for entry in manifest["workspace_manifest"]["files"]:
        rel_path = entry["rel_path"]
        # Audit fix #4: constrain all paths under workspace root
        out = _validate_safe_path(rel_path, dest)
        if str(out) in seen_paths:
            raise ValueError(f"duplicate path in manifest: {rel_path}")
        seen_paths.add(str(out))
        blob = capsule_dir / "blocks" / entry["sha256"][:2] / entry["sha256"]
        out.parent.mkdir(parents=True, exist_ok=True)
        # Audit fix #4: no symlinks
        if out.is_symlink():
            raise ValueError(f"symlink already exists at target: {out}")
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
    """Audit fix #3: Manual member validation — no unrestricted fallback.
    Validates every member before extraction. Rejects absolute paths,
    traversal, symlinks, hardlinks, and special files."""
    dest_resolved = dest.resolve()
    for member in tf.getmembers():
        # Reject absolute paths
        if member.name.startswith("/"):
            raise ValueError(f"tar member has absolute path: {member.name}")
        # Reject traversal
        if ".." in Path(member.name).parts:
            raise ValueError(f"tar member has path traversal: {member.name}")
        # Reject symlinks and hardlinks
        if member.issym() or member.islnk():
            raise ValueError(f"tar member is symlink/hardlink: {member.name}")
        # Reject special files (devices, fifos)
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"tar member is not regular file or dir: {member.name} (type={member.type})")
        # Verify resolved path stays under dest
        member_path = (dest / member.name).resolve()
        if not str(member_path).startswith(str(dest_resolved) + os.sep) and member_path != dest_resolved:
            raise ValueError(f"tar member escapes destination: {member.name} -> {member_path}")
    # All members validated — safe to extract
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


def complete_deterministic_task(workspace: Path) -> dict:
    """Audit fix #7: Complete a deterministic unfinished task.
    The workspace contains src/worker.py with a sum_of_primes function.
    Host B executes it and writes the result. The result is independently
    verifiable: sum of primes below TASK_INPUT_N must equal TASK_EXPECTED_RESULT."""
    worker_path = workspace / "src" / "worker.py"
    if not worker_path.exists():
        return {"ok": False, "reason": "src/worker.py not found in restored workspace"}
    # Execute the worker to complete the task
    import subprocess
    result = subprocess.run(
        [sys.executable, str(worker_path), str(TASK_INPUT_N)],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return {"ok": False, "reason": f"worker.py exited {result.returncode}: {result.stderr}"}
    computed = int(result.stdout.strip())
    # Write the result to the workspace
    result_path = workspace / "task_result.json"
    task_result = {
        "task": "sum_of_primes_below_N",
        "input_n": TASK_INPUT_N,
        "computed_result": computed,
        "expected_result": TASK_EXPECTED_RESULT,
        "passed": computed == TASK_EXPECTED_RESULT,
        "computed_on": platform.platform(),
        "timestamp": time.time(),
    }
    result_path.write_text(json.dumps(task_result, indent=2, sort_keys=True) + "\n")
    return {
        "ok": computed == TASK_EXPECTED_RESULT,
        "task": "sum_of_primes_below_N",
        "input_n": TASK_INPUT_N,
        "computed_result": computed,
        "expected_result": TASK_EXPECTED_RESULT,
        "passed": computed == TASK_EXPECTED_RESULT,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="Output directory. Defaults to a temp directory.")
    ap.add_argument("--host-label", default="")
    ap.add_argument("--host-a-report", default="", help="Audit fix #2: Path to Host A build report JSON for independent capsule verification.")
    ap.add_argument("--verify-runner-hash", default="", help="Audit fix #1: Expected SHA-256 of this runner script.")
    args = ap.parse_args()

    # Audit fix #6: Capture machine-generated identity and timestamps
    runner_start = time.time()
    machine_hostname = socket.gethostname()
    host_label = args.host_label or f"{machine_hostname}-host-b"
    console_log = []  # capture all output for the report

    # Audit fix #1: Runner self-authentication
    if args.verify_runner_hash:
        runner_path = Path(__file__).resolve()
        runner_hash = sha256_file(runner_path)
        if runner_hash != args.verify_runner_hash:
            msg = f"RUNNER HASH MISMATCH: {runner_hash} != {args.verify_runner_hash}"
            console_log.append(msg)
            raise SystemExit(msg)
        console_log.append(f"Runner SHA-256 verified: {runner_hash}")
    else:
        console_log.append("WARNING: --verify-runner-hash not provided; runner authenticity not verified")

    out_dir = Path(args.out).resolve() if args.out else Path(tempfile.mkdtemp(prefix="hdar-host-b-proof-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_bytes = base64.b64decode(BUNDLE_B64.encode())
    bundle_hash = sha256_bytes(bundle_bytes)
    if bundle_hash != BUNDLE_SHA256:
        raise SystemExit(f"transport bundle hash mismatch: {bundle_hash} != {BUNDLE_SHA256}")
    console_log.append(f"Transport bundle SHA-256 verified: {bundle_hash}")

    bundle_tar = out_dir / "transport_capsule_epoch_1.tar.gz"
    bundle_tar.write_bytes(bundle_bytes)
    with tarfile.open(bundle_tar, "r:gz") as tf:
        safe_extract_tar(tf, out_dir)
    console_log.append("Transport capsule extracted (safe member validation)")

    capsule_epoch_1 = out_dir / "capsule"
    before_verify = verify_capsule(capsule_epoch_1)
    console_log.append(f"Input capsule verified: ok={before_verify['ok']}, epoch={before_verify['epoch']}")
    if not before_verify["ok"]:
        raise SystemExit(f"input capsule verification failed: {before_verify['problems']}")

    # Audit fix #2: Verify against external Host A report if provided
    host_a_report_verify = None
    if args.host_a_report:
        host_a_report = json.loads(Path(args.host_a_report).read_text())
        host_a_capsule = host_a_report.get("capsule_epoch_1", {})
        host_a_report_verify = {
            "provided": True,
            "manifest_hash_match": host_a_capsule.get("manifest_hash") == before_verify["manifest_hash"],
            "workspace_root_hash_match": host_a_capsule.get("workspace_root_hash") == before_verify["workspace_root_hash"],
            "epoch_match": host_a_capsule.get("epoch") == before_verify["epoch"],
            "host_a_platform": host_a_report.get("host_a_platform", ""),
            "host_b_platform": platform.platform(),
            "platforms_differ": host_a_report.get("host_a_platform", "") != platform.platform(),
        }
        if not host_a_report_verify["manifest_hash_match"]:
            raise SystemExit("Host A report manifest_hash does not match input capsule")
        console_log.append(f"Host A report verified: manifest_hash_match={host_a_report_verify['manifest_hash_match']}, platforms_differ={host_a_report_verify['platforms_differ']}")
    else:
        host_a_report_verify = {"provided": False}
        console_log.append("WARNING: --host-a-report not provided; capsule not independently authenticated against Host A")

    restored_workspace = out_dir / "restored_workspace"
    restore_report = restore_workspace(capsule_epoch_1, restored_workspace)
    if not restore_report["exact"]:
        raise SystemExit("workspace restoration was not exact")
    console_log.append(f"Workspace restored: exact=True, files={restore_report['file_count']}")

    # Audit fix #7: Complete the deterministic task
    task_result = complete_deterministic_task(restored_workspace)
    console_log.append(f"Task continuation: ok={task_result['ok']}, result={task_result.get('computed_result', 'N/A')}")
    if not task_result["ok"]:
        raise SystemExit(f"deterministic task continuation failed: {task_result.get('reason', 'unknown')}")

    progress = restored_workspace / "progress.log"
    state_path = restored_workspace / "agent_state.json"
    state = json.loads(state_path.read_text())
    event = {
        "event": "continued_on_host_b",
        "host_label": host_label,
        "machine_hostname": machine_hostname,
        "host_platform": platform.platform(),
        "epoch_from": before_verify["epoch"],
        "epoch_to": before_verify["epoch"] + 1,
        "timestamp": time.time(),
        "task_result": task_result,
    }
    progress.write_text(progress.read_text() + json.dumps(event, sort_keys=True) + "\n")
    state["status"] = "continued_on_host_b"
    state["host_b_label"] = host_label
    state["machine_hostname"] = machine_hostname
    state["last_event"] = event
    state["task_completed"] = task_result
    state["next_action"] = "return successor capsule to Host A or another provider and verify lineage."
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    capsule_epoch_2 = out_dir / "capsule_epoch_2"
    successor_manifest = seal_workspace(
        restored_workspace,
        capsule_epoch_2,
        epoch=before_verify["epoch"] + 1,
        parent_manifest_hash=before_verify["manifest_hash"],
        source_host_label=host_label,
    )
    successor_verify = verify_capsule(capsule_epoch_2)
    successor_tar = out_dir / "successor_capsule_epoch_2.tar.gz"
    with tarfile.open(successor_tar, "w:gz") as tf:
        tf.add(capsule_epoch_2, arcname="capsule_epoch_2")

    runner_end = time.time()

    # Audit fix #6: Comprehensive host identity and provenance
    report = {
        "schema": "hdar.second-host-proof-report/v0.2",
        "claim_boundary": "Hash-only portable Host B proof with receipt verification, path safety, deterministic task, and runner authentication. Real seed proof still requires production Ed25519 verification and a genuinely independent host run.",
        # Audit fix #6: machine-generated identity (not just self-reported)
        "host_b_identity": {
            "machine_hostname": machine_hostname,
            "host_label": host_label,
            "platform": platform.platform(),
            "python_version": sys.version,
            "runner_start_timestamp": runner_start,
            "runner_end_timestamp": runner_end,
            "runner_duration_seconds": round(runner_end - runner_start, 3),
        },
        "host_b_platform": platform.platform(),
        "host_b_label": host_label,
        "transport_bundle_sha256": bundle_hash,
        "runner_sha256_verified": args.verify_runner_hash is not None and args.verify_runner_hash != "",
        "input_capsule": before_verify,
        "host_a_report_verification": host_a_report_verify,
        "restore": restore_report,
        "continuation_event": event,
        "task_continuation": task_result,
        "successor_capsule": successor_verify,
        "lineage_advanced": successor_manifest["parent_manifest_hash"] == before_verify["manifest_hash"] and successor_manifest["epoch"] == before_verify["epoch"] + 1,
        "successor_tar": {
            "path": str(successor_tar),
            "bytes": successor_tar.stat().st_size,
            "sha256": sha256_file(successor_tar),
        },
        "console_transcript": console_log,
        "output_dir": str(out_dir),
        # Audit fix #5: receipt verification status
        "receipt_verification": {
            "input_capsule_receipt": before_verify.get("receipt_verified", {}),
            "successor_capsule_receipt": successor_verify.get("receipt_verified", {}),
        },
    }
    (out_dir / "host_b_report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
