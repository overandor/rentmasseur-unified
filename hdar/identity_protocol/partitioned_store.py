"""Partitioned memory store — 7-class memory over real ContentStore.

Wraps hdar_core.capsule.store.ContentStore to add memory class tagging.
Files and bytes are ingested into the real content-addressed store, and
additionally tagged with one of seven memory classes. A partitioned root
hash groups entries by class, hashes each group, then hashes the groups
into a single root — preserving class-level auditability.

Memory classes:
  observed:          raw events, messages, files
  derived:           summaries, embeddings, hypotheses
  committed:         accepted facts and decisions
  private:           encrypted to a particular authority
  shared:            readable by an authorized group
  procedural:        skills, policies, workflows
  identity_critical: objectives, permissions, obligations, unresolved commitments
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from hdar_core.capsule.store import ContentStore, sha256_bytes, sha256_file


class MemoryClass(Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    COMMITTED = "committed"
    PRIVATE = "private"
    SHARED = "shared"
    PROCEDURAL = "procedural"
    IDENTITY_CRITICAL = "identity_critical"


def _canonicalize(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


@dataclass
class MemoryEntry:
    """A tagged entry in the partitioned memory store.

    The content_hash is the real SHA-256 key in the ContentStore.
    The memory_class is the partition tag.
    """
    entry_id: str
    memory_class: MemoryClass
    content_hash: str
    rel_path: str = ""
    size: int = 0
    created_at: float = field(default_factory=time.time)
    provenance: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "memory_class": self.memory_class.value,
            "content_hash": self.content_hash,
            "rel_path": self.rel_path,
            "size": self.size,
            "created_at": self.created_at,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntry":
        return cls(
            entry_id=d["entry_id"],
            memory_class=MemoryClass(d["memory_class"]),
            content_hash=d["content_hash"],
            rel_path=d.get("rel_path", ""),
            size=d.get("size", 0),
            created_at=d.get("created_at", 0.0),
            provenance=d.get("provenance", {}),
        )

    def entry_hash(self) -> str:
        return hashlib.sha256(_canonicalize(self.to_dict())).hexdigest()


@dataclass
class PartitionedMemoryRoot:
    """Merkle root over partitioned memory entries.

    Groups entry hashes by class, hashes each group, then hashes
    the groups into a single root. This lets the IdentityRecord bind
    to a single memory_root_hash while preserving class-level auditability.
    """
    class_roots: Dict[str, str] = field(default_factory=dict)
    total_entries: int = 0
    entry_ids: List[str] = field(default_factory=list)

    @classmethod
    def from_entries(cls, entries: List[MemoryEntry]) -> "PartitionedMemoryRoot":
        groups: Dict[str, List[str]] = {}
        for e in entries:
            mc = e.memory_class.value
            groups.setdefault(mc, []).append(e.entry_hash())

        class_roots: Dict[str, str] = {}
        for mc, hashes in sorted(groups.items()):
            class_roots[mc] = hashlib.sha256("\n".join(hashes).encode()).hexdigest()

        return cls(
            class_roots=class_roots,
            total_entries=len(entries),
            entry_ids=[e.entry_id for e in entries],
        )

    @property
    def root_hash(self) -> str:
        canonical = "\n".join(
            f"{k}|{v}" for k, v in sorted(self.class_roots.items())
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def to_dict(self) -> dict:
        return {
            "class_roots": self.class_roots,
            "total_entries": self.total_entries,
            "root_hash": self.root_hash,
            "entry_ids": self.entry_ids,
        }


class PartitionedMemoryStore:
    """Partitioned memory store backed by real ContentStore.

    All content goes through ContentStore.put_file / put_bytes for
    real on-disk SHA-256 content addressing. Entries are additionally
    tagged with a memory class and tracked in an index file.
    """

    INDEX_FILENAME = "memory_index.jsonl"

    def __init__(self, store: ContentStore):
        self.store = store
        self._entries: Dict[str, MemoryEntry] = {}
        self._index_path = Path(store.root) / self.INDEX_FILENAME
        self._load_index()

    def _load_index(self):
        if not self._index_path.exists():
            return
        for line in self._index_path.read_text().splitlines():
            if not line.strip():
                continue
            entry = MemoryEntry.from_dict(json.loads(line))
            self._entries[entry.entry_id] = entry

    def _append_index(self, entry: MemoryEntry):
        with open(self._index_path, "a") as f:
            f.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")

    def put_bytes(
        self,
        data: bytes,
        memory_class: MemoryClass,
        provenance: Optional[Dict] = None,
    ) -> MemoryEntry:
        content_hash = self.store.put_bytes(data)
        entry = MemoryEntry(
            entry_id=uuid.uuid4().hex,
            memory_class=memory_class,
            content_hash=content_hash,
            size=len(data),
            provenance=provenance or {},
        )
        self._entries[entry.entry_id] = entry
        self._append_index(entry)
        return entry

    def put_file(
        self,
        src: Path,
        memory_class: MemoryClass,
        provenance: Optional[Dict] = None,
    ) -> MemoryEntry:
        content_hash = self.store.put_file(src)
        st = src.stat()
        entry = MemoryEntry(
            entry_id=uuid.uuid4().hex,
            memory_class=memory_class,
            content_hash=content_hash,
            rel_path=str(src),
            size=st.st_size,
            provenance=provenance or {},
        )
        self._entries[entry.entry_id] = entry
        self._append_index(entry)
        return entry

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        return self._entries.get(entry_id)

    def get_content(self, entry_id: str) -> Optional[bytes]:
        entry = self._entries.get(entry_id)
        if not entry:
            return None
        return self.store.get(entry.content_hash)

    def by_class(self, mc: MemoryClass) -> List[MemoryEntry]:
        return [e for e in self._entries.values() if e.memory_class == mc]

    def all_entries(self) -> List[MemoryEntry]:
        return list(self._entries.values())

    def compute_root(self) -> PartitionedMemoryRoot:
        return PartitionedMemoryRoot.from_entries(self.all_entries())

    def identity_critical_root(self) -> str:
        """Hash over only identity-critical entries.

        This is what goes into the IdentityRecord as objective_root_hash
        when objectives are stored as identity_critical memory.
        """
        entries = self.by_class(MemoryClass.IDENTITY_CRITICAL)
        if not entries:
            return hashlib.sha256(b"").hexdigest()
        hashes = [e.entry_hash() for e in entries]
        return hashlib.sha256("\n".join(hashes).encode()).hexdigest()
