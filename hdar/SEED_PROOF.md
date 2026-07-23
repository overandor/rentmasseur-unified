# HDAR Seed-Round Technical Proof

## Executive Summary

HDAR is a **same-host real-VM pre-production prototype**. It demonstrates cryptographically governed semantic continuation across replaceable Linux VM-backed runtimes; physical cross-host migration remains unproven.

**The 100-run JSON harness is logical `UnsafeHostProvider` evidence, not real-VM evidence. The separate real-VM battle result is 10/10 same-host migrations (181 checks, 0 failures); zero failures in 10 trials has an approximately 69.1% one-sided 95% lower bound.**

---

## What Is Proven

### 1. Decisive Continuity Loop (55/55 assertions)

A single end-to-end loop that:
- Creates a real ARM64 Linux VM via Apple Containerization
- Executes a task inside the VM (`solve(10)=55`)
- Seals a capsule with Ed25519 owner signature
- Destroys the VM and proves absence (`container inspect` returns not-found)
- Creates a second real VM
- Restores the capsule on the new VM
- Continues the task (`solve(100)=5050`)
- Host B signs witness receipt with ephemeral key
- Owner advances lineage (epoch 0 → epoch 1)
- Destroys VM B and proves absence
- Offline verifier: 15 cryptographic checks, 0 failures

**Binary:** `native/hdar_native` (208 KB, OpenSSL 3.x, SQLite3)
**Hash:** `ef145622c6dd41bbe8557d3932dfb7060b493b29a45e0848220fc596d9124c6d`

### 2. 100-Migration Logical Harness

| Metric | Value |
|--------|-------|
| Total migrations | 100 logical migrations |
| Successful | 100 |
| Failed | 0 |
| Success rate | 100.0% |
| Provider | `UnsafeHostProvider` |
| Total checks passed | 1,831 |
| Total checks failed | 0 |
| Failures injected | 41 |
| Injected rejections | 41 (100%) |
| Leaked runtimes | 0 |
| All VM A absent | Yes |
| All VM B absent | Yes |
| Duration | 13.71 ms mean |

**Failure types injected:** capsule corruption, stale fencing tokens, duplicate wake attempts — all correctly detected and rejected.

### 3. Cryptographic Provenance

- **Signing:** Ed25519 (PureEdDSA) via OpenSSL 3.x
- **Hashing:** SHA-256
- **Canonical JSON:** Alphabetically sorted keys, no whitespace — byte-identical between Python and C++ implementations
- **Lease manager:** SQLite-backed with fencing tokens and lease generations
- **Evidence manifest:** Detached SHA-256 + Ed25519 signature, verification key included

### 4. Cross-Language Compatibility

Python and native C++ produce **byte-identical canonical forms** for the same capsule data:

```
C++ canonical hash:    afba67134f5c8026ed59a02ed4d6947827cc27481997ad601582e3daec9eab23
Python canonical hash: afba67134f5c8026ed59a02ed4d6947827cc27481997ad601582e3daec9eab23
RESULT: COMPATIBLE
```

### 5. Audit Fixes Applied

| Issue | Fix |
|-------|-----|
| `popen()` command execution | Replaced with `fork()/execvp()` + exit code, stderr, SIGALRM timeout |
| Three placeholder `check(..., true)` | Real filesystem, key, and capability inspections |
| `except Exception: pass` in cleanup | Logged errors with diagnostics |
| CI `container images pull` (wrong command) | Fixed to `container image pull` (singular) |
| CI conflation of simulated/real tests | Split: hosted runner for unit tests, self-hosted Apple Silicon for real VM tests |
| Migration harness labels | "LOGICAL MIGRATION SIMULATIONS (UnsafeHostProvider, not real VMs)" |
| Self-hash recursion in manifest | Detached SHA-256 file + Ed25519 signature over hash |
| Dirty git tree evidence | Pipeline aborts if working tree is not clean |
| Container CLI metadata | Package version, install source, binary SHA-256 recorded |

---

## Reproducible Pipeline

### Run the Full Pipeline

```bash
cd /Users/alep/Downloads/hdar
./run_full_pipeline.sh 100
```

This executes:
1. **Phase 1:** Environment & provenance capture (git state, toolchain, container CLI, source hashes)
2. **Phase 2:** Native C++ decisive loop (55 assertions, real VMs, ~19s)
3. **Phase 3:** 100-migration logical battle test (4×25 batches, `UnsafeHostProvider`, ~14s)
4. **Phase 4:** Failure classification & root-cause analysis
5. **Phase 5:** Cryptographic evidence bundle (manifest, detached hash, Ed25519 signature)

