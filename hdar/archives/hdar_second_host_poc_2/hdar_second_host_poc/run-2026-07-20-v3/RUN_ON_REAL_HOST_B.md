# HDAR real Host B runbook

This directory contains a portable, self-contained HDAR transport proof bundle.

Public bundle URL while the local tunnel is running:

```text
https://brown-mice-shave.loca.lt/run_on_host_b.py
```

Public Host A build report:

```text
https://brown-mice-shave.loca.lt/host_a_build_report.json
```

## Run on an independent Host B

Use a machine that is not this Mac and does not share this filesystem.

```bash
# 1. Download the runner
curl -fsS https://brown-mice-shave.loca.lt/run_on_host_b.py -o run_on_host_b.py

# 2. Download the Host A report (separately authenticated channel)
curl -fsS https://brown-mice-shave.loca.lt/host_a_build_report.json -o host_a_build_report.json

# 3. Verify the runner hash (audit fix #1)
RUNNER_SHA="eadf97be028383ce1834351127ead80b0fc27a2aebc71a0183f56843b61bfcb6"
printf '%s  %s\n' "$RUNNER_SHA" "run_on_host_b.py" | shasum -a 256 -c -

# 4. Run with full verification
python3 run_on_host_b.py \
  --out /tmp/hdar-host-b-proof \
  --host-label "$(hostname)-independent-host-b" \
  --host-a-report host_a_build_report.json \
  --verify-runner-hash "$RUNNER_SHA"
```

Return these files:

```text
/tmp/hdar-host-b-proof/host_b_report.json
/tmp/hdar-host-b-proof/successor_capsule_epoch_2.tar.gz
```

## Acceptance criteria

The returned `host_b_report.json` must show:

```json
{
  "runner_sha256_verified": true,
  "host_a_report_verification": {
    "provided": true,
    "manifest_hash_match": true,
    "platforms_differ": true
  },
  "input_capsule": { "ok": true, "receipt_verified": { "ok": true } },
  "restore": { "exact": true },
  "task_continuation": { "ok": true, "passed": true },
  "lineage_advanced": true,
  "successor_capsule": { "ok": true, "receipt_verified": { "ok": true } }
}
```

The Host B platform must differ from the Host A platform in `host_a_build_report.json`.

The `task_continuation` must show `passed: true` — Host B completed the deterministic sum-of-primes task and the result matches the expected value.

## Claim boundary

This is a hash-only portable proof so it can run anywhere with stock Python 3.
It proves capsule transport, content-addressed verification, exact restoration,
task continuation, and successor capsule sealing.

It is not the final seed-grade proof by itself. The final seed-grade proof must
reuse the production Ed25519 owner-signature verifier and a real SSH or provider
gateway on an independent host.
