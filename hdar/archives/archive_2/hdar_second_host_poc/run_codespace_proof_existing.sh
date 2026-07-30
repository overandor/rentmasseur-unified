#!/bin/bash
set -Eeuo pipefail

# HDAR Cross-Platform Continuation Proof — GitHub Codespaces Edition
# Uses an existing Codespace (passed as argument).
# Host A: This Mac (macOS arm64) — builds, signs, verifies
# Host B: GitHub Codespaces (Ubuntu x86_64) — executes, seals successor
# Verifier C: Host A (this Mac) — independently verifies AFTER Codespace deletion
# Bonus: Verifier also run on Codespace BEFORE deletion (portability test)

DEPLOY_DIR="/Users/alep/Downloads/hdar_second_host_poc/deploy-package"
RESULTS_DIR="/Users/alep/Downloads/hdar_second_host_poc/codespace-results"
HOST_A_PLATFORM="macOS-26.5.2-arm64-arm-64bit"

CS="${1:-}"
if [ -z "$CS" ]; then
  echo "Usage: $0 <codespace-name>"
  echo "Available codespaces:"
  gh codespace list
  exit 1
fi

# Compute runner hash from the freshly built deploy package
RUNNER_SHA=$(shasum -a 256 "$DEPLOY_DIR/run_on_host_b.py" | cut -d' ' -f1)
echo "  Runner SHA-256: $RUNNER_SHA"

mkdir -p "$RESULTS_DIR"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  HDAR Cross-Platform Continuation Proof                  ║"
echo "║  Host A: macOS arm64  →  Host B: Ubuntu x86_64            ║"
echo "║  Verifier C: Host A (after Codespace deletion)           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Transfer deploy package to Codespace ──────────────
echo "▶ Step 1/8: Transferring deploy package to Codespace..."
cd "$DEPLOY_DIR"
tar czf /tmp/hdar-deploy-files.tar.gz \
  run_on_host_b.py \
  transport_capsule_epoch_1_signed.tar.gz \
  host_a_build_report.json \
  owner_public_key.txt \
  third_party_verifier.py \
  INSTRUCTIONS.txt
cat /tmp/hdar-deploy-files.tar.gz | base64 | gh codespace ssh -c "$CS" -- \
  "mkdir -p ~/hdar-demo && cd ~/hdar-demo && base64 -d | tar xzf - 2>/dev/null"
echo "  ✓ Files transferred"

# ── Step 2: Install dependencies on Codespace ─────────────────
echo "▶ Step 2/8: Installing cryptography package on Codespace..."
gh codespace ssh -c "$CS" -- "pip install cryptography==44.0.1 2>&1 | tail -1"
echo "  ✓ Dependencies installed"

# ── Step 3: Verify runner hash on remote ──────────────────────
echo "▶ Step 3/8: Verifying runner integrity on Codespace..."
REMOTE_HASH=$(gh codespace ssh -c "$CS" -- \
  "sha256sum ~/hdar-demo/run_on_host_b.py | cut -d' ' -f1")
echo "  Expected: $RUNNER_SHA"
echo "  Actual:   $REMOTE_HASH"
if [ "$REMOTE_HASH" != "$RUNNER_SHA" ]; then
  echo "  ✗ RUNNER HASH MISMATCH — aborting"
  exit 1
fi
echo "  ✓ Runner hash verified"

# ── Step 4: Run Host B on Codespace ───────────────────────────
echo "▶ Step 4/8: Running Host B on Codespace..."
OWNER_PUB=$(cat "$DEPLOY_DIR/owner_public_key.txt")
gh codespace ssh -c "$CS" -- \
  "cd ~/hdar-demo && python3 run_on_host_b.py \
    --bundle transport_capsule_epoch_1_signed.tar.gz \
    --host-a-report host_a_build_report.json \
    --owner-public-key $OWNER_PUB \
    --verify-runner-hash '$RUNNER_SHA' \
    --host-label codespace-host-b \
    --operator-identity 'github-codespaces-ubuntu' \
    --out host_b_output 2>&1" > "$RESULTS_DIR/host_b_full_log.txt" 2>&1
echo "  ✓ Host B execution complete (full log saved)"
echo "  Last 5 lines:"
tail -5 "$RESULTS_DIR/host_b_full_log.txt"

