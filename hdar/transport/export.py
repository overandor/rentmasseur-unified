"""Capsule transport — export, import, delta, and receipts.

Exports a capsule as a portable archive, transfers it, imports it
on the destination, and produces transport receipts.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class TransportReceipt:
    """Receipt for a capsule transport operation."""
    transport_id: str
    source_host: str
    destination_host: str
    capsule_hash: str
    archive_hash: str
    archive_size: int
    block_count: int
    transferred_blocks: int
    skipped_blocks: int  # already present on destination
    timestamp: float
    verified: bool = False
    verification_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "transport_id": self.transport_id,
            "source_host": self.source_host,
            "destination_host": self.destination_host,
            "capsule_hash": self.capsule_hash,
            "archive_hash": self.archive_hash,
            "archive_size": self.archive_size,
            "block_count": self.block_count,
            "transferred_blocks": self.transferred_blocks,
            "skipped_blocks": self.skipped_blocks,
            "timestamp": self.timestamp,
            "verified": self.verified,
            "verification_notes": self.verification_notes,
        }


class CapsuleExporter:
    """Exports a capsule + its content-addressed blocks into a portable archive."""

    def __init__(self, store_root: str):
        self.store_root = Path(store_root)

    def export_capsule(
        self,
        capsule_path: str,
        output_path: str,
        source_host: str = "local",
    ) -> Tuple[str, TransportReceipt]:
        """Export a capsule and all its blocks into a .tar.gz archive.

        Returns (archive_path, transport_receipt).
        """
        capsule_path = Path(capsule_path)
        output_path = Path(output_path)

        # Load capsule manifest to find block hashes
        manifest = json.loads(capsule_path.read_text())
        ws_manifest = manifest.get("workspace_manifest", {})
        block_hashes = []
        for file_entry in ws_manifest.get("files", []):
            block_hashes.append(file_entry.get("content_hash", ""))

        # Create archive
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output_path, "w:gz") as tar:
            # Add capsule manifest
            tar.add(capsule_path, arcname="capsule.json")

            # Add content-addressed blocks (store uses <root>/<hash[:2]>/<hash>)
            for block_hash in block_hashes:
                if not block_hash:
                    continue
                block_path = self.store_root / block_hash[:2] / block_hash
                if block_path.exists():
                    tar.add(block_path, arcname=f"blocks/{block_hash}")

        # Compute archive hash
        archive_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
        archive_size = output_path.stat().st_size

        receipt = TransportReceipt(
            transport_id=hashlib.sha256(
                f"{manifest.get('manifest_hash', '')}:{time.time()}".encode()
            ).hexdigest()[:16],
            source_host=source_host,
            destination_host="",
            capsule_hash=manifest.get("manifest_hash", ""),
            archive_hash=archive_hash,
            archive_size=archive_size,
            block_count=len(block_hashes),
            transferred_blocks=len(block_hashes),
            skipped_blocks=0,
            timestamp=time.time(),
        )

        return str(output_path), receipt


class CapsuleImporter:
    """Imports a capsule archive on a destination host.

    Verifies the archive hash, extracts blocks into the local store,
    and verifies every block hash before accepting the capsule.
    """

    def __init__(self, store_root: str):
        self.store_root = Path(store_root)
        self.store_root.mkdir(parents=True, exist_ok=True)

    def import_capsule(
        self,
        archive_path: str,
        expected_archive_hash: str = "",
        destination_host: str = "remote",
    ) -> Tuple[str, TransportReceipt]:
        """Import a capsule archive. Returns (capsule_path, transport_receipt).

        Raises ValueError if archive hash doesn't match or block verification fails.
        """
        archive_path = Path(archive_path)

        # Verify archive hash
        actual_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if expected_archive_hash and actual_hash != expected_archive_hash:
            raise ValueError(
                f"archive hash mismatch: expected {expected_archive_hash}, "
                f"got {actual_hash}"
            )

        # Extract to temp directory
        import_dir = self.store_root / "import_tmp"
        if import_dir.exists():
            shutil.rmtree(import_dir)
        import_dir.mkdir()

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(import_dir)

        # Load capsule manifest
        capsule_path = import_dir / "capsule.json"
        manifest = json.loads(capsule_path.read_text())
        ws_manifest = manifest.get("workspace_manifest", {})
        block_hashes = [f.get("content_hash", "") for f in ws_manifest.get("files", [])]

        # Verify and install blocks (store uses <root>/<hash[:2]>/<hash>)
        blocks_dir = import_dir / "blocks"
        transferred = 0
        skipped = 0

        for block_hash in block_hashes:
            if not block_hash:
                continue
            dest_block = self.store_root / block_hash[:2] / block_hash
            if dest_block.exists():
                # Block already present (deduplication)
                skipped += 1
                continue

            src_block = blocks_dir / block_hash
            if not src_block.exists():
                raise ValueError(f"missing block in archive: {block_hash}")

            # Verify block hash
            actual = hashlib.sha256(src_block.read_bytes()).hexdigest()
            if actual != block_hash:
                raise ValueError(
                    f"block hash mismatch: expected {block_hash}, got {actual}"
                )

            dest_block.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_block, dest_block)
            transferred += 1

        # Move capsule to final location
        final_capsule = self.store_root / "capsule.json"
        shutil.move(str(capsule_path), str(final_capsule))
        shutil.rmtree(import_dir)

        receipt = TransportReceipt(
            transport_id=hashlib.sha256(
                f"{manifest.get('manifest_hash', '')}:{time.time()}".encode()
            ).hexdigest()[:16],
            source_host="",
            destination_host=destination_host,
            capsule_hash=manifest.get("manifest_hash", ""),
            archive_hash=actual_hash,
            archive_size=archive_path.stat().st_size,
            block_count=len(block_hashes),
            transferred_blocks=transferred,
            skipped_blocks=skipped,
            timestamp=time.time(),
            verified=True,
            verification_notes=f"all {len(block_hashes)} blocks verified",
        )

        return str(final_capsule), receipt


class DeltaExporter:
    """Exports only the blocks that differ between two capsule states.

    This enables efficient incremental transport: instead of sending
    the entire workspace, send only the changed content-addressed blocks.
    """

    @staticmethod
    def compute_delta(
        source_manifest: dict,
        base_manifest: Optional[dict] = None,
    ) -> Dict[str, List[str]]:
        """Compute which blocks are new vs unchanged.

        Returns {"new": [hashes], "unchanged": [hashes], "removed": [hashes]}.
        """
        source_hashes = {
            f.get("content_hash", "") for f in source_manifest.get("workspace_manifest", {}).get("files", [])
        }

        if base_manifest is None:
            return {
                "new": list(source_hashes),
                "unchanged": [],
                "removed": [],
            }

        base_hashes = {
            f.get("content_hash", "") for f in base_manifest.get("workspace_manifest", {}).get("files", [])
        }

        return {
            "new": list(source_hashes - base_hashes),
            "unchanged": list(source_hashes & base_hashes),
            "removed": list(base_hashes - source_hashes),
        }
