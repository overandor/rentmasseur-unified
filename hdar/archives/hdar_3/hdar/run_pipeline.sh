#!/bin/bash
# HDAR Comprehensive Execution Pipeline — "Snap2Text"
#
# Captures every test run with full stdout/stderr, failures included,
# records provenance (git, hashes, environment), and produces a single
# examinable, signed artifact.
#
# Usage: ./run_pipeline.sh [vm_count] [failure_rate]
# Defaults: vm_count=5, failure_rate=0.40
#
# Output: pipeline_output/ directory with:
#   manifest.txt          — full provenance + summary
#   manifest.sha256       — detached SHA-256 of manifest
#   manifest.sig          — Ed25519 signature over manifest hash
#   verify_key.pem        — Ed25519 public key for verification
#   01_native_loop.log    — full native C++ decisive loop output
#   02_cpp_unit_tests.log — C++ unit test output
#   03_python_tests.log   — Python adversarial + cross-lang test output
#   04_real_vm_harness.log — Real VM migration harness output (with failures)
#   05_native_build.log   — Build output (warnings/errors captured)
#   06_cpp_build.log      — C++ CMake build output
#   results.json          — machine-readable summary of all stages
#   signing_key.pem       — Ed25519 private key (keep secure)

set -uo pipefail

VM_COUNT="${1:-5}"
FAILURE_RATE="${2:-0.40}"
REPO="$(cd "$(dirname "$0")" && pwd)"
OUTDIR="$REPO/pipeline_output"

# ─── Clean previous output ────────────────────────────────────
rm -rf "$OUTDIR"
mkdir -p "$OUTDIR"

# Track stage results as plain variables (macOS bash 3.2 has no associative arrays)
NATIVE_BUILD_PASS="false"
CPP_BUILD_PASS="false"
NATIVE_LOOP_PASS="false"
NATIVE_LOOP_DETAIL=""
CPP_TESTS_PASS="false"
CPP_TESTS_DETAIL=""
PY_TESTS_PASS="false"
PY_TESTS_DETAIL=""
VM_HARNESS_PASS="false"
VM_HARNESS_DETAIL=""

# ─── 0. Assert clean git tree ─────────────────────────────────
echo "=== STAGE 0: Git state verification ==="
DIRTY=$(cd "$REPO" && git status --porcelain | wc -l | tr -d ' ')
if [ "$DIRTY" -ne 0 ]; then
    echo "FATAL: Git tree has $DIRTY untracked/modified files. Commit or stash first."
    cd "$REPO" && git status --short
    exit 1
fi
GIT_SHA=$(cd "$REPO" && git rev-parse HEAD)
GIT_BRANCH=$(cd "$REPO" && git rev-parse --abbrev-ref HEAD)
GIT_AUTHOR=$(cd "$REPO" && git log -1 --format='%an <%ae>  %ai')
GIT_MSG=$(cd "$REPO" && git log -1 --format='%s')
echo "  Git SHA: $GIT_SHA"
echo "  Branch: $GIT_BRANCH"
echo "  Clean: 0 dirty files"
echo "  Last commit: $GIT_MSG"
echo ""

# ─── 1. Build native C++ from clean ───────────────────────────
echo "=== STAGE 1: Build native C++ (clean) ==="
cd "$REPO/native"
make clean >/dev/null 2>&1
make 2>&1 | tee "$OUTDIR/05_native_build.log"
NATIVE_BUILD_RC=$?
if [ "$NATIVE_BUILD_RC" -ne 0 ]; then
    echo "FATAL: Native build failed (exit=$NATIVE_BUILD_RC)"
    NATIVE_BUILD_PASS="false"
    exit 1
fi
NATIVE_BUILD_PASS="true"
BINARY_PATH="$REPO/native/hdar_native"
BINARY_HASH=$(shasum -a 256 "$BINARY_PATH" | awk '{print $1}')
BINARY_SIZE=$(ls -l "$BINARY_PATH" | awk '{print $5}')
echo "  Binary SHA-256: $BINARY_HASH"
echo "  Binary size: $BINARY_SIZE bytes"
echo ""

