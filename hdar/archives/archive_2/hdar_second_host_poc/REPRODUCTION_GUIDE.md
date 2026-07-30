# HDAR Cross-Platform Continuation Proof — Reproduction Guide

## Overview

This guide enables any third party to independently reproduce the HDAR Cross-Platform Continuation Proof. The proof demonstrates that a workspace state capsule, signed by an owner on Host A, can be continued on a genuinely different platform (Host B), producing a cryptographically sealed successor capsule with verifiable lineage.

## Prerequisites

- **Host A**: Any machine with Python 3.10+ and `cryptography` package
- **Host B**: Any machine with a **different OS/architecture** from Host A
  - Examples: Linux x86_64 (if Host A is macOS ARM64), Windows x86_64, etc.
- Python packages: `cryptography>=44.0.1`

## Quick Start (3 substrates)

### Option 1: E2B Cloud Sandbox (fully automated)

```bash
pip install e2b cryptography
export E2B_API_KEY="your-e2b-api-key"
python3 run_e2b_proof.py
```

This runs the entire proof end-to-end:
1. Builds deploy package on Host A (your Mac)
2. Spawns an E2B Linux sandbox (Host B)
3. Executes the 5-stage pipeline on Host B
4. Downloads artifacts
5. Terminates the sandbox
6. Runs the verifier on Host A (post-destruction)

**Expected result**: 15/15 checks passed

### Option 2: GitHub Codespaces

```bash
# Create or use an existing Codespace
gh codespace create --repo your-repo --machine basicLinux32gb

# Run the proof
bash run_codespace_proof_existing.sh <codespace-name>
```

This runs:
1. Transfers deploy package to Codespace (Host B, Ubuntu x86_64)
2. Runs Host B pipeline on Codespace
3. Runs verifier on Codespace (portability test)
4. Downloads artifacts to Host A
5. Deletes the Codespace
6. Runs verifier on Host A (authoritative, post-destruction)

**Expected result**: 13/13 checks passed (both on Codespace and Host A)

### Option 3: Google Colab (local simulation)

```bash
python3 run_colab_proof.py
```

Simulates Colab execution locally. The `platforms_differ` check will fail if run on the same machine (expected behavior). On a real Colab runtime (Linux x86_64), all checks pass.

**Expected result**: 12/13 checks passed (1 expected failure: `platforms_differ`)

### Option 4: Manual two-machine proof

1. **Build the deploy package on Host A:**
```bash
cd deploy-package
python3 build_deploy_package.py --out ./deploy-package
```

2. **Transfer to Host B** (any independent machine):
```bash
scp deploy-package/* user@host-b:~/hdar-demo/
```

3. **Run Host B:**
```bash
ssh user@host-b
cd ~/hdar-demo
pip install cryptography==44.0.1
python3 run_on_host_b.py \
  --bundle transport_capsule_epoch_1_signed.tar.gz \
  --host-a-report host_a_build_report.json \
  --owner-public-key $(cat owner_public_key.txt) \
  --verify-runner-hash <runner-sha256> \
  --host-label my-host-b \
  --operator-identity 'your-name' \
  --out host_b_output
```

4. **Transfer artifacts back to Host A:**
```bash
scp -r user@host-b:~/hdar-demo/host_b_output/ ./results/
scp -r user@host-b:~/hdar-demo/capsule_epoch_1/ ./results/
```

5. **Run the verifier on Host A:**
```bash
python3 deploy-package/third_party_verifier.py \
  --capsule-e1 results/capsule_epoch_1 \
  --capsule-e2 results/host_b_output/capsule_epoch_2 \
  --host-b-report results/host_b_output/host_b_report.json \
  --evidence-packet results/host_b_output/host_b_evidence_packet.json \
  --owner-public-key $(cat deploy-package/owner_public_key.txt) \
  --host-a-platform "$(python3 -c 'import platform; print(platform.platform())')"
```

## Verification Checks

The verifier performs up to 15 checks:

