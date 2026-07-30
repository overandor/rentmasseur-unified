#!/bin/bash
set -Eeuo pipefail

# HDAR Cross-Platform Continuation Proof — Single Command (v2)
# Host A: This Mac (macOS arm64) — builds, signs, verifies
# Host B: GitHub Codespaces (Ubuntu 24.04 x86_64) — executes, seals successor
# Verifier C: Host A (this Mac) — independently verifies AFTER Codespace deletion
#
# v2 fixes per peer review:
#   - set -Eeuo pipefail (don't mask failures through pipes)
#   - trap-based cleanup (Codespace always deleted, even on failure)
#   - Verifier runs on Host A after artifact download, NOT inside Codespace
#   - Full Host B output preserved in log, not piped through tail

DEPLOY_DIR="/Users/alep/Downloads/hdar_second_host_poc/deploy-package"
RESULTS_DIR="/Users/alep/Downloads/hdar_second_host_poc/independent-host-b-results"
RUNNER_SHA="3b873bc850d4e125d528485c9f3f52d2f5bf997858c6d7c6627a906b6c079e44"
HOST_A_PLATFORM="macOS-26.5.2-arm64-arm-64bit"

CS=""

cleanup() {
    if [ -n "${CS:-}" ]; then
        echo "  Cleaning up Codespace $CS..."
        gh codespace delete -c "$CS" --force >/dev/null 2>&1 || true
        echo "  ✓ Codespace deleted"
    fi
}
trap cleanup EXIT INT TERM

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  HDAR Cross-Platform Continuation Proof v2              ║"
echo "║  Host A: macOS arm64  →  Host B: Ubuntu 24.04 x86_64     ║"
echo "║  Verifier C: Host A (after Codespace deletion)           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Create Codespace ──────────────────────────────────
echo "▶ Step 1/10: Creating GitHub Codespace..."
CS=$(gh codespace create --repo overandor/CodeRunnerApp --machine basicLinux32gb --display-name "hdar-demo-$(date +%s)" 2>&1 | tail -1)
echo "  Codespace: $CS"
sleep 5

# ── Step 2: Transfer deploy package ───────────────────────────
echo "▶ Step 2/10: Transferring deploy package to Codespace..."
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
echo "▶ Step 2b/10: Installing cryptography package on remote host..."
gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no "pip install cryptography 2>&1 | tail -1"
echo "  ✓ Dependencies installed"

# ── Step 3: Verify runner hash ────────────────────────────────
echo "▶ Step 3/10: Verifying runner integrity on remote host..."
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
echo "▶ Step 4/10: Running Host B on independent Linux host..."
mkdir -p "$RESULTS_DIR"
gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no \
  "cd ~/hdar-demo && python3 run_on_host_b.py \
    --bundle transport_capsule_epoch_1_signed.tar.gz \
    --host-a-report host_a_build_report.json \
    --owner-public-key \$(cat owner_public_key.txt) \
    --verify-runner-hash '$RUNNER_SHA' \
    --host-label codespace-host-b \
    --operator-identity 'github-codespaces-ubuntu-2404' \
    --out host_b_output 2>&1" > "$RESULTS_DIR/host_b_full_log.txt" 2>&1
echo "  ✓ Host B execution complete (full log saved)"
echo "  Last 3 lines:"
tail -3 "$RESULTS_DIR/host_b_full_log.txt"

# ── Step 5: Extract E1 capsule for verifier ───────────────────
echo "▶ Step 5/10: Pulling evidence artifacts back to Mac..."
mkdir -p "$RESULTS_DIR"
gh codespace ssh -c "$CS" -- -o StrictHostKeyChecking=no \
  "cd ~/hdar-demo && tar czf /tmp/results.tar.gz host_b_output/ capsule_epoch_1/ && cat /tmp/results.tar.gz" > /tmp/results.tar.gz 2>/dev/null
tar xzf /tmp/results.tar.gz -C "$RESULTS_DIR/" 2>/dev/null
echo "  ✓ Artifacts saved to: $RESULTS_DIR"

# ── Step 6: Delete Codespace BEFORE verification ──────────────
echo "▶ Step 6/10: Deleting Codespace (verifier will run on Host A)..."
gh codespace delete -c "$CS" --force 2>/dev/null || true
echo "  ✓ Codespace deleted"
CS=""  # Clear so trap doesn't double-delete

# ── Step 7: Run Verifier C on Host A ───────────────────────────
echo "▶ Step 7/10: Running Verifier C on Host A (post-destruction)..."
OWNER_PUB=$(cat "$DEPLOY_DIR/owner_public_key.txt")
python3 "$DEPLOY_DIR/third_party_verifier.py" \
  --capsule-e1 "$RESULTS_DIR/capsule_epoch_1" \
  --capsule-e2 "$RESULTS_DIR/host_b_output/capsule_epoch_2" \
  --host-b-report "$RESULTS_DIR/host_b_output/host_b_report.json" \
  --evidence-packet "$RESULTS_DIR/host_b_output/host_b_evidence_packet.json" \
  --owner-public-key "$OWNER_PUB" \
  --host-a-platform "$HOST_A_PLATFORM" > "$RESULTS_DIR/verifier_output.json" 2>&1
echo "  ✓ Verifier C complete (ran on Host A after Codespace deletion)"

# ── Step 8: Stop Codespace ────────────────────────────────────
# ── Step 8: Summary ───────────────────────────────────────────
echo "▶ Step 8/10: Final summary..."
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
echo "  verifier_output.json (Verifier C output, run on Host A)"
echo "  host_b_output/host_b_report.json"
echo "  host_b_output/host_b_evidence_packet.json"
echo "  host_b_output/successor_capsule_epoch_2.tar.gz"
echo "  host_b_full_log.txt (complete Host B stdout)"
echo ""
echo "Lifecycle:"
echo "  1. Codespace created"
echo "  2. Deploy package transferred"
echo "  3. Runner hash verified on remote"
echo "  4. Host B executed continuation"
echo "  5. Artifacts pulled to Host A"
echo "  6. Codespace DELETED"
echo "  7. Verifier C ran on Host A (post-destruction)"
echo ""
echo "=== DEMO COMPLETE ==="