# ─── 2. Build C++ CMake project ───────────────────────────────
echo "=== STAGE 2: Build C++ CMake project ==="
cd "$REPO/cpp"
cmake -B build 2>&1 | tee "$OUTDIR/06_cpp_build.log"
CPP_CMAKE_RC=$?
if [ "$CPP_CMAKE_RC" -ne 0 ]; then
    echo "WARNING: CMake configure failed (exit=$CPP_CMAKE_RC)"
    CPP_BUILD_PASS="false"
else
    make -C build -j8 2>&1 | tee -a "$OUTDIR/06_cpp_build.log"
    CPP_BUILD_RC=$?
    if [ "$CPP_BUILD_RC" -ne 0 ]; then
        echo "WARNING: C++ build failed (exit=$CPP_BUILD_RC)"
        CPP_BUILD_PASS="false"
    else
        CPP_BUILD_PASS="true"
    fi
fi
echo ""

# ─── 3. Run native C++ decisive loop ──────────────────────────
echo "=== STAGE 3: Native C++ decisive loop ==="
"$BINARY_PATH" 2>&1 | tee "$OUTDIR/01_native_loop.log"
NATIVE_RC=$?
NATIVE_PASSED=$(grep -oE '[0-9]+ passed' "$OUTDIR/01_native_loop.log" | tail -1 | awk '{print $1}')
NATIVE_FAILED=$(grep -oE '[0-9]+ failed' "$OUTDIR/01_native_loop.log" | tail -1 | awk '{print $1}')
NATIVE_LOOP_PASS=$([ "$NATIVE_RC" -eq 0 ] && echo "true" || echo "false")
NATIVE_LOOP_DETAIL="${NATIVE_PASSED:-0} passed, ${NATIVE_FAILED:-0} failed"
echo "  Exit code: $NATIVE_RC"
echo "  Result: ${NATIVE_PASSED:-0} passed, ${NATIVE_FAILED:-0} failed"
echo ""

# ─── 4. Run C++ unit tests ────────────────────────────────────
echo "=== STAGE 4: C++ unit tests ==="
if [ -f "$REPO/cpp/build/bin/test_hdar" ]; then
    "$REPO/cpp/build/bin/test_hdar" 2>&1 | tee "$OUTDIR/02_cpp_unit_tests.log"
    CPP_TEST_RC=$?
    CPP_PASSED=$(grep -oE '[0-9]+ passed' "$OUTDIR/02_cpp_unit_tests.log" | tail -1 | awk '{print $1}')
    CPP_FAILED=$(grep -oE '[0-9]+ failed' "$OUTDIR/02_cpp_unit_tests.log" | tail -1 | awk '{print $1}')
    CPP_TESTS_PASS=$([ "$CPP_TEST_RC" -eq 0 ] && echo "true" || echo "false")
    CPP_TESTS_DETAIL="${CPP_PASSED:-0} passed, ${CPP_FAILED:-0} failed"
    echo "  Exit code: $CPP_TEST_RC"
    echo "  Result: ${CPP_PASSED:-0} passed, ${CPP_FAILED:-0} failed"
else
    echo "  SKIPPED: test_hdar binary not found"
    CPP_TESTS_PASS="skipped"
    CPP_TESTS_DETAIL="binary not found"
fi
echo ""

# ─── 5. Run Python tests ──────────────────────────────────────
echo "=== STAGE 5: Python adversarial + cross-lang tests ==="
cd "$REPO"
python3 -m pytest test_adversarial.py test_cross_lang.py -v 2>&1 | tee "$OUTDIR/03_python_tests.log"
PY_TEST_RC=$?
PY_PASSED=$(grep -oE '[0-9]+ passed' "$OUTDIR/03_python_tests.log" | tail -1 | awk '{print $1}')
PY_FAILED=$(grep -oE '[0-9]+ failed' "$OUTDIR/03_python_tests.log" | tail -1 | awk '{print $1}')
PY_TESTS_PASS=$([ "$PY_TEST_RC" -eq 0 ] && echo "true" || echo "false")
PY_TESTS_DETAIL="${PY_PASSED:-0} passed, ${PY_FAILED:-0} failed"
echo "  Exit code: $PY_TEST_RC"
echo "  Result: ${PY_PASSED:-0} passed, ${PY_FAILED:-0} failed"
echo ""

