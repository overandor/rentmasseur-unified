#!/usr/bin/env python3
"""Generate a Google Colab notebook with the HDAR deploy package embedded as base64."""

import base64
import json
import os
import tarfile
import io

DEPLOY_DIR = "/Users/alep/Downloads/hdar_second_host_poc/deploy-package"
OUTPUT = "/Users/alep/Downloads/hdar_second_host_poc/HDAR_Cross_Platform_Continuation_Proof.ipynb"

# Create tarball of deploy package
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tf:
    for fname in ["run_on_host_b.py", "transport_capsule_epoch_1_signed.tar.gz",
                  "host_a_build_report.json", "owner_public_key.txt",
                  "third_party_verifier.py", "INSTRUCTIONS.txt"]:
        fpath = os.path.join(DEPLOY_DIR, fname)
        if os.path.exists(fpath):
            tf.add(fpath, arcname=fname)

deploy_b64 = base64.b64encode(buf.getvalue()).decode()

# Read owner public key for embedding
with open(os.path.join(DEPLOY_DIR, "owner_public_key.txt")) as f:
    owner_pub = f.read().strip()

# Read build report for runner hash
with open(os.path.join(DEPLOY_DIR, "host_a_build_report.json")) as f:
    build_report = json.load(f)
    runner_sha = build_report.get("runner_sha256", "")

notebook = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "colab": {"name": "HDAR_Cross_Platform_Continuation_Proof.ipynb"},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"}
    },
    "cells": []
}

def md_cell(source_lines):
    return {"cell_type": "markdown", "metadata": {}, "source": source_lines}

def code_cell(source_lines):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": source_lines}

notebook["cells"].append(md_cell([
    "# HDAR Cross-Platform Continuation Proof — Google Colab Edition\n",
    "\n",
    "This notebook runs the HDAR proof on **Google Colab** (Linux x86_64) as **Host B**.\n",
    "\n",
    "| Role | Platform | Description |\n",
    "|------|----------|-------------|\n",
    "| Host A | macOS arm64 | Built and signed the deploy package |\n",
    "| Host B | Google Colab (Linux x86_64) | Runs the continuation pipeline |\n",
    "| Verifier | Colab (portability test) | Independently verifies with Host A platform = macOS |\n",
    "\n",
    "## Expected Result\n",
    "All 13 checks pass, including `platforms_differ` (macOS vs Linux).\n",
    "\n",
    "## What This Proves\n",
    "1. A workspace state capsule signed on macOS can be continued on Linux\n",
    "2. The 5-stage deterministic pipeline produces identical output hash\n",
    "3. Cryptographic lineage (E1→E2) is verified\n",
    "4. Semantic correctness is independently recomputed (5 predicates)\n",
    "5. Internal stage chain (Merkle-like) is intact\n",
    "6. Evidence packet has independent Ed25519 signature\n",
    "7. Platforms genuinely differ (cross-platform continuation)\n"
]))

notebook["cells"].append(code_cell([
    "# Cell 1: Decode deploy package from embedded base64\n",
    "import base64, os, tarfile, io\n",
    "\n",
    f'DEPLOY_B64 = "{deploy_b64}"\n',
    "\n",
    'os.makedirs("/content/hdar-demo", exist_ok=True)\n',
    'raw = base64.b64decode(DEPLOY_B64)\n',
    'with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:\n',
    '    tf.extractall("/content/hdar-demo")\n',
    '\n',
    'print("Deploy package extracted to /content/hdar-demo/")\n',
    'for f in sorted(os.listdir("/content/hdar-demo")):\n',
    '    print(f"  {f}")'
]))

notebook["cells"].append(code_cell([
    "# Cell 2: Install pinned dependencies\n",
    "!pip install cryptography==44.0.1 -q\n",
    "import cryptography\n",
    'print(f"cryptography {cryptography.__version__} installed")'
]))

notebook["cells"].append(code_cell([
    "# Cell 3: Verify runner integrity\n",
    "import hashlib, json\n",
    "\n",
    'with open("/content/hdar-demo/run_on_host_b.py", "rb") as f:\n',
    '    runner_hash = hashlib.sha256(f.read()).hexdigest()\n',
    "\n",
    f'EXPECTED_RUNNER_SHA = "{runner_sha}"\n',
    "\n",
    'print(f"Runner SHA-256:    {runner_hash}")\n',
    'print(f"Expected SHA-256:  {EXPECTED_RUNNER_SHA}")\n',
    'if runner_hash == EXPECTED_RUNNER_SHA:\n',
    '    print("PASS: Runner hash verified")\n',
    'else:\n',
    '    print("FAIL: RUNNER HASH MISMATCH")\n',
    '    raise SystemExit(1)'
]))

