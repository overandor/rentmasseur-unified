"""Content-addressed storage backed by SHA-256.

Files are stored by their content hash. Deduplication is automatic:
identical content is written once. The store supports both file ingestion
and directory-tree hashing with a Merkle-like root.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


def sha256_file(path: Path, buf_size: int = 1 << 20) -> str:
    """Stream-hash a file and return hex digest."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(buf_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class FileEntry:
    """A single file recorded in a workspace manifest."""
    rel_path: str        # relative path within workspace
    content_hash: str    # SHA-256 of file content
    size: int
    mode: int            # permission bits

    def to_dict(self) -> dict:
        return {
            "rel_path": self.rel_path,
            "content_hash": self.content_hash,
            "size": self.size,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FileEntry":
        return cls(
            rel_path=d["rel_path"],
            content_hash=d["content_hash"],
            size=d["size"],
            mode=d["mode"],
        )


@dataclass
class WorkspaceManifest:
    """Merkle-like manifest of a workspace directory tree."""
    root_hash: str               # hash over all file entries
    files: List[FileEntry] = field(default_factory=list)
    total_size: int = 0

    def to_dict(self) -> dict:
        return {
            "root_hash": self.root_hash,
            "files": [f.to_dict() for f in self.files],
            "total_size": self.total_size,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorkspaceManifest":
        return cls(
            root_hash=d["root_hash"],
            files=[FileEntry.from_dict(f) for f in d["files"]],
            total_size=d["total_size"],
        )


class ContentStore:
    """Content-addressed blob store.

    Blobs are stored at ``<root>/<hash[:2]>/<hash>`` with two-level
    sharding to avoid huge flat directories.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _blob_path(self, content_hash: str) -> Path:
        return self.root / content_hash[:2] / content_hash

    def put_file(self, src: Path) -> str:
        """Ingest a file into the store. Returns content hash."""
        h = sha256_file(src)
        dest = self._blob_path(h)
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        return h

    def put_bytes(self, data: bytes) -> str:
        """Ingest raw bytes. Returns content hash."""
        h = sha256_bytes(data)
        dest = self._blob_path(h)
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        return h

    def get(self, content_hash: str) -> Optional[bytes]:
        """Retrieve blob content, or None if not present."""
        path = self._blob_path(content_hash)
        if not path.exists():
            return None
        return path.read_bytes()

    def has(self, content_hash: str) -> bool:
        return self._blob_path(content_hash).exists()

    def extract_to(self, content_hash: str, dest: Path, mode: int = 0o644):
        """Extract a blob to a destination path."""
        src = self._blob_path(content_hash)
        if not src.exists():
            raise FileNotFoundError(f"blob not found: {content_hash}")
        shutil.copy2(src, dest)
        os.chmod(dest, mode)

    @staticmethod
    def hash_workspace(directory: Path) -> WorkspaceManifest:
        """Hash a directory tree and return a manifest.

        Files are sorted by relative path for deterministic hashing.
        The root hash is SHA-256 over the canonical encoding of all
        file entries.
        """
        entries: List[FileEntry] = []
        for path in sorted(directory.rglob("*")):
            if path.is_file() and not path.is_symlink():
                rel = path.relative_to(directory).as_posix()
                h = sha256_file(path)
                st = path.stat()
                entries.append(FileEntry(
                    rel_path=rel,
                    content_hash=h,
                    size=st.st_size,
                    mode=st.st_mode & 0o777,
                ))

        canonical = "\n".join(
            f"{e.rel_path}|{e.content_hash}|{e.size}|{e.mode}"
            for e in entries
        ).encode()
        root_hash = hashlib.sha256(canonical).hexdigest()
        total = sum(e.size for e in entries)

        return WorkspaceManifest(
            root_hash=root_hash,
            files=entries,
            total_size=total,
        )

    def ingest_workspace(self, directory: Path) -> WorkspaceManifest:
        """Hash a workspace and ingest all files into the store."""
        manifest = self.hash_workspace(directory)
        for entry in manifest.files:
            src = directory / entry.rel_path
            self.put_file(src)
        return manifest

    def restore_workspace(self, manifest: WorkspaceManifest, dest: Path):
        """Reconstruct a workspace from a manifest and stored blobs."""
        dest.mkdir(parents=True, exist_ok=True)
        for entry in manifest.files:
            out = dest / entry.rel_path
            out.parent.mkdir(parents=True, exist_ok=True)
            self.extract_to(entry.content_hash, out, entry.mode)

    def verify_workspace(self, directory: Path, expected_hash: str) -> bool:
        """Verify that a directory's root hash matches the expected value."""
        manifest = self.hash_workspace(directory)
        return manifest.root_hash == expected_hash