# ─── 6. Run real VM migration harness ─────────────────────────
echo "=== STAGE 6: Real VM migration harness ($VM_COUNT migrations, $(awk "BEGIN{printf \"%.0f\", $FAILURE_RATE * 100}")% failure injection) ==="
echo "  This runs REAL Apple Containerization VMs. Each migration takes ~12-15s."
echo "  Estimated time: ~$(awk "BEGIN{printf \"%.0f\", $VM_COUNT * 15 / 60}") minutes"
echo ""
python3 -u real_vm_harness.py --count "$VM_COUNT" --failures "$FAILURE_RATE" \
    --output "$OUTDIR/real_vm_results.json" > "$OUTDIR/04_real_vm_harness.log" 2>&1
VM_RC=$?
cat "$OUTDIR/04_real_vm_harness.log"
VM_SUCCESS=$(python3 -c "import json; d=json.load(open('$OUTDIR/real_vm_results.json')); print(d['successful'])" 2>/dev/null || echo "?")
VM_TOTAL=$(python3 -c "import json; d=json.load(open('$OUTDIR/real_vm_results.json')); print(d['total_migrations'])" 2>/dev/null || echo "?")
VM_RATE=$(python3 -c "import json; d=json.load(open('$OUTDIR/real_vm_results.json')); print(f\"{d['success_rate']*100:.1f}%\")" 2>/dev/null || echo "?")
VM_LEAKED=$(python3 -c "import json; d=json.load(open('$OUTDIR/real_vm_results.json')); print(d.get('leaked_runtimes', '?'))" 2>/dev/null || echo "?")
VM_CHECKS_P=$(python3 -c "import json; d=json.load(open('$OUTDIR/real_vm_results.json')); print(d.get('total_checks_passed', '?'))" 2>/dev/null || echo "?")
VM_CHECKS_F=$(python3 -c "import json; d=json.load(open('$OUTDIR/real_vm_results.json')); print(d.get('total_checks_failed', '?'))" 2>/dev/null || echo "?")
VM_HARNESS_PASS=$([ "$VM_RC" -eq 0 ] && echo "true" || echo "false")
VM_HARNESS_DETAIL="$VM_SUCCESS/$VM_TOTAL migrations, ${VM_CHECKS_P} checks passed, ${VM_CHECKS_F} failed, $VM_LEAKED leaked"
echo "  Exit code: $VM_RC"
echo "  Result: $VM_SUCCESS/$VM_TOTAL ($VM_RATE), $VM_CHECKS_P checks passed, $VM_CHECKS_F failed, $VM_LEAKED leaked VMs"
echo ""

# ─── 7. Generate manifest ─────────────────────────────────────
echo "=== STAGE 7: Generating signed manifest ==="
MANIFEST="$OUTDIR/manifest.txt"
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

