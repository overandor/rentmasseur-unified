#!/bin/bash
set -e

# HDAR Two-Machine Demo — Single Command
# Host A: This Mac (macOS arm64)
# Host B: GitHub Codespaces (Ubuntu 24.04 x86_64)
# Verifier C: Same Codespaces instance (operationally separate from Host A)

DEPLOY_DIR="/Users/alep/Downloads/hdar_second_host_poc/deploy-package"
RESULTS_DIR="/Users/alep/Downloads/hdar_second_host_poc/independent-host-b-results"
RUNNER_SHA="44fbf48bd96253da7e014d0c01eaf67ee444da61c07039b95296d47a7a6b80fa"
HOST_A_PLATFORM="macOS-26.5.2-arm64-arm-64bit"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  HDAR Two-Machine Demo                                   ║"
echo "║  Host A: macOS arm64  →  Host B: Ubuntu 24.04 x86_64     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Create Codespace ──────────────────────────────────
echo "▶ Step 1/9: Creating GitHub Codespace..."
CS=$(gh codespace create --repo overandor/CodeRunnerApp --machine basicLinux32gb --display-name "hdar-demo-$(date +%s)" 2>&1 | tail -1)
echo "  Codespace: $CS"
sleep 5

# ── Step 2: Transfer deploy package ───────────────────────────
echo "▶ Step 2/9: Transferring deploy package to Codespace..."
cd "$DEPLOY_DIR"
tar czf /tmp/hdar-deploy-files.tar.gz \
  run_on_host_b.py \
  transport_capsule_epoch_1_signed.tar.gz \
  host_a_build_report.json \
  owner_public_key.txt \
  third_party_verifier.py \
  INSTRUCTIONS.txt
cat /tmp/hdar-deploy-files.tar.gz | base64 | gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no \
  "mkdir -p ~/hdar-demo && cd ~/hdar-demo && base64 -d | tar xzf - 2>/dev/null"
echo "  Files transferred"

# ── Step 2b: Install dependencies ─────────────────────────────
echo "▶ Step 2b/9: Installing cryptography package on remote host..."
gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no "pip install cryptography 2>&1 | tail -1"
echo "  ✓ Dependencies installed"

# ── Step 3: Verify runner hash ────────────────────────────────
echo "▶ Step 3/9: Verifying runner integrity on remote host..."
REMOTE_HASH=$(gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no \
  "sha256sum ~/hdar-demo/run_on_host_b.py | cut -d' ' -f1")
echo "  Expected: $RUNNER_SHA"
echo "  Actual:   $REMOTE_HASH"
if [ "$REMOTE_HASH" != "$RUNNER_SHA" ]; then
  echo "  ✗ RUNNER HASH MISMATCH — aborting"
  gh codespace stop -c "$CS" 2>/dev/null
  exit 1
fi
echo "  ✓ Runner hash verified"

# ── Step 4: Run Host B ────────────────────────────────────────
echo "▶ Step 4/9: Running Host B on independent Linux host..."
gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no \
  "cd ~/hdar-demo && python3 run_on_host_b.py \
    --bundle transport_capsule_epoch_1_signed.tar.gz \
    --host-a-report host_a_build_report.json \
    --owner-public-key \$(cat owner_public_key.txt) \
    --verify-runner-hash '$RUNNER_SHA' \
    --host-label codespace-host-b \
    --operator-identity 'github-codespaces-ubuntu-2404' \
    --out host_b_output 2>&1" | tail -3
echo "  ✓ Host B execution complete"

# ── Step 5: Extract E1 capsule for verifier ───────────────────
echo "▶ Step 5/9: Preparing capsules for verifier..."
gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no \
  "cd ~/hdar-demo && mkdir -p capsule_epoch_1 && tar xzf transport_capsule_epoch_1_signed.tar.gz -C capsule_epoch_1 --strip-components=1 2>/dev/null"
echo "  ✓ Capsules ready"

# ── Step 6: Run Verifier C ────────────────────────────────────
echo "▶ Step 6/9: Running third-party verifier (11 checks)..."
gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no \
  "cd ~/hdar-demo && python3 third_party_verifier.py \
    --capsule-e1 capsule_epoch_1 \
    --capsule-e2 host_b_output/capsule_epoch_2 \
    --host-b-report host_b_output/host_b_report.json \
    --evidence-packet host_b_output/host_b_evidence_packet.json \
    --owner-public-key \$(cat owner_public_key.txt) \
    --host-a-platform '$HOST_A_PLATFORM' 2>&1"
echo ""

# ── Step 7: Pull results back to Mac ──────────────────────────
echo "▶ Step 7/9: Pulling evidence artifacts back to Mac..."
mkdir -p "$RESULTS_DIR"
gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no \
  "cd ~/hdar-demo && python3 third_party_verifier.py \
    --capsule-e1 capsule_epoch_1 \
    --capsule-e2 host_b_output/capsule_epoch_2 \
    --host-b-report host_b_output/host_b_report.json \
    --evidence-packet host_b_output/host_b_evidence_packet.json \
    --owner-public-key \$(cat owner_public_key.txt) \
    --host-a-platform '$HOST_A_PLATFORM' 2>/dev/null" > "$RESULTS_DIR/verifier_output.json" 2>/dev/null
gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no \
  "cd ~/hdar-demo && tar czf /tmp/results.tar.gz host_b_output/ capsule_epoch_1/ && cat /tmp/results.tar.gz" > /tmp/results.tar.gz 2>/dev/null
tar xzf /tmp/results.tar.gz -C "$RESULTS_DIR/" 2>/dev/null
echo "  ✓ Artifacts saved to: $RESULTS_DIR"

# ── Step 8: Stop Codespace ────────────────────────────────────
echo "▶ Step 8/9: Stopping Codespace to preserve free hours..."
gh codespace stop -c "$CS" 2>/dev/null
echo "  ✓ Codespace stopped"

# ── Step 9: Summary ───────────────────────────────────────────
echo "▶ Step 9/9: Final summary..."
echo ""
python3 -c "
import json
d = json.load(open('$RESULTS_DIR/verifier_output.json'))
print('╔══════════════════════════════════════════════════════════╗')
print(f'║  VERIFIER RESULT: {d[\"passed\"]}/{d[\"total_checks\"]} checks passed              ║')
print(f'║  all_checks_passed: {str(d[\"all_checks_passed\"]).ljust(5)}                         ║')
print('╠══════════════════════════════════════════════════════════╣')
for c in d['checks']:
    status = '✓' if c['ok'] else '✗'
    print(f'║  {status} {c[\"check\"]:30s} {c[\"reason\"]}')
print('╚══════════════════════════════════════════════════════════╝')
"
echo ""
echo "Artifacts: $RESULTS_DIR/"
echo "  verifier_output.json"
echo "  host_b_output/host_b_report.json"
echo "  host_b_output/host_b_evidence_packet.json"
echo "  host_b_output/successor_capsule_epoch_2.tar.gz"
echo ""
echo "=== DEMO COMPLETE ==="
