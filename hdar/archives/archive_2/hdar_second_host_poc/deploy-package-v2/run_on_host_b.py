#!/usr/bin/env python3
"""Generated HDAR Host B restore/continue/reseal bundle."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BUNDLE_B64 = "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"
BUNDLE_SHA256 = "79047d79882e88d46e91e8294e93755651b81b41e8b75b6f47c3adbf64b484c6"
# Expected SHA-256 of this runner script itself (for self-verification)
# Computed after generation; set by the build script.
RUNNER_SHA256 = ""
AGENT_ID = "hdar-seed-poc-agent"
SCHEMA = "hdar.transport-capsule/v0.1"
RECEIPT_SCHEMA = "hdar.receipt/v0.1"
CHUNK_SIZE = 1024 * 1024

# Audit issue #7: Deterministic task for continuation proof
# The workspace contains src/worker.py with a partial computation.
# Host B must complete it and the result must be independently verifiable.
TASK_NAME = "multi_stage_analysis_pipeline"
TASK_INPUT = "data/input_records.jsonl"
TASK_EXPECTED_OUTPUT_HASH = "e1efd2a02130d65da232aa2338b75b0278d168a77fd8fb4f10dc6023cc6ff46f"  # filled by build script
TASK_STAGES = ["parse", "filter", "aggregate", "classify", "report"]


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
    expected_hash = sha256_bytes(canonical_json({k: v for k, v in receipt.items() if k not in ("receipt_hash", "host_signature", "host_public_key", "host_signature_algorithm")}))
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


def verify_owner_signature(manifest: dict, expected_public_key_hex: str = "") -> dict:
    """Step 4 of tightened seed criterion: verify the owner's Ed25519 signature on the capsule manifest."""
    pub_hex = expected_public_key_hex or manifest.get("owner_public_key")
    sig_hex = manifest.get("owner_signature")
    if not pub_hex:
        return {"ok": False, "reason": "no owner_public_key in manifest and none provided via --owner-public-key"}
    if not sig_hex:
        return {"ok": False, "reason": "no owner_signature in manifest — capsule is not owner-signed"}
    if manifest.get("owner_signature_algorithm") != "ed25519":
        return {"ok": False, "reason": f"unsupported owner signature algorithm: {manifest.get('owner_signature_algorithm')}"}
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        signing_content = {k: v for k, v in manifest.items() if k not in ("owner_signature", "owner_public_key", "manifest_hash")}
        public_key.verify(bytes.fromhex(sig_hex), canonical_json(signing_content))
        return {
            "ok": True,
            "reason": "owner Ed25519 signature verified",
            "owner_public_key": pub_hex,
            "algorithm": "ed25519",
        }
    except InvalidSignature:
        return {"ok": False, "reason": "owner signature INVALID — manifest content does not match signature", "owner_public_key": pub_hex}
    except ImportError:
        return {"ok": False, "reason": "cryptography package not available — cannot verify Ed25519 owner signature"}
    except Exception as e:
        return {"ok": False, "reason": f"owner signature verification error: {e}"}


def verify_capsule(capsule_dir: Path, expected_owner_public_key: str = "") -> dict:
    manifest = json.loads((capsule_dir / "manifest.json").read_text())
    expected_manifest_hash = sha256_bytes(canonical_json({k: v for k, v in manifest.items() if k not in ("manifest_hash", "owner_signature", "owner_public_key", "owner_signature_algorithm", "host_signature", "host_public_key", "host_signature_algorithm")}))
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
    # Step 4: Verify owner Ed25519 signature (only if expected or present)
    has_owner_sig = "owner_signature" in manifest or "owner_public_key" in manifest
    if expected_owner_public_key or has_owner_sig:
        owner_sig_verify = verify_owner_signature(manifest, expected_owner_public_key)
        if not owner_sig_verify["ok"]:
            problems.append(f"owner_signature: {owner_sig_verify['reason']}")
    else:
        owner_sig_verify = {"ok": True, "reason": "owner signature not present (successor capsule sealed by Host B)"}
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
        "owner_signature_verified": owner_sig_verify,
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
    # Use filter='data' when available (Python 3.12+) as defense-in-depth
    if sys.version_info >= (3, 12):
        tf.extractall(dest, filter="data")
    else:
        tf.extractall(dest)


