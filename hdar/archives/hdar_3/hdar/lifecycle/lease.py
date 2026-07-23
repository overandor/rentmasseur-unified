"""Atomic fenced wake lease — P0 addition #3.

Closes the difference between migration and cloning. At most one
lease generation may advance the authoritative agent state.

Uses SQLite for atomic compare-and-swap semantics. Every state-changing
operation must present the latest fencing token. A stale runtime may
remain physically alive briefly, but cannot publish a capsule, consume
secrets, commit effects, or advance the authoritative lineage.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_LEASE_TTL = 900  # 15 minutes


@dataclass
class Lease:
    agent_id: str
    capsule_hash: str
    epoch: int
    lease_generation: int
    holder_id: str
    destination_runtime: str
    fencing_token: str
    issued_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "capsule_hash": self.capsule_hash,
            "epoch": self.epoch,
            "lease_generation": self.lease_generation,
            "holder_id": self.holder_id,
            "destination_runtime": self.destination_runtime,
            "fencing_token": self.fencing_token,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }


class LeaseManager:
    """SQLite-backed atomic wake lease manager.

    The core invariant: at most one lease generation may advance
    the authoritative agent state. This is enforced through
    atomic compare-and-swap in SQLite transactions.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS leases (
        agent_id TEXT PRIMARY KEY,
        capsule_hash TEXT NOT NULL,
        epoch INTEGER NOT NULL,
        lease_generation INTEGER NOT NULL,
        holder_id TEXT NOT NULL,
        destination_runtime TEXT NOT NULL,
        fencing_token TEXT NOT NULL,
        issued_at REAL NOT NULL,
        expires_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS lease_history (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL,
        lease_generation INTEGER NOT NULL,
        holder_id TEXT NOT NULL,
        action TEXT NOT NULL,
        fencing_token TEXT,
        timestamp REAL NOT NULL
    );
    """

    def __init__(self, db_path: str, ttl: int = DEFAULT_LEASE_TTL):
        self.db_path = db_path
        self.ttl = ttl
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.executescript(self.SCHEMA)
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def acquire(self, agent_id: str, capsule_hash: str, epoch: int,
                holder_id: str, destination_runtime: str) -> tuple[Optional[Lease], Optional[str]]:
        """Atomically acquire an exclusive wake lease.

        Returns (lease, None) on success, (None, error_message) on failure.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM leases WHERE agent_id = ?", (agent_id,)
            ).fetchone()

            # Always check history for max generation so it keeps incrementing
            hist_row = conn.execute(
                "SELECT MAX(lease_generation) as max_gen FROM lease_history WHERE agent_id = ?",
                (agent_id,)
            ).fetchone()
            max_hist_gen = hist_row["max_gen"] if hist_row and hist_row["max_gen"] else 0

            if row is not None:
                existing = Lease(
                    agent_id=row["agent_id"],
                    capsule_hash=row["capsule_hash"],
                    epoch=row["epoch"],
                    lease_generation=row["lease_generation"],
                    holder_id=row["holder_id"],
                    destination_runtime=row["destination_runtime"],
                    fencing_token=row["fencing_token"],
                    issued_at=row["issued_at"],
                    expires_at=row["expires_at"],
                )
                if not existing.is_expired():
                    remaining = int(existing.expires_at - time.time())
                    conn.rollback()
                    return None, (
                        f"lease held by '{existing.holder_id}' "
                        f"gen={existing.lease_generation} for {remaining}s"
                    )
                # expired — reclaim
                gen = max(existing.lease_generation, max_hist_gen) + 1
            else:
                gen = max_hist_gen + 1

            fencing_token = uuid.uuid4().hex
            now = time.time()
            expires = now + self.ttl

            conn.execute(
                "INSERT OR REPLACE INTO leases "
                "(agent_id, capsule_hash, epoch, lease_generation, "
                "holder_id, destination_runtime, fencing_token, "
                "issued_at, expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (agent_id, capsule_hash, epoch, gen, holder_id,
                 destination_runtime, fencing_token, now, expires)
            )
            conn.execute(
                "INSERT INTO lease_history "
                "(agent_id, lease_generation, holder_id, action, fencing_token, timestamp) "
                "VALUES (?,?,?,?,?,?)",
                (agent_id, gen, holder_id, "acquire", fencing_token, now)
            )
            conn.commit()

            return Lease(
                agent_id=agent_id,
                capsule_hash=capsule_hash,
                epoch=epoch,
                lease_generation=gen,
                holder_id=holder_id,
                destination_runtime=destination_runtime,
                fencing_token=fencing_token,
                issued_at=now,
                expires_at=expires,
            ), None
        except Exception as e:
            conn.rollback()
            return None, str(e)
        finally:
            conn.close()

    def release(self, agent_id: str, fencing_token: str) -> bool:
        """Release a lease. Must present the correct fencing token."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM leases WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if row is None:
                conn.rollback()
                return False
            if row["fencing_token"] != fencing_token:
                conn.rollback()
                return False
            conn.execute("DELETE FROM leases WHERE agent_id = ?", (agent_id,))
            conn.execute(
                "INSERT INTO lease_history "
                "(agent_id, lease_generation, holder_id, action, fencing_token, timestamp) "
                "VALUES (?,?,?,?,?,?)",
                (agent_id, row["lease_generation"], row["holder_id"],
                 "release", fencing_token, time.time())
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def validate_token(self, agent_id: str, fencing_token: str) -> bool:
        """Check if a fencing token is the current valid one."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT fencing_token, expires_at FROM leases WHERE agent_id = ?",
                (agent_id,)
            ).fetchone()
            if row is None:
                return False
            if time.time() > row["expires_at"]:
                return False
            return row["fencing_token"] == fencing_token
        finally:
            conn.close()

    def get_current(self, agent_id: str) -> Optional[Lease]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM leases WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if row is None:
                return None
            return Lease(
                agent_id=row["agent_id"],
                capsule_hash=row["capsule_hash"],
                epoch=row["epoch"],
                lease_generation=row["lease_generation"],
                holder_id=row["holder_id"],
                destination_runtime=row["destination_runtime"],
                fencing_token=row["fencing_token"],
                issued_at=row["issued_at"],
                expires_at=row["expires_at"],
            )
        finally:
            conn.close()

    def reject_stale(self, agent_id: str, stale_token: str) -> bool:
        """Verify that a stale token is rejected."""
        return not self.validate_token(agent_id, stale_token)