notebook["cells"].append(code_cell([
    "# Cell 4: Run Host B — 5-stage pipeline on Colab (Linux x86_64)\n",
    "import subprocess, json, platform\n",
    "\n",
    'print(f"Host B platform: {platform.platform()}")\n',
    "\n",
    f'OWNER_PUB = "{owner_pub}"\n',
    "\n",
    'cmd = [\n',
    '    "python3", "/content/hdar-demo/run_on_host_b.py",\n',
    '    "--bundle", "transport_capsule_epoch_1_signed.tar.gz",\n',
    '    "--host-a-report", "host_a_build_report.json",\n',
    '    "--owner-public-key", OWNER_PUB,\n',
    '    "--verify-runner-hash", EXPECTED_RUNNER_SHA,\n',
    '    "--host-label", "google-colab-host-b",\n',
    '    "--operator-identity", "google-colab-linux-x86_64",\n',
    '    "--out", "host_b_output"\n',
    ']\n',
    '\n',
    'result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,\n',
    '                       cwd="/content/hdar-demo")\n',
    'print(f"Exit code: {result.returncode}")\n',
    'print("Last 800 chars of output:")\n',
    'print(result.stdout[-800:])\n',
    'if result.returncode != 0:\n',
    '    print("STDERR:", result.stderr[-500:])\n',
    '    raise SystemExit(1)\n',
    '\n',
    '# Parse the report from stdout\n',
    'report = json.loads(result.stdout)\n',
    'tc = report.get("task_continuation", {})\n',
    'print(f"\\nTask: {tc.get(\'task\')}")\n',
    'print(f"Stages: {tc.get(\'stages_completed\')}")\n',
    'print(f"Output hash match: {tc.get(\'computed_output_hash\') == tc.get(\'expected_output_hash\')}")\n',
    'print(f"Platforms differ: {report.get(\'host_b_platform\', \'\') != \'macOS-26.5.2-arm64-arm-64bit-Mach-O\'}")'
]))

notebook["cells"].append(code_cell([
    "# Cell 5: Run the independent verifier (portability test on Colab)\n",
    "import subprocess, json\n",
    "\n",
    '# Host A platform is macOS arm64 (where deploy package was built)\n',
    'HOST_A_PLATFORM = "macOS-26.5.2-arm64-arm-64bit-Mach-O"\n',
    '\n',
    'cmd = [\n',
    '    "python3", "/content/hdar-demo/third_party_verifier.py",\n',
    '    "--capsule-e1", "host_b_output/capsule_epoch_1",\n',
    '    "--capsule-e2", "host_b_output/capsule_epoch_2",\n',
    '    "--host-b-report", "host_b_output/host_b_report.json",\n',
    '    "--evidence-packet", "host_b_output/host_b_evidence_packet.json",\n',
    '    "--owner-public-key", OWNER_PUB,\n',
    '    "--host-a-platform", HOST_A_PLATFORM\n',
    ']\n',
    '\n',
    'result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,\n',
    '                       cwd="/content/hdar-demo")\n',
    '\n',
    'try:\n',
    '    verdict = json.loads(result.stdout)\n',
    '    passed = verdict["passed"]\n',
    '    total = verdict["total_checks"]\n',
    '    all_ok = verdict["all_checks_passed"]\n',
    '    print("=" * 60)\n',
    '    print(f"  VERIFIER RESULT: {passed}/{total} checks passed")\n',
    '    print(f"  ALL PASSED: {all_ok}")\n',
    '    print("=" * 60)\n',
    '    for c in verdict["checks"]:\n',
    '        status = "PASS" if c["ok"] else "FAIL"\n',
    '        print(f"  [{status}] {c[\'check\']:30s} {c[\'reason\'][:70]}")\n',
    '    print()\n',
    '    vb = verdict.get("version_binding", {})\n',
    '    print(f"  Protocol:  {vb.get(\'protocol_version\', \'?\')}")\n',
    '    print(f"  Verifier:  {vb.get(\'verifier_version\', \'?\')}")\n',
    '    print(f"  Worker:    {vb.get(\'worker_version\', \'?\')}")\n',
    '    print(f"  Ruleset:   {vb.get(\'ruleset_version\', \'?\')}")\n',
    '    print(f"  Verifier SHA-256: {verdict.get(\'verifier_sha256\', \'?\')[:32]}...")\n',
    'except json.JSONDecodeError:\n',
    '    print(f"Verifier exit code: {result.returncode}")\n',
    '    print(f"STDOUT: {result.stdout[:2000]}")\n',
    '    print(f"STDERR: {result.stderr[:2000]}")'
]))