def seal_workspace(workspace: Path, capsule_dir: Path, *, epoch: int, parent_manifest_hash: str, source_host_label: str, host_keypair: dict = None) -> dict:
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
        "verification_mode": "sha256-content-addressed-hash-plus-ed25519" if host_keypair else "sha256-content-addressed-hash-only",
        "signature_mode": "ed25519-host-signed" if host_keypair else "omitted-in-portable-demo-use-production-ed25519-path-for-seed",
        "workspace_manifest": workspace_manifest,
    }
    manifest["manifest_hash"] = sha256_bytes(canonical_json({k: v for k, v in manifest.items() if k not in ("manifest_hash", "host_signature", "host_public_key", "host_signature_algorithm")}))
    if host_keypair:
        signing_content = canonical_json({k: v for k, v in manifest.items() if k not in ("host_signature", "host_public_key", "host_signature_algorithm", "manifest_hash")})
        manifest["host_signature"] = sign_data(host_keypair, signing_content)
        manifest["host_public_key"] = host_keypair["public_key_hex"]
        manifest["host_signature_algorithm"] = host_keypair["algorithm"]
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
    receipt["receipt_hash"] = sha256_bytes(canonical_json({k: v for k, v in receipt.items() if k not in ("receipt_hash", "host_signature", "host_public_key", "host_signature_algorithm")}))
    if host_keypair:
        receipt_signing_content = canonical_json({k: v for k, v in receipt.items() if k not in ("host_signature", "host_public_key", "host_signature_algorithm", "receipt_hash")})
        receipt["host_signature"] = sign_data(host_keypair, receipt_signing_content)
        receipt["host_public_key"] = host_keypair["public_key_hex"]
        receipt["host_signature_algorithm"] = host_keypair["algorithm"]
    (capsule_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
    return manifest


def complete_deterministic_task(workspace: Path) -> dict:
    """Complete a multi-stage analysis pipeline.
    The workspace contains src/worker.py with a real data processing pipeline.
    Host B executes it, producing intermediate artifacts and a final report.
    The final output hash is independently verifiable."""
    worker_path = workspace / "src" / "worker.py"
    if not worker_path.exists():
        return {"ok": False, "reason": "src/worker.py not found in restored workspace"}
    # Execute the worker pipeline
    result = subprocess.run(
        [sys.executable, str(worker_path), str(workspace)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        return {"ok": False, "reason": f"worker.py exited {result.returncode}: {result.stderr}"}
    # Check for final output
    output_path = workspace / "output" / "final_report.json"
    if not output_path.exists():
        return {"ok": False, "reason": "worker.py did not produce output/final_report.json"}
    output_data = json.loads(output_path.read_text())
    computed_hash = sha256_bytes(canonical_json(output_data))
    # Check intermediate artifacts
    intermediates = []
    for stage in TASK_STAGES:
        stage_file = workspace / "output" / f"stage_{stage}.json"
        if stage_file.exists():
            intermediates.append({"stage": stage, "path": str(stage_file.relative_to(workspace)), "sha256": sha256_file(stage_file)})
        else:
            return {"ok": False, "reason": f"missing intermediate artifact: stage_{stage}.json"}
    # Write the result to the workspace
    result_path = workspace / "task_result.json"
    task_result = {
        "task": TASK_NAME,
        "stages_completed": len(intermediates),
        "stages_expected": len(TASK_STAGES),
        "computed_output_hash": computed_hash,
        "expected_output_hash": TASK_EXPECTED_OUTPUT_HASH,
        "passed": computed_hash == TASK_EXPECTED_OUTPUT_HASH,
        "intermediate_artifacts": intermediates,
        "computed_on": platform.platform(),
        "timestamp": time.time(),
        "worker_stdout": result.stdout.strip()[:500],
    }
    result_path.write_text(json.dumps(task_result, indent=2, sort_keys=True) + "\n")
    return {
        "ok": computed_hash == TASK_EXPECTED_OUTPUT_HASH,
        "task": TASK_NAME,
        "stages_completed": len(intermediates),
        "computed_output_hash": computed_hash,
        "expected_output_hash": TASK_EXPECTED_OUTPUT_HASH,
        "passed": computed_hash == TASK_EXPECTED_OUTPUT_HASH,
    }


def generate_host_b_keypair() -> dict:
    """Generate a Host B keypair for report signing.
    Uses Ed25519 from the cryptography package if available.
    Falls back to HMAC-SHA256 with a random key (clearly marked as non-production)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return {
            "algorithm": "ed25519",
            "private_key_hex": priv_bytes.hex(),
            "public_key_hex": pub_bytes.hex(),
            "production_grade": True,
        }
    except ImportError:
        seed = secrets.token_bytes(32)
        return {
            "algorithm": "hmac-sha256-placeholder",
            "private_key_hex": seed.hex(),
            "public_key_hex": hashlib.sha256(seed).hexdigest(),
            "production_grade": False,
            "warning": "cryptography package not available; using HMAC-SHA256 placeholder. Install with: pip install cryptography",
        }


def sign_data(keypair: dict, data: bytes) -> str:
    """Sign data with the Host B keypair."""
    if keypair["algorithm"] == "ed25519":
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(keypair["private_key_hex"]))
        signature = private_key.sign(data)
        return signature.hex()
    else:
        import hmac
        key = bytes.fromhex(keypair["private_key_hex"])
        return hmac.new(key, data, hashlib.sha256).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="Output directory. Defaults to a temp directory.")
    ap.add_argument("--host-label", default="")
    ap.add_argument("--host-a-report", default="", help="Audit fix #2: Path to Host A build report JSON for independent capsule verification.")
    ap.add_argument("--verify-runner-hash", default="", help="Audit fix #1: Expected SHA-256 of this runner script.")
    ap.add_argument("--network-source", default="", help="URL from which the runner was downloaded.")
    ap.add_argument("--operator-identity", default="", help="Operator identity or pseudonym for the independent Host B run.")
    ap.add_argument("--download-headers", default="", help="Path to JSON file with download response headers.")
    ap.add_argument("--owner-public-key", default="", help="Expected owner Ed25519 public key hex for capsule signature verification (step 4 of seed criterion).")
    args = ap.parse_args()

    # Evidence packet: nonce, keypair, UTC timestamps, exit codes
    runner_start = time.time()
    runner_start_utc = utc_now_iso()
    machine_hostname = socket.gethostname()
    host_label = args.host_label or f"{machine_hostname}-host-b"
    console_log = []  # capture all output for the report
    exit_codes = []
    machine_nonce = secrets.token_hex(16)
    host_b_keypair = generate_host_b_keypair()
    console_log.append(f"Host B keypair: algorithm={host_b_keypair['algorithm']}, production_grade={host_b_keypair['production_grade']}")
    if not host_b_keypair["production_grade"]:
        console_log.append(f"WARNING: {host_b_keypair.get('warning', 'non-production signing')}")

    # Download metadata
    download_headers = {}
    if args.download_headers:
        download_headers = json.loads(Path(args.download_headers).read_text())
        console_log.append(f"Download headers loaded: {len(download_headers)} fields")

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
    # Internal consistency check (bundle matches embedded hash)
    if bundle_hash != BUNDLE_SHA256:
        raise SystemExit(f"transport bundle internal hash mismatch: {bundle_hash} != {BUNDLE_SHA256}")
    # External verification: cross-check against Host A build report if provided
    external_bundle_hash = ""
    external_bundle_match = False
    if args.host_a_report:
        try:
            host_a_report_pre = json.loads(Path(args.host_a_report).read_text())
            external_bundle_hash = host_a_report_pre.get("transport_capsule_tar", {}).get("sha256", "")
            if external_bundle_hash:
                external_bundle_match = (external_bundle_hash == bundle_hash)
                if not external_bundle_match:
                    raise SystemExit(
                        f"SECURITY: bundle hash does not match Host A report! "
                        f"bundle={bundle_hash} host_a_report={external_bundle_hash} "
                        f"Do not trust this bundle."
                    )
                console_log.append(f"Transport bundle SHA-256 verified against external Host A report: {bundle_hash}")
            else:
                console_log.append("WARNING: Host A report provided but has no transport_capsule_tar.sha256 field")
        except json.JSONDecodeError:
            raise SystemExit(f"Host A report is not valid JSON: {args.host_a_report}")
    else:
        console_log.append(f"Transport bundle SHA-256 verified (internal only): {bundle_hash}")
        console_log.append("WARNING: no --host-a-report provided; bundle hash not cross-verified against external source")

    bundle_tar = out_dir / "transport_capsule_epoch_1.tar.gz"
    bundle_tar.write_bytes(bundle_bytes)
    with tarfile.open(bundle_tar, "r:gz") as tf:
        safe_extract_tar(tf, out_dir)
    console_log.append("Transport capsule extracted (safe member validation)")

    capsule_epoch_1 = out_dir / "capsule_epoch_1"
    if not capsule_epoch_1.exists():
        # Fallback: look for any directory containing manifest.json
        for d in out_dir.iterdir():
            if d.is_dir() and (d / "manifest.json").exists():
                capsule_epoch_1 = d
                break
    before_verify = verify_capsule(capsule_epoch_1, args.owner_public_key)
    console_log.append(f"Input capsule verified: ok={before_verify['ok']}, epoch={before_verify['epoch']}")
    if not before_verify["ok"]:
        raise SystemExit(f"input capsule verification failed: {before_verify['problems']}")
    owner_sig = before_verify.get("owner_signature_verified", {})
    console_log.append(f"Owner signature: ok={owner_sig.get('ok', False)}, reason={owner_sig.get('reason', 'N/A')}")

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
            "external_bundle_hash": external_bundle_hash,
            "external_bundle_hash_match": external_bundle_match,
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
        host_keypair=host_b_keypair,
    )
    successor_verify = verify_capsule(capsule_epoch_2)
    successor_tar = out_dir / "successor_capsule_epoch_2.tar.gz"
    with tarfile.open(successor_tar, "w:gz") as tf:
        tf.add(capsule_epoch_2, arcname="capsule_epoch_2")

    runner_end = time.time()
    runner_end_utc = utc_now_iso()
    exit_codes.append({"step": "complete", "exit_code": 0})

    report = {
        "schema": "hdar.second-host-proof-report/v0.3",
        "claim_boundary": ("Ed25519-signed portable Host B proof with owner signature verification, receipt verification, path safety, "
                         "deterministic task execution, runner authentication, Host B keypair signing, and evidence packet. "
                         "Seed-grade proof requires a genuinely independent host run with platforms_differ=true and external verifier."),
        "host_b_identity": {
            "machine_hostname": machine_hostname,
            "host_label": host_label,
            "platform": platform.platform(),
            "python_version": sys.version,
            "runner_start_timestamp": runner_start,
            "runner_end_timestamp": runner_end,
            "runner_start_utc": runner_start_utc,
            "runner_end_utc": runner_end_utc,
            "runner_duration_seconds": round(runner_end - runner_start, 3),
            "machine_nonce": machine_nonce,
        },
        "host_b_platform": platform.platform(),
        "host_b_label": host_label,
        "transport_bundle_sha256": bundle_hash,
        "runner_sha256_verified": args.verify_runner_hash is not None and args.verify_runner_hash != "",
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "network_source": args.network_source,
        "operator_identity": args.operator_identity,
        "download_headers": download_headers,
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
        "exit_codes": exit_codes,
        "output_dir": str(out_dir),
        "receipt_verification": {
            "input_capsule_receipt": before_verify.get("receipt_verified", {}),
            "successor_capsule_receipt": successor_verify.get("receipt_verified", {}),
        },
        "host_b_keypair": {
            "algorithm": host_b_keypair["algorithm"],
            "public_key_hex": host_b_keypair["public_key_hex"],
            "production_grade": host_b_keypair["production_grade"],
        },
    }
    # Sign the complete report: construct full unsigned report, then add signature
    report["host_b_public_key"] = host_b_keypair["public_key_hex"]
    report["host_b_signature_algorithm"] = host_b_keypair["algorithm"]
    report_for_signing = {k: v for k, v in report.items() if k != "host_b_signature"}
    report["host_b_signature"] = sign_data(host_b_keypair, canonical_json(report_for_signing))
    (out_dir / "host_b_report.json").write_text(json.dumps(report, indent=2, sort_keys=True))

    evidence_packet = {
        "proof_version": "hdar-host-b-v1",
        "host_label": host_label,
        "host_fingerprint": {
            "machine_hostname": machine_hostname,
            "platform": platform.platform(),
            "python_version": sys.version,
            "machine_nonce": machine_nonce,
        },
        "operator_identity_or_pseudonym": args.operator_identity,
        "started_at": runner_start_utc,
        "completed_at": runner_end_utc,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "runner_sha256_verified": args.verify_runner_hash is not None and args.verify_runner_hash != "",
        "source_capsule_sha256": bundle_hash,
        "restored_tree_hash": restore_report["restored_root_hash"],
        "expected_tree_hash": restore_report["expected_root_hash"],
        "restore_exact": restore_report["exact"],
        "source_epoch": before_verify["epoch"],
        "successor_epoch": successor_manifest["epoch"],
        "lineage_advanced": successor_manifest["parent_manifest_hash"] == before_verify["manifest_hash"] and successor_manifest["epoch"] == before_verify["epoch"] + 1,
        "successor_capsule_sha256": sha256_file(successor_tar),
        "host_b_report_sha256": sha256_bytes(canonical_json(report)),
        "network_source": args.network_source,
        "host_a_filesystem_accessible": {"value": False, "evidence_type": "operator_declared", "note": "Not technically measured by runner; asserted by operator."},
        "host_a_agent_runtime_accessible": {"value": False, "evidence_type": "operator_declared", "note": "Not technically measured by runner; asserted by operator."},
        "verification_commands": [
            f"shasum -a 256 -c <<< '{sha256_file(Path(__file__).resolve())}  run_on_host_b.py'",
            "python3 -c \"import json; r=json.load(open('host_b_report.json')); assert r['restore']['exact']; assert r['lineage_advanced']; assert r['successor_capsule']['ok']\"",
        ],
        "exit_codes": exit_codes,
        "console_transcript": console_log,
        "host_b_public_key": host_b_keypair["public_key_hex"],
        "signature_algorithm": host_b_keypair["algorithm"],
        "task_continuation_passed": task_result["ok"],
        "task_result": task_result,
    }
    # Sign the evidence packet with its own canonical body — not a reused report signature
    evidence_packet_for_signing = {k: v for k, v in evidence_packet.items() if k != "evidence_packet_signature"}
    evidence_packet["evidence_packet_sha256"] = sha256_bytes(canonical_json({k: v for k, v in evidence_packet_for_signing.items() if k != "evidence_packet_sha256"}))
    evidence_packet["evidence_packet_signature"] = sign_data(host_b_keypair, canonical_json({k: v for k, v in evidence_packet.items() if k not in ("evidence_packet_signature",)}))
    (out_dir / "host_b_evidence_packet.json").write_text(json.dumps(evidence_packet, indent=2, sort_keys=True))

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
