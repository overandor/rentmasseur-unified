"""Workspace compression and chunking for large workspaces.

Provides:
  - CompressedContentStore: wraps ContentStore with zstd/gzip compression
  - ChunkedStorage: splits large files into fixed-size chunks for dedup
  - WorkspaceOptimizer: adaptive strategy selection per file type

Compression is applied at the content-addressed block level, so
deduplication still works — identical files produce identical hashes
before compression, and the compressed form is stored once.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import os
import shutil
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from capsule.store import ContentStore, FileEntry, WorkspaceManifest

CHUNK_SIZE = 1 << 20  # 1 MiB default chunk
COMPRESSION_THRESHOLD = 4096  # only compress files > 4KB
COMPRESSION_LEVEL = 6  # balanced speed/ratio


@dataclass
class ChunkedFile:
    """A file split into content-addressed chunks."""
    rel_path: str
    chunks: List[str] = field(default_factory=list)  # list of chunk hashes
    total_size: int = 0
    content_hash: str = ""  # hash of full file (for compatibility)
    mode: int = 0o644
    compressed: bool = False

    def to_dict(self) -> dict:
        return {
            "rel_path": self.rel_path,
            "chunks": self.chunks,
            "total_size": self.total_size,
            "content_hash": self.content_hash,
            "mode": self.mode,
            "compressed": self.compressed,
        }


def compress_bytes(data: bytes, level: int = COMPRESSION_LEVEL) -> bytes:
    """Compress bytes using zlib (gzip-compatible)."""
    return gzip.compress(data, compresslevel=level)


def decompress_bytes(data: bytes) -> bytes:
    """Decompress gzip-compressed bytes."""
    return gzip.decompress(data)


def should_compress(file_path: str, size: int) -> bool:
    """Decide whether to compress a file based on type and size."""
    if size < COMPRESSION_THRESHOLD:
        return False
    # Don't compress already-compressed formats
    skip_extensions = {".gz", ".zip", ".png", ".jpg", ".jpeg", ".webp",
                       ".mp4", ".mp3", ".wav", ".avi", ".mov",
                       ".woff2", ".woff", ".ttf", ".ico"}
    suffix = Path(file_path).suffix.lower()
    if suffix in skip_extensions:
        return False
    return True


class CompressedContentStore(ContentStore):
    """Content store with transparent compression.

    Files are compressed before storage. The content hash is computed
    on the uncompressed bytes (for deduplication), but the stored
    blob is compressed. A metadata flag tracks whether each blob
    is compressed.
    """

    def __init__(self, root: str, chunk_size: int = CHUNK_SIZE):
        super().__init__(root)
        self.chunk_size = chunk_size
        self._meta_path = self.root / ".compression_meta.json"
        self._compression_meta: Dict[str, bool] = {}
        self._load_meta()

    def _load_meta(self):
        if self._meta_path.exists():
            import json
            self._compression_meta = json.loads(self._meta_path.read_text())

    def _save_meta(self):
        import json
        self._meta_path.write_text(json.dumps(self._compression_meta))

    def put_bytes(self, data: bytes) -> str:
        """Store bytes, compressing if beneficial. Returns content hash."""
        content_hash = hashlib.sha256(data).hexdigest()
        blob_path = self.root / content_hash[:2] / content_hash

        if blob_path.exists():
            return content_hash

        blob_path.parent.mkdir(parents=True, exist_ok=True)

        if should_compress("", len(data)):
            compressed = compress_bytes(data)
            if len(compressed) < len(data):
                blob_path.write_bytes(compressed)
                self._compression_meta[content_hash] = True
                self._save_meta()
                return content_hash

        blob_path.write_bytes(data)
        self._compression_meta[content_hash] = False
        self._save_meta()
        return content_hash

    def get_bytes(self, content_hash: str) -> Optional[bytes]:
        """Retrieve and decompress bytes."""
        blob_path = self.root / content_hash[:2] / content_hash
        if not blob_path.exists():
            return None
        data = blob_path.read_bytes()
        if self._compression_meta.get(content_hash, False):
            return decompress_bytes(data)
        return data

    def get_storage_size(self) -> dict:
        """Return actual storage size vs uncompressed size."""
        total_compressed = 0
        total_uncompressed = 0
        for content_hash, is_compressed in self._compression_meta.items():
            blob_path = self.root / content_hash[:2] / content_hash
            if blob_path.exists():
                total_compressed += blob_path.stat().st_size
                if is_compressed:
                    total_uncompressed += len(decompress_bytes(blob_path.read_bytes()))
                else:
                    total_uncompressed += blob_path.stat().st_size
        return {
            "compressed_size": total_compressed,
            "uncompressed_size": total_uncompressed,
            "ratio": total_compressed / max(total_uncompressed, 1),
            "compressed_blobs": sum(1 for v in self._compression_meta.values() if v),
            "total_blobs": len(self._compression_meta),
        }


class ChunkedStorage:
    """Splits large files into chunks for better deduplication.

    When a large file changes slightly, only the changed chunks
    need to be transferred, not the entire file.
    """

    def __init__(self, store: CompressedContentStore, chunk_size: int = CHUNK_SIZE):
        self.store = store
        self.chunk_size = chunk_size

    def ingest_file_chunked(self, file_path: Path, rel_path: str) -> ChunkedFile:
        """Ingest a file as multiple chunks. Returns ChunkedFile metadata."""
        data = file_path.read_bytes()
        content_hash = hashlib.sha256(data).hexdigest()
        mode = file_path.stat().st_mode & 0o777

        chunks: List[str] = []
        if len(data) <= self.chunk_size:
            # Small file — single chunk
            chunk_hash = self.store.put_bytes(data)
            chunks.append(chunk_hash)
        else:
            # Large file — split into chunks
            for i in range(0, len(data), self.chunk_size):
                chunk_data = data[i:i + self.chunk_size]
                chunk_hash = self.store.put_bytes(chunk_data)
                chunks.append(chunk_hash)

        return ChunkedFile(
            rel_path=rel_path,
            chunks=chunks,
            total_size=len(data),
            content_hash=content_hash,
            mode=mode,
            compressed=should_compress(rel_path, len(data)),
        )

    def restore_file_chunked(self, chunked: ChunkedFile, dest: Path):
        """Restore a chunked file to destination."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = b""
        for chunk_hash in chunked.chunks:
            chunk_data = self.store.get_bytes(chunk_hash)
            if chunk_data is None:
                raise ValueError(f"missing chunk: {chunk_hash}")
            data += chunk_data

        # Verify full file hash
        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != chunked.content_hash:
            raise ValueError(
                f"chunked file hash mismatch: expected {chunked.content_hash}, "
                f"got {actual_hash}"
            )

        dest.write_bytes(data)
        os.chmod(dest, chunked.mode)
