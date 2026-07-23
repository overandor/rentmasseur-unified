"""Agent identity and lineage epochs.

Each agent has a stable identity (UUID + Ed25519 key pair).
Each capsule belongs to a lineage epoch — a monotonically increasing
counter that forks when the agent is restored on new compute.

Ed25519 provides asymmetric signing: the signing key never leaves the
owner, while the public key enables independent offline verification.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)


def generate_agent_id() -> str:
    return f"agent-{uuid.uuid4().hex[:12]}"


def generate_signing_key() -> Ed25519PrivateKey:
    """Generate an Ed25519 private key for asymmetric signing."""
    return Ed25519PrivateKey.generate()


def key_fingerprint(public_key: Ed25519PublicKey) -> str:
    """Fingerprint of the public key for identification."""
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def serialize_public_key(public_key: Ed25519PublicKey) -> bytes:
    """Serialize a public key to raw bytes."""
    return public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)


def deserialize_public_key(data: bytes) -> Ed25519PublicKey:
    """Deserialize a public key from raw bytes."""
    return Ed25519PublicKey.from_public_bytes(data)


def serialize_private_key(private_key: Ed25519PrivateKey) -> bytes:
    """Serialize a private key to raw bytes."""
    return private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())


def deserialize_private_key(data: bytes) -> Ed25519PrivateKey:
    """Deserialize a private key from raw bytes."""
    return Ed25519PrivateKey.from_private_bytes(data)


@dataclass
class AgentIdentity:
    """Stable identity for a persistent agent.

    Uses Ed25519 for asymmetric signing. The signing_key (private) never
    leaves the owner. The public_key can be shared for independent verification.
    """
    agent_id: str
    name: str
    signing_key: Ed25519PrivateKey
    created_at: float = field(default_factory=time.time)

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.signing_key.public_key()

    @property
    def fingerprint(self) -> str:
        return key_fingerprint(self.public_key)

    def to_public_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "fingerprint": self.fingerprint,
            "public_key": serialize_public_key(self.public_key).hex(),
            "created_at": self.created_at,
        }

    @classmethod
    def create(cls, name: str, agent_id: Optional[str] = None) -> "AgentIdentity":
        return cls(
            agent_id=agent_id or generate_agent_id(),
            name=name,
            signing_key=generate_signing_key(),
        )

    def sign(self, data: bytes) -> bytes:
        """Sign data with the Ed25519 private key."""
        return self.signing_key.sign(data)

    @staticmethod
    def verify_signature(public_key: Ed25519PublicKey, data: bytes, signature: bytes) -> bool:
        """Verify an Ed25519 signature. Raises InvalidSignature on failure."""
        try:
            public_key.verify(signature, data)
            return True
        except Exception:
            return False


@dataclass
class LineageEpoch:
    """A point in the agent's lineage tree.

    Epochs form a tree: each restoration creates a child epoch with
    a new sequence number and a reference to its parent.
    """
    epoch_id: str               # unique per epoch
    agent_id: str
    sequence: int               # monotonic within the lineage
    parent_epoch: Optional[str] # None for genesis
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "epoch_id": self.epoch_id,
            "agent_id": self.agent_id,
            "sequence": self.sequence,
            "parent_epoch": self.parent_epoch,
            "created_at": self.created_at,
        }

    @classmethod
    def genesis(cls, agent_id: str) -> "LineageEpoch":
        return cls(
            epoch_id=uuid.uuid4().hex,
            agent_id=agent_id,
            sequence=0,
            parent_epoch=None,
        )

    @classmethod
    def child(cls, parent: "LineageEpoch") -> "LineageEpoch":
        return cls(
            epoch_id=uuid.uuid4().hex,
            agent_id=parent.agent_id,
            sequence=parent.sequence + 1,
            parent_epoch=parent.epoch_id,
        )

    @classmethod
    def from_dict(cls, d: dict) -> "LineageEpoch":
        return cls(
            epoch_id=d["epoch_id"],
            agent_id=d["agent_id"],
            sequence=d["sequence"],
            parent_epoch=d["parent_epoch"],
            created_at=d["created_at"],
        )
