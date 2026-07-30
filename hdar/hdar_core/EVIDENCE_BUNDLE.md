# HDAR Evidence Bundle — C++ Continuity Loop

## Demonstration Date
2026-07-18 (pipeline: hdar-pipeline-20260718T075626Z)

## Two Implementations

### 1. C++ HDAR (`cpp/` directory)
CMake-based, libsodium, 23 source files, 32 unit tests + 30 demo checks + 45 continuity assertions.

### 2. Native HDAR (`native/` directory)
Makefile-based, OpenSSL 3.x, 7 source files, 55 assertions in one decisive loop including SSH gateway.

## Environment

| Component | Value |
|-----------|-------|
| macOS | 26.5.2 (Build 25F84) |
| Architecture | arm64 (Apple M5 Pro) |
| Python | 3.13.12 |
| container CLI | 1.1.0 (build: release, commit: unspeci) |
| container binary path | /opt/homebrew/bin/container |
| container binary SHA-256 | 9fb1e387868ab01822a5efbac267161b8860af96ff9560cc8b60841840dea3f3 |
| Installation source | Homebrew (`brew install container`) |
| HDAR repo | /Users/alep/Downloads/hdar |
| Prior commit | abec525 (Python: 68 tests + 48 demo = 116 passing) |

## C++ Build

```
cd cpp && cmake -B build && make -j8
```

Dependencies: libsodium (Homebrew), SQLite3 (system)

## Test Results

| Suite | Result |
|-------|--------|
| C++ unit tests | 32/32 passed, 0 failed |
| C++ demo | 30/30 checks passed |
| C++ continuity loop (real VMs) | 45/45 assertions passed |
| Native decisive loop (real VMs) | 55/55 assertions passed |
| Native SSH gateway | 9/9 gateway checks passed |
| Offline verification | 15/15 checks passed, 0 failed |

## Continuity Loop Proof

The C++ `demo_continuity` binary executed the full continuity loop against real Apple Containerization VMs:

1. Runtime A: real ARM64 Linux VM created via `container create` + `container start`
2. Task executed inside Runtime A via `container exec`
3. Capsule sealed with Ed25519 owner signature (libsodium)
4. Runtime A destroyed via `container kill` + `container delete --force`
5. Provider confirmed Runtime A absent (`container inspect` returns non-zero)
6. Runtime B: second real ARM64 Linux VM created
7. Workspace restored from capsule, hash verified
8. Capabilities attenuated (non-expansion enforced)
9. Task executed inside Runtime B
10. Host B signed witness receipt with ephemeral Ed25519 key (separate from owner)
11. Host B cannot forge owner signature on epoch advancement
12. Owner advances lineage (epoch 0 → epoch 1)
13. Runtime B destroyed and confirmed absent
14. Offline verifier: 15 cryptographic checks, 0 failures

## What This Proves

- Real VM-backed runtime creation, execution, and provider-confirmed destruction
- Same-host cross-VM semantic continuation with cryptographic lineage
- Ed25519 owner signing with public-key-only verification at destination
- Ephemeral host witness keys separate from owner authority
- Fencing-token invalidation and stale-token rejection
- Capability attenuation with non-expansion invariant
- Tamper detection, rollback rejection, offline integrity verification

## What This Does NOT Prove

- Independent physical host migration (both VMs on same M5 Pro)
- Cross-provider migration
- Stable SSH entry point through real sshd (gateway tested via direct C++ call, not real SSH connection)
- Distributed lease authority across network partitions
- Real ambiguous external-effect reconciliation
- External developer reproduction
- Automatic interrupted-run recovery (preflight reconciler added but not tested with actual interruption)

## 100-Migration Logical Battle Test (UnsafeHostProvider — NOT real VMs)

**Provider:** `UnsafeHostProvider` — directory-based simulation, no real VMs created or destroyed
**Pipeline:** `./run_full_pipeline.sh 100` (4×25 cumulative batches)
**Result:** 100/100 logical migrations successful (100.0%)
**Wilson 95% lower bound:** 96.3%
**Total checks passed:** 1,831
**Total checks failed:** 0
**Failures injected:** 41 (corruption, stale fencing, duplicate wake) — all correctly rejected
**Duration:** ~14 seconds (logical simulation, not real VM lifecycle)
**Git commit:** bb230bfa2b50008d29373430be0bc58b2728a754
**Manifest hash:** 639360e95b2e54bdce6458f61a4e8dbd301610e14ed95b086b7f0b0735681f5c
**Ed25519 signature:** Verified Successfully

### Batch Breakdown

