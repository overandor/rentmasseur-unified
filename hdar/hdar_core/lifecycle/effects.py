"""Durable external-effect registry — P0 addition #2.

Tracks external operations through their real lifecycle to prevent
duplicate effects across migration. An agent is quiescent only when
no effect is in a blocking state.

Terminal states: committed, cancelled, proven_not_started
Blocking states: starting, submitted, unknown, reconciliation_failed
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

BLOCKING_STATES = {"starting", "submitted", "unknown", "reconciliation_failed"}
TERMINAL_STATES = {"committed", "cancelled", "proven_not_started"}


@dataclass
class ExternalEffect:
    operation_id: str
    intent_digest: str           # hash of the intended operation
    capability_used: str         # e.g. "payment", "email", "deploy"
    request_digest: str          # hash of the actual request payload
    status: str                  # starting | submitted | unknown | committed | cancelled | proven_not_started | reconciliation_failed
    provider_receipt: Optional[Dict[str, Any]] = None
    reconciliation_method: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    committed_at: Optional[float] = None

    def is_blocking(self) -> bool:
        return self.status in BLOCKING_STATES

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    def to_dict(self) -> dict:
        return {
            "operation_id": self.operation_id,
            "intent_digest": self.intent_digest,
            "capability_used": self.capability_used,
            "request_digest": self.request_digest,
            "status": self.status,
            "provider_receipt": self.provider_receipt,
            "reconciliation_method": self.reconciliation_method,
            "created_at": self.created_at,
            "committed_at": self.committed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExternalEffect":
        return cls(**{k: d.get(k) for k in [
            "operation_id", "intent_digest", "capability_used",
            "request_digest", "status", "provider_receipt",
            "reconciliation_method", "created_at", "committed_at",
        ]})


class EffectRegistry:
    """Durable append-only registry of external effects.

    Prevents restore from duplicating an email, payment, deployment,
    or API mutation. The registry is the foundation for semantic
    quiescence: an agent may seal only when no effect is blocking.

    When a lease_manager and agent_id are provided, all state-changing
    operations require a valid fencing token. A stale runtime cannot
    register or commit effects.
    """

    def __init__(self, ledger_path: str, lease_manager=None, agent_id: str = ""):
        self.ledger_path = ledger_path
        self.lease_manager = lease_manager
        self.agent_id = agent_id
        os.makedirs(os.path.dirname(ledger_path), exist_ok=True)

    def _check_fencing(self, fencing_token: str) -> None:
        """Raise if the fencing token is stale or missing."""
        if self.lease_manager and self.agent_id:
            if not fencing_token:
                raise ValueError("fencing token required but not provided")
            if not self.lease_manager.validate_token(self.agent_id, fencing_token):
                raise ValueError(
                    f"stale or invalid fencing token — "
                    f"this runtime's lease generation is no longer authoritative"
                )

    def _load(self) -> List[dict]:
        if not os.path.exists(self.ledger_path):
            return []
        return [json.loads(line) for line in open(self.ledger_path) if line.strip()]

    def _append(self, record: dict):
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    def _current(self, agent_id: str) -> Dict[str, ExternalEffect]:
        """Fold the append-only ledger into current state per operation_id."""
        cur: Dict[str, ExternalEffect] = {}
        for r in self._load():
            if r.get("agent") != agent_id:
                continue
            cur[r["operation_id"]] = ExternalEffect.from_dict(r)
        return cur

    def register(
        self,
        agent_id: str,
        capability_used: str,
        request_payload: bytes,
        operation_id: Optional[str] = None,
        fencing_token: str = "",
    ) -> ExternalEffect:
        """Register intent BEFORE executing. This is the whole trick.

        When lease validation is enabled, a valid fencing token is required.
        A stale runtime cannot register new effects.
        """
        self._check_fencing(fencing_token)
        import uuid
        op_id = operation_id or f"op-{uuid.uuid4().hex[:12]}"
        intent_digest = hashlib.sha256(request_payload).hexdigest()

        cur = self._current(agent_id)
        if op_id in cur and cur[op_id].status == "committed":
            return ExternalEffect(
                operation_id=op_id,
                intent_digest=intent_digest,
                capability_used=capability_used,
                request_digest=intent_digest,
                status="committed",
                committed_at=cur[op_id].committed_at,
            )

        effect = ExternalEffect(
            operation_id=op_id,
            intent_digest=intent_digest,
            capability_used=capability_used,
            request_digest=intent_digest,
            status="starting",
        )
        self._append({"agent": agent_id, **effect.to_dict()})
        return effect

    def submit(self, agent_id: str, operation_id: str,
               fencing_token: str = "") -> ExternalEffect:
        """Mark an effect as submitted to the provider.

        When lease validation is enabled, a valid fencing token is required.
        A stale runtime cannot submit effects.
        """
        self._check_fencing(fencing_token)
        return self._update(agent_id, operation_id, "submitted")

    def commit(self, agent_id: str, operation_id: str,
               provider_receipt: Optional[dict] = None,
               fencing_token: str = "") -> ExternalEffect:
        """Mark an effect as committed by the provider.

        When lease validation is enabled, a valid fencing token is required.
        A stale runtime cannot commit effects.
        """
        self._check_fencing(fencing_token)
        effect = self._update(agent_id, operation_id, "committed",
                              provider_receipt=provider_receipt,
                              committed_at=time.time())
        return effect

    def mark_unknown(self, agent_id: str, operation_id: str,
                     fencing_token: str = "") -> ExternalEffect:
        """Mark an effect as unknown (e.g. crash before confirmation).

        When lease validation is enabled, a valid fencing token is required.
        """
        self._check_fencing(fencing_token)
        return self._update(agent_id, operation_id, "unknown")

    def cancel(self, agent_id: str, operation_id: str,
              fencing_token: str = "") -> ExternalEffect:
        """Mark an effect as cancelled.

        When lease validation is enabled, a valid fencing token is required.
        """
        self._check_fencing(fencing_token)
        return self._update(agent_id, operation_id, "cancelled")

    def _update(self, agent_id: str, operation_id: str, status: str,
                **kwargs) -> ExternalEffect:
        cur = self._current(agent_id)
        if operation_id not in cur:
            raise ValueError(f"unknown operation_id: {operation_id}")
        existing = cur[operation_id]
        updated = ExternalEffect(
            operation_id=operation_id,
            intent_digest=existing.intent_digest,
            capability_used=existing.capability_used,
            request_digest=existing.request_digest,
            status=status,
            provider_receipt=kwargs.get("provider_receipt", existing.provider_receipt),
            reconciliation_method=kwargs.get("reconciliation_method", existing.reconciliation_method),
            created_at=existing.created_at,
            committed_at=kwargs.get("committed_at", existing.committed_at),
        )
        self._append({"agent": agent_id, **updated.to_dict()})
        return updated

    def check_quiescence(self, agent_id: str) -> dict:
        """Is the agent safe to seal? Returns the quiescence verdict."""
        cur = self._current(agent_id)
        blocking = [e for e in cur.values() if e.is_blocking()]
        return {
            "agent": agent_id,
            "quiescent": not blocking,
            "blocking_effects": [e.to_dict() for e in blocking],
            "verdict": "SAFE TO SEAL" if not blocking else
                       "REFUSE TO SEAL — external effects in flight",
            "effects_total": len(cur),
        }

    def reconcile(self, agent_id: str, probe_fn) -> dict:
        """On wake: resolve UNKNOWN effects before the agent may act.

        probe_fn(operation_id, effect) -> str: returns the real status
        from the provider ('committed', 'cancelled', or 'proven_not_started').
        """
        cur = self._current(agent_id)
        unknown = [e for e in cur.values() if e.status == "unknown"]
        results = []
        for e in unknown:
            truth = probe_fn(e.operation_id, e)
            if truth == "committed":
                self.commit(agent_id, e.operation_id)
            elif truth == "cancelled":
                self.cancel(agent_id, e.operation_id)
            elif truth == "proven_not_started":
                self._update(agent_id, e.operation_id, "proven_not_started")
            else:
                self._update(agent_id, e.operation_id, "reconciliation_failed",
                             reconciliation_method=probe_fn.__name__)
            results.append({
                "operation_id": e.operation_id,
                "capability_used": e.capability_used,
                "resolved_to": truth,
                "action": "do NOT re-execute" if truth == "committed" else
                          "safe to retry" if truth == "proven_not_started" else
                          "reconciliation failed — manual review required",
            })
        q = self.check_quiescence(agent_id)
        return {
            "agent": agent_id,
            "reconciled": len(results),
            "results": results,
            "now_quiescent": q["quiescent"],
        }

    def is_duplicate(self, agent_id: str, operation_id: str) -> bool:
        """Check if an operation was already committed."""
        cur = self._current(agent_id)
        return operation_id in cur and cur[operation_id].status == "committed"
