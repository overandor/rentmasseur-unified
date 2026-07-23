# Primitive Landscape — 13 Missing Primitives (July 2026)

As of July 17, 2026, no mature public repository implements these as
reusable, end-to-end primitives. The ecosystem has fragments (CRIU,
Firecracker, Daytona, vLLM, SPIFFE, Cordium) but nobody has assembled
them into a provider-neutral, hardware-detached agent runtime.

## The 13 primitives

1. **Agent-native suspension capsule** — packages agent as persistent computational entity (not just files or VM state)
2. **Semantic quiescence barrier** — proves agent reached safe boundary before suspension
3. **Cross-ISA process-state translator** — ARM64 → x86-64 → RISC-V execution state translation
4. **Universal accelerator-state IR** — vendor-neutral representation for suspended GPU/TPU/Accelerator computation
5. **Portable inference-continuation state** — KV cache, sampling RNG, logit processors across engines
6. **Dual exact-and-semantic restoration protocol** — explicitly distinguishes exact vs semantic restore
7. **Capability-continuity lattice** — authority mapping with attenuation, never expansion
8. **Portable secret-reference rebinding** — use authority without possessing credentials
9. **Proof-carrying migration receipt chain** — cryptographic chain of custody for transitions
10. **Agent-addressed SSH identity resolver** — SSH addresses the agent, not the machine
11. **Transactional external-session continuation** — safely continue or reconstruct active external relationships
12. **Fork-, rollback-, and merge-safe computational identity** — signed lineage, monotonic epochs, anti-rollback
13. **Universal materialize-run-collapse scheduler** — accepts dormant capsule, auto-resolves through collapse

## Three deepest primitives

1. Agent-native suspension capsule
2. Universal accelerator-state representation
3. Capability-continuity lattice

Once those exist, the rest becomes brutal systems engineering. Without
them, HDAR remains snapshots + containers + identity + SSH + receipts
that cannot honestly claim provider-neutral operational continuity.

## Current build status

| # | Primitive | Status |
|---|---|---|
| 1 | Suspension capsule | ✅ Built + tested |
| 2 | Semantic quiescence | ✅ Built + tested |
| 3 | Cross-ISA translator | ❌ Not started (research-level) |
| 4 | Accelerator-state IR | ❌ Not started (research-level) |
| 5 | Inference-continuation | ❌ Not started |
| 6 | Dual exact/semantic restore | ⚠️ Partial (semantic only) |
| 7 | Capability-continuity lattice | ✅ Built + tested (compiler + non-expansion) |
| 8 | Secret-reference rebinding | ❌ Not started |
| 9 | Proof-carrying receipt chain | ✅ Built + tested (receipts + offline verifier) |
| 10 | Agent-addressed SSH resolver | ✅ Built + tested (gateway) |
| 11 | External-session continuation | ⚠️ Partial (effect registry handles idempotency) |
| 12 | Fork-safe identity | ⚠️ Partial (lineage epochs, anti-rollback) |
| 13 | Materialize-run-collapse scheduler | ✅ Built + tested (lifecycle controller) |

## Monthly GitHub watch

Track these categories to catch first serious implementations before
the avalanche of repositories renaming ordinary checkpointing as
"immortal agent infrastructure."
