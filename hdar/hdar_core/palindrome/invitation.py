"""Palindrome invitation system.

A one-use invitation is a hotel keycard — it opens one mailbox,
for one guest, one time. After redemption it is dead.

The invitation flow:
  1. Owner creates a mailbox with a TTL and permitted files
  2. Owner generates a one-use invitation bound to that mailbox
  3. Invitation is pasted into a chat (contains only mailbox ID + token + task description)
  4. Guest redeems invitation at the Space front desk
  5. Space exchanges invitation for a short-lived session credential
  6. Invitation is marked redeemed — cannot be used again
  7. Session credential expires when mailbox TTL expires

The invitation never contains:
  - Private keys
  - Local file paths
  - Permanent API keys
  - Machine addresses

It contains:
  - Mailbox ID (e.g. "wolf-moon-72")
  - One-use token (random 256-bit hex)
  - Task description (human-readable)
  - Expiration timestamp
"""

from __future__ import annotations

import hashlib
import base64
import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class InvitationStatus(Enum):
    PENDING = "pending"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class Invitation:
    """A one-use, device-signed MirrorLease invitation.

    ``token`` is the disposable bearer secret. The public key is only an
    identity and verification mechanism; it never grants access by itself.
    The signature binds the token hash to the recipient, exact grants,
    mailbox, challenge, and expiration.
    """
    invitation_id: str
    mailbox_id: str
    token: str  # 256-bit random hex, one-use
    task_description: str = ""
    created_at: float = 0.0
    expires_at: float = 0.0
    redeemed_at: float = 0.0
    redeemed_by: str = ""  # guest identifier (e.g. ChatGPT session ID)
    status: InvitationStatus = InvitationStatus.PENDING
    session_credential: str = ""  # set after redemption
    recipient_id: str = ""
    conversation_label: str = ""
    challenge: str = ""
    grants: Dict[str, List[str]] = field(default_factory=dict)
    issuer_public_key: str = ""
    issuer_fingerprint: str = ""
    lease_signature: str = ""

    def signed_claims(self) -> dict:
        """Canonical claims covered by the device signature."""
        return {
            "invitation_id": self.invitation_id,
            "mailbox_id": self.mailbox_id,
            "token_hash": hashlib.sha256(self.token.encode()).hexdigest(),
            "task_description": self.task_description,
            "recipient_id": self.recipient_id,
            "conversation_label": self.conversation_label,
            "challenge": self.challenge,
            "grants": {cid: list(ops) for cid, ops in self.grants.items()},
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "issuer_fingerprint": self.issuer_fingerprint,
        }

    def canonical_claims(self) -> bytes:
        return json.dumps(
            self.signed_claims(), sort_keys=True, separators=(",", ":")
        ).encode()

    def verify_signature(self) -> bool:
        """Verify this lease without possessing any private key."""
        if not self.issuer_public_key or not self.lease_signature:
            return False
        try:
            from crypto import PublicKey

            return PublicKey.from_hex(self.issuer_public_key).verify_bytes(
                self.canonical_claims(), self.lease_signature
            )
        except (ValueError, TypeError):
            return False

    def to_public_dict(self) -> dict:
        """What gets pasted into chat — no secrets beyond the one-use token."""
        return {
            "invitation_id": self.invitation_id,
            "mailbox_id": self.mailbox_id,
            "token": self.token,
            "task": self.task_description,
            "recipient_id": self.recipient_id,
            "conversation_label": self.conversation_label,
            "challenge": self.challenge,
            "grants": {cid: list(ops) for cid, ops in self.grants.items()},
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "issuer_public_key": self.issuer_public_key,
            "issuer_fingerprint": self.issuer_fingerprint,
            "lease_signature": self.lease_signature,
        }

    def to_invite_string(self) -> str:
        """Self-contained public invitation for pasting into chat.

        Base64url is used only as transport encoding. Authenticity comes from
        the Ed25519 signature and access from the one-use random token.
        """
        payload = json.dumps(
            self.to_public_dict(), sort_keys=True, separators=(",", ":")
        ).encode()
        encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        return f"mirrorlease:v1:{encoded}"

    def to_dict(self) -> dict:
        return {
            "invitation_id": self.invitation_id,
            "mailbox_id": self.mailbox_id,
            "token": self.token,
            "task_description": self.task_description,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "redeemed_at": self.redeemed_at,
            "redeemed_by": self.redeemed_by,
            "status": self.status.value,
            "session_credential": self.session_credential,
            "recipient_id": self.recipient_id,
            "conversation_label": self.conversation_label,
            "challenge": self.challenge,
            "grants": {cid: list(ops) for cid, ops in self.grants.items()},
            "issuer_public_key": self.issuer_public_key,
            "issuer_fingerprint": self.issuer_fingerprint,
            "lease_signature": self.lease_signature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Invitation":
        return cls(
            invitation_id=d["invitation_id"],
            mailbox_id=d["mailbox_id"],
            token=d["token"],
            task_description=d.get("task_description", ""),
            created_at=d.get("created_at", 0.0),
            expires_at=d.get("expires_at", 0.0),
            redeemed_at=d.get("redeemed_at", 0.0),
            redeemed_by=d.get("redeemed_by", ""),
            status=InvitationStatus(d.get("status", "pending")),
            session_credential=d.get("session_credential", ""),
            recipient_id=d.get("recipient_id", ""),
            conversation_label=d.get("conversation_label", ""),
            challenge=d.get("challenge", ""),
            grants={cid: list(ops) for cid, ops in d.get("grants", {}).items()},
            issuer_public_key=d.get("issuer_public_key", ""),
            issuer_fingerprint=d.get("issuer_fingerprint", ""),
            lease_signature=d.get("lease_signature", ""),
        )

    @classmethod
    def from_public_dict(cls, d: dict) -> "Invitation":
        """Reconstruct the public portion solely for offline verification."""
        return cls(
            invitation_id=d.get("invitation_id", ""),
            mailbox_id=d.get("mailbox_id", ""),
            token=d.get("token", ""),
            task_description=d.get("task", ""),
            created_at=d.get("created_at", 0.0),
            expires_at=d.get("expires_at", 0.0),
            recipient_id=d.get("recipient_id", ""),
            conversation_label=d.get("conversation_label", ""),
            challenge=d.get("challenge", ""),
            grants={cid: list(ops) for cid, ops in d.get("grants", {}).items()},
            issuer_public_key=d.get("issuer_public_key", ""),
            issuer_fingerprint=d.get("issuer_fingerprint", ""),
            lease_signature=d.get("lease_signature", ""),
        )

    @staticmethod
    def parse_invite_string(s: str) -> Optional[dict]:
        """Decode a public invitation. Decoding does not authorize access."""
        s = s.strip()
        if not s.startswith("mirrorlease:v1:"):
            return None
        encoded = s.removeprefix("mirrorlease:v1:")
        if not encoded:
            return None
        try:
            padding = "=" * (-len(encoded) % 4)
            decoded = base64.urlsafe_b64decode(encoded + padding)
            payload = json.loads(decoded)
            required = {"mailbox_id", "token", "expires_at", "lease_signature"}
            return payload if required.issubset(payload) else None
        except (ValueError, TypeError, json.JSONDecodeError):
            return None


class InvitationManager:
    """Creates and tracks one-use invitations.

    All state is in-memory by default. For production, persist to SQLite.
    """

    def __init__(self, device_key=None, require_signed: bool = True):
        self.device_key = device_key
        self.require_signed = require_signed
        self._invitations: Dict[str, Invitation] = {}  # by invitation_id
        self._by_token: Dict[str, str] = {}  # token -> invitation_id
        self._sessions: Dict[str, dict] = {}  # session_credential -> session info

    def create(
        self,
        mailbox_id: str,
        ttl_seconds: float = 86400.0,
        task_description: str = "",
        recipient_id: str = "",
        conversation_label: str = "",
        grants: Optional[Dict[str, List[str]]] = None,
        challenge: str = "",
    ) -> Invitation:
        """Create a signed, one-use invitation for a mailbox."""
        if self.require_signed and self.device_key is None:
            raise ValueError("a device signing key is required for MirrorLease invitations")
        now = time.time()
        token = secrets.token_hex(32)  # 256-bit
        invitation = Invitation(
            invitation_id=secrets.token_hex(16),
            mailbox_id=mailbox_id,
            token=token,
            task_description=task_description,
            created_at=now,
            expires_at=now + ttl_seconds,
            recipient_id=recipient_id,
            conversation_label=conversation_label,
            challenge=challenge or secrets.token_hex(16),
            grants=grants or {},
        )
        if self.device_key is not None:
            invitation.issuer_public_key = self.device_key.public_key_hex
            invitation.issuer_fingerprint = self.device_key.fingerprint
            invitation.lease_signature = self.device_key.sign_bytes(
                invitation.canonical_claims()
            )
        self._invitations[invitation.invitation_id] = invitation
        self._by_token[token] = invitation.invitation_id
        return invitation

    def redeem(
        self,
        mailbox_id: str,
        token: str,
        guest_id: str = "",
        now: Optional[float] = None,
    ) -> Tuple[Optional[str], str]:
        """Redeem a one-use invitation.

        Returns (session_credential, reason). On success, session_credential
        is a short-lived token. On failure, session_credential is None.
        """
        now = time.time() if now is None else now
        invitation_id = self._by_token.get(token)
        if invitation_id is None:
            return None, "invalid token — not found"

        inv = self._invitations[invitation_id]
        if inv.mailbox_id != mailbox_id:
            return None, "mailbox ID mismatch"

        if self.require_signed and not inv.verify_signature():
            return None, "lease signature invalid"
        if self.device_key is not None and inv.issuer_public_key != self.device_key.public_key_hex:
            return None, "lease issuer is not this device"

        if inv.status == InvitationStatus.REDEEMED:
            return None, "invitation already redeemed — one-use only"
        if inv.status == InvitationStatus.REVOKED:
            return None, "invitation revoked by owner"
        if now >= inv.expires_at:
            inv.status = InvitationStatus.EXPIRED
            return None, "invitation expired"

        if inv.recipient_id and guest_id != inv.recipient_id:
            return None, "recipient mismatch"

        # Redeem — generate session credential
        session_cred = secrets.token_hex(32)
        inv.redeemed_at = now
        inv.redeemed_by = guest_id
        inv.status = InvitationStatus.REDEEMED
        inv.session_credential = session_cred

        self._sessions[session_cred] = {
            "mailbox_id": mailbox_id,
            "guest_id": guest_id,
            "issued_at": now,
            "expires_at": inv.expires_at,
            "invitation_id": invitation_id,
            "grants": {cid: list(ops) for cid, ops in inv.grants.items()},
        }

        # Token can never be used again — but keep mapping so reuse
        # attempts get 'already redeemed' instead of 'not found'
        # del self._by_token[token]  -- intentionally NOT deleted

        return session_cred, "redeemed"

    def revoke(self, invitation_id: str) -> bool:
        """Revoke an invitation."""
        inv = self._invitations.get(invitation_id)
        if inv is None:
            return False
        if inv.status in (InvitationStatus.REDEEMED, InvitationStatus.EXPIRED):
            return False
        inv.status = InvitationStatus.REVOKED
        if inv.token in self._by_token:
            del self._by_token[inv.token]
        return True

    def validate_session(self, session_credential: str, now: Optional[float] = None) -> Optional[dict]:
        """Validate a session credential. Returns session info or None."""
        now = time.time() if now is None else now
        session = self._sessions.get(session_credential)
        if session is None:
            return None
        if now >= session["expires_at"]:
            del self._sessions[session_credential]
            return None
        return session

    def revoke_session(self, session_credential: str) -> bool:
        """Revoke a session credential."""
        if session_credential in self._sessions:
            del self._sessions[session_credential]
            return True
        return False

    def revoke_mailbox(self, mailbox_id: str) -> int:
        """Revoke every pending invitation and live session for a mailbox."""
        revoked = 0
        for inv in self._invitations.values():
            if inv.mailbox_id != mailbox_id:
                continue
            if inv.status == InvitationStatus.PENDING:
                inv.status = InvitationStatus.REVOKED
                self._by_token.pop(inv.token, None)
                revoked += 1
        for credential, session in list(self._sessions.items()):
            if session["mailbox_id"] == mailbox_id:
                del self._sessions[credential]
                revoked += 1
        return revoked

    def destroy_mailbox_authority(self, mailbox_id: str) -> int:
        """Invalidate and scrub disposable bearer material for one mailbox."""
        scrubbed = self.revoke_mailbox(mailbox_id)
        for inv in self._invitations.values():
            if inv.mailbox_id != mailbox_id:
                continue
            self._by_token.pop(inv.token, None)
            inv.token = ""
            inv.session_credential = ""
            inv.grants.clear()
            if inv.status != InvitationStatus.EXPIRED:
                inv.status = InvitationStatus.REVOKED
            scrubbed += 1
        return scrubbed

    def get_invitation(self, invitation_id: str) -> Optional[Invitation]:
        return self._invitations.get(invitation_id)

    def list_invitations(self) -> List[Invitation]:
        return list(self._invitations.values())