### Verify the Evidence

```bash
# Verify manifest hash
shasum -a 256 pipeline_output/evidence/manifest.txt | diff - pipeline_output/evidence/manifest.sha256

# Verify Ed25519 signature
openssl pkeyutl -verify -pubin \
  -inkey pipeline_output/evidence/verify_key.pem \
  -rawin -in pipeline_output/evidence/manifest.sha256 \
  -sigfile pipeline_output/evidence/manifest.sig

# Verify source hashes match
shasum -a 256 native/main.cpp

# Verify binary hash
shasum -a 256 native/hdar_native

# Re-run the decisive loop
cd native && make && ./hdar_native
```

### Artifact Inventory

| Path | Contents |
|------|----------|
| `pipeline_output/evidence/manifest.txt` | Full signed manifest with all results |
| `pipeline_output/evidence/manifest.sha256` | Detached SHA-256 of manifest |
| `pipeline_output/evidence/manifest.sig` | Ed25519 signature over manifest hash |
| `pipeline_output/evidence/verify_key.pem` | Public key for signature verification |
| `pipeline_output/evidence/battle_test_100.json` | Aggregate 100-migration results |
| `pipeline_output/evidence/battle_test_batch_{1-4}.json` | Per-batch results (25 each) |
| `pipeline_output/logs/decisive_loop.log` | Full native decisive loop output |
| `pipeline_output/logs/battle_test.log` | Full battle test output (all batches) |
| `pipeline_output/logs/battle_test_batch_{1-4}.log` | Per-batch logs |
| `pipeline_output/logs/pipeline.log` | Pipeline execution log |
| `pipeline_output/failures/*.json` | Preserved failure records with diagnostics |

---

## What Is NOT Proven (Honest Gaps)

1. **Cross-host migration** — both VMs run on the same M5 Pro. Next: VPS or second Mac.
2. **Real SSH session** — gateway logic is tested via direct C++ call, not through OpenSSH `ForceCommand`. Next: wire through `sshd`.
3. **External developer reproduction** — no one outside the original developer has run this. Next: reproduction package + 3 outside developers.
4. **Model requirements in capsule** — capsules carry workspace state, not model weights or inference configs.
5. **External side-effect reconciliation** — quiescence checking exists but no real ambiguous-effect scenarios tested.
6. **Production-grade reliability** — 100/100 on one host is strong but not production. The 1 preserved failure (blob-not-found) came from a competing-process run, not the clean pipeline.

---

## Readiness Assessment

| Dimension | Status | Evidence |
|-----------|--------|----------|
| Conceptual architecture | 90% | Two implementations (C++ + native), 23+ source files |
| Tested protocol logic | 85% | 55/55 decisive loop + 100/100 battle test |
| Integrated prototype | 65% | Real VMs, real crypto, real destruction — same host only |
| Production readiness | 25-30% | No SSH, no cross-host, no external reproduction |
| External validation | 5-10% | No outside developers yet |

---

## Seed-Round Gate Status

| Gate | Status | Evidence |
|------|--------|----------|
| Separate-runtime restoration | ✅ | 10/10 real-VM migrations (Apple Containerization); 100/100 logical migrations (UnsafeHostProvider) |
| Cryptographic lineage | ✅ | Ed25519 owner signing, host witness, offline verification (15 checks) |
| Fencing & authority | ✅ | Stale token rejection, capability attenuation, lease management |
| Tamper detection | ✅ | Capsule corruption detected, rollback rejected |
| Repeated reliability | ✅ | 100/100 logical (Wilson 95% LB = 96.3%); 10/10 real-VM (Wilson 95% LB ≈ 69.1%); 41 injected faults rejected |
| Signed evidence | ✅ | Detached SHA-256 + Ed25519 signature, full provenance |
| Reproducible pipeline | ✅ | `./run_full_pipeline.sh 100` — 5-phase automated pipeline |
| Stable SSH identity | ❌ | Gateway logic only, not through real sshd |
| Cross-host migration | ❌ | Same Mac only |
| External reproduction | ❌ | No outside developers |
| Design partners | ❌ | None yet |

**Technical readiness for $2-3M seed:** ~70-75% (up from ~60-65%)
**Blocking gaps:** SSH integration, cross-host migration, external reproduction

---

## Git Provenance

```
Commit: 1daa50d (HEAD -> main)
Pipeline commit: bb230bfa2b50008d29373430be0bc58b2728a754
Manifest hash: 639360e95b2e54bdce6458f61a4e8dbd301610e14ed95b086b7f0b0735681f5c
Signature: Verified Successfully
```
