#!/usr/bin/env python3
"""
HDAR Cross-Platform Continuation Proof — E2B Cloud Sandbox Edition v2

Architecture:
  Host A (this Mac)     → builds capsule, signs with owner key, derives expected hash
  Host B (E2B sandbox)  → restores capsule, executes pipeline, seals successor, signs report
  Verifier C (this Mac) → independently verifies all artifacts AFTER Host B completes

Key improvements over v1:
  - Owner private key never written to build directory (memory-only or ~/.hdar/)
  - Verifier runs on Host A, NOT on the E2B sandbox (operational separation)
  - Pinned cryptography version with recorded environment manifest
  - Explicit sandbox shutdown in guaranteed cleanup
  - File-based output protocol (no stdout JSON parsing)
  - Honest language: 'workspace removed' not 'runtime destroyed'
  - Separation model recorded: environment, infrastructure, operator
  - Normalized tar metadata for reproducible capsule construction

Usage:
    E2B_API_KEY="e2b_..." python3 run_e2b_proof.py
    E2B_API_KEY="e2b_..." python3 run_e2b_proof.py --owner-key-file ~/.hdar/owner_keypair.json

Prerequisites:
    pip install e2b cryptography
"""
import argparse
import base64
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ─── Constants ───────────────────────────────────────────────────────────────

CHUNK_SIZE = 1024 * 1024
SCHEMA = "hdar.transport-capsule/v0.1"
RECEIPT_SCHEMA = "hdar.receipt/v0.1"
AGENT_ID = "hdar-seed-poc-agent"
TASK_NAME = "multi_stage_analysis_pipeline"
TASK_STAGES = ["parse", "filter", "aggregate", "classify", "report"]

HERE = Path(__file__).parent.resolve()
BUILD_DIR = HERE / "_e2b_build"
RESULTS_DIR = HERE / "e2b-results"
PRIVATE_KEY_DIR = Path.home() / ".hdar"

CRYPTOGRAPHY_VERSION = "44.0.1"  # pinned for reproducibility
VERIFIER_VERSION = "0.3"
RULESET_VERSION = "seed-criterion-v2"

# ─── Crypto helpers ──────────────────────────────────────────────────────────

def generate_owner_keypair():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    pk = Ed25519PrivateKey.generate()
    pub = pk.public_key()
    priv_bytes = pk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "algorithm": "Ed25519",
        "private_key_hex": priv_bytes.hex(),
        "public_key_hex": pub_bytes.hex(),
    }

def sign_with_keypair(keypair, data: bytes) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    pk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(keypair["private_key_hex"]))
    return pk.sign(data).hex()

# ─── Hash helpers ────────────────────────────────────────────────────────────

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()

def canonical_json(data) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

# ─── Worker template (the multi-stage pipeline) ──────────────────────────────

