# Canonical Technical Position — Hardware-Detached Agent Runtime

## Correct product boundary

**What exists now (durable truth layer):**

```
Agent identity
+ signed immutable state
+ content-addressed workspace
+ lineage and rollback protection
+ capability attenuation
+ typed execution policy
+ independently verifiable capsule integrity
```

**What remains unproved (runtime lifecycle layer):**

```
exclusive runtime ownership
+ safe semantic suspension
+ real isolated materialization
+ verified runtime destruction
+ cross-machine transport
+ destination execution attestation
+ stable agent-addressed SSH continuity
```

The current repository owns the **durable truth layer**. The missing work is the **runtime lifecycle layer**.

## Canonical repository structure

```
capsule-runtime/
├── capsule/
│   ├── identity.py
│   ├── manifest.py
│   ├── blocks.py
│   ├── lineage.py
│   ├── capabilities.py
│   └── verifier.py
│
├── lifecycle/
│   ├── state_machine.py
│   ├── quiescence.py
│   ├── effects.py
│   ├── lease.py
│   └── fencing.py
│
├── providers/
│   ├── base.py
│   ├── apple_container.py
│   ├── remote_ssh.py
│   └── unsafe_host.py
│
├── transport/
│   ├── export.py
│   ├── import.py
│   ├── delta.py
│   └── receipts.py
│
├── gateway/
│   ├── forced_command.py
│   ├── resolver.py
│   └── session_proxy.py
│
└── evidence/
    ├── host_attestation.py
    ├── execution_receipt.py
    ├── termination_receipt.py
    └── offline_verify.py
```

## Five P0 additions, in dependency order

### 1. Lifecycle state machine

```
DORMANT
→ ACQUIRING_LEASE
→ MATERIALIZING
→ VERIFYING_INPUT
→ RUNNING
→ QUIESCING
→ SEALING
→ DESTROYING
→ DORMANT
```

Failure states:
```
QUARANTINED
DEGRADED
UNKNOWN_EFFECT
LEASE_LOST
RESTORE_REJECTED
DESTRUCTION_UNCONFIRMED
```

A capsule must not be sealed from an arbitrary runtime state. It may seal only after the state machine confirms quiescence and effect reconciliation.

### 2. Durable external-effect registry

Each external operation needs:
```
operation_id
intent_digest
capability_used
request_digest
status
provider_receipt
reconciliation_method
created_at
committed_at
```

Allowed terminal states: `committed`, `cancelled`, `proven_not_started`
Blocking states: `starting`, `submitted`, `unknown`, `reconciliation_failed`

### 3. Atomic fenced wake lease

Lease contains:
```
agent_id
capsule_hash
epoch
lease_generation
holder_id
destination_runtime
issued_at
expires_at
fencing_token
```

Core invariant: **At most one lease generation may advance the authoritative agent state.**

### 4. Real Apple container controller

Provider receipt records:
```
provider: apple-container
container_id
image_digest
vm/runtime identity
cpu_limit
memory_limit
workspace_mount
network_policy
start timestamp
stop timestamp
delete timestamp
post_delete_inspection
```

Destruction gate passes only when:
```
process exited
container stopped
container deleted
provider listing no longer contains runtime identity
session proxy cannot reconnect to old runtime
old fencing token is rejected
```

### 5. Cross-host restore plus stable SSH gateway

Host B receives: capsule, owner public key, expected agent_id, expected epoch, lease and fencing token, attenuated capability set.

Host B verifies owner signature before restoration. Receives no owner private key.

Host B signs: input capsule hash, host OS/arch, runtime identity, owner-sig verification result, restored workspace root, operations performed, test results, output workspace root, returned delta hash, fencing token used.

SSH gateway:
```sshconfig
Match User capsule-agent
    ForceCommand /usr/local/bin/capsule-ssh-gateway
    DisableForwarding yes
    PermitTTY yes
    X11Forwarding no
    PermitTunnel no
```

## Stage 5 acceptance demonstration

20-step sequence without manual substitution (see FOUNDER_PROOF_BRIEF.md).

## Required negative tests

Offline verifier must fail when modifying: one filesystem byte, one block digest, parent capsule hash, epoch, agent identity, a capability, fencing token, destination receipt, test result, owner signature, Host B signature.

Runtime must reject: two concurrent wake attempts, stale lease publishing state, broader capability requests, old capsule after newer epoch, suspension during unknown effect, valid blocks with wrong lineage.

## Gate structure

| Gate | Present | Required evidence |
|------|---------|-------------------|
| Cryptographic capsule kernel | Yes | 4 capsule core tests + 16 cap/verifier tests |
| Semantic safe suspension | Yes (logic) | Effect registry blocks seal, reconciles unknown — 5 tests |
| Exclusive wake ownership | Yes (logic) | SQLite fenced leases, stale-token rejection — 6 tests |
| Isolated materialization | Partial | Provider interface + unsafe_host tested; Apple container adapter written but CLI not installed |
| Runtime destruction | Yes (unsafe-host) | Provider verify_destruction + termination receipt — 4 tests |
| Capability non-expansion | Yes | Compiler rejects broadening, allows attenuation — 10 tests |
| Dual exact/semantic restoration | Yes | Contract classifies exact vs semantic vs degraded, warns about divergence — 9 tests |
| Cross-host continuation | No | Needs genuine second host + remote_ssh provider test |
| Stable SSH identity | Yes (logic) | Gateway tested in demo; real sshd not deployed |
| Offline proof continuity | Yes (logic) | Offline verifier validates chain, detects tamper/rollback — 6 tests |
| Transport + delta | Yes | Export/import roundtrip, hash mismatch rejected, deduplication — 4 tests |
| Execution/termination receipts | Yes | Destination-signed receipts, tamper detection, host attestation — 7 tests |
| One-command proof | Yes | 48 assertions, exit 0, no network |

## Fundraising classification

- **Technical pre-seed credibility:** yes
- **Novel primitive:** signed, content-addressed, capability-constrained agent capsule kernel
- **Hardware-detached runtime:** no
- **Stage 5:** not yet
- **Most important remaining proof:** atomic fenced ownership + actual cross-host execution

> We built a provider-neutral continuity kernel that detaches an agent's signed operational state from its execution machine, permits only one authoritative continuation, restores it on heterogeneous compute under attenuated authority, and proves the entire transition offline.
