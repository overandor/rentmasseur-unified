"""Distributed lease interface — abstract + SQLite implementation with advisory locks.

Provides:
  - DistributedLeaseManager: abstract interface for multi-host lease coordination
  - SQLiteLeaseManager: enhanced SQLite impl with WAL mode + busy timeout
  - LeaseBackend: abstract storage backend (SQLite now, etcd/Postgres later)

The existing lifecycle/lease.py LeaseManager remains for backward compatibility.
This module provides the interface for distributed deployment.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LeaseRecord:
    """A lease record with full metadata."""
    lease_id: str
    agent_id: str
    holder_id: str
    capsule_hash: str
    epoch: int
    lease_generation: int
    fencing_token: str
    status: str  # active, released, expired
    acquired_at: float
    expires_at: float
    released_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "lease_id": self.lease_id,
            "agent_id": self.agent_id,
            "holder_id": self.holder_id,
            "capsule_hash": self.capsule_hash,
            "epoch": self.epoch,
            "lease_generation": self.lease_generation,
            "fencing_token": self.fencing_token,
            "status": self.status,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "released_at": self.released_at,
        }


class LeaseBackend(ABC):
    """Abstract storage backend for lease coordination."""

    @abstractmethod
    def acquire(
        self,
        agent_id: str,
        capsule_hash: str,
        epoch: int,
        holder_id: str,
        ttl_seconds: int,
    ) -> Tuple[Optional[LeaseRecord], Optional[str]]:
        """Atomically acquire a lease. Returns (record, error)."""
        pass

    @abstractmethod
    def release(self, agent_id: str, fencing_token: str) -> bool:
        """Release a lease."""
        pass

    @abstractmethod
    def validate(self, agent_id: str, fencing_token: str) -> bool:
        """Check if a fencing token is valid."""
        pass

    @abstractmethod
    def get_active(self, agent_id: str) -> Optional[LeaseRecord]:
        """Get the active lease for an agent."""
        pass

    @abstractmethod
    def get_generation(self, agent_id: str) -> int:
        """Get the current lease generation for an agent."""
        pass

    @abstractmethod
    def expire_stale(self) -> int:
        """Expire leases past their TTL. Returns count expired."""
        pass


class SQLiteLeaseBackend(LeaseBackend):
    """SQLite backend with WAL mode and busy timeout for concurrent access.

    Suitable for single-node or shared-file-system multi-process deployment.
    For true multi-host deployment, use etcd or Postgres backend.
    """

    def __init__(self, db_path: str, default_ttl: int = 900):
        self.db_path = db_path
        self.default_ttl = default_ttl
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leases (
                lease_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                holder_id TEXT NOT NULL,
                capsule_hash TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                lease_generation INTEGER NOT NULL,
                fencing_token TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'active',
                acquired_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                released_at REAL DEFAULT 0,
                UNIQUE(agent_id, status)
            );
            CREATE INDEX IF NOT EXISTS idx_leases_agent ON leases(agent_id, status);
            CREATE INDEX IF NOT EXISTS idx_leases_token ON leases(fencing_token);
        """)
        conn.commit()
        conn.close()

    def acquire(
        self,
        agent_id: str,
        capsule_hash: str,
        epoch: int,
        holder_id: str,
        ttl_seconds: int = 0,
    ) -> Tuple[Optional[LeaseRecord], Optional[str]]:
        ttl = ttl_seconds or self.default_ttl
        conn = self._conn()
        try:
            # Expire stale leases first
            conn.execute(
                "UPDATE leases SET status='expired' WHERE status='active' AND expires_at < ?",
                (time.time(),)
            )

            # Check for existing active lease
            row = conn.execute(
                "SELECT lease_id FROM leases WHERE agent_id=? AND status='active'",
                (agent_id,)
            ).fetchone()

            if row:
                conn.close()
                return None, f"active lease exists for agent {agent_id}"

            # Get next generation
            gen_row = conn.execute(
                "SELECT MAX(lease_generation) FROM leases WHERE agent_id=?",
                (agent_id,)
            ).fetchone()
            next_gen = (gen_row[0] or 0) + 1

            lease_id = uuid.uuid4().hex
            fencing_token = f"{agent_id}:{next_gen}:{uuid.uuid4().hex[:16]}"
            now = time.time()

            conn.execute(
                """INSERT INTO leases
                   (lease_id, agent_id, holder_id, capsule_hash, epoch,
                    lease_generation, fencing_token, status, acquired_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
                (lease_id, agent_id, holder_id, capsule_hash, epoch,
                 next_gen, fencing_token, now, now + ttl)
            )
            conn.commit()

            return LeaseRecord(
                lease_id=lease_id, agent_id=agent_id, holder_id=holder_id,
                capsule_hash=capsule_hash, epoch=epoch,
                lease_generation=next_gen, fencing_token=fencing_token,
                status="active", acquired_at=now, expires_at=now + ttl,
            ), None
        except sqlite3.IntegrityError as e:
            return None, f"lease conflict: {e}"
        finally:
            conn.close()

    def release(self, agent_id: str, fencing_token: str) -> bool:
        conn = self._conn()
        try:
            cursor = conn.execute(
                "UPDATE leases SET status='released', released_at=? "
                "WHERE agent_id=? AND fencing_token=? AND status='active'",
                (time.time(), agent_id, fencing_token)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def validate(self, agent_id: str, fencing_token: str) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT expires_at FROM leases "
                "WHERE agent_id=? AND fencing_token=? AND status='active'",
                (agent_id, fencing_token)
            ).fetchone()
            if not row:
                return False
            return time.time() < row[0]
        finally:
            conn.close()

    def get_active(self, agent_id: str) -> Optional[LeaseRecord]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM leases WHERE agent_id=? AND status='active'",
                (agent_id,)
            ).fetchone()
            if not row:
                return None
            return LeaseRecord(
                lease_id=row[0], agent_id=row[1], holder_id=row[2],
                capsule_hash=row[3], epoch=row[4], lease_generation=row[5],
                fencing_token=row[6], status=row[7], acquired_at=row[8],
                expires_at=row[9], released_at=row[10],
            )
        finally:
            conn.close()

    def get_generation(self, agent_id: str) -> int:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT MAX(lease_generation) FROM leases WHERE agent_id=?",
                (agent_id,)
            ).fetchone()
            return row[0] or 0
        finally:
            conn.close()

    def expire_stale(self) -> int:
        conn = self._conn()
        try:
            cursor = conn.execute(
                "UPDATE leases SET status='expired' "
                "WHERE status='active' AND expires_at < ?",
                (time.time(),)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


class DistributedLeaseManager:
    """Distributed lease manager wrapping a backend.

    Drop-in compatible with the existing LeaseManager interface.
    """

    def __init__(self, backend: LeaseBackend):
        self.backend = backend

    def acquire(
        self,
        agent_id: str,
        capsule_hash: str,
        epoch: int,
        holder_id: str,
        status: str = "pending",
        ttl: int = 900,
    ) -> Tuple[Optional[LeaseRecord], Optional[str]]:
        return self.backend.acquire(agent_id, capsule_hash, epoch, holder_id, ttl)

    def release(self, agent_id: str, fencing_token: str) -> bool:
        return self.backend.release(agent_id, fencing_token)

    def validate_token(self, agent_id: str, fencing_token: str) -> bool:
        return self.backend.validate(agent_id, fencing_token)

    def get_generation(self, agent_id: str) -> int:
        return self.backend.get_generation(agent_id)

    def expire_stale(self) -> int:
        return self.backend.expire_stale()