| Batch | Success | Rate | Wilson LB |
|-------|---------|------|----------|
| 1 | 25/25 | 100% | 86.7% |
| 2 | 25/25 | 100% | 86.7% |
| 3 | 25/25 | 100% | 86.7% |
| 4 | 25/25 | 100% | 86.7% |
| **Aggregate** | **100/100** | **100%** | **96.3%** |

### Reproducible Artifacts

All artifacts in `pipeline_output/`:
- `evidence/manifest.txt` — full signed manifest
- `evidence/manifest.sha256` — detached SHA-256
- `evidence/manifest.sig` — Ed25519 signature
- `evidence/verify_key.pem` — public verification key
- `evidence/battle_test_100.json` — aggregate results
- `evidence/battle_test_batch_{1-4}.json` — per-batch results
- `logs/decisive_loop.log` — full native loop output
- `logs/battle_test.log` — full battle test output
- `logs/battle_test_batch_{1-4}.log` — per-batch logs
- `failures/failure_16e2347e_0002.json` — preserved failure with diagnostics

### Verification Command

```bash
shasum -a 256 pipeline_output/evidence/manifest.txt | diff - pipeline_output/evidence/manifest.sha256
openssl pkeyutl -verify -pubin -inkey pipeline_output/evidence/verify_key.pem \
  -rawin -in pipeline_output/evidence/manifest.sha256 \
  -sigfile pipeline_output/evidence/manifest.sig
```

## SSH Gateway Status

The native SSH gateway (`hdar_gateway.cpp`) now passes all 9 checks:
- Resolves SSH user to agent identity
- Rejects unknown SSH users
- Loads capsule from durable storage
- Verifies owner Ed25519 signature (no longer fails)
- Acquires fenced lease
- Materializes real VM
- Executes command inside VM
- Signs witness receipt with ephemeral host key
- Destroys VM and proves absence
- Releases lease

The gateway is tested via direct C++ function call, not through a real OpenSSH `ForceCommand` session. The next step is to wire it through actual `sshd`.

## Cryptographic Implementation

### Native C++ (OpenSSL 3.x)
- Signing: Ed25519 via OpenSSL `EVP_DigestSign` / `EVP_DigestVerify` (PureEdDSA)
- Hashing: SHA-256 via OpenSSL `EVP_Digest`
- Key generation: `EVP_PKEY_keygen` with Ed25519 algorithm
- Lease store: SQLite3 with fencing tokens and lease generations
- Canonical JSON: alphabetically sorted keys, no whitespace, matching Python's `json.dumps(sort_keys=True, separators=(',',':'))`

### C++ (libsodium)
- Signing: Ed25519 via `crypto_sign_detached` / `crypto_sign_verify_detached`
- Hashing: SHA-256 via `crypto_hash_sha256`
- Key generation: `crypto_sign_ed25519_seed_keypair` with random seed

### Cross-Language Wire Compatibility

The Python and native C++ implementations now produce **byte-identical canonical forms** for the same capsule data. Verified by `test_cross_lang.py`:

```
C++ canonical hash:    afba67134f5c8026ed59a02ed4d6947827cc27481997ad601582e3daec9eab23
Python canonical hash: afba67134f5c8026ed59a02ed4d6947827cc27481997ad601582e3daec9eab23
RESULT: COMPATIBLE
```

The native binary also publishes a full canonical signing transcript:
- Owner public key (hex)
- Canonical bytes (the exact JSON string signed)
- Canonical hash (SHA-256 of canonical bytes)
- Signature hex
- Manifest hash
- Epoch and parent hash
- Verification result

## Stubs Fixed This Session

| File | Was | Now |
|------|-----|-----|
| effects.cpp:91 | Ledger loading skipped all lines | Uses parse_json to load records |
| seal.cpp:183 | verify_capsule_file returned true for non-empty file | Parses JSON, verifies Ed25519 signature |
| gateway.cpp:76 | execute() returned fake success | Routes through ExecuteFn callback, fails closed |
| ci.yml:40 | pytest \|\| true (CI passed on failure) | Removed \|\| true, added C++ job |
| apple_container.cpp | Used non-existent `container run` | Uses `container create` + `container start` |
| restore.cpp | Threw "not implemented" for JSON parsing | Uses parse_json |
| controller.cpp | Sealed from wrong workspace path | Uses runtime->workspace_mount |
| hdar_store.cpp canonical_form() | Fixed field order (epoch first) | Alphabetical key order matching Python sort_keys=True |
| real_vm_harness.py preflight | Only cleaned current run ID | Scans ALL hdar-* VMs, checks lease registry, preserves valid runtimes |