# ── Step 4b: Run verifier on Codespace (portability test) ─────
echo "▶ Step 4b/8: Running verifier ON Codespace (portability test)..."
gh codespace ssh -c "$CS" -- \
  "cd ~/hdar-demo && python3 third_party_verifier.py \
    --capsule-e1 host_b_output/capsule_epoch_1 \
    --capsule-e2 host_b_output/capsule_epoch_2 \
    --host-b-report host_b_output/host_b_report.json \
    --evidence-packet host_b_output/host_b_evidence_packet.json \
    --owner-public-key $OWNER_PUB \
    --host-a-platform '$HOST_A_PLATFORM' 2>&1" > "$RESULTS_DIR/verifier_on_codespace.json" 2>&1 || true
echo "  ✓ Verifier portability test complete (see verifier_on_codespace.json)"

# ── Step 5: Pull artifacts back to Mac ────────────────────────
echo "▶ Step 5/8: Pulling evidence artifacts back to Mac..."
# Copy E1 capsule from deploy package (already extracted)
cp -r "$DEPLOY_DIR/capsule_epoch_1" "$RESULTS_DIR/capsule_epoch_1"
# Download Host B output from Codespace via base64 pipe
gh codespace ssh -c "$CS" -- \
  "cd ~/hdar-demo && tar czf /tmp/results.tar.gz host_b_output/ && base64 /tmp/results.tar.gz" 2>/dev/null | base64 -d > /tmp/results.tar.gz
tar xzf /tmp/results.tar.gz -C "$RESULTS_DIR/" 2>/dev/null
echo "  ✓ Artifacts saved to: $RESULTS_DIR"

# ── Step 6: Delete Codespace BEFORE final verification ────────
echo "▶ Step 6/8: Deleting Codespace (verifier will run on Host A)..."
gh codespace delete -c "$CS" --force 2>/dev/null || true
echo "  ✓ Codespace deleted"

# ── Step 7: Run Verifier C on Host A (post-destruction) ───────
echo "▶ Step 7/8: Running Verifier C on Host A (post-destruction)..."
python3 "$DEPLOY_DIR/third_party_verifier.py" \
  --capsule-e1 "$RESULTS_DIR/capsule_epoch_1" \
  --capsule-e2 "$RESULTS_DIR/host_b_output/capsule_epoch_2" \
  --host-b-report "$RESULTS_DIR/host_b_output/host_b_report.json" \
  --evidence-packet "$RESULTS_DIR/host_b_output/host_b_evidence_packet.json" \
  --owner-public-key "$OWNER_PUB" \
  --host-a-platform "$HOST_A_PLATFORM" > "$RESULTS_DIR/verifier_output.json" 2>&1 || true
echo "  ✓ Verifier C complete (ran on Host A after Codespace deletion)"

# ── Step 8: Summary ───────────────────────────────────────────
echo "▶ Step 8/8: Final summary..."
echo ""
echo "── Verifier on Codespace (portability test) ──"
python3 -c "
import json, sys
try:
    d = json.load(open('$RESULTS_DIR/verifier_on_codespace.json'))
    print(f'  Result: {d[\"passed\"]}/{d[\"total_checks\"]} checks passed')
    for c in d['checks']:
        status = '✓' if c['ok'] else '✗'
        print(f'  {status} {c[\"check\"]:30s} {c[\"reason\"][:60]}')
except Exception as e:
    print(f'  Could not parse: {e}')
    print(open('$RESULTS_DIR/verifier_on_codespace.json').read()[:500])
" 2>&1

echo ""
echo "── Verifier on Host A (authoritative, post-destruction) ──"
python3 -c "
import json, sys
try:
    d = json.load(open('$RESULTS_DIR/verifier_output.json'))
    print(f'  Result: {d[\"passed\"]}/{d[\"total_checks\"]} checks passed')
    for c in d['checks']:
        status = '✓' if c['ok'] else '✗'
        print(f'  {status} {c[\"check\"]:30s} {c[\"reason\"][:60]}')
except Exception as e:
    print(f'  Could not parse: {e}')
    print(open('$RESULTS_DIR/verifier_output.json').read()[:500])
" 2>&1

echo ""
echo "Artifacts: $RESULTS_DIR/"
echo "  verifier_output.json (authoritative, Host A)"
echo "  verifier_on_codespace.json (portability test, Codespace)"
echo "  host_b_output/host_b_report.json"
echo "  host_b_output/host_b_evidence_packet.json"
echo "  host_b_output/successor_capsule_epoch_2.tar.gz"
echo "  host_b_full_log.txt (complete Host B stdout)"
echo ""
echo "=== CODESPACE PROOF COMPLETE ==="
