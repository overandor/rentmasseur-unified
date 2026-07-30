# HDAR real Host B runbook

This directory contains a portable, self-contained HDAR transport proof bundle
with Ed25519 owner signing, Host B signature verification, and third-party
verification support.

## Current proof status

**The cryptographic chain is verified locally. The remaining gap is a genuinely
independent Host B machine.**

The runner demonstrates:
- Owner Ed25519 signing of capsule E1 (step 1)
- Host B verification of owner signature (step 4)
- Capsule transport, content-addressed verification, exact workspace restoration
- Deterministic task continuation, epoch advancement, successor capsule sealing
- Host B Ed25519 report signing (step 7)
- Third-party verification of all signatures, lineage, and capsules (step 8)

Local end-to-end test passes all 9 third-party verification checks.

## Public bundle URLs

Transport is replaceable. Any HTTPS file server works. Example URLs:

```text
https://brown-mice-shave.loca.lt/run_on_host_b.py
https://brown-mice-shave.loca.lt/host_a_build_report.json
```

## Step 1 (Host A): Sign capsule E1 with owner Ed25519 key

Before distributing the bundle, Host A signs the capsule manifest:

```bash
python3 owner_sign_capsule.py sign \
  --capsule-dir capsule_epoch_1 \
  --owner-key-file owner_keypair.json
```

This generates an Ed25519 keypair (if one doesn't exist), signs the manifest,
and embeds `owner_signature`, `owner_public_key`, and `owner_signature_algorithm`
into the manifest. The `manifest_hash` and receipt are recomputed.

Record the owner public key for Host B and the third-party verifier:

```bash
OWNER_PUB=$(python3 -c "import json; print(json.load(open('owner_keypair.json'))['public_key_hex'])")
echo "Owner public key: $OWNER_PUB"
```

## Step 2 (Host A): Shut down or disconnect

Host A must be shut down or disconnected after sealing and signing E1.

## Step 3 (Host B): Download the bundle

Use a machine that is not Host A and does not share Host A's filesystem.

```bash
curl -fsS https://brown-mice-shave.loca.lt/run_on_host_b.py -o run_on_host_b.py
curl -fsS https://brown-mice-shave.loca.lt/host_a_build_report.json -o host_a_build_report.json
```

## Step 4 (Host B): Verify runner hash

```bash
RUNNER_SHA="d577c5ee836491fd39e9c512d4bf2b01ef5474a7f034c2c67f2f14a2bbfc930c"
printf '%s  %s\n' "$RUNNER_SHA" "run_on_host_b.py" | shasum -a 256 -c -

# Extract owner public key from Host A build report
OWNER_PUB=$(python3 -c "import json; print(json.load(open('host_a_build_report.json'))['capsule_epoch_1']['owner_public_key'])")
echo "Owner public key: $OWNER_PUB"
```

## Step 5 (Host B): Run with full verification including owner signature

```bash
python3 run_on_host_b.py \
  --out /tmp/hdar-host-b-proof \
  --host-label "$(hostname)-independent-host-b" \
  --host-a-report host_a_build_report.json \
  --verify-runner-hash "$RUNNER_SHA" \
  --owner-public-key "$OWNER_PUB" \
  --network-source "https://brown-mice-shave.loca.lt/run_on_host_b.py" \
  --operator-identity "your-pseudonym"
```

The `--owner-public-key` flag triggers step 4 of the seed criterion: Host B
verifies the owner's Ed25519 signature on the capsule manifest before
proceeding with restoration.

The `--host-a-report` flag triggers external bundle hash verification: the
decoded bundle's SHA-256 is cross-checked against `transport_capsule_tar.sha256`
in the Host A build report. This prevents circular trust where the bundle hash
is verified only against a constant embedded in the same file.

### Prerequisites

- Python 3.8+
- `cryptography` package (required for Ed25519 signing)

```bash
pip install cryptography
```

### Flags

| Flag | Purpose |
|------|---------|
| `--owner-public-key` | Owner Ed25519 public key hex for capsule signature verification (step 4) |
| `--verify-runner-hash` | Expected SHA-256 of the runner script |
| `--host-a-report` | Path to Host A build report for independent capsule verification |
| `--network-source` | URL from which the runner was downloaded |
| `--operator-identity` | Operator identity or pseudonym for the Host B run |
| `--download-headers` | Path to JSON file with download response headers |

## Return these files

```text
/tmp/hdar-host-b-proof/host_b_report.json
/tmp/hdar-host-b-proof/host_b_evidence_packet.json
/tmp/hdar-host-b-proof/successor_capsule_epoch_2.tar.gz
/tmp/hdar-host-b-proof/capsule_epoch_2/
```

## Step 8 (Third Party): Independent verification

A third party — neither Host A nor Host B — verifies the complete chain:

```bash
python3 third_party_verifier.py \
  --capsule-e1 capsule_epoch_1 \
  --capsule-e2 /tmp/hdar-host-b-proof/capsule_epoch_2 \
  --host-b-report /tmp/hdar-host-b-proof/host_b_report.json \
  --owner-public-key "$OWNER_PUB" \
  --host-a-platform "macOS-26.5.2-arm64-arm-64bit-Mach-O"
```

The verifier checks:
1. Host A owner Ed25519 signature on E1
2. E1 capsule integrity (manifest, blocks, receipt)
3. E2 capsule integrity (manifest, blocks, receipt)
4. Lineage chain (E1 hash == E2 parent, epoch +1)
5. State advancement (root hash changed)
6. Host B Ed25519 signature on report
7. Task continuation passed
8. Report-E1 and Report-E2 cross-checks
9. Platforms differ (independent host evidence)

Exit code 0 = all checks passed.

## Acceptance criteria

The returned `host_b_report.json` must show:

```json
{
  "schema": "hdar.second-host-proof-report/v0.3",
  "runner_sha256_verified": true,
  "host_a_report_verification": {
    "provided": true,
    "manifest_hash_match": true,
    "platforms_differ": true
  },
  "input_capsule": {
    "ok": true,
    "receipt_verified": { "ok": true },
    "owner_signature_verified": { "ok": true }
  },
  "restore": { "exact": true },
  "task_continuation": { "ok": true, "passed": true },
  "lineage_advanced": true,
  "successor_capsule": { "ok": true, "receipt_verified": { "ok": true } },
  "host_b_signature_algorithm": "ed25519"
}
```

The third-party verifier must exit 0 with all 9 checks passing.

## Local end-to-end test

Run the full 8-step chain locally to verify the cryptographic logic:

```bash
python3 test_seed_criterion.py
```

Expected output: `ALL CHECKS PASSED -- cryptographic chain verified`

This is a **local simulation** -- both hosts run on the same machine. The
`platforms_differ` check is not included. For a real seed proof, run Host B
on an independent machine.

## Claim boundary

This bundle now includes Ed25519 owner signing (step 1), Host B owner signature
verification (step 4), Host B report signing (step 7), and third-party
verification (step 8).

The remaining gap for full seed-grade proof is:
- A genuinely independent Host B machine (not the same macOS host)
- The `platforms_differ` check passing in the third-party verifier
- At least one external operator reproducing the entire chain
