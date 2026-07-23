"""Ed25519 asymmetric cryptography for provider-neutral continuity.

The owner holds an Ed25519 private key. Hosts receive only the public key.
Hosts generate ephemeral Ed25519 key pairs for execution-witness receipts.

This replaces the HMAC-SHA256 symmetric scheme in the original HDAR code.
With Ed25519, a host can verify owner signatures but cannot forge them.
A host signs its own witness receipts with its ephemeral key, creating
a verifiable authority boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature


def _canonicalize(obj: dict) -> bytes:
    """Stable JSON serialization for hashing and signing."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class OwnerKeyPair:
    """The owner's Ed25519 key pair. Private key never leaves the owner."""

    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey

    @property
    def fingerprint(self) -> str:
        return key_fingerprint(self.public_key)

    @property
    def public_key_hex(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

    @property
    def private_key_hex(self) -> str:
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        ).hex()

    def sign(self, obj: dict) -> str:
        """Sign a canonical JSON object. Returns hex signature."""
        return self.sign_bytes(_canonicalize(obj))

    def sign_bytes(self, data: bytes) -> str:
        return self.private_key.sign(data).hex()

    def to_public(self) -> "PublicKey":
        """Return a PublicKey object safe to share with hosts."""
        return PublicKey(self.public_key)

    @classmethod
    def generate(cls) -> "OwnerKeyPair":
        sk = Ed25519PrivateKey.generate()
        return cls(private_key=sk, public_key=sk.public_key())

    @classmethod
    def from_private_hex(cls, hex_key: str) -> "OwnerKeyPair":
        raw = bytes.fromhex(hex_key)
        sk = Ed25519PrivateKey.from_private_bytes(raw)
        return cls(private_key=sk, public_key=sk.public_key())

    def save(self, path: str, password: Optional[bytes] = None):
        """Save private key to file. Use password for encryption."""
        enc = (
            serialization.BestAvailableEncryption(password)
            if password
            else serialization.NoEncryption()
        )
        data = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=enc,
        )
        with open(path, "wb") as f:
            f.write(data)
        os.chmod(path, 0o600)

    @classmethod
    def load(cls, path: str, password: Optional[bytes] = None) -> "OwnerKeyPair":
        with open(path, "rb") as f:
            sk = serialization.load_pem_private_key(f.read(), password=password)
        return cls(private_key=sk, public_key=sk.public_key())


@dataclass
class PublicKey:
    """A public key for verification only. Safe to share with hosts."""

    public_key: Ed25519PublicKey

    @property
    def fingerprint(self) -> str:
        return key_fingerprint(self.public_key)

    @property
    def hex(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

    def verify(self, obj: dict, signature_hex: str) -> bool:
        """Verify a signature over a canonical JSON object."""
        return self.verify_bytes(_canonicalize(obj), signature_hex)

    def verify_bytes(self, data: bytes, signature_hex: str) -> bool:
        try:
            self.public_key.verify(bytes.fromhex(signature_hex), data)
            return True
        except (InvalidSignature, ValueError):
            return False

    @classmethod
    def from_hex(cls, hex_key: str) -> "PublicKey":
        raw = bytes.fromhex(hex_key)
        return cls(public_key=Ed25519PublicKey.from_public_bytes(raw))


@dataclass
class HostKeyPair:
    """Ephemeral Ed25519 key pair for a host.

    The host generates this on materialization. The public key is
    included in the execution-witness receipt so the owner (and any
    offline verifier) can verify host-signed receipts.
    """

    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey
    host_id: str = ""

    @property
    def fingerprint(self) -> str:
        return key_fingerprint(self.public_key)

    @property
    def public_key_hex(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

    def sign(self, obj: dict) -> str:
        return self.sign_bytes(_canonicalize(obj))

    def sign_bytes(self, data: bytes) -> str:
        return self.private_key.sign(data).hex()

    def to_public(self) -> "PublicKey":
        return PublicKey(self.public_key)

    @classmethod
    def generate(cls, host_id: str = "") -> "HostKeyPair":
        sk = Ed25519PrivateKey.generate()
        return cls(private_key=sk, public_key=sk.public_key(), host_id=host_id)


def key_fingerprint(public_key: Ed25519PublicKey) -> str:
    """First 16 hex chars of SHA-256 over the raw public key bytes."""
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()[:16]


def canonicalize(obj: dict) -> bytes:
    """Public canonical serialization function."""
    return _canonicalize(obj)


def sha256_hex(data: bytes) -> str:
    return _hash(data)


def sha256_dict(obj: dict) -> str:
    return _hash(_canonicalize(obj))
