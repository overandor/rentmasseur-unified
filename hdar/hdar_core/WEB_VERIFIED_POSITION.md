# Web-Verified Position — July 17, 2026

## The genuine invention (narrower and stronger than "persistent sandbox")

> **Authoritative agent continuity across execution providers.**

One persistent computational identity, one authoritative lineage, one current
lease holder, capabilities that can only remain equal or shrink, independently
verifiable migration evidence, and a stable access point that survives the
disappearance of every temporary runtime.

## What the web confirms already exists

- **OpenAI Agents SDK**: native sandbox execution, snapshotting, rehydration,
  multiple execution providers. "One agent framework that survives a lost
  container" is NOT our unique claim.
- **Codex**: durable threads (create, resume, fork, archive), persisted event
  history, sandbox execution under policy.
- **Daytona**: VM sandboxes with pause/resume, memory+filesystem snapshots,
  fork with tracked ancestry, explicit lifecycle states.

**Respect boundaries**: pause, resume, memory snapshots, persistent filesystems,
sandbox deletion, and fork ancestry are NOT the new primitive.

## What our system governs that those platforms do not yet define together

- Which restored runtime is the sole authoritative continuation
- Whether a transition is exact or merely semantic
- Whether authority was preserved, reduced, or illegally expanded
- Whether external effects can safely continue without duplication
- Whether the destination can prove what it executed
- Whether the full chain can be verified independently of every provider

## Five primitives that form the true moat

1. **Agent-native suspension capsule** — portable signed representation of
   identity, task state, obligations, permissions, evidence, restoration requirements
2. **Dual exact-and-semantic restoration contract** — states precisely what
   survived, what was reconstructed, what divergence is possible
3. **Fenced authoritative continuity** — many copies may exist, but only the
   newest lease generation can commit effects or advance lineage
4. **Capability-continuity and secretless rebinding** — destination uses
   attenuated authority without receiving transferable secrets
5. **Proof-carrying migration lineage** — source termination, lease transfer,
   destination verification, remote execution, returned deltas, owner re-sealing
   form one offline-verifiable chain

## The fundable claim

> We created the authoritative continuity protocol that lets an agent leave
> one provider, surrender the old runtime's authority, materialize under
> reduced capabilities elsewhere, continue its work, and prove the entire
> transition independently.

NOT: "We made containers persistent."

## Exact vs semantic restoration (do not soften this distinction)

- **Exact**: preserves memory, processes, runtime state, accelerator state
  when source and destination are sufficiently compatible
- **Semantic**: preserves durable identity, files, goals, obligations, evidence,
  permissions, safe continuation point while rebuilding execution on different hardware

The industry repeatedly uses "resume" to describe everything from restoring RAM
to replaying a prompt and hoping the model develops the same personality.

## Build status against the five moat primitives

| Moat primitive | Status | Tests |
|---|---|---|
| #1 Suspension capsule | ✅ Built | 4 core + 16 verifier tests |
| #2 Dual exact/semantic | ⚠️ Partial (semantic only, contract labeled) | — |
| #3 Fenced continuity | ✅ Built | 6 lease + 5 controller tests |
| #4 Capability continuity | ✅ Built | 10 capability tests |
| #5 Proof-carrying lineage | ✅ Built | 6 offline verifier tests |

**83 test assertions, all passing. 42-assertion one-command demo.**

## What remains (none of it is more code for pre-seed)

1. Genuine second host ($5/month VPS)
2. Three developers run `demo.py`
3. Two design partners
4. Apple container CLI install → real isolated materialization
5. 100-migration stress test with published metrics