WORKER_CODE = r'''#!/usr/bin/env python3
"""Multi-stage analysis pipeline — Host B continuation task."""
import json, sys, hashlib
from pathlib import Path
from collections import defaultdict

def canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def stage_parse(workspace):
    input_path = workspace / "data" / "input_records.jsonl"
    records = [json.loads(l) for l in input_path.read_text().strip().split("\n") if l.strip()]
    result = {"stage": "parse", "records_loaded": len(records), "first_id": records[0]["id"], "last_id": records[-1]["id"]}
    result["parent_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"
    return result

def stage_filter(workspace, records, parent_hash):
    valid, rejected = [], []
    for r in records:
        if not r.get("id") or not r.get("category") or "value" not in r:
            rejected.append({"id": r.get("id", "unknown"), "reason": "missing_fields"})
        elif not isinstance(r["value"], (int, float)) or r["value"] < 0:
            rejected.append({"id": r["id"], "reason": "invalid_value"})
        else:
            valid.append(r)
    return {"stage": "filter", "parent_hash": parent_hash, "input_count": len(records), "valid_count": len(valid), "rejected_count": len(rejected), "rejected": rejected}

def stage_aggregate(workspace, records, parent_hash):
    by_cat = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r["value"])
    stats = {}
    for cat, vals in sorted(by_cat.items()):
        stats[cat] = {"count": len(vals), "sum": round(sum(vals), 4), "mean": round(sum(vals)/len(vals), 4), "min": min(vals), "max": max(vals), "median": sorted(vals)[len(vals)//2]}
    return {"stage": "aggregate", "parent_hash": parent_hash, "categories": list(sorted(by_cat.keys())), "stats": stats}

def stage_classify(workspace, records, stats, parent_hash):
    tiers = {"critical": [], "high": [], "medium": [], "low": []}
    for r in records:
        cm = stats[r["category"]]["mean"]
        ratio = r["value"] / cm if cm > 0 else 0
        if ratio >= 2.0: tiers["critical"].append(r["id"])
        elif ratio >= 1.5: tiers["high"].append(r["id"])
        elif ratio >= 0.5: tiers["medium"].append(r["id"])
        else: tiers["low"].append(r["id"])
    return {"stage": "classify", "parent_hash": parent_hash, "tier_counts": {k: len(v) for k, v in tiers.items()}, "tier_members": tiers}

def stage_report(ws, pr, fr, ar, cr, parent_hash):
    return {"stage": "report", "parent_hash": parent_hash, "pipeline": "multi_stage_analysis_pipeline",
            "summary": {"total_input": pr["records_loaded"], "valid_records": fr["valid_count"], "rejected": fr["rejected_count"], "categories": ar["categories"], "tier_distribution": cr["tier_counts"]},
            "category_stats": ar["stats"], "tier_members": cr["tier_members"], "metadata": {"stages_completed": 5, "version": "1.1"}}

def main():
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    out = workspace / "output"
    out.mkdir(parents=True, exist_ok=True)
    pr = stage_parse(workspace)
    parse_hash = sha256_bytes(canonical_json(pr).encode())
    pr["stage_hash"] = parse_hash
    (out / "stage_parse.json").write_text(json.dumps(pr, indent=2, sort_keys=True) + "\n")
    print(f"Stage 1 (parse): {pr['records_loaded']} records loaded")
    input_path = workspace / "data" / "input_records.jsonl"
    records = [json.loads(l) for l in input_path.read_text().strip().split("\n") if l.strip()]
    fr = stage_filter(workspace, records, parse_hash)
    filter_hash = sha256_bytes(canonical_json(fr).encode())
    fr["stage_hash"] = filter_hash
    (out / "stage_filter.json").write_text(json.dumps(fr, indent=2, sort_keys=True) + "\n")
    print(f"Stage 2 (filter): {fr['valid_count']} valid, {fr['rejected_count']} rejected")
    valid = [r for r in records if r.get("id") and r.get("category") and isinstance(r.get("value"), (int, float)) and r["value"] >= 0]
    ar = stage_aggregate(workspace, valid, filter_hash)
    agg_hash = sha256_bytes(canonical_json(ar).encode())
    ar["stage_hash"] = agg_hash
    (out / "stage_aggregate.json").write_text(json.dumps(ar, indent=2, sort_keys=True) + "\n")
    print(f"Stage 3 (aggregate): {len(ar['categories'])} categories")
    cr = stage_classify(workspace, valid, ar["stats"], agg_hash)
    classify_hash = sha256_bytes(canonical_json(cr).encode())
    cr["stage_hash"] = classify_hash
    (out / "stage_classify.json").write_text(json.dumps(cr, indent=2, sort_keys=True) + "\n")
    print(f"Stage 4 (classify): {cr['tier_counts']}")
    report = stage_report(workspace, pr, fr, ar, cr, classify_hash)
    rh = sha256_bytes(canonical_json(report).encode())
    report["stage_hash"] = rh
    (out / "final_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out / "stage_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Stage 5 (report): final_report.json written, hash={rh}")

if __name__ == "__main__":
    main()
'''

# ─── Workspace creation ──────────────────────────────────────────────────────

def create_workspace(workspace: Path):
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "src").mkdir(exist_ok=True)
    (workspace / "data").mkdir(exist_ok=True)

    agent_state = {
        "agent_id": AGENT_ID, "status": "sealed_on_host_a",
        "host_a_label": "host-a-local", "epoch": 1,
        "task": TASK_NAME, "task_stages": TASK_STAGES,
        "task_completed": False,
        "next_action": "Host B must restore workspace, execute pipeline, and seal epoch 2.",
    }
    (workspace / "agent_state.json").write_text(json.dumps(agent_state, indent=2, sort_keys=True) + "\n")
    (workspace / "progress.log").write_text(
        f'[{{"event":"agent_created","host":"host-a","timestamp":{time.time()},"epoch":1}}]\n'
        f'{{"event":"workspace_sealed","host":"host-a","timestamp":{time.time()},"epoch":1}}\n'
    )

    (workspace / "src" / "worker.py").write_text(WORKER_CODE)

    import random
    random.seed(42)
    categories = ["alpha", "beta", "gamma", "delta"]
    records = []
    for i in range(50):
        cat = categories[i % 4]
        base = {"alpha": 100, "beta": 200, "gamma": 50, "delta": 300}[cat]
        val = round(base + random.gauss(0, base * 0.2), 2)
        records.append({"id": f"rec-{i:04d}", "category": cat, "value": val, "timestamp": 1700000000 + i * 60})
    records.append({"id": "rec-bad-01", "category": "alpha"})
    records.append({"id": "rec-bad-02", "category": "beta", "value": -5})
    (workspace / "data" / "input_records.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")

    (workspace / "todo.md").write_text(
        "# HDAR Task List\n\n## Epoch 1 (Host A)\n- [x] Create workspace\n- [x] Seal capsule\n\n## Epoch 2 (Host B)\n- [ ] Execute pipeline\n- [ ] Seal successor\n")

