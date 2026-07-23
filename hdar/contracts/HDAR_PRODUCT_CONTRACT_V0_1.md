# HDAR Product Contract v0.1

**Status:** Frozen Stage 0 contract  
**Contract version:** `0.1.0`  
**Capsule format reference:** `CAPSULE_SPEC.md` (draft format version 1.0)

## Product promise

HDAR suspends an agent into an owner-signed capsule, destroys the active
runtime, and restores the agent through the same logical SSH identity with its
unfinished objective, authorized workspace, attenuated authority, lineage,
and evidence intact.

This is a protocol contract, not a claim that every provider combination is
already implemented or proven. A feature is conforming only when its evidence
satisfies an acceptance test in `ACCEPTANCE_TESTS_V0_1.md`.

## Durable truth carried by a capsule

A valid capsule binds all of the following to one agent identity and epoch:

- content-addressed workspace manifest and referenced blocks;
- objective, continuation point, and working summary;
- capability grants and constraints;
- opaque secret references, never secret values;
- pending external-operation records;
- hash-linked receipts and parent lineage;
- runtime compatibility requirements;
- declared restoration class;
- owner signature and signer fingerprint.

Omission of a required durable component makes the capsule incomplete. An
incomplete capsule must be rejected, not silently downgraded.

## Invariants

1. **Owner authority:** only the owner key may advance authoritative lineage.
2. **Single continuation:** at most one live lease generation may commit
   effects or seal a successor capsule.
3. **Non-expansion:** restoration may preserve or reduce authority, never
   broaden it without a new explicit owner grant.
4. **Deny by default:** unknown capabilities and unmappable scopes are denied.
5. **Verified materialization:** referenced blocks, signatures, receipt links,
   lineage, and capability mappings are verified before execution.
6. **Semantic quiescence:** sealing is forbidden while an external effect is
   starting, submitted, or unknown.
7. **No false exactness:** exact, semantic, and degraded restorations are
   distinct outcomes with different continuation rules.
8. **Runtime destruction evidence:** a suspension is not complete until the
   provider reports the old runtime absent and its fencing token is invalid.
9. **No duplicate effects:** wake reconciliation uses stable operation IDs and
   provider idempotency evidence before retrying an uncertain effect.
10. **Offline verifiability:** capsule integrity and authoritative lineage can
    be checked without trusting the source host, destination host, or transport.

## Restoration contracts

### Exact

`exact` means all required durable state is verified byte-for-byte and all
volatile state named by the compatibility profile is preserved. The source and
destination must be compatible for process, model-engine, sampling, open-file,
network-session, shared-memory, and accelerator state. Any named volatile loss
forbids an exact classification.

Continuation may proceed without a degradation approval after lease and policy
checks pass. HDAR's current public proof does **not** establish exact live
process restoration.

### Semantic

`semantic` means the durable truth layer is verified exactly, but one or more
volatile runtime components are reconstructed or discarded. Work resumes from
the explicit continuation point, not the previous instruction or token.

The restoration report must list preserved, reconstructed, and discarded
components, disclose possible divergence, and require approval before
continuing when policy requires it. This is the class supported by the current
same-host VM-backed demonstration.

### Degraded

`degraded` means at least one requested durable capability or durable state
component cannot be preserved. The report must name every loss and authority
reduction. Degraded restoration must not execute external effects or claim
continuity until an owner explicitly approves the disclosed result.

Missing blocks, invalid signatures, broken receipt chains, unauthorized
rollback, or ambiguous identity are integrity failures, not degraded restores;
they are rejected.

## Capability attenuation

- The destination grant set must be a subset of source grants by capability
  type, scope, budget, constraints, and lifetime.
- Filesystem roots may stay equal or narrow to descendants; they may not widen.
- Network access is allowlist-based. A destination cannot introduce a new host
  or wildcard.
- Monetary and compute budgets may stay equal or decrease; they may not rise.
- Secret references may be rebound only to the same logical secret under an
  equal-or-narrower use policy. Secret values never enter the capsule.
- Unknown capability types, failed translations, and absent destination policy
  entries are denied and reported.
- Deploy and shell authority require explicit source grants and destination
  policy approval.
- A destination request for broader authority requires a new owner-signed
  grant; it cannot be treated as restoration.

## Lifecycle contract

```text
active
→ external effects reconciled
→ semantic quiescence established
→ capsule atomically sealed
→ lease generation invalidated
→ source runtime destroyed and absence verified
→ capsule transported and verified
→ exclusive wake lease acquired
→ capabilities compiled without expansion
→ runtime materialized
→ restoration class disclosed
→ continuation checkpoint resumed
```

Any interrupted transition must either resume idempotently from durable state
or stop in an explicit failure state. A green receipt without the required
provider evidence does not satisfy this contract.

## Evidence boundary at v0.1

The repository contains a same-physical-host, sequential VM-backed semantic
continuation proof. It does not by itself prove physical second-host migration,
stable public SSH restoration, cross-ISA process restoration, or hosted
multi-tenant isolation. Those remain gated by the acceptance catalog and the
unsupported-features list.

