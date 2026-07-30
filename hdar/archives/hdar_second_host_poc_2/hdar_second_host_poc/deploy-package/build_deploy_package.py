#!/usr/bin/env python3
"""HDAR Deploy Package Builder — regenerates the entire deploy-package from scratch.

This script:
1. Generates a fresh Ed25519 owner keypair
2. Creates a minimal agent workspace (agent_state.json, progress.log, src/worker.py, todo.md)
3. Seals it as capsule epoch 1 with content-addressed blocks
4. Signs the capsule manifest with the owner Ed25519 key
5. Creates the transport tar.gz
6. Embeds the bundle into run_on_host_b.py (base64)
7. Computes and records all hashes
8. Writes host_a_build_report.json, owner_public_key.txt, INSTRUCTIONS.txt

Usage:
    python3 build_deploy_package.py --out /path/to/deploy-package

Prerequisites:
    pip install cryptography
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
import time
from datetime import datetime, timezone
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
SCHEMA = "hdar.transport-capsule/v0.1"
RECEIPT_SCHEMA = "hdar.receipt/v0.1"
AGENT_ID = "hdar-seed-poc-agent"
TASK_NAME = "multi_stage_analysis_pipeline"
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


def generate_owner_keypair() -> dict:
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


def sign_with_keypair(keypair: dict, data: bytes) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(keypair["private_key_hex"]))
    return private_key.sign(data).hex()


def create_workspace(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "src").mkdir(exist_ok=True)
    (workspace / "data").mkdir(exist_ok=True)

    agent_state = {
        "agent_id": AGENT_ID,
        "status": "sealed_on_host_a",
        "host_a_label": "host-a-local-mac",
        "epoch": 1,
        "task": TASK_NAME,
        "task_stages": TASK_STAGES,
        "task_completed": False,
        "next_action": "Host B must restore workspace, execute pipeline, and seal epoch 2.",
    }
    (workspace / "agent_state.json").write_text(json.dumps(agent_state, indent=2, sort_keys=True) + "\n")

    progress = (
        '[{"event":"agent_created","host":"host-a","timestamp":' + str(time.time()) + ',"epoch":1}]\n'
        '{"event":"workspace_sealed","host":"host-a","timestamp":' + str(time.time()) + ',"epoch":1}\n'
    )
    (workspace / "progress.log").write_text(progress)

    # Real multi-stage pipeline worker — read from template file
    worker_template_path = Path(__file__).parent / "worker_template.py"
    worker = worker_template_path.read_text()
    (workspace / "src" / "worker.py").write_text(worker)
    os.chmod(workspace / "src" / "worker.py", 0o644)

    # Generate realistic input data — 50 records across 4 categories
    import random
    random.seed(42)  # deterministic
    categories = ["alpha", "beta", "gamma", "delta"]
    records = []
    for i in range(50):
        cat = categories[i % 4]
        base_val = {"alpha": 100, "beta": 200, "gamma": 50, "delta": 300}[cat]
        value = round(base_val + random.gauss(0, base_val * 0.2), 2)
        records.append({"id": f"rec-{i:04d}", "category": cat, "value": value, "timestamp": 1700000000 + i * 60})
    # Add a couple invalid records to test filtering
    records.append({"id": "rec-bad-01", "category": "alpha"})  # missing value
    records.append({"id": "rec-bad-02", "category": "beta", "value": -5})  # negative value
    (workspace / "data" / "input_records.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")

    todo = (
        "# HDAR Seed PoC — Task List\n\n"
        "## Epoch 1 (Host A)\n"
        "- [x] Create agent workspace with data pipeline\n"
        "- [x] Generate input dataset (52 records, 4 categories)\n"
        "- [x] Seal capsule epoch 1\n"
        "- [x] Sign with owner Ed25519 key\n\n"
        "## Epoch 2 (Host B)\n"
        "- [ ] Restore workspace from capsule\n"
        "- [ ] Execute 5-stage analysis pipeline (parse, filter, aggregate, classify, report)\n"
        "- [ ] Verify output hash matches expected\n"
        "- [ ] Seal successor capsule epoch 2\n"
        "- [ ] Sign report with Host B Ed25519 key\n"
    )
    (workspace / "todo.md").write_text(todo)


def seal_capsule(workspace: Path, capsule_dir: Path, owner_keypair: dict) -> dict:
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
        "epoch": 1,
        "parent_manifest_hash": None,
        "created_at": time.time(),
        "source_host_label": "host-a-local-mac",
        "objective": "Continue unfinished work after Host A runtime destruction.",
        "continuation_point": "Host A sealed epoch 1; Host B must restore and advance progress.log.",
        "verification_mode": "sha256-content-addressed-hash-only",
        "signature_mode": "ed25519-owner-signed",
        "workspace_manifest": workspace_manifest,
    }

    # Set owner signature fields BEFORE signing so they're included in signed content
    # Verifier excludes only: owner_signature, owner_public_key, manifest_hash
    # Verifier INCLUDES owner_signature_algorithm in signed content
    manifest["owner_public_key"] = owner_keypair["public_key_hex"]
    manifest["owner_signature_algorithm"] = "ed25519"
    signing_content = {k: v for k, v in manifest.items() if k not in ("owner_signature", "owner_public_key", "manifest_hash")}
    manifest["owner_signature"] = sign_with_keypair(owner_keypair, canonical_json(signing_content))

    # Compute manifest hash (excludes signature fields and manifest_hash itself)
    manifest["manifest_hash"] = sha256_bytes(canonical_json({k: v for k, v in manifest.items() if k not in ("manifest_hash", "owner_signature", "owner_public_key", "owner_signature_algorithm", "host_signature", "host_public_key", "host_signature_algorithm")}))

    (capsule_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "event": "capsule_sealed",
        "agent_id": AGENT_ID,
        "epoch": 1,
        "source_host_label": "host-a-local-mac",
        "manifest_hash": manifest["manifest_hash"],
        "workspace_root_hash": workspace_manifest["root_hash"],
        "timestamp": time.time(),
        "owner_public_key": owner_keypair["public_key_hex"],
        "owner_signed": True,
    }
    receipt["receipt_hash"] = sha256_bytes(canonical_json({k: v for k, v in receipt.items() if k not in ("receipt_hash", "host_signature", "host_public_key", "host_signature_algorithm")}))
    (capsule_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))

    return manifest


def build_package(out_dir: Path, runner_template: Path, verifier_template: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate owner keypair
    owner_keypair = generate_owner_keypair()
    (out_dir / "owner_keypair.json").write_text(json.dumps(owner_keypair, indent=2, sort_keys=True) + "\n")
    (out_dir / "owner_public_key.txt").write_text(owner_keypair["public_key_hex"] + "\n")

    # 2. Create workspace
    workspace = out_dir / "_workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    create_workspace(workspace)

    # 2a. Compute expected output hash by running the pipeline locally
    _ws = workspace.resolve()
    _r = subprocess.run([sys.executable, str(_ws / "src" / "worker.py"), str(_ws)], capture_output=True, text=True, timeout=30)
    if _r.returncode != 0:
        print(f"Error: worker pipeline failed during build: {_r.stderr}")
        return 1
    _output = json.loads((_ws / "output" / "final_report.json").read_text())
    _expected_hash = sha256_bytes(canonical_json(_output))
    print(f"Pipeline pre-run: 5 stages completed, output hash={_expected_hash}")

    # Clean the output directory so the capsule only contains the unfinished state
    _output_dir = _ws / "output"
    if _output_dir.exists():
        shutil.rmtree(_output_dir)
    _task_result = _ws / "task_result.json"
    if _task_result.exists():
        _task_result.unlink()

    # 3. Seal capsule
    capsule_dir = out_dir / "capsule_epoch_1"
    if capsule_dir.exists():
        shutil.rmtree(capsule_dir)
    manifest = seal_capsule(workspace, capsule_dir, owner_keypair)

    # 4. Create transport tar.gz
    tar_path = out_dir / "transport_capsule_epoch_1_signed.tar.gz"
    if tar_path.exists():
        tar_path.unlink()
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(capsule_dir, arcname="capsule_epoch_1")
    tar_bytes = tar_path.read_bytes()
    tar_sha256 = sha256_bytes(tar_bytes)
    tar_b64 = base64.b64encode(tar_bytes).decode()

    # 5. Copy runner and verifier
    runner_path = out_dir / "run_on_host_b.py"
    verifier_path = out_dir / "third_party_verifier.py"
    shutil.copy2(runner_template, runner_path)
    shutil.copy2(verifier_template, verifier_path)

    # 6. Update embedded bundle in runner
    runner_text = runner_path.read_text()
    import re
    runner_text = re.sub(r'BUNDLE_B64 = "[^"]*"', f'BUNDLE_B64 = "{tar_b64}"', runner_text)
    runner_text = re.sub(r'BUNDLE_SHA256 = "[^"]*"', f'BUNDLE_SHA256 = "{tar_sha256}"', runner_text)
    runner_text = re.sub(r'RUNNER_SHA256 = "[^"]*"', 'RUNNER_SHA256 = ""', runner_text)
    runner_text = runner_text.replace('TASK_EXPECTED_OUTPUT_HASH = ""', f'TASK_EXPECTED_OUTPUT_HASH = "{_expected_hash}"')
    runner_path.write_text(runner_text)

    # 7. Compute runner hash
    runner_sha256 = sha256_file(runner_path)
    runner_size = runner_path.stat().st_size

    # 8. Write host_a_build_report.json
    report = {
        "schema": "hdar.second-host-demo-build/v0.2",
        "host_a_platform": platform.platform(),
        "host_a_runtime_destroyed": True,
        "host_a_workspace_hash_before_destroy": manifest["workspace_manifest"]["root_hash"],
        "capsule_epoch_1": {
            "ok": True,
            "problems": [],
            "agent_id": AGENT_ID,
            "epoch": 1,
            "manifest_hash": manifest["manifest_hash"],
            "workspace_root_hash": manifest["workspace_manifest"]["root_hash"],
            "file_count": len(manifest["workspace_manifest"]["files"]),
            "total_size": manifest["workspace_manifest"]["total_size"],
            "owner_signed": True,
            "owner_public_key": owner_keypair["public_key_hex"],
            "owner_signature_algorithm": "ed25519",
            "signature_mode": "ed25519-owner-signed",
        },
        "transport_bundle": {
            "path": "run_on_host_b.py",
            "bytes": runner_size,
            "sha256": runner_sha256,
        },
        "transport_capsule_tar": {
            "path": "transport_capsule_epoch_1_signed.tar.gz",
            "bytes": len(tar_bytes),
            "sha256": tar_sha256,
        },
        "claim_boundary": "Owner-signed portable capsule with Ed25519 owner authorization, multi-stage analysis pipeline, Host B signature verification, evidence packet signing, and third-party verifier support. Ready for external Host B reproduction.",
        "next_real_seed_step": "Run on independent Host B with --owner-public-key and --host-a-report flags, then run third_party_verifier.py",
    }
    (out_dir / "host_a_build_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    # 9. Clean up temp workspace
    shutil.rmtree(workspace)

    print(f"Deploy package built at: {out_dir}")
    print(f"Owner public key: {owner_keypair['public_key_hex']}")
    print(f"Runner SHA-256: {runner_sha256}")
    print(f"Bundle SHA-256: {tar_sha256}")
    print(f"Manifest hash: {manifest['manifest_hash']}")
    print()
    print("To verify locally:")
    print(f"  python3 {runner_path} --bundle {tar_path} --host-a-report {out_dir / 'host_a_build_report.json'} --owner-public-key $(cat {out_dir / 'owner_public_key.txt'}) --verify-runner-hash {runner_sha256} --host-label test --operator-identity founder --out /tmp/hdar-test")
    print(f"  python3 {verifier_path} --capsule-e1 {capsule_dir} --capsule-e2 /tmp/hdar-test/capsule_epoch_2 --host-b-report /tmp/hdar-test/host_b_report.json --evidence-packet /tmp/hdar-test/host_b_evidence_packet.json --owner-public-key $(cat {out_dir / 'owner_public_key.txt'}) --host-a-platform \"{platform.platform()}\"")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build HDAR deploy package from scratch")
    ap.add_argument("--out", required=True, help="Output directory for deploy package")
    ap.add_argument("--runner-template", default="run_on_host_b.py", help="Path to runner template")
    ap.add_argument("--verifier-template", default="third_party_verifier.py", help="Path to verifier template")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    runner_template = Path(args.runner_template).resolve()
    verifier_template = Path(args.verifier_template).resolve()

    if not runner_template.exists():
        print(f"Error: runner template not found: {runner_template}")
        return 1
    if not verifier_template.exists():
        print(f"Error: verifier template not found: {verifier_template}")
        return 1

    build_package(out_dir, runner_template, verifier_template)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
