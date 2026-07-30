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
curl -fsS https://brown-mice-shave.loca.lt/run_on_host_b.py -o run_on_host_b.py
python3 run_on_host_b.py --out /tmp/hdar-host-b-proof --host-label "$(hostname)-independent-host-b"
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
  "input_capsule": { "ok": true },
  "restore": { "exact": true },
  "lineage_advanced": true,
  "successor_capsule": { "ok": true }
}
```

The Host B platform must differ from the Host A platform in `host_a_build_report.json`.

## Claim boundary

This is a hash-only portable proof so it can run anywhere with stock Python 3.
It proves capsule transport, content-addressed verification, exact restoration,
task continuation, and successor capsule sealing.

It is not the final seed-grade proof by itself. The final seed-grade proof must
reuse the production Ed25519 owner-signature verifier and a real SSH or provider
gateway on an independent host.
