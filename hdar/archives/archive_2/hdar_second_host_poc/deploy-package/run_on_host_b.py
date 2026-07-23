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
BUNDLE_SHA256 = "830c3bc65b4ec24362209b937fbc6871014712a494f7cdd9b1058102380310d3"
# Expected SHA-256 of this runner script itself (for self-verification)
# Computed after generation; set by the build script.
RUNNER_SHA256 = ""
AGENT_ID = "hdar-seed-poc-agent"
SCHEMA = "hdar.transport-capsule/v0.1"
RECEIPT_SCHEMA = "hdar.receipt/v0.1"
CHUNK_SIZE = 1024 * 1024

# Deterministic task for continuation proof
# The workspace contains src/worker.py with a multi-stage analysis pipeline.
# Host B executes it with the workspace path as argument.
# The output hash must match TASK_EXPECTED_OUTPUT_HASH (set by build script).
TASK_EXPECTED_OUTPUT_HASH = "8708384aa5f7118c1f1b356e9abfda416c1b3c1c33943498c6016fb29b9d396a"  # filled by build_deploy_package.py


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
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
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
    """Complete the deterministic unfinished task.
    The workspace contains src/worker.py — a multi-stage analysis pipeline.
    Host B executes it with the workspace path as argument.
    The output hash must match TASK_EXPECTED_OUTPUT_HASH."""
    worker_path = workspace / "src" / "worker.py"
    if not worker_path.exists():
        return {"ok": False, "reason": "src/worker.py not found in restored workspace"}
    result = subprocess.run(
        [sys.executable, str(worker_path), str(workspace)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        return {"ok": False, "reason": f"worker.py exited {result.returncode}: {result.stderr}"}
    output_path = workspace / "output" / "final_report.json"
    if not output_path.exists():
        return {"ok": False, "reason": "worker.py did not produce output/final_report.json"}
    output = json.loads(output_path.read_text())
    computed_hash = sha256_bytes(json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())
    passed = bool(TASK_EXPECTED_OUTPUT_HASH) and computed_hash == TASK_EXPECTED_OUTPUT_HASH
    result_path = workspace / "task_result.json"
    
    # Build stage chain from intermediate artifacts
    stage_chain = {"stages": []}
    stage_names = ["parse", "filter", "aggregate", "classify", "report"]
    for sname in stage_names:
        sfile = workspace / "output" / f"stage_{sname}.json"
        if sfile.exists():
            sdata = json.loads(sfile.read_text())
            stage_chain["stages"].append({
                "stage": sname,
                "hash": sdata.get("stage_hash", ""),
                "parent_hash": sdata.get("parent_hash"),
            })
    stage_chain["valid"] = len(stage_chain["stages"]) == 5
    
    task_result = {
        "task": "multi_stage_analysis_pipeline",
        "stages_completed": output.get("metadata", {}).get("stages_completed", 0),
        "computed_output_hash": computed_hash,
        "expected_output_hash": TASK_EXPECTED_OUTPUT_HASH,
        "passed": passed,
        "computed_on": platform.platform(),
        "timestamp": time.time(),
        "stage_chain": stage_chain,
    }
    result_path.write_text(json.dumps(task_result, indent=2, sort_keys=True) + "\n")
    return {
        "ok": passed,
        "task": "multi_stage_analysis_pipeline",
        "stages_completed": output.get("metadata", {}).get("stages_completed", 0),
        "computed_output_hash": computed_hash,
        "expected_output_hash": TASK_EXPECTED_OUTPUT_HASH,
        "passed": passed,
        "stage_chain": stage_chain,
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
    ap.add_argument("--bundle", default="", help="Path to external transport capsule tar.gz. If not provided, uses embedded bundle.")
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
    if args.bundle:
        bundle_path = Path(args.bundle).resolve()
        if not bundle_path.exists():
            raise SystemExit(f"bundle file not found: {bundle_path}")
        bundle_bytes = bundle_path.read_bytes()
        bundle_hash = sha256_bytes(bundle_bytes)
        console_log.append(f"Loaded external bundle: {bundle_path} (sha256={bundle_hash})")
    else:
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

    # Auto-detect capsule directory name (handles both 'capsule' and 'capsule_epoch_1')
    capsule_epoch_1 = None
    for candidate in ("capsule", "capsule_epoch_1"):
        candidate_dir = out_dir / candidate
        if (candidate_dir / "manifest.json").exists():
            capsule_epoch_1 = candidate_dir
            break
    if capsule_epoch_1 is None:
        # Fallback: search for any directory containing manifest.json
        for d in out_dir.iterdir():
            if d.is_dir() and (d / "manifest.json").exists():
                capsule_epoch_1 = d
                break
    if capsule_epoch_1 is None:
        raise SystemExit(f"could not find capsule directory with manifest.json in {out_dir}")
    console_log.append(f"Capsule directory detected: {capsule_epoch_1.name}")
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
                         "Seed-grade proof requires a cross-platform continuation run with platforms_differ=true and external verifier."),
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
        "lifecycle_events": [
            {"event": "host_b_provisioned", "timestamp": runner_start_utc, "detail": f"Runner started on {platform.platform()}"},
            {"event": "capsule_restored", "timestamp": runner_start_utc, "detail": f"E1 capsule restored, exact={restore_report['exact']}"},
            {"event": "task_executed", "timestamp": runner_end_utc, "detail": f"5-stage pipeline completed, passed={task_result['ok']}"},
            {"event": "successor_sealed", "timestamp": runner_end_utc, "detail": f"E2 capsule sealed, epoch={successor_manifest['epoch']}"},
            {"event": "evidence_archived", "timestamp": runner_end_utc, "detail": "Report and evidence packet signed and written"},
        ],
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
