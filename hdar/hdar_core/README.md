# Hardware-Detached Agent Runtime

A storage-rooted, proof-carrying runtime for persistent AI agents.

MirrorLease, the narrow local file-to-agent authority protocol, is specified in
[`MIRRORLEASE_SPEC.md`](MIRRORLEASE_SPEC.md). Its machine-readable evidence
boundary is [`MIRRORLEASE_CLAIM_STATUS.json`](MIRRORLEASE_CLAIM_STATUS.json).
The installed Finder workflow is documented in
[`MirrorLeaseFinderQuickAction/README.md`](MirrorLeaseFinderQuickAction/README.md).

See `../FOUNDER_PROOF_BRIEF.md` for the canonical thesis.

## Phase one: Capsule core

Content-addressed storage, atomic sealing, agent identity, lineage epochs,
hash-linked receipts, signature verification, and workspace reconstruction.

### Pass condition

```
workspace → sealed capsule → original workspace deleted → restored workspace matches its recorded root hash
```

### Run the test

```bash
python3 -m pytest tests/test_phase1.py -v
# or
python3 tests/test_phase1.py
```
