# Open Capsule and Receipt Specification

**Version:** 1.0  
**Status:** Draft for public review

## 1. Purpose

This specification defines a provider-neutral format for suspending,
transporting, and resuming autonomous AI agents across heterogeneous
execution environments.

A capsule is a signed, content-addressed artifact that carries an
agent's complete operational state: workspace, objectives, authority,
evidence, and lineage. Any host can verify a capsule offline without
trusting the source provider, the transport layer, or any intermediary.

The specification does not define container formats, runtime
interfaces, or model-serving protocols. It defines only the durable
state format and the cryptographic evidence chain that binds it.

## 2. Key Concepts

### 2.1 Owner

The owner holds an Ed25519 private signing key. Only the owner can
advance the authoritative agent lineage by sealing a new capsule
epoch. Hosts, providers, and intermediaries cannot.

### 2.2 Host

A host is any execution environment that materializes an agent from a
capsule. A host receives the owner's public key for verification but
never receives the owner's private key. A host signs its own
execution-witness receipt using an ephemeral key.

### 2.3 Capsule

A capsule is a JSON document containing a manifest, workspace
references, capabilities, pending obligations, and a receipt chain.
It is content-addressed by the SHA-256 of its canonical serialization.

### 2.4 Epoch

An epoch is a point in the agent's lineage tree. Each capsule belongs
to exactly one epoch. Epochs are monotonically increasing within a
lineage branch. A child epoch references its parent epoch and parent
capsule hash.

### 2.5 Fencing Token

A fencing token is a monotonically increasing, single-use credential
issued by the lease manager. Every state-changing operation must
present the current valid token. When a lease is released or expires,
the token becomes permanently invalid. A stale runtime holding an old
token cannot seal capsules, commit effects, or advance lineage.

## 3. Cryptographic Primitives

### 3.1 Signing Algorithm

All signatures use Ed25519 (RFC 8032). The owner generates an
Ed25519 key pair. The private key never leaves the owner's control.
Hosts generate ephemeral Ed25519 key pairs for execution-witness
receipts.

HMAC-SHA256 is permitted only for internal receipt chain linkage
hashes, not for authoritative signatures.

### 3.2 Hashing

SHA-256 is used for all content addressing, manifest hashing, and
receipt chaining.

### 3.3 Canonical Serialization

All JSON objects are canonicalized before hashing or signing:

- Keys sorted lexicographically (UTF-8 byte order)
- Separators: `(",", ":")`
- No whitespace
- `ensure_ascii=True`
- No trailing newline

## 4. Capsule Manifest

```json
{
  "spec_version": "1.0",
  "agent_id": "agent-<hex>",
  "agent_name": "<string>",
  "epoch": {
    "epoch_id": "<uuid hex>",
    "agent_id": "agent-<hex>",
    "sequence": <integer>,
    "parent_epoch": "<uuid hex or null>",
    "created_at": <unix timestamp>
  },
  "parent_capsule_hash": "<sha256 hex or null>",
  "objective": "<string>",
  "continuation_point": "<string>",
  "working_summary": "<string>",
  "workspace_manifest": {
    "root_hash": "<sha256 hex>",
    "files": [
      {
        "rel_path": "<posix relative path>",
        "content_hash": "<sha256 hex>",
        "size": <integer>,
        "mode": <integer>
      }
    ],
    "total_size": <integer>
  },
  "capabilities": {
    "grants": [
      {
        "name": "<capability name>",
        "scope": "<scope string>",
        "granted": true,
        "constraints": {}
      }
    ],
    "note": "<string>"
  },
  "secret_references": [
    {
      "name": "<string>",
      "provider": "<string>",
      "reference": "<opaque string>"
    }
  ],
  "pending_operations": [],
  "runtime_compatibility": {},
  "restoration_contract": "exact|semantic|degraded",
  "receipts": [<receipt objects>],
  "manifest_hash": "<sha256 hex>",
  "signer_fingerprint": "<sha256 of public key, first 16 hex chars>",
  "signature": "<ed25519 hex>",
  "sealed_at": <unix timestamp>
}
```

### 4.1 Manifest Hash

The manifest hash is computed over the canonical serialization of the
manifest with `manifest_hash`, `signature`, and `sealed_at` fields
removed.

### 4.2 Manifest Signature

The signature is an Ed25519 signature over the canonical serialization
of the manifest with `signature` and `sealed_at` removed. The
`manifest_hash` field is included in the signed bytes.

### 4.3 Verification

A verifier with the owner's public key checks:

1. Recompute `manifest_hash` from the unsigned fields.
2. Verify the Ed25519 signature over the canonical bytes including
   `manifest_hash` but excluding `signature` and `sealed_at`.
3. Verify every receipt in the receipt chain (Section 5).
4. Verify workspace root hash matches the Merkle root of file entries.
5. If `parent_capsule_hash` is present, verify it matches the parent
   capsule's `manifest_hash`.
6. Verify epoch sequence is strictly greater than the parent's.

## 5. Receipt Chain

Each capsule contains an ordered list of receipts. Receipts form a
hash-linked chain: each receipt references the hash of its predecessor.

### 5.1 Receipt Structure

