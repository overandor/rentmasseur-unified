# HDAR Threat Model and Trust Boundaries v0.1

## Protected assets

- owner signing authority and authoritative agent lineage;
- workspace content and content-addressed blocks;
- objectives, continuation checkpoints, and pending obligations;
- capability grants, budgets, and secret references;
- effect IDs, idempotency records, leases, and fencing generations;
- execution, suspension, destruction, migration, and restoration evidence;
- stable agent-to-capsule identity resolution.

## Trust boundaries

| Component | Trust granted | Must not be trusted for |
|---|---|---|
| Owner signer | Authoritative epoch advancement and explicit grants | Host execution truth without receipts |
| Lease/fencing authority | Exclusive generation issuance and invalidation | Capsule content integrity |
| Offline verifier | Deterministic validation using pinned keys and artifacts | Runtime destruction it cannot observe |
| Secret broker | Reference resolution under capability and lease policy | Lineage advancement |
| SSH identity resolver | Agent-to-capsule routing and exclusive wake coordination | Capsule signatures or host claims |
| Source/destination provider | Availability and provider-specific measurements | Owner authority, capsule integrity, or silent restoration classification |
| Capsule store and transport | Byte delivery and availability | Integrity, freshness, ordering, or confidentiality unless separately encrypted |
| Agent/runtime process | Work within granted capabilities | Policy definition, lease issuance, or self-attestation |

`UnsafeHostProvider` is a development adapter and crosses no isolation
boundary. Evidence produced with it must never be labeled isolated execution.

## Threats and required controls

| Threat | Required control | Failure behavior |
|---|---|---|
| Modified block or manifest | Content hashes plus owner signature | Reject |
| Receipt insertion, deletion, or reordering | Hash-linked signed receipt chain | Reject |
| Old capsule replay | Parent binding, monotonic epoch, anti-rollback state | Reject |
| Two concurrent wakes | Exclusive lease and monotonically increasing fencing token | Permit one; reject the other |
| Destroyed runtime commits later | Fencing checks on effects, secret access, and sealing | Reject stale generation |
| Destination grants broader authority | Capability compiler and offline non-expansion check | Reject grant |
| Unknown external-effect outcome | Durable pending registry and idempotency reconciliation | Block seal/retry until reconciled |
| Malicious destination host forges continuity | Host witness is non-authoritative; owner key remains absent | Reject successor without owner seal |
| Transport truncates capsule | Required-file inventory and block verification | Reject incomplete capsule |
| Provider lies about destruction | Provider-specific absence evidence plus fencing invalidation | Do not claim destruction; keep transition incomplete |
| Secret disclosure through capsule | Store opaque references only; broker enforces scoped resolution | Reject embedded secret material |
| Compatibility mismatch hidden as success | Signed restoration report and class-specific policy | Block or require approval |
| Stable SSH identity resolves stale fork | Resolver checks authoritative head and lease generation | Reject stale branch |

## Out of scope for v0.1

- physical compromise of the owner signing environment;
- denial of service by a provider, store, transport, or network;
- confidentiality of unencrypted capsule artifacts at rest;
- malicious model output that remains within granted capabilities;
- side-channel resistance beyond the selected runtime provider;
- correctness of third-party APIs used to reconcile effects.

These exclusions do not permit authority escalation, forged evidence, or false
restoration claims; they bound what the current protocol can guarantee.

