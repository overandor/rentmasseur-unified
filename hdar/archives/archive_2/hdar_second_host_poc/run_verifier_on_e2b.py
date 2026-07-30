#!/usr/bin/env python3
"""Run the third-party verifier inside an E2B sandbox to test verifier portability.

This proves the verifier is not tied to Host A's platform — it can run on
a completely different OS/architecture and produce the same verdict.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BUILD_DIR = BASE_DIR / "_e2b_build"
RESULTS_DIR = BASE_DIR / "codespace-results"
REMOTE_DIR = "/home/user/hdar-verify"


def main():
    from e2b import Sandbox

    # Read owner key from the host_b_report (since this run used a different ephemeral key)
    host_b_report = json.loads((RESULTS_DIR / "host_b_output" / "host_b_report.json").read_text())
    owner_key = host_b_report["input_capsule"]["owner_signature_verified"]["owner_public_key"]
    host_a_platform = platform.platform()

    print("=== E2B VERIFIER PORTABILITY TEST ===")
    print(f"Host A platform: {host_a_platform}")
    print()

    sbx = None
    sandbox_id = "unknown"
    try:
        sbx = Sandbox.create()
        sandbox_id = sbx.sandbox_id
        print(f"Sandbox: {sandbox_id}")
        r = sbx.commands.run("uname -a")
        print(f"Platform: {r.stdout.strip()}")
        print()

        # Install pinned cryptography
        print("Installing pinned cryptography==44.0.1...")
        r = sbx.commands.run("pip install cryptography==44.0.1 -q")
        print(f"  exit: {r.exit_code}")
        print()

        # Create remote directory structure
        print("Creating remote directories...")
        sbx.commands.run(f"mkdir -p {REMOTE_DIR}/capsule_epoch_1/blocks")
        sbx.commands.run(f"mkdir -p {REMOTE_DIR}/capsule_epoch_2/blocks")

        # Collect all files to upload
        files_to_upload = []

        # Verifier script
        files_to_upload.append((
            str(BUILD_DIR / "third_party_verifier.py"),
            f"{REMOTE_DIR}/third_party_verifier.py",
        ))

        # Write owner key file for the sandbox
        sbx.files.write(f"{REMOTE_DIR}/owner_public_key.txt", owner_key.encode())

        # Host B report (from Codespace run)
        files_to_upload.append((
            str(RESULTS_DIR / "host_b_output" / "host_b_report.json"),
            f"{REMOTE_DIR}/host_b_report.json",
        ))

        # Evidence packet
        files_to_upload.append((
            str(RESULTS_DIR / "host_b_output" / "host_b_evidence_packet.json"),
            f"{REMOTE_DIR}/host_b_evidence_packet.json",
        ))

        # E1 capsule (from the codespace run's output)
        e1_dir = RESULTS_DIR / "capsule_epoch_1"
        files_to_upload.append((
            str(e1_dir / "manifest.json"),
            f"{REMOTE_DIR}/capsule_epoch_1/manifest.json",
        ))
        files_to_upload.append((
            str(e1_dir / "receipt.json"),
            f"{REMOTE_DIR}/capsule_epoch_1/receipt.json",
        ))
        for block_path in (e1_dir / "blocks").rglob("*"):
            if block_path.is_file():
                rel = block_path.relative_to(e1_dir / "blocks")
                remote_subdir = f"{REMOTE_DIR}/capsule_epoch_1/blocks/{rel.parent}"
                sbx.commands.run(f"mkdir -p {remote_subdir}")
                files_to_upload.append((
                    str(block_path),
                    f"{REMOTE_DIR}/capsule_epoch_1/blocks/{rel}",
                ))

        # E2 capsule (from Codespace run)
        e2_dir = RESULTS_DIR / "host_b_output" / "capsule_epoch_2"
        files_to_upload.append((
            str(e2_dir / "manifest.json"),
            f"{REMOTE_DIR}/capsule_epoch_2/manifest.json",
        ))
        files_to_upload.append((
            str(e2_dir / "receipt.json"),
            f"{REMOTE_DIR}/capsule_epoch_2/receipt.json",
        ))
        for block_path in (e2_dir / "blocks").rglob("*"):
            if block_path.is_file():
                rel = block_path.relative_to(e2_dir / "blocks")
                remote_subdir = f"{REMOTE_DIR}/capsule_epoch_2/blocks/{rel.parent}"
                sbx.commands.run(f"mkdir -p {remote_subdir}")
                files_to_upload.append((
                    str(block_path),
                    f"{REMOTE_DIR}/capsule_epoch_2/blocks/{rel}",
                ))

        # Upload all files
        print(f"Uploading {len(files_to_upload)} files to sandbox...")
        for local_path, remote_path in files_to_upload:
            sbx.files.write(remote_path, open(local_path, "rb").read())
        print("  All files uploaded.")
        print()

        # Verify file count on remote
        r = sbx.commands.run(f"find {REMOTE_DIR} -type f | wc -l")
        print(f"Remote file count: {r.stdout.strip()}")
        print()

        # Run the verifier on the sandbox
        # Note: --sandbox-terminated is passed because the Codespace (where Host B ran)
        # was already terminated. The verifier runs on E2B here, which is a third
        # independent platform — neither Host A nor the Codespace.
        print("=== RUNNING VERIFIER ON E2B SANDBOX ===")
        cmd = (
            f"cd {REMOTE_DIR} && "
            f"OWNER_KEY=$(cat owner_public_key.txt) && "
            f"python3 third_party_verifier.py "
            f"  --capsule-e1 {REMOTE_DIR}/capsule_epoch_1 "
            f"  --capsule-e2 {REMOTE_DIR}/capsule_epoch_2 "
            f"  --host-b-report {REMOTE_DIR}/host_b_report.json "
            f"  --evidence-packet {REMOTE_DIR}/host_b_evidence_packet.json "
            f"  --owner-public-key $OWNER_KEY "
            f"  --host-a-platform '{host_a_platform}' "
            f"  --sandbox-id github-codespace-refactored-train "
            f"  --sandbox-terminated"
        )
        r = sbx.commands.run(cmd, timeout=60)
        print(r.stdout)
        if r.stderr:
            print("STDERR:", r.stderr)
        print(f"Verifier exit code: {r.exit_code}")
        print()

        # Save the verifier output
        output_path = RESULTS_DIR / "verifier_output_e2b.json"
        output_path.write_text(r.stdout)
        print(f"Verifier output saved to: {output_path}")

        # Parse and summarize
        try:
            verdict = json.loads(r.stdout)
            passed = verdict.get("passed", 0)
            total = verdict.get("total_checks", 0)
            all_passed = verdict.get("all_checks_passed", False)
            print()
            print(f"  Verifier on E2B: {passed}/{total} checks passed. ALL: {all_passed}")
        except json.JSONDecodeError:
            print("  Warning: could not parse verifier output as JSON")

    finally:
        if sbx is not None:
            print()
            print("=== SANDBOX SHUTDOWN ===")
            try:
                sbx.kill()
                print(f"  Sandbox {sandbox_id} terminated.")
            except Exception as e:
                print(f"  Shutdown error: {e}")

    print()
    print("=== PORTABILITY TEST COMPLETE ===")


if __name__ == "__main__":
    main()
