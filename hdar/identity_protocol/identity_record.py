"""IdentityRecord — minimal "same agent continued" proof.

A lightweight signed record that binds:
  - agent_id:          stable agent identity
  - epoch:             monotonic counter
  - parent_state_hash: hash of the previous IdentityRecord
  - memory_root_hash:  Merkle root over partitioned memory
  - objective_root_hash: hash over identity-critical objectives
  - policy_hash:       hash over the active PolicySet
  - authority_key:     owner's public key hex
  - writer_lease_id:   current lease holder
  - fencing_token:     fencing token from LeaseManager
  - signature:         Ed25519 by owner

This is derivable from a ContinuityCapsule but much smaller — it's
the minimal proof that "this state is a continuation of the same agent,
authorized by the root authority, at epoch N."

The ContinuityCapsule carries the full workspace manifest, capabilities,
receipts, etc. The IdentityRecord is what you verify when you only need
to know: is this the same agent?
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from hdar_core.crypto import canonicalize, sha256_hex, sha256_dict


@dataclass
class ObjectiveSet:
    """Identity-critical objectives, permissions, and obligations.

    Only these affect identity continuity. Changes here require
    explicit validation by the root authority.
    """
    objectives: Dict[str, str] = field(default_factory=dict)
    permissions: Dict[str, Any] = field(default_factory=dict)
    obligations: Dict[str, Any] = field(default_factory=dict)
    unresolved_commitments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "objectives": self.objectives,
            "permissions": self.permissions,
            "obligations": self.obligations,
            "unresolved_commitments": self.unresolved_commitments,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ObjectiveSet":
        return cls(
            objectives=d.get("objectives", {}),
            permissions=d.get("permissions", {}),
            obligations=d.get("obligations", {}),
            unresolved_commitments=d.get("unresolved_commitments", {}),
        )

    def root_hash(self) -> str:
        return sha256_dict(self.to_dict())


@dataclass
class IdentityRecord:
    """A single canonical identity state.

    Minimal proof that a state is a continuation of the same agent.
    Signed by the owner's Ed25519 private key.
    """
    agent_id: str
    epoch: int
    parent_state_hash: Optional[str]
    memory_root_hash: str
    objective_root_hash: str
    policy_hash: str
    authority_key: str
    writer_lease_id: str = ""
    fencing_token: str = ""
    created_at: float = field(default_factory=time.time)
    signature: str = ""
    state_hash: str = ""

    def unsigned_canonical(self) -> bytes:
        d = self.to_dict()
        for k in ("signature", "state_hash"):
            d.pop(k, None)
        return canonicalize(d)

    def compute_state_hash(self) -> str:
        d = self.to_dict()
        for k in ("signature", "state_hash"):
            d.pop(k, None)
        return sha256_dict(d)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "epoch": self.epoch,
            "parent_state_hash": self.parent_state_hash,
            "memory_root_hash": self.memory_root_hash,
            "objective_root_hash": self.objective_root_hash,
            "policy_hash": self.policy_hash,
            "authority_key": self.authority_key,
            "writer_lease_id": self.writer_lease_id,
            "fencing_token": self.fencing_token,
            "created_at": self.created_at,
            "signature": self.signature,
            "state_hash": self.state_hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IdentityRecord":
        return cls(
            agent_id=d["agent_id"],
            epoch=d["epoch"],
            parent_state_hash=d.get("parent_state_hash"),
            memory_root_hash=d["memory_root_hash"],
            objective_root_hash=d["objective_root_hash"],
            policy_hash=d["policy_hash"],
            authority_key=d["authority_key"],
            writer_lease_id=d.get("writer_lease_id", ""),
            fencing_token=d.get("fencing_token", ""),
            created_at=d.get("created_at", 0.0),
            signature=d.get("signature", ""),
            state_hash=d.get("state_hash", ""),
        )

    def sign(self, owner_key) -> None:
        """Sign with an OwnerKeyPair from hdar_core.crypto."""
        self.state_hash = self.compute_state_hash()
        self.signature = owner_key.sign_bytes(self.unsigned_canonical())

    def verify(self, owner_public_key) -> bool:
        """Verify with a PublicKey from hdar_core.crypto."""
        try:
            ok = owner_public_key.verify_bytes(
                self.unsigned_canonical(), self.signature
            )
            return ok and self.compute_state_hash() == self.state_hash
        except Exception:
            return False

    @classmethod
    def from_capsule(
        cls,
        capsule,
        policy_hash: str,
        objective_root_hash: str,
        memory_root_hash: Optional[str] = None,
    ) -> "IdentityRecord":
        """Derive an IdentityRecord from a ContinuityCapsule.

        Extracts the minimal fields from a full capsule. The
        memory_root_hash defaults to the capsule's workspace root hash
        but can be overridden with a PartitionedMemoryRoot.
        """
        from hdar_core.crypto import key_fingerprint
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        ws_hash = (
            capsule.workspace_manifest.get("root_hash", "")
            if capsule.workspace_manifest
            else ""
        )

        return cls(
            agent_id=capsule.agent_id,
            epoch=capsule.epoch.get("sequence", 0),
            parent_state_hash=capsule.parent_capsule_hash,
            memory_root_hash=memory_root_hash or ws_hash,
            objective_root_hash=objective_root_hash,
            policy_hash=policy_hash,
            authority_key=capsule.signer_fingerprint,
            writer_lease_id="",
            fencing_token="",
        )
