"""Hash-linked receipts with Ed25519 signatures.

Each receipt records an observable transition in the capsule's lifecycle.
Receipts form a hash-linked chain: each receipt references the hash of
its predecessor. Signatures use Ed25519 for asymmetric, independently
verifiable provenance.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)


def _canonicalize(obj: dict) -> bytes:
    """Stable JSON serialization for hashing and signing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Receipt:
    """A single observable transition in the capsule lifecycle."""
    receipt_type: str            # SEAL, RESTORE, EXECUTE, MUTATE, SUSPEND, etc.
    agent_id: str
    epoch_id: str
    timestamp: float
    prior_receipt_hash: Optional[str]
    action: str                  # short description
    action_payload: Dict[str, Any] = field(default_factory=dict)
    state_root: str = ""         # workspace root hash at this point
    receipt_hash: str = ""       # computed over canonical + signature
    signer_fingerprint: str = ""
    signature: str = ""

    def canonical_bytes(self) -> bytes:
        """Bytes that are signed and hashed (excludes signature and receipt_hash)."""
        return _canonicalize({
            "receipt_type": self.receipt_type,
            "agent_id": self.agent_id,
            "epoch_id": self.epoch_id,
            "timestamp": self.timestamp,
            "prior_receipt_hash": self.prior_receipt_hash,
            "action": self.action,
            "action_payload": self.action_payload,
            "state_root": self.state_root,
            "signer_fingerprint": self.signer_fingerprint,
        })

    def compute_hash(self) -> str:
        """Compute the receipt hash over canonical bytes + signature."""
        return _hash(self.canonical_bytes() + self.signature.encode())

    def sign(self, private_key: Ed25519PrivateKey) -> None:
        """Sign with Ed25519 private key. Signature stored as hex."""
        self.signature = private_key.sign(self.canonical_bytes()).hex()
        self.receipt_hash = self.compute_hash()

    def verify(self, public_key: Ed25519PublicKey) -> bool:
        """Verify Ed25519 signature and hash linkage."""
        try:
            public_key.verify(
                bytes.fromhex(self.signature),
                self.canonical_bytes(),
            )
        except Exception:
            return False
        return self.compute_hash() == self.receipt_hash

    def to_dict(self) -> dict:
        return {
            "receipt_type": self.receipt_type,
            "agent_id": self.agent_id,
            "epoch_id": self.epoch_id,
            "timestamp": self.timestamp,
            "prior_receipt_hash": self.prior_receipt_hash,
            "action": self.action,
            "action_payload": self.action_payload,
            "state_root": self.state_root,
            "receipt_hash": self.receipt_hash,
            "signer_fingerprint": self.signer_fingerprint,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Receipt":
        return cls(
            receipt_type=d["receipt_type"],
            agent_id=d["agent_id"],
            epoch_id=d["epoch_id"],
            timestamp=d["timestamp"],
            prior_receipt_hash=d["prior_receipt_hash"],
            action=d["action"],
            action_payload=d.get("action_payload", {}),
            state_root=d.get("state_root", ""),
            receipt_hash=d["receipt_hash"],
            signer_fingerprint=d["signer_fingerprint"],
            signature=d["signature"],
        )


class ReceiptChain:
    """Ordered, hash-linked chain of receipts.

    The chain is stored as a JSON file alongside the capsule. Each
    new receipt references the hash of the previous one, forming a
    tamper-evident log.
    """

    def __init__(self, agent_id: str, epoch_id: str, signing_key: Ed25519PrivateKey):
        self.agent_id = agent_id
        self.epoch_id = epoch_id
        self.signing_key = signing_key
        self.public_key = signing_key.public_key()
        raw = self.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.fingerprint = hashlib.sha256(raw).hexdigest()[:16]
        self.receipts: List[Receipt] = []

    @property
    def head_hash(self) -> Optional[str]:
        return self.receipts[-1].receipt_hash if self.receipts else None

    def append(self, receipt_type: str, action: str,
               action_payload: Optional[dict] = None,
               state_root: str = "") -> Receipt:
        """Create, sign, and append a new receipt."""
        receipt = Receipt(
            receipt_type=receipt_type,
            agent_id=self.agent_id,
            epoch_id=self.epoch_id,
            timestamp=time.time(),
            prior_receipt_hash=self.head_hash,
            action=action,
            action_payload=action_payload or {},
            state_root=state_root,
            signer_fingerprint=self.fingerprint,
        )
        receipt.sign(self.signing_key)
        self.receipts.append(receipt)
        return receipt

    def verify(self, public_key: Optional[Ed25519PublicKey] = None) -> bool:
        """Verify the entire chain: linkage, signatures, hashes."""
        key = public_key or self.public_key
        prev_hash = None
        for r in self.receipts:
            if r.prior_receipt_hash != prev_hash:
                return False
            if not r.verify(key):
                return False
            prev_hash = r.receipt_hash
        return True

    def to_list(self) -> List[dict]:
        return [r.to_dict() for r in self.receipts]

    @classmethod
    def from_list(cls, receipts: List[dict], signing_key: Ed25519PrivateKey) -> "ReceiptChain":
        if not receipts:
            raise ValueError("cannot load empty receipt chain")
        first = receipts[0]
        chain = cls(first["agent_id"], first["epoch_id"], signing_key)
        chain.receipts = [Receipt.from_dict(r) for r in receipts]
        return chain

    def __len__(self) -> int:
        return len(self.receipts)
