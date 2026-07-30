"""Secret management — lease-gated access to protected credentials.

Provides:
  - SecretBackend: abstract interface for secret storage
  - FileSecretBackend: file-based implementation for development
  - SecretManager: lease-gated access control for secrets

Security model:
  - Secrets are never stored in the capsule
  - The capsule contains only secret_references (name + provider + opaque handle)
  - A runtime must hold a valid lease to access secrets
  - The lease's fencing token is validated on every secret access
  - When the lease is released/destroyed, secrets become inaccessible
  - Secret access is logged for audit
"""
from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lifecycle.lease import LeaseManager


@dataclass
class SecretReference:
    """A reference to a secret stored outside the capsule."""
    name: str
    provider: str
    reference: str  # opaque handle (e.g., "vault://secret/path", "file://path")
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "provider": self.provider,
            "reference": self.reference,
            "description": self.description,
        }


@dataclass
class SecretAccessRecord:
    """Audit record of a secret access."""
    agent_id: str
    secret_name: str
    fencing_token: str
    lease_generation: int
    timestamp: float
    success: bool
    reason: str = ""


class SecretBackend(ABC):
    """Abstract interface for secret storage backends."""

    @abstractmethod
    def get_secret(self, reference: str) -> Tuple[bool, bytes, str]:
        """Retrieve a secret by its reference.

        Returns (success, secret_bytes, reason).
        """
        pass

    @abstractmethod
    def put_secret(self, reference: str, value: bytes) -> Tuple[bool, str]:
        """Store a secret."""
        pass

    @abstractmethod
    def list_secrets(self) -> List[str]:
        """List available secret references."""
        pass


class FileSecretBackend(SecretBackend):
    """File-based secret storage for development.

    Stores secrets as files in a directory. NOT for production use.
    Production should use Vault, AWS Secrets Manager, or equivalent.
    """

    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)

    def _resolve(self, reference: str) -> Path:
        # Strip "file://" prefix if present
        ref = reference.replace("file://", "")
        return self.root / ref

    def get_secret(self, reference: str) -> Tuple[bool, bytes, str]:
        path = self._resolve(reference)
        if not path.exists():
            return False, b"", f"secret not found: {reference}"
        return True, path.read_bytes(), "retrieved"

    def put_secret(self, reference: str, value: bytes) -> Tuple[bool, str]:
        path = self._resolve(reference)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        os.chmod(path, 0o600)
        return True, "stored"

    def list_secrets(self) -> List[str]:
        return [str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()]


class SecretManager:
    """Lease-gated secret access control.

    A runtime must present a valid fencing token to access secrets.
    When the lease is released or expires, secrets become inaccessible.
    All access is logged for audit.
    """

    def __init__(
        self,
        backend: SecretBackend,
        lease_manager: LeaseManager,
    ):
        self.backend = backend
        self.lease_manager = lease_manager
        self._access_log: List[SecretAccessRecord] = []

    def access_secret(
        self,
        agent_id: str,
        secret_reference: SecretReference,
        fencing_token: str,
    ) -> Tuple[bool, bytes, str]:
        """Access a secret, gated by lease validation.

        Args:
            agent_id: The agent requesting access
            secret_reference: The secret to access
            fencing_token: The current lease's fencing token

        Returns (success, secret_bytes, reason).
        """
        # Validate the fencing token is current
        if not self.lease_manager.validate_token(agent_id, fencing_token):
            record = SecretAccessRecord(
                agent_id=agent_id,
                secret_name=secret_reference.name,
                fencing_token=fencing_token,
                lease_generation=-1,
                timestamp=time.time(),
                success=False,
                reason="invalid or expired fencing token",
            )
            self._access_log.append(record)
            return False, b"", "invalid or expired fencing token — secret access denied"

        # Get the lease generation for audit
        lease_gen = self.lease_manager.get_generation(agent_id)

        # Retrieve the secret
        success, secret, reason = self.backend.get_secret(secret_reference.reference)

        record = SecretAccessRecord(
            agent_id=agent_id,
            secret_name=secret_reference.name,
            fencing_token=fencing_token,
            lease_generation=lease_gen,
            timestamp=time.time(),
            success=success,
            reason=reason if not success else "accessed",
        )
        self._access_log.append(record)

        return success, secret, reason

    def get_access_log(self) -> List[Dict]:
        """Return the audit log of all secret accesses."""
        return [
            {
                "agent_id": r.agent_id,
                "secret_name": r.secret_name,
                "fencing_token": r.fencing_token,
                "lease_generation": r.lease_generation,
                "timestamp": r.timestamp,
                "success": r.success,
                "reason": r.reason,
            }
            for r in self._access_log
        ]

    def store_secret(
        self,
        reference: str,
        value: bytes,
    ) -> Tuple[bool, str]:
        """Store a secret in the backend (admin operation)."""
        return self.backend.put_secret(reference, value)
