#!/usr/bin/env python3
"""
HDAR Cross-Platform Continuation Proof — Google Colab Edition

This script simulates what the Colab notebook (hdar_host_b_colab.ipynb) does,
but can be run from the command line. It:

1. Builds a fresh deploy package on Host A (this Mac)
2. Runs Host B execution locally in a simulated Colab Linux environment
   (using the same run_on_host_b.py runner)
3. Runs Verifier C on Host A after Host B completes

For actual Colab execution, open hdar_host_b_colab.ipynb in Google Colab
and upload the deploy package files. This script produces equivalent artifacts
and can be used to verify the pipeline works before uploading to Colab.

Usage:
    python3 run_colab_proof.py [--reuse-build]
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
DEPLOY_DIR = HERE / "deploy-package"
BUILD_DIR = HERE / "_colab_build"
RESULTS_DIR = HERE / "colab-results"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_package(out_dir: Path, runner_template: Path, verifier_template: Path, owner_key_file: str = "") -> dict:
    """Build deploy package using the same build_deploy_package.py logic."""
    build_script = DEPLOY_DIR / "build_deploy_package.py"
    cmd = [sys.executable, str(build_script), "--out", str(out_dir)]
    if owner_key_file:
        cmd.extend(["--owner-key-file", owner_key_file])

    print(f"  Building deploy package...")
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(DEPLOY_DIR))
    if r.returncode != 0:
        print(f"  BUILD ERROR: {r.stderr}")
        sys.exit(1)
    print(f"  Build complete")

    # Read build outputs
    owner_pub = (out_dir / "owner_public_key.txt").read_text().strip()
    runner_hash = sha256_file(out_dir / "run_on_host_b.py")

    # Read the build report for manifest hash
    build_report = json.loads((out_dir / "host_a_build_report.json").read_text())
    manifest_hash = build_report.get("capsule_epoch_1", {}).get("manifest_hash", "?")

    return {
        "owner_key": owner_pub,
        "runner_sha256": runner_hash,
        "manifest_hash": manifest_hash,
    }


def run_host_b_simulated(deploy_dir: Path, owner_key: str, runner_hash: str, host_a_platform: str) -> dict:
    """Run Host B execution simulating Colab Linux environment.

    In real Colab, this would run on Google's Linux VMs.
    Here we run locally but label it as a Colab simulation.
    """
    runner = deploy_dir / "run_on_host_b.py"
    capsule = deploy_dir / "transport_capsule_epoch_1_signed.tar.gz"
    host_a_report = deploy_dir / "host_a_build_report.json"

    out_dir = RESULTS_DIR / "host_b_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(runner),
        "--bundle", str(capsule),
        "--host-a-report", str(host_a_report),
        "--owner-public-key", owner_key,
        "--verify-runner-hash", runner_hash,
        "--host-label", "colab-linux-simulation",
        "--operator-identity", "google-colab-simulated",
        "--out", str(out_dir),
    ]

    print(f"  Running Host B (Colab simulation)...")
    print(f"  Platform: {platform.platform()}")

    # Save full output
    log_path = RESULTS_DIR / "host_b_full_log.txt"
    r = subprocess.run(cmd, capture_output=True, text=True)
    log_path.write_text(r.stdout + "\n" + r.stderr)

    if r.returncode != 0:
        print(f"  HOST B ERROR (exit {r.returncode})")
        print(f"  Last 5 lines: {r.stdout[-500:]}")
        sys.exit(1)

    # Load report
    report_path = out_dir / "host_b_report.json"
    if not report_path.exists():
        print(f"  ERROR: host_b_report.json not found at {report_path}")
        sys.exit(1)

    report = json.loads(report_path.read_text())
    print(f"  Host B complete: {report.get('host_b_platform', '?')}")
    print(f"  Task: {report.get('task_continuation', {}).get('task', '?')}")
    print(f"  Stages: {report.get('task_continuation', {}).get('stages_completed', '?')}")

    return {"report": report, "out_dir": out_dir}


def run_verifier_on_host_a(deploy_dir: Path, owner_key: str, host_a_platform: str) -> dict:
    """Run Verifier C on Host A after Host B completes."""
    verifier_path = deploy_dir / "third_party_verifier.py"

    # Extract E1 capsule for verifier
    e1_dir = RESULTS_DIR / "capsule_epoch_1"
    if not e1_dir.exists():
        import tarfile
        e1_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(deploy_dir / "transport_capsule_epoch_1_signed.tar.gz", "r:gz") as tf:
            tf.extractall(e1_dir)
            # Handle potential nested directory
            children = list(e1_dir.iterdir())
            if len(children) == 1 and children[0].is_dir():
                nested = children[0]
                for item in nested.iterdir():
                    shutil.move(str(item), str(e1_dir / item.name))
                nested.rmdir()

    e2_dir = RESULTS_DIR / "host_b_output" / "capsule_epoch_2"
    host_b_report = RESULTS_DIR / "host_b_output" / "host_b_report.json"
    evidence_packet = RESULTS_DIR / "host_b_output" / "host_b_evidence_packet.json"

    print(f"\n=== VERIFIER C (RUNNING ON HOST A) ===")
    print(f"  Verifier: {verifier_path}")
    print(f"  E1 capsule: {e1_dir}")
    print(f"  E2 capsule: {e2_dir}")

    cmd = [
        sys.executable, str(verifier_path),
        "--capsule-e1", str(e1_dir),
        "--capsule-e2", str(e2_dir),
        "--host-b-report", str(host_b_report),
        "--evidence-packet", str(evidence_packet),
        "--owner-public-key", owner_key,
        "--host-a-platform", host_a_platform,
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    # Verifier exits 1 when any check fails (e.g. platforms_differ on local sim)
    # This is expected — parse the JSON output regardless of exit code
    try:
        verdict = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"  VERIFIER ERROR (exit {r.returncode}): {r.stderr[:500]}")
        return {"error": r.stderr, "all_checks_passed": False}

    with open(RESULTS_DIR / "verifier_output.json", "w") as f:
        json.dump(verdict, f, indent=2, sort_keys=True)

    for c in verdict["checks"]:
        s = "PASS" if c["ok"] else "FAIL"
        print(f"  [{s}] {c['check']}: {c['reason']}")
    print(f"\n  {verdict['passed']}/{verdict['total_checks']} passed. ALL: {verdict['all_checks_passed']}")

    return verdict


def main():
    ap = argparse.ArgumentParser(description="HDAR Colab Proof — Local Simulation")
    ap.add_argument("--reuse-build", action="store_true", help="Reuse existing build in _colab_build/")
    args = ap.parse_args()

    host_a_platform = platform.platform()

    runner_template = DEPLOY_DIR / "run_on_host_b.py"
    verifier_template = DEPLOY_DIR / "third_party_verifier.py"

    if args.reuse_build and (BUILD_DIR / "run_on_host_b.py").exists():
        print("Reusing existing build...")
        owner_key = (BUILD_DIR / "owner_public_key.txt").read_text().strip()
        runner_hash = sha256_file(BUILD_DIR / "run_on_host_b.py")
    else:
        print("=== PHASE 1: BUILDING DEPLOY PACKAGE ON HOST A ===")
        if BUILD_DIR.exists():
            shutil.rmtree(BUILD_DIR)
        info = build_package(BUILD_DIR, runner_template, verifier_template)
        owner_key = info["owner_key"]
        runner_hash = info["runner_sha256"]
        print(f"  Owner key (public): {owner_key}")
        print(f"  Runner SHA-256: {runner_hash}")

    print("\n=== PHASE 2: HOST B EXECUTION (COLAB SIMULATION) ===")
    result = run_host_b_simulated(BUILD_DIR, owner_key, runner_hash, host_a_platform)

    print("\n=== PHASE 3: VERIFIER C ON HOST A ===")
    verdict = run_verifier_on_host_a(BUILD_DIR, owner_key, host_a_platform)

    # Final manifest
    packet_manifest = {
        "schema": "hdar.proof-packet/v0.2",
        "substrate": "google-colab-simulation",
        "host_a_platform": host_a_platform,
        "host_b_platform": result["report"].get("host_b_platform", "?"),
        "owner_public_key": owner_key,
        "runner_sha256": runner_hash,
        "task": result["report"]["task_continuation"]["task"],
        "stages_completed": result["report"]["task_continuation"]["stages_completed"],
        "verifier_passed": verdict.get("passed", 0),
        "verifier_total": verdict.get("total_checks", 0),
        "verifier_all_passed": verdict.get("all_checks_passed", False),
        "verifier_location": "host_a",
        "note": "Simulated Colab execution. For real Colab, open hdar_host_b_colab.ipynb in Google Colab.",
    }
    with open(RESULTS_DIR / "proof_packet_manifest.json", "w") as f:
        json.dump(packet_manifest, f, indent=2, sort_keys=True)

    print("\n" + "=" * 60)
    print("  HDAR COLAB PROOF — COMPLETE")
    print("=" * 60)
    print(f"  Host A:       {host_a_platform}")
    print(f"  Host B:       {result['report'].get('host_b_platform', '?')}")
    print(f"  Verifier C:   Host A")
    print(f"  Verifier:     {verdict.get('passed', 0)}/{verdict.get('total_checks', 0)}")
    print(f"  ALL PASSED:   {verdict.get('all_checks_passed', False)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
