#!/usr/bin/env bash
# Reorganize HDAR repository by function instead of by history.
# Moves dated experiments into archive/, creates functional directories.
# Safe to run — does not delete anything, only moves.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== HDAR Repository Reorganization ==="
echo "Root: $ROOT"
echo ""

# Create functional directories
mkdir -p runtime transport verification security evidence sdk examples docs investor archive

# --- runtime/ ---
echo "Organizing runtime/..."
cp execution_broker.py runtime/ 2>/dev/null || true
cp hdar_second_host_bundle_demo.py runtime/ 2>/dev/null || true
cp demo_two_machines.py runtime/ 2>/dev/null || true
cp run_two_machine_demo.sh runtime/ 2>/dev/null || true
cp seed_milestone_demo.py runtime/ 2>/dev/null || true
cp owner_sign_capsule.py runtime/ 2>/dev/null || true

# --- transport/ ---
echo "Organizing transport/..."
# Keep deploy-package-v2 as canonical transport package
cp -r deploy-package-v2 transport/deploy-package 2>/dev/null || true
cp hdar-deploy-package.tar.gz transport/ 2>/dev/null || true

# --- verification/ ---
echo "Organizing verification/..."
cp third_party_verifier.py verification/ 2>/dev/null || true
cp test_seed_criterion.py verification/ 2>/dev/null || true
cp test_audit_fixes.py verification/ 2>/dev/null || true

# --- security/ ---
echo "Organizing security/..."
cp secret_scanner.py security/ 2>/dev/null || true
cp -r negative_evidence security/negative_evidence 2>/dev/null || true

# --- evidence/ ---
echo "Organizing evidence/..."
# evidence/ already has EVP files and claims/ milestones/ are at root
cp -r claims evidence/claims 2>/dev/null || true
cp -r milestones evidence/milestones 2>/dev/null || true
cp claim_registry.json evidence/ 2>/dev/null || true
cp claim_coverage.json evidence/ 2>/dev/null || true
cp protocol_fsm.json evidence/ 2>/dev/null || true
cp technical_ledger.json evidence/ 2>/dev/null || true
cp commercial_ledger.json evidence/ 2>/dev/null || true

# --- sdk/ ---
echo "Organizing sdk/..."
# execution_broker.py is the SDK entry point
cp execution_broker.py sdk/ 2>/dev/null || true

# --- examples/ ---
echo "Organizing examples/..."
cp hdar_host_b_colab.ipynb examples/ 2>/dev/null || true
cp run_e2b_proof.py examples/ 2>/dev/null || true

# --- docs/ ---
echo "Organizing docs/..."
# Copy runbooks and instructions
find . -maxdepth 2 -name "RUN_ON_REAL_HOST_B.md" -exec cp {} docs/ \; 2>/dev/null || true
find . -maxdepth 2 -name "INSTRUCTIONS.txt" -exec cp {} docs/ \; 2>/dev/null || true
find . -maxdepth 2 -name "PRD_300K_FEATURE_SET.md" -exec cp {} docs/ \; 2>/dev/null || true

# --- investor/ ---
echo "Organizing investor/..."
cp SEED_PITCH.md investor/ 2>/dev/null || true
find . -maxdepth 2 -name "SEED_INVESTMENT_SUMMARY.md" -exec cp {} investor/ \; 2>/dev/null || true

# --- archive/ — move dated experiments and old runs ---
echo "Organizing archive/..."
for dir in run-2026-07-20 run-2026-07-20-v2 run-2026-07-20-v3 deploy-package e2b-results host-b-results independent-host-b-results; do
  if [ -d "$dir" ]; then
    mv "$dir" archive/ 2>/dev/null || true
  fi
done

# Move __pycache__ to archive
mv __pycache__ archive/ 2>/dev/null || true

# Move .DS_Store to archive
mv .DS_Store archive/ 2>/dev/null || true

echo ""
echo "=== Reorganization complete ==="
echo ""
echo "Functional structure:"
echo "  runtime/       — execution scripts, broker, bundle demo"
echo "  transport/      — deploy packages, signed capsules"
echo "  verification/   — verifier, test suites"
echo "  security/       — secret scanner, negative evidence"
echo "  evidence/       — claims, milestones, ledgers, FSM, coverage"
echo "  sdk/            — broker API entry point"
echo "  examples/       — Colab notebook, E2B proof"
echo "  docs/           — runbooks, PRD, instructions"
echo "  investor/       — SEED_PITCH, investment summary"
echo "  archive/        — dated runs, old experiments, caches"
echo ""
echo "Note: Original files remain at root level. Remove them manually after verifying the reorganization."
