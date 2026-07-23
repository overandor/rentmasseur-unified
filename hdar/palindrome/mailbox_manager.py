"""Palindrome mailbox manager.

A MirrorLease mailbox is a temporary container that:
  - Has a public name (e.g. "wolf-moon-72")
  - Contains enrolled file citizens with specific permissions
  - Has a TTL with explicit lifecycle states and no ambiguous fidelity decay
  - Accepts one-use invitations
  - Returns receipts for all access

The mailbox lives on the local machine. The HF Space is just the
front desk — it forwards requests to the local daemon via a secure
channel. The Space never stores file content.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from palindrome.invitation import InvitationManager, Invitation
from palindrome.file_citizen import FileCitizenRegistry, FileCitizen


class LeaseStatus(Enum):
    """Discrete mailbox states. Time never silently changes data resolution."""

    OPEN = "open"          # owner may enroll files and issue an invitation
    WAITING = "waiting"    # invitation issued; no access request received yet
    USED = "used"          # at least one access request was processed
    EXPIRED = "expired"    # TTL ended naturally
    REVOKED = "revoked"    # owner ended authority early
    DESTROYED = "destroyed"  # live credentials and grants were scrubbed

    def allows_access(self) -> bool:
        return self in (LeaseStatus.OPEN, LeaseStatus.WAITING, LeaseStatus.USED)


@dataclass
class PalindromeMailbox:
    """A temporary mailbox through which an AI may perceive selected files."""
    mailbox_id: str  # human-readable name like "wolf-moon-72"
    created_at: float = 0.0
    ttl_seconds: float = 86400.0
    citizen_ids: List[str] = field(default_factory=list)
    task_description: str = ""
    status: LeaseStatus = LeaseStatus.OPEN
    closed_at: float = 0.0
    first_used_at: float = 0.0
    destroyed_at: float = 0.0
    access_receipts: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mailbox_id": self.mailbox_id,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
            "citizen_ids": self.citizen_ids,
            "task_description": self.task_description,
            "status": self.status.value,
            "closed_at": self.closed_at,
            "first_used_at": self.first_used_at,
            "destroyed_at": self.destroyed_at,
            "access_receipts": self.access_receipts,
        }

    def current_status(self, now: Optional[float] = None) -> LeaseStatus:
        """Return the explicit state, expiring atomically at the TTL boundary."""
        now = time.time() if now is None else now
        if self.status.allows_access() and now >= self.created_at + self.ttl_seconds:
            self.status = LeaseStatus.EXPIRED
            self.closed_at = now
        return self.status


class MailboxManager:
    """Creates and manages Palindrome mailboxes.

    The flow:
      1. Owner creates mailbox with TTL and file permissions
      2. Owner generates invitation
      3. Guest redeems invitation -> gets session credential
      4. Guest requests file access through session
      5. Each access is checked against lease state + exact permissions
      6. Access produces a receipt
      7. Mailbox expires atomically; authority never silently degrades
    """

    def __init__(
        self,
        citizens: FileCitizenRegistry,
        invitations: InvitationManager,
    ):
        self.citizens = citizens
        self.invitations = invitations
        self._mailboxes: Dict[str, PalindromeMailbox] = {}

    def create_mailbox(
        self,
        name: Optional[str] = None,
        ttl_seconds: float = 86400.0,
        task_description: str = "",
    ) -> PalindromeMailbox:
        """Create a new mailbox with a human-readable name."""
        if name is None:
            name = self._generate_name()

        mailbox = PalindromeMailbox(
            mailbox_id=name,
            created_at=time.time(),
            ttl_seconds=ttl_seconds,
            task_description=task_description,
        )
        self._mailboxes[name] = mailbox
        return mailbox

    def enroll_file(
        self,
        mailbox_id: str,
        local_path: str,
        permissions: List[str],
        owner_key=None,
    ) -> Optional[FileCitizen]:
        """Enroll a file into a mailbox with specific permissions."""
        mailbox = self._mailboxes.get(mailbox_id)
        if mailbox is None:
            return None
        if mailbox.current_status() != LeaseStatus.OPEN:
            return None

        citizen = self.citizens.enroll(local_path, permissions, owner_key)
        if citizen.citizen_id not in mailbox.citizen_ids:
            mailbox.citizen_ids.append(citizen.citizen_id)
        return citizen

    def create_invitation(
        self,
        mailbox_id: str,
        task_description: str = "",
        recipient_id: str = "",
        conversation_label: str = "",
    ) -> Optional[Invitation]:
        """Create a one-use invitation for a mailbox."""
        mailbox = self._mailboxes.get(mailbox_id)
        if mailbox is None:
            return None

        if mailbox.current_status() != LeaseStatus.OPEN:
            return None

        ttl = mailbox.ttl_seconds - (time.time() - mailbox.created_at)
        if ttl <= 0:
            return None

        grants = {
            cid: list(self.citizens.get(cid).permissions)
            for cid in mailbox.citizen_ids
            if self.citizens.get(cid) is not None
        }
        invitation = self.invitations.create(
            mailbox_id=mailbox_id,
            ttl_seconds=ttl,
            task_description=task_description or mailbox.task_description,
            recipient_id=recipient_id,
            conversation_label=conversation_label,
            grants=grants,
        )
        mailbox.status = LeaseStatus.WAITING
        return invitation

    def access_file(
        self,
        session_credential: str,
        citizen_id: str,
        operation: str,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Access a file through a session credential.

        Returns a result dict with:
          - granted: bool
          - state: current explicit lease state
          - data: file content (if granted)
          - reason: why access was denied (if applicable)
          - receipt: access receipt
        """
        now = time.time() if now is None else now

        # Validate session
        session = self.invitations.validate_session(session_credential, now)
        if session is None:
            return {"granted": False, "state": "expired", "reason": "invalid or expired session", "receipt": None}

        mailbox_id = session["mailbox_id"]
        mailbox = self._mailboxes.get(mailbox_id)
        if mailbox is None:
            return {"granted": False, "state": "destroyed", "reason": "mailbox not found", "receipt": None}

        state = mailbox.current_status(now)
        if not state.allows_access():
            return {"granted": False, "reason": f"mailbox {state.value}", "state": state.value, "receipt": None}

        if mailbox.first_used_at == 0.0:
            mailbox.first_used_at = now
        mailbox.status = LeaseStatus.USED
        state = mailbox.status

        # Check citizen is in mailbox
        if citizen_id not in mailbox.citizen_ids:
            return {"granted": False, "state": state.value, "reason": "file not enrolled in this mailbox", "receipt": None}

        # Check permission
        citizen = self.citizens.get(citizen_id)
        if citizen is None:
            return {"granted": False, "state": state.value, "reason": "file citizen not found", "receipt": None}

        lease_grants = session.get("grants", {})
        if operation not in lease_grants.get(citizen_id, []):
            return {"granted": False, "state": state.value, "reason": f"operation '{operation}' not permitted", "receipt": None}

        result: Dict[str, Any] = {
            "granted": True,
            "state": state.value,
            "citizen_id": citizen_id,
            "content_hash": citizen.content_hash,
            "reason": "granted",
        }

        if operation == "read":
            content, _ = self.citizens.read_content(citizen_id, mailbox_id, session.get("guest_id", ""))
            result["data"] = content.decode("utf-8", errors="replace") if content else ""
        elif operation == "summarize":
            summary, _ = self.citizens.read_summary(citizen_id, mailbox_id, session.get("guest_id", ""))
            result["summary"] = summary
        elif operation == "verify_hash":
            verified, reason = self.citizens.verify_hash(citizen_id, citizen.content_hash)
            result["verified"] = verified
            result["reason"] = reason
        else:
            # Other operations (search, compare, inspect) — check permission was already done
            result["reason"] = f"operation '{operation}' permitted"

        # Generate receipt
        receipt = {
            "mailbox_id": mailbox_id,
            "citizen_id": citizen_id,
            "operation": operation,
            "granted": result["granted"],
            "lease_state": state.value,
            "timestamp": now,
            "receipt_hash": hashlib.sha256(
                json.dumps({
                    "mailbox_id": mailbox_id,
                    "citizen_id": citizen_id,
                    "operation": operation,
                    "granted": result["granted"],
                    "lease_state": state.value,
                    "timestamp": now,
                }, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }
        result["receipt"] = receipt
        mailbox.access_receipts.append(receipt)

        return result

    def revoke_mailbox(self, mailbox_id: str) -> bool:
        """End a lease early and invalidate every invitation and session."""
        mailbox = self._mailboxes.get(mailbox_id)
        if mailbox is None:
            return False
        if mailbox.status == LeaseStatus.DESTROYED:
            return False
        mailbox.status = LeaseStatus.REVOKED
        mailbox.closed_at = time.time()
        self.invitations.revoke_mailbox(mailbox_id)
        return True

    def close_mailbox(self, mailbox_id: str) -> bool:
        """Compatibility alias for explicit revocation."""
        return self.revoke_mailbox(mailbox_id)

    def destroy_mailbox(self, mailbox_id: str) -> bool:
        """Scrub live authority while retaining non-secret receipt evidence."""
        mailbox = self._mailboxes.get(mailbox_id)
        if mailbox is None:
            return False
        self.invitations.destroy_mailbox_authority(mailbox_id)
        mailbox.citizen_ids.clear()
        mailbox.status = LeaseStatus.DESTROYED
        mailbox.destroyed_at = time.time()
        mailbox.closed_at = mailbox.closed_at or mailbox.destroyed_at
        return True

    def get_mailbox(self, mailbox_id: str) -> Optional[PalindromeMailbox]:
        return self._mailboxes.get(mailbox_id)

    def list_mailboxes(self) -> List[PalindromeMailbox]:
        return list(self._mailboxes.values())

    def mailbox_status(self, mailbox_id: str, now: Optional[float] = None) -> Optional[dict]:
        """Get the explicit lease status and enrolled public file identities."""
        now = time.time() if now is None else now
        mailbox = self._mailboxes.get(mailbox_id)
        if mailbox is None:
            return None

        state = mailbox.current_status(now)
        citizens = [
            self.citizens.get(cid).to_public_dict()
            for cid in mailbox.citizen_ids
            if self.citizens.get(cid)
        ]

        return {
            "mailbox_id": mailbox.mailbox_id,
            "status": state.value,
            "created_at": mailbox.created_at,
            "ttl_seconds": mailbox.ttl_seconds,
            "age_seconds": now - mailbox.created_at,
            "citizens": citizens,
            "access_count": len(mailbox.access_receipts),
            "task_description": mailbox.task_description,
        }

    def _generate_name(self) -> str:
        """Generate a human-readable mailbox name like 'wolf-moon-72'."""
        adjectives = ["wolf", "stone", "river", "iron", "shadow", "ember", "frost", "storm"]
        nouns = ["moon", "sun", "gate", "star", "tree", "lake", "wind", "fire"]
        adj = secrets.choice(adjectives)
        noun = secrets.choice(nouns)
        num = secrets.randbelow(100)
        return f"{adj}-{noun}-{num}"
