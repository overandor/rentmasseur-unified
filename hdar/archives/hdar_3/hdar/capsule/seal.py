"""Atomic capsule sealing.

Takes a workspace directory, ingests it into content-addressed storage,
creates a signed capsule manifest with lineage and receipt chain, and
writes the capsule as a single portable JSON file.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .store import ContentStore, WorkspaceManifest
from .identity import AgentIdentity, LineageEpoch, key_fingerprint, serialize_public_key
from .receipt import ReceiptChain, Receipt

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


@dataclass
class CapsuleManifest:
    """The sealed manifest inside a capsule.

    This is the agent's operational passport — not a complete copy
    of every machine it has visited.
    """
    # Identity
    agent_id: str
    agent_name: str
    epoch: Dict[str, Any]               # LineageEpoch.to_dict()
    parent_capsule_hash: Optional[str]   # None for genesis capsule

    # Model references (by digest, not embedded)
    model_digest: str = ""
    tokenizer_digest: str = ""
    inference_requirements: Dict[str, Any] = field(default_factory=dict)

    # Agent state
    objective: str = ""
    continuation_point: str = ""
    working_summary: str = ""

    # Workspace
    workspace_manifest: Optional[Dict[str, Any]] = None  # WorkspaceManifest.to_dict()

    # Capabilities
    capabilities: Dict[str, Any] = field(default_factory=dict)
    capability_note: str = ""

    # Secrets
    secret_references: List[Dict[str, str]] = field(default_factory=list)

    # Pending operations
    pending_operations: List[Dict[str, Any]] = field(default_factory=list)

    # Compatibility
    runtime_compatibility: Dict[str, Any] = field(default_factory=dict)

    # Restoration
    restoration_contract: str = "exact"  # exact | semantic | degraded

    # Receipts
    receipts: List[Dict[str, Any]] = field(default_factory=list)

    # Signature
    manifest_hash: str = ""
    signer_fingerprint: str = ""
    signature: str = ""
    sealed_at: float = 0.0

    def canonical_bytes(self) -> bytes:
        """Bytes that are signed (excludes signature, manifest_hash, sealed_at)."""
        d = self.to_dict()
        for k in ("signature", "manifest_hash", "sealed_at"):
            d.pop(k, None)
        return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

    def compute_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "epoch": self.epoch,
            "parent_capsule_hash": self.parent_capsule_hash,
            "model_digest": self.model_digest,
            "tokenizer_digest": self.tokenizer_digest,
            "inference_requirements": self.inference_requirements,
            "objective": self.objective,
            "continuation_point": self.continuation_point,
            "working_summary": self.working_summary,
            "workspace_manifest": self.workspace_manifest,
            "capabilities": self.capabilities,
            "capability_note": self.capability_note,
            "secret_references": self.secret_references,
            "pending_operations": self.pending_operations,
            "runtime_compatibility": self.runtime_compatibility,
            "restoration_contract": self.restoration_contract,
            "receipts": self.receipts,
            "manifest_hash": self.manifest_hash,
            "signer_fingerprint": self.signer_fingerprint,
            "signature": self.signature,
            "sealed_at": self.sealed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CapsuleManifest":
        return cls(**{k: d.get(k) for k in [
            "agent_id", "agent_name", "epoch", "parent_capsule_hash",
            "model_digest", "tokenizer_digest", "inference_requirements",
            "objective", "continuation_point", "working_summary",
            "workspace_manifest", "capabilities", "capability_note",
            "secret_references", "pending_operations", "runtime_compatibility",
            "restoration_contract", "receipts", "manifest_hash",
            "signer_fingerprint", "signature", "sealed_at",
        ]})


class CapsuleSealer:
    """Seals a workspace into a portable, signed capsule.

    When a lease_manager is provided, sealing requires a valid fencing
    token. A stale runtime cannot publish a successor capsule.
    """

    def __init__(self, store: ContentStore, identity: AgentIdentity, lease_manager=None):
        self.store = store
        self.identity = identity
        self.lease_manager = lease_manager

    def seal(
        self,
        workspace_dir: Path,
        epoch: LineageEpoch,
        objective: str = "",
        continuation_point: str = "",
        working_summary: str = "",
        capabilities: Optional[dict] = None,
        capability_note: str = "",
        parent_capsule_hash: Optional[str] = None,
        model_digest: str = "",
        tokenizer_digest: str = "",
        inference_requirements: Optional[dict] = None,
        secret_references: Optional[list] = None,
        pending_operations: Optional[list] = None,
        runtime_compatibility: Optional[dict] = None,
        fencing_token: str = "",
    ) -> tuple[CapsuleManifest, ReceiptChain]:
        """Seal a workspace into a capsule.

        Returns (manifest, receipt_chain).

        When lease validation is enabled, a valid fencing token is required.
        A stale runtime cannot advance the authoritative lineage.
        """
        # 0. Validate fencing token if lease manager is present
        if self.lease_manager and fencing_token:
            if not self.lease_manager.validate_token(self.identity.agent_id, fencing_token):
                raise ValueError(
                    f"stale or invalid fencing token — "
                    f"this runtime's lease generation is no longer authoritative; "
                    f"cannot seal capsule"
                )
        # 1. Ingest workspace into content store
        ws_manifest = self.store.ingest_workspace(workspace_dir)

        # 2. Build receipt chain
        chain = ReceiptChain(
            agent_id=self.identity.agent_id,
            epoch_id=epoch.epoch_id,
            signing_key=self.identity.signing_key,
        )

        # 3. Append SEAL receipt
        seal_receipt = chain.append(
            receipt_type="SEAL",
            action="capsule_sealed",
            action_payload={
                "workspace_root_hash": ws_manifest.root_hash,
                "file_count": len(ws_manifest.files),
                "total_size": ws_manifest.total_size,
                "objective": objective,
            },
            state_root=ws_manifest.root_hash,
        )

        # 4. Build capsule manifest
        manifest = CapsuleManifest(
            agent_id=self.identity.agent_id,
            agent_name=self.identity.name,
            epoch=epoch.to_dict(),
            parent_capsule_hash=parent_capsule_hash,
            model_digest=model_digest,
            tokenizer_digest=tokenizer_digest,
            inference_requirements=inference_requirements or {},
            objective=objective,
            continuation_point=continuation_point,
            working_summary=working_summary,
            workspace_manifest=ws_manifest.to_dict(),
            capabilities=capabilities or {},
            capability_note=capability_note,
            secret_references=secret_references or [],
            pending_operations=pending_operations or [],
            runtime_compatibility=runtime_compatibility or {},
            restoration_contract="exact",
            receipts=chain.to_list(),
            signer_fingerprint=self.identity.fingerprint,
            sealed_at=time.time(),
        )

        # 5. Sign manifest with Ed25519
        manifest.manifest_hash = manifest.compute_hash()
        manifest.signature = self.identity.sign(manifest.canonical_bytes()).hex()

        return manifest, chain

    def write_capsule(self, manifest: CapsuleManifest, output_path: Path):
        """Write a capsule manifest as a JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(manifest.to_dict(), indent=2, ensure_ascii=True)
        )

    def verify_manifest(self, manifest: CapsuleManifest, public_key: Ed25519PublicKey) -> bool:
        """Verify the manifest Ed25519 signature."""
        try:
            public_key.verify(
                bytes.fromhex(manifest.signature),
                manifest.canonical_bytes(),
            )
            return True
        except Exception:
            return False

    def verify_capsule_file(self, capsule_path: Path, public_key: Ed25519PublicKey) -> bool:
        """Load and verify a capsule file's manifest hash and signature."""
        data = json.loads(capsule_path.read_text())
        manifest = CapsuleManifest.from_dict(data)
        expected_hash = manifest.compute_hash()
        if manifest.manifest_hash != expected_hash:
            return False
        return self.verify_manifest(manifest, public_key)
