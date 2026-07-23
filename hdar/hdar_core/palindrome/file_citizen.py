"""Palindrome file citizenship.

Each enrolled file receives:
  - Public identity: a stable ID + content hash that can be shown to GPT
  - Private authority: owner signature that authorizes operations

The public identity is NOT a password. It says "this is the file."
The owner signature says "I permit this operation."
The mailbox invitation says "this visitor may perform it until this time."

Files are enrolled by the local machine. The machine tracks:
  - File path (private, never exposed)
  - Content hash (public)
  - Public ID (derived from hash, stable across renames)
  - Owner authorization chain
  - Access history
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class FilePermission(Enum):
    READ = "read"
    SEARCH = "search"
    SUMMARIZE = "summarize"
    VERIFY_HASH = "verify_hash"
    COMPARE = "compare"
    INSPECT = "inspect"  # inspect without seeing credentials

    def to_dict(self) -> str:
        return self.value


@dataclass
class FileAccessRecord:
    """Record of one access to a file citizen."""
    mailbox_id: str
    guest_id: str
    permission: str
    granted: bool
    timestamp: float = 0.0
    receipt_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "mailbox_id": self.mailbox_id,
            "guest_id": self.guest_id,
            "permission": self.permission,
            "granted": self.granted,
            "timestamp": self.timestamp,
            "receipt_hash": self.receipt_hash,
        }


@dataclass
class FileCitizen:
    """A file enrolled in Palindrome with public identity and private authority.

    Public (sharable with GPT):
      - citizen_id: stable public ID
      - content_hash: SHA-256 of file content
      - size: file size
      - enrolled_at: when it was enrolled

    Private (never leaves the machine):
      - local_path: actual filesystem path
      - owner_signature: Ed25519 signature authorizing enrollment
      - permissions: what operations are permitted
      - access_history: who accessed it and when
    """
    citizen_id: str
    content_hash: str
    local_path: str  # private
    size: int
    enrolled_at: float = 0.0
    owner_signature: str = ""  # private
    permissions: List[str] = field(default_factory=list)
    access_history: List[FileAccessRecord] = field(default_factory=list)
    version: int = 1
    previous_hash: str = ""  # for version tracking

    def to_public_dict(self) -> dict:
        """Public identity — safe to share with GPT."""
        return {
            "citizen_id": self.citizen_id,
            "content_hash": self.content_hash,
            "size": self.size,
            "enrolled_at": self.enrolled_at,
            "version": self.version,
            "permissions": self.permissions,
        }

    def to_private_dict(self) -> dict:
        """Full record including private fields — never leaves the machine."""
        return {
            "citizen_id": self.citizen_id,
            "content_hash": self.content_hash,
            "local_path": self.local_path,
            "size": self.size,
            "enrolled_at": self.enrolled_at,
            "owner_signature": self.owner_signature,
            "permissions": self.permissions,
            "access_history": [a.to_dict() for a in self.access_history],
            "version": self.version,
            "previous_hash": self.previous_hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FileCitizen":
        return cls(
            citizen_id=d["citizen_id"],
            content_hash=d["content_hash"],
            local_path=d.get("local_path", ""),
            size=d.get("size", 0),
            enrolled_at=d.get("enrolled_at", 0.0),
            owner_signature=d.get("owner_signature", ""),
            permissions=d.get("permissions", []),
            access_history=[
                FileAccessRecord(**a) for a in d.get("access_history", [])
            ],
            version=d.get("version", 1),
            previous_hash=d.get("previous_hash", ""),
        )


class FileCitizenRegistry:
    """Enrolls and manages file citizens on the local machine.

    The registry is the vault — it never exposes local paths to the network.
    All GPT sees is the public identity (citizen_id + content_hash).
    """

    def __init__(self):
        self._citizens: Dict[str, FileCitizen] = {}  # citizen_id -> FileCitizen
        self._by_path: Dict[str, str] = {}  # local_path -> citizen_id

    def enroll(
        self,
        local_path: str,
        permissions: List[str],
        owner_key=None,
    ) -> FileCitizen:
        """Enroll a file as a citizen with public identity and private authority."""
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {local_path}")

        content_hash = self._hash_file(path)
        size = path.stat().st_size

        # Check if this path was previously enrolled (version update)
        previous_id = self._by_path.get(str(path.resolve()))
        previous_hash = ""
        version = 1
        if previous_id and previous_id in self._citizens:
            prev = self._citizens[previous_id]
            if prev.content_hash == content_hash:
                # Same content — return existing
                return prev
            previous_hash = prev.content_hash
            version = prev.version + 1
            # Remove old citizen
            del self._citizens[previous_id]

        # Derive citizen_id from content hash (stable across renames)
        citizen_id = f"file-{content_hash[:16]}"

        # Sign the enrollment if owner key provided
        signature = ""
        if owner_key:
            canonical = json.dumps(
                {
                    "citizen_id": citizen_id,
                    "content_hash": content_hash,
                    "size": size,
                    "version": version,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            signature = owner_key.sign_bytes(canonical)

        citizen = FileCitizen(
            citizen_id=citizen_id,
            content_hash=content_hash,
            local_path=str(path.resolve()),
            size=size,
            enrolled_at=time.time(),
            owner_signature=signature,
            permissions=permissions,
            version=version,
            previous_hash=previous_hash,
        )

        self._citizens[citizen_id] = citizen
        self._by_path[str(path.resolve())] = citizen_id
        return citizen

    def get(self, citizen_id: str) -> Optional[FileCitizen]:
        return self._citizens.get(citizen_id)

    def get_by_path(self, local_path: str) -> Optional[FileCitizen]:
        resolved = str(Path(local_path).resolve())
        cid = self._by_path.get(resolved)
        return self._citizens.get(cid) if cid else None

    def check_permission(
        self,
        citizen_id: str,
        permission: str,
        mailbox_id: str,
        guest_id: str = "",
    ) -> Tuple[bool, str]:
        """Check if a permission is granted for this file citizen."""
        citizen = self._citizens.get(citizen_id)
        if citizen is None:
            return False, "file citizen not found"

        if permission not in citizen.permissions:
            return False, f"permission '{permission}' not granted for {citizen_id}"

        # Record access
        record = FileAccessRecord(
            mailbox_id=mailbox_id,
            guest_id=guest_id,
            permission=permission,
            granted=True,
            timestamp=time.time(),
        )
        citizen.access_history.append(record)
        return True, "granted"

    def read_content(self, citizen_id: str, mailbox_id: str, guest_id: str = "") -> Tuple[Optional[bytes], str]:
        """Read file content if read permission is granted."""
        granted, reason = self.check_permission(citizen_id, "read", mailbox_id, guest_id)
        if not granted:
            return None, reason

        citizen = self._citizens[citizen_id]
        with open(citizen.local_path, "rb") as f:
            return f.read(), "read"

    def read_summary(self, citizen_id: str, mailbox_id: str, guest_id: str = "") -> Tuple[Optional[dict], str]:
        """Return file summary (metadata only, no content) if summarize permission granted."""
        granted, reason = self.check_permission(citizen_id, "summarize", mailbox_id, guest_id)
        if not granted:
            return None, reason

        citizen = self._citizens[citizen_id]
        return {
            "citizen_id": citizen.citizen_id,
            "content_hash": citizen.content_hash,
            "size": citizen.size,
            "version": citizen.version,
            "permissions": citizen.permissions,
            "enrolled_at": citizen.enrolled_at,
        }, "summarized"

    def verify_hash(self, citizen_id: str, expected_hash: str) -> Tuple[bool, str]:
        """Verify that a file's current content matches its enrolled hash."""
        citizen = self._citizens.get(citizen_id)
        if citizen is None:
            return False, "file citizen not found"

        current_hash = self._hash_file(Path(citizen.local_path))
        if current_hash != expected_hash:
            return False, f"hash mismatch: expected {expected_hash[:16]}, got {current_hash[:16]}"
        return True, "verified"

    def list_public_identities(self) -> List[dict]:
        """List all file citizens' public identities."""
        return [c.to_public_dict() for c in self._citizens.values()]

    def list_all(self) -> List[FileCitizen]:
        return list(self._citizens.values())

    def revoke(self, citizen_id: str) -> bool:
        """Revoke a file citizen (remove from registry)."""
        citizen = self._citizens.get(citizen_id)
        if citizen is None:
            return False
        del self._citizens[citizen_id]
        if citizen.local_path in self._by_path:
            del self._by_path[citizen.local_path]
        return True

    def _hash_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