| # | Check | Description |
|---|-------|-------------|
| 1 | `owner_signature` | Host A Ed25519 signature on E1 capsule verified |
| 2 | `e1_integrity` | E1 capsule manifest, content blocks, and receipt verified |
| 3 | `e2_integrity` | E2 capsule manifest, content blocks, and receipt verified |
| 4 | `lineage` | E1 → E2 chain: parent hash + epoch +1 |
| 5 | `state_advanced` | Workspace root hash changed (state actually advanced) |
| 6 | `host_b_signature` | Host B Ed25519 signature on report verified |
| 7 | `task_continuation` | Deterministic 5-stage pipeline output hash matches |
| 8 | `platforms_differ` | Host A platform ≠ Host B platform |
| 9 | `report_e1_cross_check` | Host B report input_capsule matches E1 manifest |
| 10 | `report_e2_cross_check` | Host B report successor_capsule matches E2 manifest |
| 11 | `evidence_packet_signature` | Evidence packet has independent Ed25519 signature |
| 12 | `semantic_correctness` | 5 predicates: category sums, rejected IDs, tier memberships, structural checks, final report summary |
| 13 | `stage_chain` | Internal Merkle-like stage chain (parse→filter→aggregate→classify→report) |
| 14 | `sandbox_terminated` | Sandbox confirmed terminated before verifier ran (E2B only) |
| 15 | `environment_manifest` | Pinned dependencies recorded (E2B only) |

## Semantic Predicates (Check 12)

The verifier independently recomputes expected results from the input records in the E1 capsule and compares against the E2 capsule's stage outputs:

1. **Category sums**: For each category, the sum of values in `stage_aggregate.json` must match the independently computed sum
2. **Rejected record IDs**: The set of rejected record IDs in `stage_filter.json` must match exactly
3. **Tier memberships**: For each tier (critical/high/medium/low), the set of member IDs in `stage_classify.json` must match
4. **Structural checks**: 5 stages completed, task name correct, output hash matches expected
5. **Final report summary**: Total input, valid records, and rejected counts in `final_report.json` must match

## Lifecycle Events

The evidence packet records the full Host B lifecycle:

| Event | When | Recorded By |
|-------|------|-------------|
| `host_b_provisioned` | Runner starts | Host B runner |
| `capsule_restored` | E1 capsule extracted | Host B runner |
| `task_executed` | 5-stage pipeline completes | Host B runner |
| `successor_sealed` | E2 capsule sealed | Host B runner |
| `evidence_archived` | Report + evidence packet signed | Host B runner |
| `host_b_destroyed` | Sandbox/Codespace terminated | Host A orchestrator (post-sign) |

The first 5 events are part of the signed evidence packet body. The `host_b_destroyed` event is appended after signing (the Host B key is gone with the sandbox) and is marked with `lifecycle_events_post_sign: true`.

## Version Binding

The verifier output includes a `version_binding` block:

```json
{
  "protocol_version": "hdar.transport-capsule/v0.1",
  "verifier_version": "0.3",
  "worker_version": "1.1",
  "ruleset_version": "seed-criterion-v2",
  "environment_manifest_hash": "<sha256>"
}
```

This binds the verification result to exact protocol, verifier, worker, and ruleset versions, plus the environment manifest hash for reproducibility.

## Interpreting Results

- **All checks passed**: The proof is valid. Host B genuinely continued the workspace state on a different platform, and the verifier independently confirmed semantic correctness.
- **`platforms_differ` failed**: Host B ran on the same platform as Host A. This is expected in local simulations. Use a genuinely different platform for a valid proof.
- **`semantic_correctness` failed**: The pipeline output does not match independent recomputation. This indicates either a bug in the worker or tampering with the stage outputs.
- **`evidence_packet_signature` failed**: The evidence packet's signature is invalid. This could indicate tampering or a post-sign modification that wasn't properly excluded.

## File Structure

```
hdar_second_host_poc/
├── deploy-package/
│   ├── build_deploy_package.py    # Builds signed deploy package
│   ├── run_on_host_b.py           # Host B runner (self-contained)
│   ├── third_party_verifier.py    # Independent verifier
│   ├── worker_template.py         # 5-stage pipeline template
│   ├── INSTRUCTIONS.txt           # Step-by-step instructions
│   └── capsule_epoch_1/           # E1 capsule (extracted)
├── run_e2b_proof.py               # E2B fully automated proof
├── run_colab_proof.py             # Colab local simulation
├── run_codespace_proof_existing.sh # Codespace proof (existing CS)
├── run_two_machine_demo.sh        # Codespace proof (creates CS)
└── REPRODUCTION_GUIDE.md          # This file
```
