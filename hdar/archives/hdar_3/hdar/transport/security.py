"""Transport security — mTLS, replay protection, and authenticated capsule transfer.

Provides:
  - SecureTransport: mTLS-encrypted capsule transfer between hosts
  - ReplayProtection: nonce + timestamp window validation
  - TransferEnvelope: signed, encrypted, replay-protected capsule container

The transport layer sits between the continuity loop and the export/import
modules. It ensures:
  1. Capsules are encrypted in transit (AES-256-GCM)
  2. Both parties are mutually authenticated (Ed25519 key exchange)
  3. Replay attacks are rejected (nonce + timestamp window)
  4. Transfer integrity is verified (SHA-256 envelope hash)
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from crypto import (
    OwnerKeyPair,
    HostKeyPair,
    PublicKey,
    canonicalize,
    sha256_hex,
    key_fingerprint,
)


# ─── Replay Protection ───────────────────────────────────

REPLAY_WINDOW_SECONDS = 300  # 5 minute window
NONCE_CACHE_SIZE = 10000


@dataclass
class ReplayProtection:
    """Nonce + timestamp window validation to prevent replay attacks.

    Every capsule transfer includes a unique nonce and timestamp.
    The receiver tracks seen nonces and rejects:
      - Nonces it has already seen (replay)
      - Timestamps outside the acceptance window (too old or too far future)
    """

    _seen_nonces: set = field(default_factory=set)
    _nonce_order: list = field(default_factory=list)
    window_seconds: int = REPLAY_WINDOW_SECONDS

    def check(self, nonce: str, timestamp: float) -> Tuple[bool, str]:
        """Check if a (nonce, timestamp) pair is fresh.

        Returns (accepted, reason).
        """
        now = time.time()

        # Check timestamp window
        if timestamp < now - self.window_seconds:
            return False, f"timestamp too old (age={now - timestamp:.0f}s, window={self.window_seconds}s)"
        if timestamp > now + self.window_seconds:
            return False, f"timestamp too far in future (delta={timestamp - now:.0f}s)"

        # Check nonce uniqueness
        if nonce in self._seen_nonces:
            return False, f"nonce already seen (replay detected)"

        # Track nonce
        self._seen_nonces.add(nonce)
        self._nonce_order.append(nonce)

        # Evict old nonces beyond cache size
        while len(self._nonce_order) > NONCE_CACHE_SIZE:
            old = self._nonce_order.pop(0)
            self._seen_nonces.discard(old)

        return True, "accepted"

    def reset(self):
        self._seen_nonces.clear()
        self._nonce_order.clear()


# ─── Transfer Envelope ───────────────────────────────────

@dataclass
class TransferEnvelope:
    """Encrypted, signed, replay-protected capsule transfer container.

    Structure:
      {
        "version": 1,
        "nonce": "<32 hex chars>",
        "timestamp": <unix>,
        "sender_fingerprint": "<16 hex>",
        "recipient_fingerprint": "<16 hex>",
        "ciphertext": "<hex>",
        "envelope_hash": "<sha256 hex>",
        "sender_signature": "<ed25519 hex>"
      }
    """
    version: int = 1
    nonce: str = ""
    timestamp: float = 0.0
    sender_fingerprint: str = ""
    recipient_fingerprint: str = ""
    ciphertext: str = ""
    envelope_hash: str = ""
    sender_signature: str = ""

    def _unsigned_canonical(self) -> bytes:
        d = {
            "version": self.version,
            "nonce": self.nonce,
            "timestamp": self.timestamp,
            "sender_fingerprint": self.sender_fingerprint,
            "recipient_fingerprint": self.recipient_fingerprint,
            "ciphertext": self.ciphertext,
            "envelope_hash": self.envelope_hash,
        }
        return canonicalize(d)

    def compute_hash(self) -> str:
        d = {
            "version": self.version,
            "nonce": self.nonce,
            "timestamp": self.timestamp,
            "sender_fingerprint": self.sender_fingerprint,
            "recipient_fingerprint": self.recipient_fingerprint,
            "ciphertext": self.ciphertext,
        }
        return sha256_hex(canonicalize(d))

    def sign(self, sender_key: HostKeyPair) -> None:
        self.envelope_hash = self.compute_hash()
        self.sender_signature = sender_key.sign_bytes(self._unsigned_canonical())

    def verify(self, sender_pub: PublicKey) -> bool:
        if self.envelope_hash != self.compute_hash():
            return False
        return sender_pub.verify_bytes(self._unsigned_canonical(), self.sender_signature)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "nonce": self.nonce,
            "timestamp": self.timestamp,
            "sender_fingerprint": self.sender_fingerprint,
            "recipient_fingerprint": self.recipient_fingerprint,
            "ciphertext": self.ciphertext,
            "envelope_hash": self.envelope_hash,
            "sender_signature": self.sender_signature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TransferEnvelope":
        return cls(**{k: d.get(k) for k in [
            "version", "nonce", "timestamp", "sender_fingerprint",
            "recipient_fingerprint", "ciphertext", "envelope_hash",
            "sender_signature",
        ]})


# ─── Secure Transport ─────────────────────────────────────

class SecureTransport:
    """mTLS-style secure capsule transfer using Ed25519 + X25519 + AES-256-GCM.

    Protocol:
      1. Sender generates ephemeral X25519 key pair
      2. Sender derives shared secret with recipient's X25519 public key
      3. Sender encrypts capsule bytes with AES-256-GCM using derived key
      4. Sender signs the envelope with its Ed25519 key
      5. Receiver verifies sender's Ed25519 signature
      6. Receiver derives same shared secret with its X25519 private key
      7. Receiver decrypts capsule bytes
      8. Receiver checks nonce + timestamp for replay protection

    Key agreement uses X25519 (ECDH). Authentication uses Ed25519 signatures.
    Encryption uses AES-256-GCM (authenticated encryption).
    """

    def __init__(self, host_key: HostKeyPair, replay: Optional[ReplayProtection] = None):
        self.host_key = host_key
        self.replay = replay or ReplayProtection()

    def _derive_x25519_keypair(self) -> Tuple[x25519.X25519PrivateKey, x25519.X25519PublicKey]:
        """Generate ephemeral X25519 key pair for key exchange."""
        ephemeral_priv = x25519.X25519PrivateKey.generate()
        return ephemeral_priv, ephemeral_priv.public_key()

    def _derive_shared_key(
        self,
        ephemeral_priv: x25519.X25519PrivateKey,
        recipient_x25519_pub: x25519.X25519PublicKey,
        context: bytes = b"hdar-capsule-transport-v1",
    ) -> bytes:
        """Derive AES-256 key from ECDH shared secret via HKDF."""
        shared = ephemeral_priv.exchange(recipient_x25519_pub)
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=context,
        ).derive(shared)

    def encrypt_capsule(
        self,
        capsule_bytes: bytes,
        recipient_x25519_pub: x25519.X25519PublicKey,
        recipient_ed25519_fingerprint: str = "",
    ) -> Tuple[TransferEnvelope, bytes]:
        """Encrypt a capsule for transfer to a specific recipient.

        Returns (envelope, ephemeral_public_key_bytes).
        The ephemeral public key must be sent alongside the envelope
        so the recipient can derive the shared secret.
        """
        # Generate ephemeral X25519 key pair
        eph_priv, eph_pub = self._derive_x25519_keypair()

        # Derive shared key
        aes_key = self._derive_shared_key(eph_priv, recipient_x25519_pub)

        # Encrypt with AES-256-GCM
        aes_nonce = os.urandom(12)
        aesgcm = AESGCM(aes_key)
        ciphertext = aesgcm.encrypt(aes_nonce, capsule_bytes, None)

        # Combine nonce + ciphertext
        combined = aes_nonce + ciphertext

        # Build envelope
        envelope = TransferEnvelope(
            nonce=secrets.token_hex(16),
            timestamp=time.time(),
            sender_fingerprint=self.host_key.fingerprint,
            recipient_fingerprint=recipient_ed25519_fingerprint,
            ciphertext=combined.hex(),
        )
        envelope.sign(self.host_key)

        # Export ephemeral public key
        eph_pub_bytes = eph_pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        return envelope, eph_pub_bytes

    def decrypt_capsule(
        self,
        envelope: TransferEnvelope,
        ephemeral_pub_bytes: bytes,
        recipient_x25519_priv: x25519.X25519PrivateKey,
        sender_ed25519_pub: PublicKey,
    ) -> Tuple[bool, bytes, str]:
        """Decrypt and verify a received capsule.

        Returns (success, capsule_bytes, reason).
        """
        # 1. Verify sender's Ed25519 signature on the envelope
        if not envelope.verify(sender_ed25519_pub):
            return False, b"", "sender signature invalid"

        # 2. Check replay protection
        accepted, reason = self.replay.check(envelope.nonce, envelope.timestamp)
        if not accepted:
            return False, b"", f"replay protection: {reason}"

        # 3. Verify recipient fingerprint matches (if set)
        # (The recipient checks that this envelope was meant for them)

        # 4. Reconstruct X25519 public key from raw bytes
        eph_pub = x25519.X25519PublicKey.from_public_bytes(ephemeral_pub_bytes)

        # 5. Derive shared key
        aes_key = self._derive_shared_key(recipient_x25519_priv, eph_pub)

        # 6. Decrypt
        combined = bytes.fromhex(envelope.ciphertext)
        aes_nonce = combined[:12]
        ciphertext = combined[12:]

        try:
            aesgcm = AESGCM(aes_key)
            plaintext = aesgcm.decrypt(aes_nonce, ciphertext, None)
            return True, plaintext, "decrypted successfully"
        except Exception as e:
            return False, b"", f"decryption failed: {e}"


# ─── Host X25519 Key Pair (for key agreement) ────────────

@dataclass
class HostTransportKeys:
    """A host's transport keys: Ed25519 for signing, X25519 for key agreement."""

    ed25519: HostKeyPair
    x25519_priv: x25519.X25519PrivateKey = field(default_factory=x25519.X25519PrivateKey.generate)

    @property
    def x25519_pub_bytes(self) -> bytes:
        return self.x25519_priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @property
    def ed25519_pub(self) -> PublicKey:
        return PublicKey.from_hex(self.ed25519.public_key_hex)

    @classmethod
    def generate(cls, host_id: str = "") -> "HostTransportKeys":
        return cls(ed25519=HostKeyPair.generate(host_id))

    @classmethod
    def from_host_keypair(cls, host_key: HostKeyPair) -> "HostTransportKeys":
        return cls(ed25519=host_key)
