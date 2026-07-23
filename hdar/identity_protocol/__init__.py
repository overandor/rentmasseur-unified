"""Identity protocol layer — thin wrapper over real HDAR components.

Builds on:
  - hdar_core.capsule.store.ContentStore  (on-disk SHA-256 content addressing)
  - hdar_core.crypto.OwnerKeyPair         (Ed25519 owner keys)
  - hdar_core.lifecycle.lease.LeaseManager (SQLite atomic fenced leases)
  - hdar_core.lifecycle.effects.EffectRegistry (quiescence gating)
  - hdar_core.capsule.identity.AgentIdentity / LineageEpoch

Adds:
  - PartitionedMemoryStore: 7-class memory partitioning over ContentStore
  - IdentityRecord: minimal "same agent continued" proof
  - PolicySet: explicit fork/quiescence/capability policy
  - ForkArbiter: fork detection and arbitration
"""

from .partitioned_store import (
    MemoryClass,
    PartitionedMemoryStore,
    PartitionedMemoryRoot,
    MemoryEntry,
)
from .policy_set import PolicySet, ForkPolicyType
from .identity_record import IdentityRecord, ObjectiveSet
from .fork_arbiter import ForkArbiter, Fork, MergeRecord

__all__ = [
    "MemoryClass",
    "PartitionedMemoryStore",
    "PartitionedMemoryRoot",
    "MemoryEntry",
    "PolicySet",
    "ForkPolicyType",
    "IdentityRecord",
    "ObjectiveSet",
    "ForkArbiter",
    "Fork",
    "MergeRecord",
]
