"""Capsule restoration — workspace reconstruction from a sealed capsule.

Restores a workspace from a capsule manifest using the content-addressed
store. Verifies manifest signature, receipt chain, and workspace root hash
after restoration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from .store import ContentStore, WorkspaceManifest
from .identity import LineageEpoch, deserialize_public_key
from .receipt import ReceiptChain
from .seal import CapsuleManifest, CapsuleSealer

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class CapsuleRestorer:
    """Restores a workspace from a sealed capsule."""

    def __init__(self, store: ContentStore):
        self.store = store

    def load_capsule(self, capsule_path: Path) -> CapsuleManifest:
        """Load a capsule manifest from a JSON file."""
        data = json.loads(capsule_path.read_text())
        return CapsuleManifest.from_dict(data)

    def verify_manifest(self, manifest: CapsuleManifest, owner_public_key: Ed25519PublicKey) -> bool:
        """Verify the manifest Ed25519 signature and hash."""
        expected_hash = manifest.compute_hash()
        if expected_hash != manifest.manifest_hash:
            return False
        try:
            owner_public_key.verify(
                bytes.fromhex(manifest.signature),
                manifest.canonical_bytes(),
            )
            return True
        except Exception:
            return False

    def verify_receipts(self, manifest: CapsuleManifest, owner_public_key: Ed25519PublicKey) -> bool:
        """Verify the embedded receipt chain using Ed25519 public key."""
        if not manifest.receipts:
            return False
        from .receipt import Receipt
        receipts = [Receipt.from_dict(r) for r in manifest.receipts]
        prev_hash = None
        for r in receipts:
            if r.prior_receipt_hash != prev_hash:
                return False
            if not r.verify(owner_public_key):
                return False
            prev_hash = r.receipt_hash
        return True

    def restore_workspace(
        self,
        manifest: CapsuleManifest,
        dest_dir: Path,
    ) -> Tuple[WorkspaceManifest, bool]:
        """Reconstruct the workspace from the capsule.

        Returns (restored_manifest, hash_matches).
        """
        ws_dict = manifest.workspace_manifest
        if ws_dict is None:
            raise ValueError("capsule has no workspace manifest")

        ws_manifest = WorkspaceManifest.from_dict(ws_dict)

        # Restore files from content store
        self.store.restore_workspace(ws_manifest, dest_dir)

        # Verify restored workspace hash
        restored_manifest = self.store.hash_workspace(dest_dir)
        hash_matches = restored_manifest.root_hash == ws_manifest.root_hash

        return restored_manifest, hash_matches

    def restore(
        self,
        capsule_path: Path,
        dest_dir: Path,
        owner_public_key: Optional[Ed25519PublicKey] = None,
    ) -> dict:
        """Full restoration: load, verify, restore workspace.

        Returns a restoration report dict.
        """
        manifest = self.load_capsule(capsule_path)

        # Signature verification (skip if no key provided)
        sig_valid = None
        if owner_public_key is not None:
            sig_valid = self.verify_manifest(manifest, owner_public_key)

        # Receipt chain verification
        receipts_valid = None
        if owner_public_key is not None:
            receipts_valid = self.verify_receipts(manifest, owner_public_key)

        # Workspace restoration
        restored_manifest, hash_matches = self.restore_workspace(manifest, dest_dir)

        return {
            "agent_id": manifest.agent_id,
            "agent_name": manifest.agent_name,
            "epoch": manifest.epoch,
            "objective": manifest.objective,
            "continuation_point": manifest.continuation_point,
            "working_summary": manifest.working_summary,
            "restoration_contract": manifest.restoration_contract,
            "workspace_root_hash": manifest.workspace_manifest["root_hash"],
            "restored_root_hash": restored_manifest.root_hash,
            "workspace_hash_matches": hash_matches,
            "signature_valid": sig_valid,
            "receipts_valid": receipts_valid,
            "file_count": len(restored_manifest.files),
            "total_size": restored_manifest.total_size,
            "capabilities": manifest.capabilities,
            "capability_note": manifest.capability_note,
            "pending_operations": manifest.pending_operations,
        }