notebook["cells"].append(code_cell([
    "# Cell 6: Display lifecycle events from evidence packet\n",
    "import json\n",
    "\n",
    'with open("/content/hdar-demo/host_b_output/host_b_evidence_packet.json") as f:\n',
    '    ep = json.load(f)\n',
    '\n',
    'print("Lifecycle Events:\")\n',
    'print("-" * 80)\n',
    'for event in ep.get("lifecycle_events", []):\n',
    '    print(f"  {event[\'event\']:25s}  {event[\'timestamp\']}  {event[\'detail\'][:50]}")\n',
    '\n',
    'print(f"\\nPost-sign modifications: {ep.get(\'lifecycle_events_post_sign\', False)}")\n',
    'print(f"Evidence packet SHA-256: {ep.get(\'evidence_packet_sha256\', \'?\')[:32]}...")\n',
    'print(f"Host B public key:       {ep.get(\'host_b_public_key\', \'?\')[:32]}...")\n',
    'print(f"Signature algorithm:     {ep.get(\'signature_algorithm\', \'?\')}")'
]))

notebook["cells"].append(code_cell([
    "# Cell 7: Display semantic correctness details\n",
    "import json\n",
    "\n",
    "# Re-read verifier output from cell 5\n",
    'verdict = json.loads(result.stdout)\n',
    'sem = None\n',
    'for c in verdict["checks"]:\n',
    '    if c["check"] == "semantic_correctness":\n',
    '        sem = c\n',
    '        break\n',
    '\n',
    'if sem:\n',
    '    print(f"Semantic Correctness: {\'PASS\' if sem[\'ok\'] else \'FAIL\'}")\n',
    '    print(f"Predicates checked: {sem.get(\'predicates_checked\', 0)}")\n',
    '    print(f"Reason: {sem[\'reason\']}\")\n',
    '    ic = sem.get("independently_computed", {})\n',
    '    print(f"\\nIndependently computed:\")\n',
    '    print(f"  Total records:    {ic.get(\'total_records\', \'?\')}")\n',
    '    print(f"  Valid records:    {ic.get(\'valid_records\', \'?\')}")\n',
    '    print(f"  Rejected records: {ic.get(\'rejected_records\', \'?\')}")\n',
    '    print(f"  Rejected IDs:     {ic.get(\'rejected_ids\', [])}")\n',
    '    print(f"  Categories:       {ic.get(\'categories\', [])}")\n',
    '    print(f"  Category sums:    {ic.get(\'category_sums\', {})}")\n',
    '    print(f"  Category counts:  {ic.get(\'category_counts\', {})}")\n',
    '    print(f"  Tier counts:      {ic.get(\'tier_counts\', {})}")'
]))

notebook["cells"].append(md_cell([
    "## Run Verifier on Host A (Authoritative)\n",
    "\n",
    "After running this notebook, download the results and run the verifier on your Mac (Host A)\n",
    "to get the authoritative post-destruction verdict:\n",
    "\n",
    "1. Run the download cell below to get `hdar-colab-results.tar.gz`\n",
    "2. On your Mac:\n",
    "```bash\n",
    "tar xzf hdar-colab-results.tar.gz\n",
    "python3 deploy-package/third_party_verifier.py \\\n",
    "  --capsule-e1 capsule_epoch_1 \\\n",
    "  --capsule-e2 host_b_output/capsule_epoch_2 \\\n",
    "  --host-b-report host_b_output/host_b_report.json \\\n",
    "  --evidence-packet host_b_output/host_b_evidence_packet.json \\\n",
    "  --owner-public-key $(cat deploy-package/owner_public_key.txt) \\\n",
    "  --host-a-platform \"$(python3 -c 'import platform; print(platform.platform())')\"\n",
    "```\n",
    "\n",
    "This gives the authoritative verdict with the verifier running on a different machine\n",
    "from where Host B executed."
]))

notebook["cells"].append(code_cell([
    "# Cell 8: Download results for Host A verification\n",
    "from google.colab import files\n",
    "import tarfile, os\n",
    "\n",
    'with tarfile.open("/content/hdar-colab-results.tar.gz", "w:gz") as tf:\n',
    '    tf.add("/content/hdar-demo/host_b_output", arcname="host_b_output")\n',
    '    tf.add("/content/hdar-demo/host_b_output/capsule_epoch_1", arcname="capsule_epoch_1")\n',
    '\n',
    'print(f"Results archive: {os.path.getsize(\"/content/hdar-colab-results.tar.gz\")} bytes")\n',
    'files.download("/content/hdar-colab-results.tar.gz")\n',
    'print("\\nDownload started. Run the verifier on your Mac (Host A) for authoritative verdict.")'
]))

with open(OUTPUT, "w") as f:
    json.dump(notebook, f, indent=2)

print(f"Notebook written: {os.path.getsize(OUTPUT)} bytes")
print(f"Embedded deploy package: {len(deploy_b64)} bytes base64")