```json
{
  "receipt_type": "SEAL|RESTORE|EXECUTE|MUTATE|SUSPEND|DESTROY|WITNESS",
  "agent_id": "agent-<hex>",
  "epoch_id": "<uuid hex>",
  "timestamp": <unix timestamp>,
  "prior_receipt_hash": "<sha256 hex or null>",
  "action": "<short string>",
  "action_payload": {},
  "state_root": "<sha256 hex>",
  "receipt_hash": "<sha256 hex>",
  "signer_fingerprint": "<16 hex chars>",
  "signer_role": "owner|host",
  "signature": "<ed25519 hex>"
}
```

### 5.2 Receipt Hash

The receipt hash is SHA-256 over the canonical serialization of the
receipt with `receipt_hash` removed, concatenated with the signature
bytes.

### 5.3 Receipt Signature

Owner-typed receipts are signed with the owner's Ed25519 private key.
Host-typed receipts are signed with the host's ephemeral Ed25519
private key. The verifier must know which public key to use based on
`signer_role` and the host attestation record.

### 5.4 Chain Verification

1. The first receipt has `prior_receipt_hash: null`.
2. Each subsequent receipt's `prior_receipt_hash` equals the previous
   receipt's `receipt_hash`.
3. Each receipt's signature is valid under the appropriate public key.
4. Each `receipt_hash` matches the recomputed value.

## 6. Execution-Witness Receipt

When a host completes work on a capsule, it produces an
execution-witness receipt. This receipt is signed by the host's
ephemeral key, not the owner's key.

### 6.1 Structure

```json
{
  "witness_type": "execution",
  "input_capsule_hash": "<sha256 hex>",
  "owner_signature_verified": true,
  "agent_id": "agent-<hex>",
  "epoch_sequence": <integer>,
  "host_os": "<string>",
  "host_arch": "<string>",
  "runtime_id": "<string>",
  "ephemeral_key_fingerprint": "<16 hex chars>",
  "workspace_root_hash": "<sha256 hex>",
  "restoration_class": "exact|semantic|degraded",
  "operations": [],
  "test_results": [],
  "output_workspace_root_hash": "<sha256 hex>",
  "delta_hash": "<sha256 hex>",
  "fencing_token_used": "<string>",
  "capabilities_applied": [],
  "timestamp": <unix timestamp>,
  "receipt_hash": "<sha256 hex>",
  "signature": "<ed25519 hex>"
}
```

### 6.2 Authority Boundary

The execution-witness receipt records what the host did. It does
**not** create the next authoritative agent epoch. The owner verifies
this receipt and then seals the next capsule, advancing the lineage.

A host cannot produce a valid capsule manifest signature because it
lacks the owner's private key.

## 7. Fencing Invalidation

When a runtime is destroyed, the lease manager records a fencing
invalidation receipt:

```json
{
  "fencing_type": "invalidation",
  "agent_id": "agent-<hex>",
  "lease_generation": <integer>,
  "fencing_token": "<string>",
  "runtime_id": "<string>",
  "destroyed_at": <unix timestamp>,
  "destruction_verified": true,
  "receipt_hash": "<sha256 hex>",
  "signature": "<ed25519 hex>"
}
```

A stale runtime holding the old fencing token cannot:

- Seal a successor capsule
- Register or commit external effects
- Access secrets via the lease authority
- Advance the agent's lineage

## 8. Capability Continuity

Capabilities travel in the capsule. On restoration, the destination
host compiles source capabilities against its local policy.

### 8.1 Non-Expansion Invariant

Destination capabilities may preserve or reduce source authority but
may never silently expand it. Any mapping that broadens scope, increases
budget, or grants new capability types is rejected.

### 8.2 Deny by Default

Any capability not present in the capsule is not granted. Unknown
capability types are denied.

## 9. Semantic Quiescence

A capsule may be sealed only when the agent is quiescent — no external
effects are in a blocking state (starting, submitted, unknown).

### 9.1 Effect Lifecycle

```
starting → submitted → committed | cancelled | proven_not_started
                 ↘ unknown → reconciled on wake
```

### 9.2 Reconciliation

On wake, effects in `unknown` state are reconciled against the provider
by idempotency key before the agent may act. Reconciliation determines
the true outcome without re-executing the operation.

## 10. Restoration Contract

| Class | Condition | Workspace | Runtime State |
|-------|-----------|-----------|---------------|
| exact | Same OS, arch, runtime | Byte-identical | Preserved |
| semantic | Different OS/arch/runtime | Byte-identical | Discarded |
| degraded | Partial compatibility | Partial | Discarded |

The durable layer (workspace files, objectives, capabilities, receipts)
is always preserved exactly. The volatile layer (KV cache, process
state, loaded models) may be discarded on cross-provider migration.

## 11. Offline Verification

An offline verifier with only the owner's public key and the capsule
artifacts can verify the complete chain without network access, without
trusting any host, and without trusting any provider.

The verifier checks:

1. Every manifest hash and signature
2. Every receipt signature and chain linkage
3. Epoch lineage monotonicity
4. Parent capsule hash binding
5. Capability non-expansion across migrations
6. Quiescence at every seal point
7. Destruction evidence for every destroyed runtime
8. Execution-witness receipt signatures from hosts

## 12. Versioning

Every published capsule identifies:

- `spec_version`: this specification version
- `tokenizer_digest`: if applicable
- `model_digest`: if applicable
- `inference_requirements`: if applicable

When this specification changes in a backward-incompatible way, the
`spec_version` increments. Previous capsules remain verifiable under
their original version.