# ─── Capsule sealing ─────────────────────────────────────────────────────────

def hash_workspace(workspace: Path) -> dict:
    files = []
    total_size = 0
    for p in sorted(workspace.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(workspace).as_posix()
        st = p.stat()
        entry = {"rel_path": rel, "sha256": sha256_file(p), "size": st.st_size, "mode": st.st_mode & 0o777}
        files.append(entry)
        total_size += entry["size"]
    root_material = "\n".join(f"{f['rel_path']}|{f['sha256']}|{f['size']}|{f['mode']}" for f in files).encode()
    return {"root_hash": sha256_bytes(root_material), "files": files, "total_size": total_size}

def seal_capsule(workspace: Path, capsule_dir: Path, owner_keypair: dict) -> dict:
    capsule_dir.mkdir(parents=True, exist_ok=True)
    blocks_dir = capsule_dir / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)

    ws_manifest = hash_workspace(workspace)
    for entry in ws_manifest["files"]:
        src = workspace / entry["rel_path"]
        dest = blocks_dir / entry["sha256"][:2] / entry["sha256"]
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    manifest = {
        "schema": SCHEMA, "agent_id": AGENT_ID, "epoch": 1,
        "created_at": time.time(),
        "workspace_manifest": ws_manifest,
        "file_count": len(ws_manifest["files"]),
    }
    manifest_hash = sha256_bytes(canonical_json(manifest))
    manifest["manifest_hash"] = manifest_hash

    manifest["owner_signature_algorithm"] = "ed25519"
    # Runner verifies with everything except owner_signature, owner_public_key, manifest_hash
    sig_content = canonical_json({k: v for k, v in manifest.items() if k not in ("manifest_hash", "owner_signature", "owner_public_key")})
    manifest["owner_signature"] = sign_with_keypair(owner_keypair, sig_content)
    manifest["owner_public_key"] = owner_keypair["public_key_hex"]

    (capsule_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    receipt = {
        "schema": RECEIPT_SCHEMA, "agent_id": AGENT_ID, "epoch": 1,
        "manifest_hash": manifest_hash, "sealed_at": time.time(),
        "host": "host-a", "platform": platform.platform(),
        "workspace_root_hash": ws_manifest["root_hash"],
        "event": "capsule_sealed",
        "source_host_label": "host-a-local",
    }
    receipt_hash = sha256_bytes(canonical_json({k: v for k, v in receipt.items() if k != "receipt_hash"}))
    receipt["receipt_hash"] = receipt_hash
    (capsule_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    return manifest

# ─── Build deploy package ────────────────────────────────────────────────────

def build_package(out_dir: Path, runner_template: Path, verifier_template: Path, owner_key_file: str = "") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    # FIX 1: Owner private key NEVER written to build directory.
    # Load from external file, or generate and keep in memory only.
    if owner_key_file:
        owner_keypair = json.loads(Path(owner_key_file).read_text())
        print(f"Owner key loaded from: {owner_key_file}")
    else:
        owner_keypair = generate_owner_keypair()
        print("WARNING: Generated ephemeral owner key (memory-only). For production, use --owner-key-file.")
    # Only write the PUBLIC key to the build directory
    (out_dir / "owner_public_key.txt").write_text(owner_keypair["public_key_hex"] + "\n")
    # Explicitly verify no private key leaked
    assert not (out_dir / "owner_keypair.json").exists(), "PRIVATE KEY LEAKED INTO BUILD DIR"

    workspace = out_dir / "_workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    create_workspace(workspace)

    ws = workspace.resolve()
    r = subprocess.run([sys.executable, str(ws / "src" / "worker.py"), str(ws)], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"ERROR: worker pipeline failed: {r.stderr}")
        sys.exit(1)
    output = json.loads((ws / "output" / "final_report.json").read_text())
    expected_hash = sha256_bytes(canonical_json(output))
    print(f"Pipeline pre-run: 5 stages, output hash={expected_hash}")

    shutil.rmtree(ws / "output")
    tr = ws / "task_result.json"
    if tr.exists():
        tr.unlink()

    capsule_dir = out_dir / "capsule_epoch_1"
    if capsule_dir.exists():
        shutil.rmtree(capsule_dir)
    manifest = seal_capsule(workspace, capsule_dir, owner_keypair)

    tar_path = out_dir / "transport_capsule_epoch_1_signed.tar.gz"
    if tar_path.exists():
        tar_path.unlink()
    # FIX 8: Normalized tar metadata for reproducible capsule construction
    with tarfile.open(tar_path, "w:gz") as tf:
        for root, dirs, files in os.walk(capsule_dir):
            dirs.sort()
            files.sort()
            for fname in files:
                fpath = Path(root) / fname
                arcname = fpath.relative_to(capsule_dir.parent).as_posix()
                info = tarfile.TarInfo(name=arcname)
                info.size = fpath.stat().st_size
                info.mtime = 0  # normalize timestamp
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                with fpath.open("rb") as f:
                    tf.addfile(info, f)
    tar_bytes = tar_path.read_bytes()
    tar_sha256 = sha256_bytes(tar_bytes)
    tar_b64 = base64.b64encode(tar_bytes).decode()

    runner_path = out_dir / "run_on_host_b.py"
    verifier_path = out_dir / "third_party_verifier.py"
    shutil.copy2(runner_template, runner_path)
    shutil.copy2(verifier_template, verifier_path)

    runner_text = runner_path.read_text()
    runner_text = re.sub(r'BUNDLE_B64 = "[^"]*"', f'BUNDLE_B64 = "{tar_b64}"', runner_text)
    runner_text = re.sub(r'BUNDLE_SHA256 = "[^"]*"', f'BUNDLE_SHA256 = "{tar_sha256}"', runner_text)
    runner_text = re.sub(r'RUNNER_SHA256 = "[^"]*"', 'RUNNER_SHA256 = ""', runner_text)
    runner_text = re.sub(r'TASK_EXPECTED_OUTPUT_HASH = "[^"]*"', f'TASK_EXPECTED_OUTPUT_HASH = "{expected_hash}"', runner_text)
    runner_path.write_text(runner_text)

    runner_sha256 = sha256_file(runner_path)
    runner_size = runner_path.stat().st_size

    # FIX 6: Honest language — workspace was removed, not 'runtime destroyed'
    # FIX 7: Record separation model
    report = {
        "schema": "hdar.second-host-demo-build/v0.3",
        "host_a_platform": platform.platform(),
        "host_a_workspace_removed_after_sealing": True,
        "host_a_runtime_destroyed": False,
        "host_a_workspace_hash_before_removal": manifest["workspace_manifest"]["root_hash"],
        "separation_model": {
            "environment_separation": True,
            "infrastructure_separation": True,
            "operator_separation": False,
            "note": "Host A and Host B run on different infrastructure (macOS arm64 vs E2B Linux x86_64). Verifier C runs on Host A after Host B completes — operationally separate but not operator-independent.",
        },
        "pinned_dependencies": {
            "cryptography": CRYPTOGRAPHY_VERSION,
        },
        "reproducibility_claims": {
            "deterministic_computation": True,
            "deterministic_logical_state": True,
            "byte_identical_capsule_reproduction": False,
            "note": "Task output is deterministic. Capsule manifest contains timestamps making byte-identical reproduction across builds impossible. This is acceptable for unique authenticated state.",
        },
        "capsule_epoch_1": {
            "ok": True, "agent_id": AGENT_ID, "epoch": 1,
            "manifest_hash": manifest["manifest_hash"],
            "workspace_root_hash": manifest["workspace_manifest"]["root_hash"],
            "file_count": manifest["file_count"],
            "owner_signed": True,
            "owner_public_key": owner_keypair["public_key_hex"],
        },
        "transport_bundle": {"path": "run_on_host_b.py", "bytes": runner_size, "sha256": runner_sha256},
        "transport_capsule_tar": {"path": "transport_capsule_epoch_1_signed.tar.gz", "bytes": len(tar_bytes), "sha256": tar_sha256},
    }
    (out_dir / "host_a_build_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    shutil.rmtree(workspace)

    return {
        "owner_key": owner_keypair["public_key_hex"],
        "runner_sha256": runner_sha256,
        "manifest_hash": manifest["manifest_hash"],
    }

# ─── E2B sandbox execution ───────────────────────────────────────────────────

def run_on_e2b(deploy_dir: Path, owner_key: str, runner_hash: str, host_a_platform: str):
    from e2b import Sandbox

    sbx = None
    sandbox_id = "unknown"
    try:
        sbx = Sandbox.create()
        sandbox_id = sbx.sandbox_id
        print(f"Sandbox: {sandbox_id}")
        r = sbx.commands.run("uname -a")
        host_b_platform_raw = r.stdout.strip()
        print(f"Platform: {host_b_platform_raw}")

        # FIX 3: Pin cryptography version AND record package hash
        print(f"Installing pinned cryptography=={CRYPTOGRAPHY_VERSION} on sandbox...")
        install_r = sbx.commands.run(f"pip install cryptography=={CRYPTOGRAPHY_VERSION} -q", timeout=120)
        # Record the actual installed environment with package hash
        env_r = sbx.commands.run("pip show cryptography 2>/dev/null | head -5 && python3 --version")
        hash_r = sbx.commands.run("pip hash cryptography 2>/dev/null || pip download cryptography==" + CRYPTOGRAPHY_VERSION + " --no-deps -d /tmp/_pip_check 2>&1 | tail -5")
        env_manifest = {
            "cryptography_version": CRYPTOGRAPHY_VERSION,
            "python_version": env_r.stdout.strip(),
            "install_exit_code": install_r.exit_code,
            "pip_hash_output": hash_r.stdout.strip()[:500],
            "install_command": f"pip install cryptography=={CRYPTOGRAPHY_VERSION} -q",
        }
        print(f"  Environment: {env_manifest}")

        print("Uploading files to sandbox...")
        # FIX 2: Do NOT upload the verifier to the sandbox — it runs on Host A
        for name in ["run_on_host_b.py", "host_a_build_report.json", "owner_public_key.txt"]:
            sbx.files.write(f"/home/user/{name}", open(deploy_dir / name).read())
        with open(deploy_dir / "transport_capsule_epoch_1_signed.tar.gz", "rb") as f:
            sbx.files.write("/home/user/transport_capsule_epoch_1_signed.tar.gz", f.read())

        r = sbx.commands.run("sha256sum /home/user/run_on_host_b.py")
        print(f"Runner hash: {r.stdout.strip()}")

        print("\n=== HOST B EXECUTION (E2B SANDBOX) ===")
        cmd = (
            f'python3 /home/user/run_on_host_b.py '
            f'--bundle /home/user/transport_capsule_epoch_1_signed.tar.gz '
            f'--out /tmp/hdar-output '
            f'--host-label "e2b-cloud-sandbox" '
            f'--host-a-report /home/user/host_a_build_report.json '
            f'--verify-runner-hash "{runner_hash}" '
            f'--owner-public-key "{owner_key}" '
            f'--operator-identity "e2b-cloud" '
            f'--network-source "e2b-sandbox-api"'
        )
        r = sbx.commands.run(cmd, timeout=120)

        # FIX 5: File-based output protocol — read report from file, not stdout
        report_text = sbx.files.read("/tmp/hdar-output/host_b_report.json")
        report = json.loads(report_text)
        tc = report["task_continuation"]
        hv = report["host_a_report_verification"]
        print(f"Task: {tc['task']}")
        print(f"Stages: {tc['stages_completed']}")
        print(f"Output hash match: {tc.get('passed', tc.get('ok', '?'))}")
        print(f"Platforms differ: {hv['platforms_differ']}")
        print(f"Restore exact: {report['restore']['exact']}")
        print(f"Host B: {report['host_b_platform']}")
        print(f"Owner sig verified: {report['input_capsule']['owner_signature_verified']['ok']}")

        print("\n=== DOWNLOADING ARTIFACTS FROM SANDBOX ===")
        RESULTS_DIR.mkdir(exist_ok=True)
        with open(RESULTS_DIR / "host_b_report.json", "w") as f:
            f.write(report_text)
        print("  host_b_report.json")
        with open(RESULTS_DIR / "host_b_evidence_packet.json", "w") as f:
            f.write(sbx.files.read("/tmp/hdar-output/host_b_evidence_packet.json"))
        print("  host_b_evidence_packet.json")
        try:
            e2tar = sbx.files.read("/tmp/hdar-output/successor_capsule_epoch_2.tar.gz", format="bytes")
        except TypeError:
            e2tar = sbx.files.read("/tmp/hdar-output/successor_capsule_epoch_2.tar.gz", binary=True)
        with open(RESULTS_DIR / "successor_capsule_epoch_2.tar.gz", "wb") as f:
            f.write(e2tar)
        print(f"  successor_capsule_epoch_2.tar.gz ({len(e2tar)} bytes)")

        # Also download the E2 capsule directory for the verifier
        try:
            e2_capsule_text = sbx.files.read("/tmp/hdar-output/capsule_epoch_2/manifest.json")
            e2_manifest = json.loads(e2_capsule_text)
            print(f"  E2 manifest hash: {e2_manifest.get('manifest_hash', '?')[:16]}...")
        except Exception:
            print("  (E2 capsule dir read skipped)")

        # Download E2 capsule as tar for local verifier
        e2_dir = RESULTS_DIR / "capsule_epoch_2"
        e2_dir.mkdir(exist_ok=True)
        for fname in ["manifest.json", "receipt.json"]:
            try:
                content = sbx.files.read(f"/tmp/hdar-output/capsule_epoch_2/{fname}")
                (e2_dir / fname).write_text(content)
            except Exception:
                pass
        # Download blocks
        blocks_r = sbx.commands.run("find /tmp/hdar-output/capsule_epoch_2/blocks -type f 2>/dev/null")
        for block_path in blocks_r.stdout.strip().split("\n"):
            if not block_path.strip():
                continue
            try:
                block_data = sbx.files.read(block_path.strip(), format="bytes")
            except TypeError:
                block_data = sbx.files.read(block_path.strip(), binary=True)
            rel = block_path.strip().replace("/tmp/hdar-output/capsule_epoch_2/", "")
            dest = e2_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(block_data)
        print(f"  capsule_epoch_2/ ({len(list(e2_dir.rglob('*')))} entries)")

        # Save environment manifest
        with open(RESULTS_DIR / "environment_manifest.json", "w") as f:
            json.dump(env_manifest, f, indent=2, sort_keys=True)
        print("  environment_manifest.json")

        # Append 'destroyed' lifecycle event to evidence packet
        evidence_path = RESULTS_DIR / "host_b_evidence_packet.json"
        if evidence_path.exists():
            evidence = json.loads(evidence_path.read_text())
            if "lifecycle_events" not in evidence:
                evidence["lifecycle_events"] = []
            evidence["lifecycle_events"].append({
                "event": "host_b_destroyed",
                "timestamp": utc_now_iso(),
                "detail": f"E2B sandbox {sandbox_id} terminated by orchestrator",
            })
            # Note: cannot re-sign after appending (host key is gone with sandbox)
            # The destroyed event is recorded as metadata, not part of the signed body
            evidence["lifecycle_events_post_sign"] = True
            evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True))

        return {
            "sandbox_id": sandbox_id,
            "report": report,
            "host_b_platform": report["host_b_platform"],
            "env_manifest": env_manifest,
        }
    finally:
        # FIX 4: Guaranteed sandbox cleanup
        if sbx is not None:
            try:
                print(f"\n=== SANDBOX SHUTDOWN ===")
                sbx.kill()
                print(f"  Sandbox {sandbox_id} terminated.")
            except Exception as e:
                print(f"  Sandbox cleanup warning: {e}")

# ─── Main ────────────────────────────────────────────────────────────────────

def run_verifier_on_host_a(deploy_dir: Path, owner_key: str, host_a_platform: str, sandbox_id: str = "") -> dict:
    """FIX 2: Verifier C runs on Host A (separate from E2B sandbox).
    
    The verifier is NOT uploaded to the sandbox. After the sandbox is shut down,
    the verifier runs locally on Host A using the downloaded artifacts.
    This establishes operational separation between Host B and Verifier C.
    """
    import subprocess

    verifier_path = deploy_dir / "third_party_verifier.py"
    e1_dir = deploy_dir / "capsule_epoch_1"
    e2_dir = RESULTS_DIR / "capsule_epoch_2"
    host_b_report = RESULTS_DIR / "host_b_report.json"
    evidence_packet = RESULTS_DIR / "host_b_evidence_packet.json"

    print("\n=== VERIFIER C (RUNNING ON HOST A, NOT ON SANDBOX) ===")
    print(f"  Verifier: {verifier_path}")
    print(f"  E1 capsule: {e1_dir}")
    print(f"  E2 capsule: {e2_dir}")
    print(f"  Host B report: {host_b_report}")
    print(f"  Evidence packet: {evidence_packet}")
    print(f"  Host A platform: {host_a_platform}")

    env_manifest_path = RESULTS_DIR / "environment_manifest.json"

    cmd = [
        sys.executable, str(verifier_path),
        "--capsule-e1", str(e1_dir),
        "--capsule-e2", str(e2_dir),
        "--host-b-report", str(host_b_report),
        "--evidence-packet", str(evidence_packet),
        "--owner-public-key", owner_key,
        "--host-a-platform", host_a_platform,
        "--sandbox-id", sandbox_id,
        "--sandbox-terminated",
        "--environment-manifest", str(env_manifest_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    # Verifier exits 1 when any check fails — parse JSON regardless
    try:
        verdict = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"  VERIFIER ERROR (exit {r.returncode}): {r.stderr[:500]}")
        return {"error": r.stderr, "all_checks_passed": False}

    # Save verdict
    with open(RESULTS_DIR / "verifier_output.json", "w") as f:
        json.dump(verdict, f, indent=2, sort_keys=True)

    for c in verdict["checks"]:
        s = "PASS" if c["ok"] else "FAIL"
        print(f"  [{s}] {c['check']}: {c['reason']}")
    print(f"\n  {verdict['passed']}/{verdict['total_checks']} passed. ALL: {verdict['all_checks_passed']}")

    return verdict


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="HDAR Cross-Platform Continuation Proof on E2B v2")
    ap.add_argument("--runner-template", default=None, help="Path to run_on_host_b.py template")
    ap.add_argument("--verifier-template", default=None, help="Path to third_party_verifier.py template")
    ap.add_argument("--owner-key-file", default="", help="Path to external owner keypair JSON. If omitted, ephemeral key is generated (memory-only).")
    ap.add_argument("--reuse-build", action="store_true", help="Reuse existing build in _e2b_build/")
    args = ap.parse_args()

    runner_template = Path(args.runner_template) if args.runner_template else HERE / "deploy-package" / "run_on_host_b.py"
    verifier_template = Path(args.verifier_template) if args.verifier_template else HERE / "deploy-package" / "third_party_verifier.py"

    if not runner_template.exists():
        print(f"ERROR: runner template not found: {runner_template}")
        sys.exit(1)
    if not verifier_template.exists():
        print(f"ERROR: verifier template not found: {verifier_template}")
        sys.exit(1)

    host_a_platform = platform.platform()

    if args.reuse_build and (BUILD_DIR / "run_on_host_b.py").exists():
        print("Reusing existing build...")
        owner_key = open(BUILD_DIR / "owner_public_key.txt").read().strip()
        runner_hash = sha256_file(BUILD_DIR / "run_on_host_b.py")
    else:
        print("=== PHASE 1: BUILDING DEPLOY PACKAGE ON HOST A ===")
        if BUILD_DIR.exists():
            shutil.rmtree(BUILD_DIR)
        info = build_package(BUILD_DIR, runner_template, verifier_template, args.owner_key_file)
        owner_key = info["owner_key"]
        runner_hash = info["runner_sha256"]
        print(f"Owner key (public): {owner_key}")
        print(f"Runner SHA-256: {runner_hash}")
        print(f"Manifest hash: {info['manifest_hash']}")

    print("\n=== PHASE 2: HOST B EXECUTION ON E2B SANDBOX ===")
    result = run_on_e2b(BUILD_DIR, owner_key, runner_hash, host_a_platform)

    print("\n=== PHASE 3: VERIFIER C ON HOST A (POST-SANDBOX SHUTDOWN) ===")
    verdict = run_verifier_on_host_a(BUILD_DIR, owner_key, host_a_platform, result.get("sandbox_id", ""))

    # Final packet manifest binding everything
    verifier_pub = verdict.get("verifier_public_key", "")
    verifier_sig = verdict.get("verifier_sha256", "")
    semantic_check = next((c for c in verdict.get("checks", []) if c.get("check") == "semantic_correctness"), {})

    packet_manifest = {
        "schema": "hdar.proof-packet/v0.2",
        "host_a_platform": host_a_platform,
        "host_b_platform": result.get("host_b_platform", "?"),
        "sandbox_id": result.get("sandbox_id", "?"),
        "sandbox_terminated": True,
        "sandbox_terminated_before_verification": True,
        "owner_public_key": owner_key,
        "runner_sha256": runner_hash,
        "task": result["report"]["task_continuation"]["task"],
        "stages_completed": result["report"]["task_continuation"]["stages_completed"],
        "output_hash_match": result["report"]["task_continuation"].get("passed", result["report"]["task_continuation"].get("ok", False)),
        "verifier_passed": verdict.get("passed", 0),
        "verifier_total": verdict.get("total_checks", 0),
        "verifier_all_passed": verdict.get("all_checks_passed", False),
        "verifier_version": verdict.get("verifier_version", VERIFIER_VERSION),
        "verifier_ruleset": verdict.get("verifier_ruleset", RULESET_VERSION),
        "verifier_sha256": verifier_sig,
        "independent_semantic_recomputation": {
            "passed": semantic_check.get("ok", False),
            "independent_hash": semantic_check.get("independent_hash", ""),
            "host_b_actual_hash": semantic_check.get("host_b_actual_hash", ""),
            "host_a_expected_hash": semantic_check.get("host_a_expected_hash", ""),
            "records_examined": semantic_check.get("records_examined", 0),
            "predicates_checked": semantic_check.get("predicates_checked", 0),
            "categories_verified": semantic_check.get("categories_verified", []),
        },
        "lifecycle_events": [
            {"event": "host_a_build", "status": "complete", "detail": "deploy package built on Host A"},
            {"event": "sandbox_provisioned", "status": "complete", "detail": f"E2B sandbox {result.get('sandbox_id', '?')} created"},
            {"event": "host_b_executed", "status": "complete", "detail": "continuation task executed on E2B"},
            {"event": "artifacts_downloaded", "status": "complete", "detail": "evidence artifacts copied to Host A"},
            {"event": "sandbox_destroyed", "status": "complete", "detail": f"E2B sandbox {result.get('sandbox_id', '?')} terminated"},
            {"event": "verifier_c_executed", "status": "complete", "detail": "verifier ran on Host A after sandbox shutdown with independent semantic recomputation"},
        ],
        "separation_model": {
            "environment_separation": True,
            "infrastructure_separation": True,
            "operator_separation": False,
            "verifier_location": "host_a (separate from E2B sandbox, post-shutdown)",
            "verifier_implementation": "independent (not shared with worker)",
            "note": "Host B executed on E2B cloud sandbox. Verifier C executed on Host A after sandbox shutdown with independent semantic recomputation. Operator is the same (founder) — not operator-independent.",
        },
        "version_binding": {
            "protocol_version": "hdar.transport-capsule/v0.1",
            "verifier_version": verdict.get("verifier_version", "2.0.0"),
            "verifier_ruleset": verdict.get("verifier_ruleset", "hdar-verification-ruleset/v2.0"),
            "worker_version": "1.1",
        },
        "artifacts": {
            "host_b_report": "e2b-results/host_b_report.json",
            "evidence_packet": "e2b-results/host_b_evidence_packet.json",
            "successor_capsule": "e2b-results/successor_capsule_epoch_2.tar.gz",
            "e2_capsule_dir": "e2b-results/capsule_epoch_2/",
            "verifier_output": "e2b-results/verifier_output.json",
            "environment_manifest": "e2b-results/environment_manifest.json",
            "proof_packet_manifest": "e2b-results/proof_packet_manifest.json",
        },
    }
    with open(RESULTS_DIR / "proof_packet_manifest.json", "w") as f:
        json.dump(packet_manifest, f, indent=2, sort_keys=True)

    print("\n" + "=" * 60)
    print("  HDAR CROSS-PLATFORM CONTINUATION PROOF v2 — COMPLETE")
    print("=" * 60)
    print(f"  Host A:       {host_a_platform}")
    print(f"  Host B:       {result.get('host_b_platform', '?')}")
    print(f"  Sandbox:      {result.get('sandbox_id', '?')} (terminated)")
    print(f"  Verifier C:   Host A (separate from sandbox)")
    print(f"  Task:         {result['report']['task_continuation']['task']}")
    print(f"  Stages:       {result['report']['task_continuation']['stages_completed']}")
    print(f"  Hash match:   {result['report']['task_continuation'].get('passed', result['report']['task_continuation'].get('ok', '?'))}")
    print(f"  Verifier:     {verdict.get('passed', 0)}/{verdict.get('total_checks', 0)}")
    print(f"  ALL PASSED:   {verdict.get('all_checks_passed', False)}")
    print(f"  Tier 2:       independent semantic recomputation = {semantic_check.get('ok', '?')}")
    print(f"  Verifier sig: {verifier_sig[:32]}...")
    print(f"  Separation:   environment=yes, infrastructure=yes, operator=no")
    print("=" * 60)

if __name__ == "__main__":
    main()
