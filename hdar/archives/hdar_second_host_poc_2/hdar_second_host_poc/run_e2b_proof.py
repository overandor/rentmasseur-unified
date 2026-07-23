#!/usr/bin/env python3
"""Run HDAR proof on E2B cloud sandbox — real independent Linux machine."""
import json
import os
from e2b import Sandbox

DEPLOY = "deploy-package-v2"
RESULTS = "e2b-results"
OWNER_KEY = open(f"{DEPLOY}/owner_public_key.txt").read().strip()
RUNNER_HASH = "0c5b3d752f6d8dba9a7d1c838b8d0f698f4d662e1ff3262f80be2fbe2bb06618"

os.makedirs(RESULTS, exist_ok=True)

sbx = Sandbox.create()
print(f"Sandbox: {sbx.sandbox_id}")
r = sbx.commands.run("uname -a")
print(f"Platform: {r.stdout.strip()}")

# Install cryptography
print("Installing cryptography...")
sbx.commands.run("pip install cryptography -q", timeout=60)

# Upload files
print("Uploading files...")
for name, path in [
    ("run_on_host_b.py", f"{DEPLOY}/run_on_host_b.py"),
    ("host_a_build_report.json", f"{DEPLOY}/host_a_build_report.json"),
    ("owner_public_key.txt", f"{DEPLOY}/owner_public_key.txt"),
    ("third_party_verifier.py", f"{DEPLOY}/third_party_verifier.py"),
]:
    sbx.files.write(f"/home/user/{name}", open(path).read())
    print(f"  {name}")

with open(f"{DEPLOY}/transport_capsule_epoch_1_signed.tar.gz", "rb") as f:
    sbx.files.write("/home/user/transport_capsule_epoch_1_signed.tar.gz", f.read())
print("  transport_capsule_epoch_1_signed.tar.gz")

# Verify runner hash
r = sbx.commands.run("sha256sum /home/user/run_on_host_b.py")
print(f"\nRunner hash: {r.stdout.strip()}")

# Run Host B
print("\n=== HOST B EXECUTION ===")
cmd = (
    f'python3 /home/user/run_on_host_b.py '
    f'--out /tmp/hdar-output '
    f'--host-label "e2b-cloud-sandbox" '
    f'--host-a-report /home/user/host_a_build_report.json '
    f'--verify-runner-hash "{RUNNER_HASH}" '
    f'--owner-public-key "{OWNER_KEY}" '
    f'--operator-identity "e2b-cloud" '
    f'--network-source "e2b-sandbox-api"'
)
r = sbx.commands.run(cmd, timeout=60)
report = json.loads(r.stdout)
tc = report["task_continuation"]
hv = report["host_a_report_verification"]
print(f"Task: {tc['task']}")
print(f"Stages: {tc['stages_completed']}")
print(f"Output hash match: {tc['passed']}")
print(f"Platforms differ: {hv['platforms_differ']}")
print(f"Restore exact: {report['restore']['exact']}")
print(f"Host B: {report['host_b_platform']}")
print(f"Owner sig: {report['input_capsule']['owner_signature_verified']['ok']}")

# Extract E1 capsule for verifier
sbx.commands.run("cd /home/user && tar xzf transport_capsule_epoch_1_signed.tar.gz")

# Run verifier
print("\n=== VERIFIER ===")
vcmd = (
    f'python3 /home/user/third_party_verifier.py '
    f'--capsule-e1 /home/user/capsule_epoch_1 '
    f'--capsule-e2 /tmp/hdar-output/capsule_epoch_2 '
    f'--host-b-report /tmp/hdar-output/host_b_report.json '
    f'--evidence-packet /tmp/hdar-output/host_b_evidence_packet.json '
    f'--owner-public-key "{OWNER_KEY}" '
    f'--host-a-platform "macOS-26.5.2-arm64-arm-64bit"'
)
r = sbx.commands.run(vcmd, timeout=60)
verdict = json.loads(r.stdout)
for c in verdict["checks"]:
    s = "PASS" if c["ok"] else "FAIL"
    print(f"  [{s}] {c['check']}: {c['reason']}")
print(f"\n  {verdict['passed']}/{verdict['total_checks']} passed. ALL: {verdict['all_checks_passed']}")

# Download artifacts
print("\n=== DOWNLOADING ARTIFACTS ===")
with open(f"{RESULTS}/host_b_report.json", "w") as f:
    f.write(sbx.files.read("/tmp/hdar-output/host_b_report.json"))
print("  host_b_report.json")
with open(f"{RESULTS}/host_b_evidence_packet.json", "w") as f:
    f.write(sbx.files.read("/tmp/hdar-output/host_b_evidence_packet.json"))
print("  host_b_evidence_packet.json")
e2tar = sbx.files.read("/tmp/hdar-output/successor_capsule_epoch_2.tar.gz", format="bytes")
with open(f"{RESULTS}/successor_capsule_epoch_2.tar.gz", "wb") as f:
    f.write(e2tar)
print(f"  successor_capsule_epoch_2.tar.gz ({len(e2tar)} bytes)")

print("\n=== PROOF COMPLETE ===")
print(f"Host A: macOS-26.5.2-arm64-arm-64bit-Mach-O")
print(f"Host B: {report['host_b_platform']}")
print(f"Sandbox: {sbx.sandbox_id}")
print(f"Verifier: {verdict['passed']}/{verdict['total_checks']}")
print(f"All passed: {verdict['all_checks_passed']}")
