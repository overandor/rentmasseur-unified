"""Perception receipts.

Cryptographic receipts recording what the model was permitted to
perceive during execution. Unlike execution receipts that record
what the agent *did*, perception receipts record what the agent
*was allowed to see*:

  - Which files were readable and were accessed
  - Which network endpoints were visible
  - Which environment variables were exposed
  - What model fidelity was in effect
  - What capabilities were active during perception

Each perception receipt is signed by the host's ephemeral key and
enters the capsule's evidence chain. The owner can verify after
the fact exactly what the model was allowed to perceive, even if
the model didn't actually access all of it.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from machine.auth_gate import AuthorizationRecord, AuthorizationDecision
from machine.mailbox import FidelityLevel


@dataclass
class PerceptionEvent:
    """A single perception event — something the model was permitted to perceive."""
    perception_type: str  # "file.read", "env.var", "network.dns", "model.inference"
    resource: str         # path, variable name, endpoint, model ID
    permitted: bool       # was this perception permitted?
    fidelity: str = ""    # fidelity level at time of perception
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "perception_type": self.perception_type,
            "resource": self.resource,
            "permitted": self.permitted,
            "fidelity": self.fidelity,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class PerceptionReceipt:
    """Signed receipt for all perceptions during an execution session.

    The receipt records:
      - The complete set of perception events
      - The authorization records that governed them
      - The model that was used (may differ from addressed model)
      - The fidelity level throughout the session
      - A signed hash binding all of the above
    """
    session_id: str
    agent_id: str
    model_used: str = ""
    addressed_model: str = ""
    model_substituted: bool = False
    fidelity: str = ""
    perceptions: List[PerceptionEvent] = field(default_factory=list)
    authorizations: List[Dict[str, Any]] = field(default_factory=list)
    perception_count: int = 0
    permitted_count: int = 0
    denied_count: int = 0
    host_fingerprint: str = ""
    signed_at: float = 0.0
    receipt_hash: str = ""
    signature: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "model_used": self.model_used,
            "addressed_model": self.addressed_model,
            "model_substituted": self.model_substituted,
            "fidelity": self.fidelity,
            "perceptions": [p.to_dict() for p in self.perceptions],
            "authorizations": self.authorizations,
            "perception_count": self.perception_count,
            "permitted_count": self.permitted_count,
            "denied_count": self.denied_count,
            "host_fingerprint": self.host_fingerprint,
            "signed_at": self.signed_at,
            "receipt_hash": self.receipt_hash,
            "signature": self.signature,
        }

    def unsigned_canonical(self) -> bytes:
        d = self.to_dict()
        d.pop("signature", None)
        d.pop("receipt_hash", None)
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()

    def compute_hash(self) -> str:
        return hashlib.sha256(self.unsigned_canonical()).hexdigest()


class PerceptionLedger:
    """Accumulates perception events during an execution session.

    The ledger is the live record of what the model is permitted to
    perceive. At session end, it produces a signed PerceptionReceipt.

    Usage:
        ledger = PerceptionLedger(session_id, agent_id, model_used, fidelity)
        ledger.record_perception("file.read", "/workspace/data.txt", permitted=True)
        ledger.record_perception("env.var", "API_KEY", permitted=False)
        receipt = ledger.finalize(host_key)
    """

    def __init__(
        self,
        session_id: str,
        agent_id: str,
        model_used: str = "",
        addressed_model: str = "",
        fidelity: FidelityLevel = FidelityLevel.FULL,
    ):
        self.session_id = session_id
        self.agent_id = agent_id
        self.model_used = model_used
        self.addressed_model = addressed_model
        self.model_substituted = model_used != addressed_model if addressed_model else False
        self.fidelity = fidelity
        self.events: List[PerceptionEvent] = []
        self._auth_records: List[AuthorizationRecord] = []

    def record_perception(
        self,
        perception_type: str,
        resource: str,
        permitted: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PerceptionEvent:
        """Record a single perception event."""
        event = PerceptionEvent(
            perception_type=perception_type,
            resource=resource,
            permitted=permitted,
            fidelity=self.fidelity.value,
            timestamp=time.time(),
            metadata=metadata or {},
        )
        self.events.append(event)
        return event

    def record_authorization(self, record: AuthorizationRecord) -> None:
        """Link an authorization record to the perception ledger."""
        self._auth_records.append(record)

    def finalize(self, host_key) -> PerceptionReceipt:
        """Produce a signed perception receipt.

        Args:
            host_key: HostKeyPair for signing
        """
        permitted = sum(1 for e in self.events if e.permitted)
        denied = sum(1 for e in self.events if not e.permitted)

        receipt = PerceptionReceipt(
            session_id=self.session_id,
            agent_id=self.agent_id,
            model_used=self.model_used,
            addressed_model=self.addressed_model,
            model_substituted=self.model_substituted,
            fidelity=self.fidelity.value,
            perceptions=list(self.events),
            authorizations=[r.to_dict() for r in self._auth_records],
            perception_count=len(self.events),
            permitted_count=permitted,
            denied_count=denied,
            host_fingerprint=host_key.fingerprint,
            signed_at=time.time(),
        )

        receipt.receipt_hash = receipt.compute_hash()
        receipt.signature = host_key.sign_bytes(receipt.unsigned_canonical())

        return receipt

    def summary(self) -> Dict[str, Any]:
        """Live summary without finalizing."""
        permitted = sum(1 for e in self.events if e.permitted)
        denied = sum(1 for e in self.events if not e.permitted)
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "model_used": self.model_used,
            "fidelity": self.fidelity.value,
            "total_perceptions": len(self.events),
            "permitted": permitted,
            "denied": denied,
            "authorizations": len(self._auth_records),
        }
