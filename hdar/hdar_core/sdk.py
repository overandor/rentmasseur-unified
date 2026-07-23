"""HDAR Continuity SDK — Python client library for the continuity protocol.

Provides a high-level API for:
  - Creating and managing agent identities
  - Sealing and restoring capsules
  - Running the full continuity loop
  - Offline verification
  - Key rotation
  - Secret access

Usage:
    from sdk import ContinuityClient

    client = ContinuityClient(state_dir="/path/to/state")
    client.init_owner_key()  # or load existing

    # Seal a capsule
    capsule = client.seal(workspace_dir="/path/to/workspace",
                          agent_id="my-agent",
                          objective="do something")

    # Restore on another host
    restoration = client.restore(capsule, workspace_dir="/path/to/dest")

    # Verify offline
    result = client.verify_chain([capsule])
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from crypto import (
    OwnerKeyPair, HostKeyPair, PublicKey,
    canonicalize, sha256_hex, key_fingerprint,
)
from crypto.key_rotation import KeyRotation
from capsule.store import ContentStore
from capsule.identity import LineageEpoch
from capsule.capabilities import Capability, CapabilityCompiler
from lifecycle.lease import LeaseManager
from lifecycle.effects import EffectRegistry
from lifecycle.observability import (
    StructuredLogger, MetricsCollector, EventStream, ContinuityObserver,
)
from lifecycle.secrets import SecretManager, FileSecretBackend, SecretReference
from lifecycle.distributed_lease import SQLiteLeaseBackend, DistributedLeaseManager
from lifecycle.crash_recovery import CrashRecovery
from provider_factory import create_provider, ProviderType
from continuity import (
    ContinuityLoop, ContinuityVerifier, ContinuityCapsule, FencingInvalidation,
)
from evidence.attestation import (
    HostAttestation, HostPolicy, AttestationVerifier, build_attestation,
)
from transport.security import (
    SecureTransport, ReplayProtection, TransferEnvelope, HostTransportKeys,
)


class ContinuityClient:
    """High-level SDK client for the continuity protocol.

    Wraps the low-level modules into a simple API suitable for
    integration into agent frameworks, CI systems, and applications.
    """

    def __init__(
        self,
        state_dir: str,
        owner_key_path: Optional[str] = None,
        enable_observability: bool = True,
    ):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Core components
        self.store = ContentStore(str(self.state_dir / "store"))
        self.lease_backend = SQLiteLeaseBackend(str(self.state_dir / "leases.db"))
        self.lease_manager = DistributedLeaseManager(self.lease_backend)
        self.effects = EffectRegistry(str(self.state_dir / "effects.jsonl"))
        self.cap_compiler = CapabilityCompiler()

        # Owner key
        self.owner_key: Optional[OwnerKeyPair] = None
        self.key_rotation: Optional[KeyRotation] = None
        if owner_key_path and os.path.exists(owner_key_path):
            self.owner_key = OwnerKeyPair.load(owner_key_path)
        elif owner_key_path:
            self.owner_key = OwnerKeyPair.generate()
            self.owner_key.save(owner_key_path)
        else:
            self.owner_key = OwnerKeyPair.generate()

        self.key_rotation = KeyRotation(self.owner_key)

        # Observability
        if enable_observability:
            self.logger = StructuredLogger("sdk")
            self.metrics = MetricsCollector()
            self.event_stream = EventStream(str(self.state_dir / "events.jsonl"))
            self.observer = ContinuityObserver(self.logger, self.metrics, self.event_stream)
        else:
            self.observer = None

        # Continuity loop
        self.loop = ContinuityLoop(
            self.owner_key, self.store, self.lease_manager.backend, str(self.state_dir),
        )

        # Verifier
        self.verifier = ContinuityVerifier(self.owner_key.to_public())

        # Secret management
        self.secret_backend = FileSecretBackend(str(self.state_dir / "secrets"))
        self.secrets = SecretManager(self.secret_backend, self.lease_manager.backend)

        # Crash recovery
        self.recovery = CrashRecovery(
            str(self.state_dir), self.lease_backend, self.effects, self.logger,
        )

    # ─── Key Management ───────────────────────────────

    def init_owner_key(self, path: Optional[str] = None):
        """Generate a new owner key and optionally save it."""
        self.owner_key = OwnerKeyPair.generate()
        if path:
            self.owner_key.save(path)

    def load_owner_key(self, path: str, password: Optional[bytes] = None):
        """Load an owner key from file."""
        self.owner_key = OwnerKeyPair.load(path, password)
        self.key_rotation = KeyRotation(self.owner_key)

    def rotate_key(self, reason: str = "routine") -> dict:
        """Rotate the owner's signing key."""
        new_key = OwnerKeyPair.generate()
        receipt = self.key_rotation.rotate(new_key, reason=reason)
        self.owner_key = new_key
        self.verifier = ContinuityVerifier(self.owner_key.to_public())
        return receipt.to_dict()

    @property
    def owner_public_key(self) -> PublicKey:
        return self.owner_key.to_public()

    @property
    def owner_fingerprint(self) -> str:
        return self.owner_key.fingerprint

    # ─── Capsule Operations ───────────────────────────

    def seal(
        self,
        workspace_dir: str,
        agent_id: str,
        agent_name: str = "",
        objective: str = "",
        continuation_point: str = "",
        capabilities: Optional[List[Capability]] = None,
        parent_capsule_hash: Optional[str] = None,
        epoch: Optional[LineageEpoch] = None,
    ) -> ContinuityCapsule:
        """Seal a capsule from a workspace."""
        if epoch is None:
            epoch = LineageEpoch.genesis(agent_id)

        lease, err = self.lease_manager.acquire(
            agent_id, "pending", epoch.sequence, "sdk-client", "sdk-runtime"
        )
        if err:
            raise RuntimeError(f"lease acquisition failed: {err}")

        capsule, path = self.loop.seal_on_host_a(
            workspace_dir=Path(workspace_dir),
            agent_id=agent_id,
            agent_name=agent_name or agent_id,
            epoch=epoch,
            objective=objective,
            continuation_point=continuation_point,
            capabilities=capabilities or [],
            effects=self.effects,
            fencing_token=lease.fencing_token,
        )
        return capsule

    def restore(
        self,
        capsule: ContinuityCapsule,
        workspace_dir: str,
        holder_id: str = "sdk-restore",
        destination_policy: Optional[Dict] = None,
        provider_type: ProviderType = ProviderType.AUTO,
    ) -> dict:
        """Restore a capsule on the local host."""
        provider = create_provider(provider_type, str(self.state_dir / "provider"))
        host_key = HostKeyPair.generate(holder_id)
        return self.loop.restore_on_host_b(
            capsule, provider, host_key, workspace_dir,
            holder_id=holder_id,
            destination_policy=destination_policy or {},
        )

    def verify_chain(
        self,
        capsules: List[ContinuityCapsule],
        invalidations: Optional[List[FencingInvalidation]] = None,
        witnesses: Optional[List[Tuple[dict, PublicKey]]] = None,
    ) -> dict:
        """Verify a continuity chain offline."""
        return self.verifier.verify_full_chain(capsules, invalidations, witnesses)

    # ─── Secret Management ────────────────────────────

    def store_secret(self, name: str, value: bytes, provider: str = "file"):
        """Store a secret."""
        self.secrets.store_secret(name, value)

    def access_secret(
        self,
        agent_id: str,
        secret_name: str,
        secret_reference: str,
        fencing_token: str,
    ) -> Tuple[bool, bytes, str]:
        """Access a secret (requires valid lease)."""
        ref = SecretReference(name=secret_name, provider="file", reference=secret_reference)
        return self.secrets.access_secret(agent_id, ref, fencing_token)

    def get_secret_access_log(self) -> List[dict]:
        """Get the audit log of secret accesses."""
        return self.secrets.get_access_log()

    # ─── Recovery ─────────────────────────────────────

    def recover(self) -> dict:
        """Run crash recovery on startup."""
        report = self.recovery.recover()
        return report.to_dict()

    def mark_clean_shutdown(self):
        """Mark a clean shutdown."""
        self.recovery.mark_clean_shutdown()

    # ─── Metrics ──────────────────────────────────────

    def get_metrics(self) -> dict:
        """Get current metrics snapshot."""
        return self.metrics.snapshot() if self.observer else {}

    def get_events(self, since: float = 0) -> List[dict]:
        """Get events since a timestamp."""
        return self.event_stream.read(since) if self.event_stream else []

    # ─── Transport ────────────────────────────────────

    def create_transport(self, host_key: HostKeyPair) -> SecureTransport:
        """Create a secure transport channel."""
        return SecureTransport(host_key)

    # ─── Attestation ──────────────────────────────────

    def attest_host(
        self,
        host_id: str,
        runtime_provider: str,
        host_key: HostKeyPair,
    ) -> dict:
        """Build and sign a host attestation."""
        att = build_attestation(host_id, runtime_provider, host_key)
        return att.to_dict()

    def verify_attestation(
        self,
        attestation: dict,
        host_pub: PublicKey,
        policy: Optional[HostPolicy] = None,
    ) -> Tuple[bool, List[str]]:
        """Verify a host attestation against policy."""
        att = HostAttestation.from_dict(attestation)
        verifier = AttestationVerifier(policy)
        return verifier.verify(att, host_pub)
