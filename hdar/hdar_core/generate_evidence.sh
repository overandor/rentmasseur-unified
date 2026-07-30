#!/bin/bash
# HDAR Evidence Bundle Generator
#
# Produces a cryptographically-bound evidence package:
#   1. Asserts clean git tree (zero untracked/modified files)
#   2. Records environment, source hashes, binary hash, test results
#   3. Writes immutable manifest (no self-hash recursion)
#   4. Produces detached SHA-256 of the manifest
#   5. Signs the manifest hash with Ed25519 via OpenSSL
#   6. Provides a verification command
#
# Usage: ./generate_evidence.sh [output_dir]
# Default output: evidence/

set -euo pipefail

OUTDIR="${1:-evidence}"
REPO="$(cd "$(dirname "$0")" && pwd)"

# Make OUTDIR absolute relative to REPO
case "$OUTDIR" in
    /*) ;;
    *) OUTDIR="$REPO/$OUTDIR" ;;
esac

mkdir -p "$OUTDIR"

# ─── 1. Assert clean git tree ─────────────────────────────────
DIRTY=$(cd "$REPO" && git status --porcelain | wc -l | tr -d ' ')
if [ "$DIRTY" -ne 0 ]; then
    echo "FATAL: Git tree has $DIRTY untracked/modified files. Commit or stash before generating evidence."
    cd "$REPO" && git status --short
    exit 1
fi

GIT_SHA=$(cd "$REPO" && git rev-parse HEAD)
GIT_BRANCH=$(cd "$REPO" && git rev-parse --abbrev-ref HEAD)

# ─── 2. Build native binary from clean ────────────────────────
cd "$REPO/native"
make clean >/dev/null 2>&1
make >/dev/null 2>&1
BINARY_PATH="$REPO/native/hdar_native"
BINARY_HASH=$(shasum -a 256 "$BINARY_PATH" | awk '{print $1}')
BINARY_SIZE=$(ls -l "$BINARY_PATH" | awk '{print $5}')

# ─── 3. Run native test ───────────────────────────────────────
TEST_OUTPUT=$("$BINARY_PATH" 2>&1)
TEST_SUMMARY=$(echo "$TEST_OUTPUT" | grep -E "passed.*failed" | tail -1)

# ─── 4. Generate manifest ─────────────────────────────────────
MANIFEST="$OUTDIR/manifest.txt"
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

{
    echo "=== HDAR EVIDENCE MANIFEST ==="
    echo "Generated: $TIMESTAMP"
    echo "Git SHA: $GIT_SHA"
    echo "Git branch: $GIT_BRANCH"
    echo "Git clean: 0 untracked/modified files (verified before generation)"
    echo ""
    echo "=== ENVIRONMENT ==="
    echo "macOS: $(sw_vers -productVersion)"
    echo "Darwin: $(uname -r)"
    echo "Arch: $(uname -m)"
    echo "Python: $(python3 --version 2>&1)"
    echo "Compiler: $(clang++ --version 2>&1 | head -1)"
    echo "OpenSSL: $(openssl version 2>&1)"
    echo ""
    echo "=== APPLE CONTAINERIZATION ==="
    echo "container CLI: $(container --version 2>&1)"
    echo "container path: $(which container 2>&1)"
    echo "container SHA-256: $(shasum -a 256 "$(which container)" | awk '{print $1}')"
    echo "container package: $(brew list --versions container 2>/dev/null | head -1 || echo 'unknown')"
    echo "container formula source: https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/c/container.rb"
    echo "container formula stable: $(brew info container --json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["versions"]["stable"])' 2>/dev/null || echo 'unknown')"
    echo "container install path: $(brew --prefix container 2>/dev/null)/bin/container"
    echo "macOS build: $(sw_vers -buildVersion 2>/dev/null)"
    echo "Darwin kernel: $(uname -r)"
    echo "Virtualization framework: built into macOS $(sw_vers -productVersion)"
    echo ""
    echo "=== SOURCE HASHES ==="
    for f in \
        native/main.cpp \
        native/hdar_provider.cpp \
        native/hdar_provider.h \
        native/hdar_crypto.cpp \
        native/hdar_crypto.h \
        native/hdar_crypto.mm \
        native/hdar_lease.cpp \
        native/hdar_lease.h \
        native/hdar_continuity.cpp \
        native/hdar_continuity.h \
        native/hdar_gateway.cpp \
        native/hdar_gateway.h \
        native/hdar_store.cpp \
        native/hdar_store.h \
        native/Makefile \
        real_vm_harness.py \
        migration_harness.py \
        .github/workflows/ci.yml \
        test_cross_lang.py \
        EVIDENCE_BUNDLE.md; do
        if [ -f "$REPO/$f" ]; then
            echo "  $(shasum -a 256 "$REPO/$f" | awk '{print $1}')  $f"
        fi
    done
    echo ""
    echo "=== NATIVE BINARY ==="
    echo "Binary SHA-256: $BINARY_HASH"
    echo "Binary size: $BINARY_SIZE bytes"
    echo ""
    echo "=== NATIVE TEST RESULT ==="
    echo "$TEST_OUTPUT" | grep -E "passed|failed|CANONICAL|canonical_hash|verify_result|RESULT|EVIDENCE|Runtime|Capsule|Fencing|Witness|Offline|Task" | sed 's/^/  /'
    echo ""
    echo "=== CROSS-LANGUAGE COMPATIBILITY ==="
    cd "$REPO" && python3 test_cross_lang.py 2>&1 | grep -E "RESULT|hash:" | sed 's/^/  /'
    echo ""
    echo "=== VERIFICATION INSTRUCTIONS ==="
    echo "To verify this evidence package:"
    echo "  1. Check git commit matches: git rev-parse HEAD"
    echo "  2. Verify source hashes match: shasum -a 256 <file>"
    echo "  3. Verify binary hash matches: shasum -a 256 native/hdar_native"
    echo "  4. Verify manifest integrity: shasum -a 256 evidence/manifest.txt"
    echo "  5. Compare to detached hash: cat evidence/manifest.sha256"
    echo "  6. Verify Ed25519 signature: openssl pkeyutl -verify -pubin -inkey evidence/verify_key.pem -rawin -in evidence/manifest.sha256 -sigfile evidence/manifest.sig"
} > "$MANIFEST"

# ─── 5. Detached SHA-256 of manifest ──────────────────────────
MANIFEST_HASH=$(shasum -a 256 "$MANIFEST" | awk '{print $1}')
echo "$MANIFEST_HASH" > "$OUTDIR/manifest.sha256"

# ─── 6. Ed25519 signature over manifest hash ──────────────────
# Generate a one-time Ed25519 key pair for signing the evidence
SIGN_KEY="$OUTDIR/signing_key.pem"
VERIFY_KEY="$OUTDIR/verify_key.pem"

# Only generate if keys don't already exist (allows re-signing with same key)
if [ ! -f "$SIGN_KEY" ]; then
    openssl genpkey -algorithm Ed25519 -out "$SIGN_KEY" 2>/dev/null
    openssl pkey -in "$SIGN_KEY" -pubout -out "$VERIFY_KEY" 2>/dev/null
fi

# Sign the manifest hash with Ed25519 (requires -rawin for Ed25519 in OpenSSL 3.x)
printf '%s' "$MANIFEST_HASH" > "$OUTDIR/manifest.sha256"
openssl pkeyutl -sign -inkey "$SIGN_KEY" -rawin -in "$OUTDIR/manifest.sha256" -out "$OUTDIR/manifest.sig" 2>/dev/null

# ─── 7. Summary ───────────────────────────────────────────────
echo ""
echo "Evidence package generated in $OUTDIR/"
echo "  manifest.txt      — full evidence manifest"
echo "  manifest.sha256   — detached SHA-256: $MANIFEST_HASH"
echo "  manifest.sig      — Ed25519 signature over manifest hash"
echo "  signing_key.pem   — Ed25519 private key (keep secure)"
echo "  verify_key.pem    — Ed25519 public key (share for verification)"
echo ""
echo "Git commit: $GIT_SHA"
echo "Manifest hash: $MANIFEST_HASH"
echo ""
echo "Verify with:"
echo "  shasum -a 256 $OUTDIR/manifest.txt | diff - $OUTDIR/manifest.sha256"
echo "  openssl pkeyutl -verify -pubin -inkey $OUTDIR/verify_key.pem -rawin -in $OUTDIR/manifest.sha256 -sigfile $OUTDIR/manifest.sig"
