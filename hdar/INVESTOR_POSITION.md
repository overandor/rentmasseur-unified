# Agent Continuity Protocol — Investor Position

## The fundable primitive

> **One authoritative agent identity can leave Runtime A, revoke Runtime A's authority, become dormant signed state, materialize on unrelated Runtime B with reduced permissions, continue unfinished work, return verifiable evidence, advance its official lineage, and remain reachable through the same stable identity.**

## What to call it

**Agent Continuity Protocol.**

Current companies provide computers for agents. We provide continuity **between** those computers.

E2B, Daytona, Firecracker, Apple containers, Kubernetes, local Macs, and future sandbox providers become execution substrates beneath our protocol. We are not trying to outbuild every cloud. We are defining the layer that decides which continuation is legitimate when an agent moves among them.

## What already exists (do not claim invention of)

- Agent persistence (Letta Agent File)
- Sandbox snapshots (Daytona, Firecracker)
- KV cache migration/offloading (vLLM, various inference projects)
- Workload identity (SPIFFE)
- SSH routing (OpenSSH ForceCommand)
- Cryptographic receipts (emerging in public repos)
- OpenAI Agents SDK sandbox providers

## What does not exist as a mature product

The complete authoritative transition:
- One cryptographic agent identity
- One signed lineage
- One current authoritative lease
- A stale-runtime fencing mechanism
- Semantic quiescence before suspension
- Capability attenuation during migration
- Destination verification without destination ownership
- Signed destination execution evidence
- Owner-controlled re-sealing
- Stable access independent of the current host
- Offline verification of the complete chain

**That combination is our category.**

## What to tell investors

> Agent runtimes are becoming interchangeable, but agent authority and operational history are still trapped inside provider-specific sessions. We built the continuity layer that makes one signed agent identity safely movable between them. The old runtime loses authority, the destination receives only attenuated capabilities, every transition produces independently verifiable evidence, and the user reconnects through the same stable identity.

## What NOT to say

- "We invented persistent agents" — invites Letta/Daytona/OpenAI comparisons
- "We migrate an exact running LLM across arbitrary hardware" — not supported

## The investor demonstration (three-minute video)

1. Runtime A running on M5 Pro with an unfinished task
2. Capsule sealing (signed state, lineage, capabilities, effects)
3. Runtime A destroyed — named resource proven absent
4. Host B running Linux on a genuinely different machine
5. Signature verification on Host B
6. Work continuation under attenuated capabilities
7. Host B attempting and failing to use owner signing authority
8. Signed execution receipt returned to owner
9. Owner verifies receipt and signs next epoch
10. Same SSH identity reconnecting — same agent, completed task
11. Offline verifier passing with no provider access
12. One deliberate tampering attempt failing

No architecture lecture before the proof. No claim that SSD has become a GPU. No thirty repositories. No beautiful diagrams trying to substitute for the old runtime actually disappearing.

## The moat

The capsule archive itself will not be the moat. The moat comes from:

- **Fenced ownership** — every effect and state publication must present the newest generation
- **Semantic quiescence** — suspension must understand unfinished operations, not merely freeze bytes
- **Capability continuity** — every provider adapter must prove non-expansion
- **Effect reconciliation** — provider-specific mechanisms to determine whether interrupted operations committed
- **Execution witnessing** — destination signs what it performed without gaining power to sign the next epoch
- **Offline proof** — every transition remains independently verifiable when providers are unavailable

A competitor can copy the visible demo quickly. Reproducing a growing adapter library, effect-reconciliation catalog, policy compiler, verifier ecosystem, provider compatibility database, and accumulated failure evidence is substantially harder.

## Four things to finish for investor-sendable status

1. **Real isolated Runtime A creation and verified destruction**
   - Apple container CLI installed and working
   - Named container created, started, stopped, deleted
   - Post-delete inspection proves absence
   - Termination receipt signed

2. **Atomic leased ownership with stale fencing-token rejection**
   - SQLite compare-and-swap lease acquisition
   - Two concurrent restore attempts — only one wins
   - Stale holder cannot publish state, commit effects, or advance lineage
   - Fencing token monotonically increases

3. **Independent Host B restoration and signed execution witnessing**
   - Capsule transported to genuine second host (VPS)
   - Host B verifies owner signature, content blocks, agent identity, parent epoch
   - Host B receives attenuated capabilities (no deploy, no owner secrets, no epoch signing)
   - Host B creates ephemeral key and signs execution receipt
   - Host B cannot sign the next owner epoch
   - Owner verifies Host B receipt and re-seals

4. **Stable SSH reconnection plus offline verification of the entire lineage**
   - Same SSH identity reconnects after migration
   - Gateway resolves to latest capsule, acquires lease, materializes runtime
   - Offline verifier validates complete A→B→A chain with no network access
   - Tamper detection: modifying any byte, hash, signature, or token fails verification

## $3M seed requirements beyond the prototype

- Independent developer reproducing the migration
- Two design partners confirming they need provider-independent agent continuity
- Repeated migration benchmarks rather than one successful performance
- Founding team or unusually strong solo-founder execution record
- Defensible plan to become the neutral control plane

## The six-year vision

Universal exact heterogeneous LLM continuation:

> Suspend an active LLM process — including registers, process memory, inference scheduler, RNG state, KV cache, compiled kernels, accelerator streams, and partially completed generation — on Apple ARM/Metal, then resume it instruction-for-instruction on Linux x86/CUDA, ROCm, TPU, or CPU.

That may be several years away. Do not make the seed contingent on solving it.

The immediate product treats exact restoration and semantic restoration as separate contracts:
- Exact restoration when hardware and runtime compatibility permit it
- Cryptographically governed semantic continuation when they do not

**The company we can fund now is the authoritative continuity layer that works before universal exact migration exists.**

## Current build status

| Component | Status | Tests |
|-----------|--------|-------|
| Cryptographic capsule kernel | ✅ Built | 20 |
| Semantic quiescence + effect registry | ✅ Built | 5 |
| Fenced wake leases | ✅ Built | 6 |
| Capability continuity compiler | ✅ Built | 10 |
| Restoration contract (exact/semantic/degraded) | ✅ Built | 9 |
| Transport + delta | ✅ Built | 4 |
| Execution/termination receipts | ✅ Built | 7 |
| Host attestation | ✅ Built | 2 |
| Offline verifier | ✅ Built | 6 |
| SSH gateway (forced command) | ✅ Built (logic) | demo |
| Lifecycle controller | ✅ Built | 7 |
| Provider interface + unsafe host | ✅ Built | 7 |
| Apple container adapter | ⚠️ Written, CLI not installed | 0 |
| Remote SSH provider | ⚠️ Written, no second host | 0 |
| One-command demo | ✅ 48 assertions | 48 |
| **Total** | | **112 + 48 = 160** |

## What remains (infrastructure)

1. `brew install container` → real isolated materialization
2. $5/month VPS → genuine cross-host migration
3. Real sshd configuration → stable SSH identity
4. Three developers run `demo.py`
5. Two design partners
6. 100-migration stress test with published metrics
