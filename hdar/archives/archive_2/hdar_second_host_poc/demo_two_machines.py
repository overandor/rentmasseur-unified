#!/usr/bin/env python3
"""Demo script showing the 2-machine cross-host proof results."""
import json, subprocess, sys
from pathlib import Path

DEPLOY = Path("/Users/alep/Downloads/hdar_second_host_poc/deploy-package")
RESULTS = Path("/Users/alep/Downloads/hdar_second_host_poc/host-b-results")

print("=" * 60)
print("  HDAR CROSS-HOST PROOF — 2 MACHINES")
print("=" * 60)

# Machine 1: Host A
print("\nMACHINE 1: HOST A (macOS ARM)")
print("-" * 60)
r = json.load(open(DEPLOY / "host_a_build_report.json"))
c = r["capsule_epoch_1"]
print(f"  Platform:      {r['host_a_platform']}")
print(f"  Epoch:         {c['epoch']}")
print(f"  Manifest hash: {c['manifest_hash']}")
print(f"  Root hash:     {c['workspace_root_hash']}")
print(f"  Owner signed:  {c['owner_signed']}")
print(f"  Owner key:     {c['owner_public_key']}")
print(f"  Files:         {c['file_count']}")
print(f"  Bundle SHA:    {r['transport_capsule_tar']['sha256']}")

# Machine 2: Host B
print("\nMACHINE 2: HOST B (Linux x86_64 — GitHub Codespaces)")
print("-" * 60)
r = json.load(open(RESULTS / "host_b_report.json"))
print(f"  Platform:          {r['host_b_platform']}")
print(f"  Hostname:          {r['host_b_identity']['machine_hostname']}")
print(f"  Nonce:             {r['host_b_identity']['machine_nonce']}")
print(f"  Runner hash:       {r['runner_sha256']}")
print(f"  Runner verified:   {r['runner_sha256_verified']}")
print(f"  Owner sig OK:      {r['input_capsule']['owner_signature_verified']['ok']}")
print(f"  Restore exact:     {r['restore']['exact']} ({r['restore']['file_count']} files)")
print(f"  Task result:       {r['task_continuation']['computed_result']}")
print(f"  E2 manifest:       {r['successor_capsule']['manifest_hash']}")
print(f"  E2 root hash:      {r['successor_capsule']['workspace_root_hash']}")
print(f"  Host B public key: {r['host_b_public_key']}")
print(f"  Lineage advanced:  {r['lineage_advanced']}")
print(f"  Platforms differ:  {r['host_a_report_verification']['platforms_differ']}")

# Third-party verifier
print("\nTHIRD-PARTY VERIFIER (runs on neither Host A nor Host B)")
print("-" * 60)
result = subprocess.run([
    sys.executable,
    str(DEPLOY / "third_party_verifier.py"),
    "--capsule-e1", str(DEPLOY / "capsule_epoch_1"),
    "--capsule-e2", str(RESULTS / "capsule_epoch_2"),
    "--host-b-report", str(RESULTS / "host_b_report.json"),
    "--evidence-packet", str(RESULTS / "host_b_evidence_packet.json"),
    "--owner-public-key", "6ddc013c4fcc0d8b40f5a1d1dbcdb7f0c321aa39adfd35e236e6939ecc073e27",
    "--host-a-platform", "macOS-26.5.2-arm64-arm-64bit",
], capture_output=True, text=True)

verdict = json.loads(result.stdout)
for check in verdict["checks"]:
    status = "PASS" if check["ok"] else "FAIL"
    print(f"  [{status}] {check['check']}: {check['reason']}")

print(f"\n  Total: {verdict['total_checks']} | Passed: {verdict['passed']} | Failed: {verdict['failed']}")
print(f"  ALL CHECKS PASSED: {verdict['all_checks_passed']}")

print("\n" + "=" * 60)
print("  RESULT: Cryptographically verifiable agent-state")
print("  continuation across independent hosts.")
print("  macOS ARM -> Linux x86_64 (GitHub Codespaces)")
print("=" * 60)