{
    echo "=== HDAR COMPREHENSIVE EXECUTION PIPELINE — SIGNED MANIFEST ==="
    echo "Generated: $TIMESTAMP"
    echo "Pipeline: run_pipeline.sh (Snap2Text)"
    echo ""
    echo "=== GIT PROVENANCE ==="
    echo "Git SHA: $GIT_SHA"
    echo "Git branch: $GIT_BRANCH"
    echo "Git clean: 0 untracked/modified files (verified before generation)"
    echo "Last commit: $GIT_MSG"
    echo "Commit author: $GIT_AUTHOR"
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
    echo "container package: $(brew info container --json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["name"]+"-"+d[0]["versions"]["stable"])' 2>/dev/null || echo 'unknown')"
    echo ""
    echo "=== SOURCE HASHES ==="
    for f in \
        native/main.cpp \
        native/hdar_provider.cpp \
        native/hdar_provider.h \
        native/hdar_crypto.cpp \
        native/hdar_crypto.h \
        native/hdar_lease.cpp \
        native/hdar_lease.h \
        native/hdar_continuity.cpp \
        native/hdar_continuity.h \
        native/hdar_gateway.cpp \
        native/hdar_gateway.h \
        native/hdar_store.cpp \
        native/hdar_store.h \
        native/Makefile \
        continuity.py \
        real_vm_harness.py \
        migration_harness.py \
        generate_evidence.sh \
        run_pipeline.sh \
        .github/workflows/ci.yml \
        test_cross_lang.py \
        test_adversarial.py; do
        if [ -f "$REPO/$f" ]; then
            echo "  $(shasum -a 256 "$REPO/$f" | awk '{print $1}')  $f"
        fi
    done
    echo ""
    echo "=== BINARY HASHES ==="
    echo "  Native binary SHA-256: $BINARY_HASH"
    echo "  Native binary size: $BINARY_SIZE bytes"
    if [ -f "$REPO/cpp/build/bin/test_hdar" ]; then
        echo "  C++ test binary SHA-256: $(shasum -a 256 "$REPO/cpp/build/bin/test_hdar" | awk '{print $1}')"
    fi
    echo ""
    echo "=== STAGE RESULTS ==="
    echo "  Stage 1 — Native build:          $NATIVE_BUILD_PASS"
    echo "  Stage 2 — C++ CMake build:       $CPP_BUILD_PASS"
    echo "  Stage 3 — Native decisive loop:  $NATIVE_LOOP_PASS ($NATIVE_LOOP_DETAIL)"
    echo "  Stage 4 — C++ unit tests:        $CPP_TESTS_PASS ($CPP_TESTS_DETAIL)"
    echo "  Stage 5 — Python tests:          $PY_TESTS_PASS ($PY_TESTS_DETAIL)"
    echo "  Stage 6 — Real VM harness:       $VM_HARNESS_PASS ($VM_HARNESS_DETAIL)"
    echo ""
    echo "=== NATIVE DECISIVE LOOP — KEY EVIDENCE ==="
    grep -E '✓|✗|passed|failed|RESULT|EVIDENCE|Runtime|Capsule|Fencing|Witness|Offline|Task|CANONICAL|canonical_hash|verify_result' \
        "$OUTDIR/01_native_loop.log" 2>/dev/null | sed 's/^/  /'
    echo ""
    echo "=== REAL VM HARNESS — KEY EVIDENCE ==="
    grep -E '✓|✗|RESULT|RELIABILITY|Total|Successful|Failed|Success|Leaked|Duration|Wilson|Provider|Isolation|Faults|checks' \
        "$OUTDIR/04_real_vm_harness.log" 2>/dev/null | sed 's/^/  /'
    echo ""
    echo "=== LOG FILES ==="
    for f in "$OUTDIR"/*.log; do
        basename_f=$(basename "$f")
        file_hash=$(shasum -a 256 "$f" | awk '{print $1}')
        file_lines=$(wc -l < "$f" | tr -d ' ')
        file_size=$(ls -l "$f" | awk '{print $5}')
        echo "  $basename_f  ($file_lines lines, $file_size bytes, SHA-256: $file_hash)"
    done
    echo ""
    echo "=== FAILURE HONESTY ==="
    echo "All failures are preserved in the log files above."
    echo "No output was filtered, truncated, or modified."
    echo "The real VM harness includes injected faults (corruption, duplicate_wake, stale_fencing)."
    echo "Failures in the harness are expected — they prove the rejection mechanisms work."
    echo ""
    echo "=== VERIFICATION INSTRUCTIONS ==="
    echo "To verify this pipeline artifact:"
    echo "  1. Check git commit matches: git rev-parse HEAD"
    echo "  2. Verify source hashes match: shasum -a 256 <file>"
    echo "  3. Verify manifest integrity: shasum -a 256 pipeline_output/manifest.txt"
    echo "  4. Compare to detached hash: cat pipeline_output/manifest.sha256"
    echo "  5. Verify Ed25519 signature:"
    echo "     openssl pkeyutl -verify -pubin -inkey pipeline_output/verify_key.pem -rawin -in pipeline_output/manifest.sha256 -sigfile pipeline_output/manifest.sig"
    echo "  6. Re-run pipeline: ./run_pipeline.sh $VM_COUNT $FAILURE_RATE"
    echo "  7. Examine individual logs: cat pipeline_output/0X_*.log"
} > "$MANIFEST"

# ─── 8. Detached SHA-256 + Ed25519 signature ──────────────────
MANIFEST_HASH=$(shasum -a 256 "$MANIFEST" | awk '{print $1}')
printf '%s' "$MANIFEST_HASH" > "$OUTDIR/manifest.sha256"

SIGN_KEY="$OUTDIR/signing_key.pem"
VERIFY_KEY="$OUTDIR/verify_key.pem"
openssl genpkey -algorithm Ed25519 -out "$SIGN_KEY" 2>/dev/null
openssl pkey -in "$SIGN_KEY" -pubout -out "$VERIFY_KEY" 2>/dev/null
openssl pkeyutl -sign -inkey "$SIGN_KEY" -rawin -in "$OUTDIR/manifest.sha256" -out "$OUTDIR/manifest.sig" 2>/dev/null

# ─── 9. Machine-readable results JSON ─────────────────────────
python3 -c "
import json, hashlib, os
out = {}
out['pipeline'] = 'run_pipeline.sh'
out['timestamp'] = '$TIMESTAMP'
out['git_sha'] = '$GIT_SHA'
out['git_branch'] = '$GIT_BRANCH'
out['git_clean'] = True
out['binary_hash'] = '$BINARY_HASH'
out['stages'] = {
    'native_build': {'pass': '$NATIVE_BUILD_PASS'},
    'cpp_build': {'pass': '$CPP_BUILD_PASS'},
    'native_loop': {'pass': '$NATIVE_LOOP_PASS', 'detail': '$NATIVE_LOOP_DETAIL'},
    'cpp_tests': {'pass': '$CPP_TESTS_PASS', 'detail': '$CPP_TESTS_DETAIL'},
    'python_tests': {'pass': '$PY_TESTS_PASS', 'detail': '$PY_TESTS_DETAIL'},
    'vm_harness': {'pass': '$VM_HARNESS_PASS', 'detail': '$VM_HARNESS_DETAIL'}
}
out['manifest_hash'] = '$MANIFEST_HASH'
logs = {}
for f in sorted(os.listdir('$OUTDIR')):
    if f.endswith('.log'):
        path = os.path.join('$OUTDIR', f)
        with open(path, 'rb') as fh:
            logs[f] = hashlib.sha256(fh.read()).hexdigest()
out['log_hashes'] = logs
with open('$OUTDIR/results.json', 'w') as f:
    json.dump(out, f, indent=2)
" 2>&1

# ─── 10. Summary ──────────────────────────────────────────────
echo ""
echo "========================================================================"
echo "  PIPELINE COMPLETE — SIGNED ARTIFACT IN pipeline_output/"
echo "========================================================================"
echo ""
echo "  manifest.txt          — full provenance + stage results + key evidence"
echo "  manifest.sha256       — $MANIFEST_HASH"
echo "  manifest.sig          — Ed25519 signature (verified with verify_key.pem)"
echo "  verify_key.pem        — Ed25519 public key"
echo "  results.json          — machine-readable summary"
echo ""
echo "  LOGS (all failures preserved, nothing filtered):"
for f in "$OUTDIR"/*.log; do
    basename_f=$(basename "$f")
    file_lines=$(wc -l < "$f" | tr -d ' ')
    echo "    $basename_f  ($file_lines lines)"
done
echo ""
echo "  Git commit: $GIT_SHA"
echo "  Manifest hash: $MANIFEST_HASH"
echo ""
echo "  Verify with:"
echo "    openssl pkeyutl -verify -pubin -inkey $OUTDIR/verify_key.pem -rawin -in $OUTDIR/manifest.sha256 -sigfile $OUTDIR/manifest.sig"
echo ""
