"""Key rotation — owner Ed25519 key rotation with lineage continuation.

Provides:
  - KeyRotation: rotate the owner's signing key without breaking the chain
  - RotationReceipt: signed proof that the key was rotated
  - Verifier support: offline verifier can verify chains that span key rotations

Protocol:
  1. Owner generates new Ed25519 key pair
  2. Owner signs a RotationReceipt with BOTH old and new keys
    (old key signs "I am rotating to new key", new key signs "I accept this lineage")
  3. The next capsule is signed with the new key
  4. The RotationReceipt is embedded in the receipt chain
  5. Offline verifiers follow the key rotation to verify post-rotation capsules

Security properties:
  - Old key compromise after rotation cannot forge new capsules
  - New key cannot back-date capsules to before the rotation
  - Both keys must agree on the rotation (bidirectional signing)
  - The rotation is auditable in the receipt chain
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from crypto import (
    OwnerKeyPair,
    PublicKey,
    canonicalize,
    sha256_hex,
    key_fingerprint,
)


@dataclass
class RotationReceipt:
    """Signed proof that the owner's signing key was rotated.

    Both the old and new keys sign this receipt, creating a verifiable
    bridge between two key epochs.
    """

    rotation_id: str = ""
    old_key_fingerprint: str = ""
    new_key_fingerprint: str = ""
    timestamp: float = 0.0
    last_capsule_hash: str = ""  # last capsule signed by old key
    reason: str = ""

    # Signatures
    old_key_signature: str = ""
    new_key_signature: str = ""
    receipt_hash: str = ""

    def _unsigned_canonical(self) -> bytes:
        d = {
            "rotation_id": self.rotation_id,
            "old_key_fingerprint": self.old_key_fingerprint,
            "new_key_fingerprint": self.new_key_fingerprint,
            "timestamp": self.timestamp,
            "last_capsule_hash": self.last_capsule_hash,
            "reason": self.reason,
        }
        return canonicalize(d)

    def compute_hash(self) -> str:
        return sha256_hex(self._unsigned_canonical())

    def sign(
        self,
        old_key: OwnerKeyPair,
        new_key: OwnerKeyPair,
    ) -> None:
        """Sign the rotation receipt with both old and new keys."""
        self.timestamp = time.time()
        self.receipt_hash = self.compute_hash()
        unsigned = self._unsigned_canonical()
        self.old_key_signature = old_key.sign_bytes(unsigned)
        self.new_key_signature = new_key.sign_bytes(unsigned)

    def verify(
        self,
        old_pub: PublicKey,
        new_pub: PublicKey,
    ) -> Tuple[bool, List[str]]:
        """Verify both signatures on the rotation receipt."""
        issues: List[str] = []
        unsigned = self._unsigned_canonical()

        if self.receipt_hash != self.compute_hash():
            issues.append("rotation receipt hash mismatch")
            return False, issues

        if not old_pub.verify_bytes(unsigned, self.old_key_signature):
            issues.append("old key signature invalid on rotation receipt")

        if not new_pub.verify_bytes(unsigned, self.new_key_signature):
            issues.append("new key signature invalid on rotation receipt")

        return len(issues) == 0, issues

    def to_dict(self) -> dict:
        return {
            "rotation_id": self.rotation_id,
            "old_key_fingerprint": self.old_key_fingerprint,
            "new_key_fingerprint": self.new_key_fingerprint,
            "timestamp": self.timestamp,
            "last_capsule_hash": self.last_capsule_hash,
            "reason": self.reason,
            "old_key_signature": self.old_key_signature,
            "new_key_signature": self.new_key_signature,
            "receipt_hash": self.receipt_hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RotationReceipt":
        return cls(**{k: d.get(k) for k in [
            "rotation_id", "old_key_fingerprint", "new_key_fingerprint",
            "timestamp", "last_capsule_hash", "reason",
            "old_key_signature", "new_key_signature", "receipt_hash",
        ]})


class KeyRotation:
    """Manages owner key rotation with lineage continuation."""

    def __init__(self, current_key: OwnerKeyPair):
        self.current_key = current_key
        self.rotation_history: List[RotationReceipt] = []
        self.key_history: List[Tuple[PublicKey, float]] = [
            (current_key.to_public(), time.time())
        ]

    def rotate(
        self,
        new_key: OwnerKeyPair,
        last_capsule_hash: str = "",
        reason: str = "routine rotation",
    ) -> RotationReceipt:
        """Rotate to a new owner key.

        Args:
            new_key: The new Ed25519 key pair
            last_capsule_hash: Hash of the last capsule signed by the old key
            reason: Why the rotation is happening

        Returns:
            The signed RotationReceipt
        """
        import uuid
        receipt = RotationReceipt(
            rotation_id=uuid.uuid4().hex,
            old_key_fingerprint=self.current_key.fingerprint,
            new_key_fingerprint=new_key.fingerprint,
            last_capsule_hash=last_capsule_hash,
            reason=reason,
        )
        receipt.sign(self.current_key, new_key)

        self.rotation_history.append(receipt)
        self.key_history.append((new_key.to_public(), time.time()))
        self.current_key = new_key

        return receipt

    def get_public_key_at(self, timestamp: float) -> Optional[PublicKey]:
        """Get the public key that was active at a given timestamp."""
        for i in range(len(self.key_history) - 1, -1, -1):
            pub, ts = self.key_history[i]
            if timestamp >= ts:
                return pub
        return None

    def get_public_key_by_fingerprint(self, fingerprint: str) -> Optional[PublicKey]:
        """Get a public key by its fingerprint."""
        for pub, _ in self.key_history:
            if pub.fingerprint == fingerprint:
                return pub
        return None

    @property
    def current_public_key(self) -> PublicKey:
        return self.current_key.to_public()

    @property
    def rotation_count(self) -> int:
        return len(self.rotation_history)
