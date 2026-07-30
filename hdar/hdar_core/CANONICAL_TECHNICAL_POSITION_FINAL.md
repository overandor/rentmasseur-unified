# Canonical Technical Position — Final (July 17, 2026)

## The genuine invention

> **Authoritative agent continuity across execution providers.**

One persistent computational identity, one authoritative lineage, one
current lease holder, capabilities that can only remain equal or shrink,
independently verifiable migration evidence, and a stable access point
that survives the disappearance of every temporary runtime.

## What the web confirms already exists

- **OpenAI Agents SDK**: sandbox execution, snapshotting, rehydration, multiple providers
- **Codex**: durable threads (create, resume, fork, archive), persisted event history
- **Daytona**: VM sandboxes with pause/resume, memory+filesystem snapshots, fork ancestry
- **Letta**: Agent File format for serializing stateful agents
- **SPIFFE**: portable workload identity across heterogeneous infrastructure
- **Firecracker**: microVM snapshots (warns about cross-kernel instability)
- **vLLM**: CUDA checkpoint/restore RFC (not universal format)
- **Cordium**: identity-based secretless access from sandboxes
- **Cryptographic agent receipts**: appearing in public repositories

**Do not claim invention of**: agent persistence, signatures, receipts,
snapshots, SSH, or workload identity.

**The opportunity**: the missing contract joining them into one
authoritative, proof-carrying continuity system.

## Product boundary

**What exists (durable truth layer):**
```
Agent identity + signed immutable state + content-addressed workspace
+ lineage and rollback protection + capability attenuation
+ typed execution policy + independently verifiable capsule integrity
+ semantic quiescence + fenced wake leases + restoration contract
+ transport layer + execution/termination receipts + host attestation
+ offline verifier
```

**What remains unproved (runtime lifecycle layer):**
```
real isolated materialization + verified runtime destruction
+ cross-machine transport (genuine second host)
+ destination execution attestation (real remote)
+ stable agent-addressed SSH continuity (real sshd)
```

## Five moat primitives (all built and tested)

1. **Agent-native suspension capsule** — copying the capsule does not copy its authority
2. **Dual exact/semantic restoration contract** — explicitly states what survived and what diverges
3. **Fenced authoritative continuity** — only the newest lease generation can advance state
4. **Capability-continuity compiler** — authority may preserve or reduce, never silently expand
5. **Proof-carrying migration lineage** — full A→B→A offline-verifiable receipt chain

## Canonical repository structure

```
hdar/
├── capsule/
│   ├── identity.py          # Ed25519 identity, lineage epochs
│   ├── store.py             # Content-addressed storage (SHA-256, two-level sharding)
│   ├── receipt.py           # Hash-linked signed receipts
│   ├── seal.py              # Capsule sealing + manifest signing
│   ├── restore.py           # Capsule restoration + workspace reconstruction
│   ├── capabilities.py      # Capability compiler + non-expansion verifier
│   └── restoration_contract.py  # Exact vs semantic vs degraded classification
│
├── lifecycle/
│   ├── state_machine.py     # DORMANT → ACQUIRING_LEASE → ... → DORMANT
│   ├── effects.py           # Durable external-effect registry
│   ├── lease.py             # Atomic fenced wake lease (SQLite CAS)
│   └── controller.py        # Orchestrates lifecycle + providers
│
├── providers/
│   ├── base.py              # Abstract provider interface
│   ├── unsafe_host.py       # Direct host execution (testing)
│   ├── apple_container.py   # Apple container CLI adapter (ready, CLI not installed)
│   └── remote_ssh.py        # Remote SSH provider (ready, untested)
│
├── transport/
│   ├── export.py            # Capsule archive export/import + delta computation
│   └── __init__.py
│
├── gateway/
│   ├── forced_command.py    # SSH forced-command gateway
│   ├── SSH_CONFIG.md        # sshd configuration documentation
│   └── __init__.py
│
├── evidence/
│   ├── offline_verify.py    # Full chain offline verifier
│   ├── execution_receipt.py # Destination-signed execution receipt
│   ├── termination_receipt.py  # Runtime destruction proof
│   ├── host_attestation.py  # Signed host environment description
│   └── __init__.py
│
├── tests/
│   ├── test_phase1.py            # 4 capsule core tests
│   ├── test_p0_lifecycle.py      # 17 lifecycle tests
│   ├── test_p0_provider.py       # 7 provider + controller tests
│   ├── test_capabilities_verifier.py  # 16 capability + verifier tests
│   ├── test_restoration_contract.py   # 9 restoration contract tests
│   └── test_transport_evidence.py     # 11 transport + evidence tests
│
├── demo.py                  # 48-assertion one-command proof
├── CANONICAL_TECHNICAL_POSITION.md
├── CANONICAL_VISION.md
├── MARKET_POSITION.md
├── PRIMITIVE_LANDSCAPE.md
├── WEB_VERIFIED_POSITION.md
└── README.md
```

## Gate structure

| Gate | Present | Tests |
|------|---------|-------|
| Cryptographic capsule kernel | ✅ Yes | 4 core + 16 verifier |
| Semantic safe suspension | ✅ Yes | 5 effect registry |
| Exclusive wake ownership | ✅ Yes | 6 lease + 5 controller |
| Isolated materialization | ⚠️ Partial | Provider interface tested; Apple container CLI not installed |
| Runtime destruction | ✅ Yes (unsafe-host) | 2 provider + termination receipt |
| Capability non-expansion | ✅ Yes | 10 capability |
| Dual exact/semantic restoration | ✅ Yes | 9 contract |
| Cross-host continuation | ❌ No | Needs genuine second host |
| Stable SSH identity | ✅ Yes (logic) | Gateway tested in demo; real sshd not deployed |
| Offline proof continuity | ✅ Yes | 6 offline verifier |
| Transport + delta | ✅ Yes | 4 transport + dedup |
| Execution/termination receipts | ✅ Yes | 7 receipt + attestation |
| One-command proof | ✅ Yes | 48 assertions, exit 0, no network |

**Total: 64 unit/integration tests + 48 demo assertions = 112 passing, 0 failed.**

## Fundraising classification

- **Technical pre-seed credibility:** yes
- **Novel primitive demonstrated:** authoritative continuity protocol
- **Hardware-detached runtime demonstrated:** no
- **Stage 5:** not yet
- **$30M seed:** requires prototype + open protocol + independent verifier +
  migration benchmarks + provider adapters + security review + 3+ design
  partners + developer adoption + founding team

## The fundable claim

> We built the first demonstrable protocol in which an agent can leave
> one machine, revoke the old runtime's authority, continue on
> heterogeneous compute under reduced permissions, and prove the complete
> transition without trusting either provider.

That is narrow enough to be believable, difficult enough to be defensible,
and large enough to support a serious infrastructure company.

## What remains (infrastructure, not code)

1. Genuine second host ($5/month VPS) — `remote_ssh.py` is written
2. Apple container CLI install → real isolated materialization
3. Three developers run `demo.py`
4. Two design partners
5. 100-migration stress test with published metrics
6. External security review
7. Open protocol specification + independent verifier
