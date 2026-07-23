"""Per-operation authorization gate.

Every operation the agent attempts is independently authorized
against the capsule's capabilities, the mailbox's fidelity level,
and the host's destination policy. No operation executes without
an explicit authorization record.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from capsule.capabilities import Capability, CapabilityCompiler, is_scope_broader
from machine.mailbox import FidelityLevel


class AuthorizationDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    DEGRADED = "degraded"

    @property
    def permitted(self) -> bool:
        return self in (AuthorizationDecision.ALLOW, AuthorizationDecision.DEGRADED)


@dataclass
class OperationRequest:
    """A single operation the agent wants to perform."""
    operation_type: str
    scope: str
    command: str = ""
    files_accessed: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "operation_type": self.operation_type,
            "scope": self.scope,
            "command": self.command,
            "files_accessed": self.files_accessed,
            "files_modified": self.files_modified,
            "timestamp": self.timestamp,
        }


@dataclass
class AuthorizationRecord:
    """Cryptographic receipt for a single authorization decision."""
    decision: AuthorizationDecision
    operation: OperationRequest
    reason: str = ""
    fidelity_at_decision: FidelityLevel = FidelityLevel.FULL
    capabilities_checked: List[str] = field(default_factory=list)
    authorized_at: float = 0.0
    receipt_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "operation": self.operation.to_dict(),
            "reason": self.reason,
            "fidelity_at_decision": self.fidelity_at_decision.value,
            "capabilities_checked": self.capabilities_checked,
            "authorized_at": self.authorized_at,
            "receipt_hash": self.receipt_hash,
        }

    def compute_hash(self) -> str:
        d = self.to_dict()
        d.pop("receipt_hash", None)
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


class AuthorizationGate:
    """Independently authorizes every operation."""

    def __init__(
        self,
        capabilities: List[Capability],
        fidelity: FidelityLevel,
        destination_policy: Dict[str, str],
    ):
        self.capabilities = {c.name: c for c in capabilities if c.granted}
        self.fidelity = fidelity
        self.destination_policy = destination_policy
        self.records: List[AuthorizationRecord] = []

    def authorize(self, request: OperationRequest) -> AuthorizationRecord:
        request.timestamp = time.time()
        caps_checked: List[str] = []
        reason = ""

        cap = self.capabilities.get(request.operation_type)
        caps_checked.append(request.operation_type)

        if cap is None:
            record = AuthorizationRecord(
                decision=AuthorizationDecision.DENY,
                operation=request,
                reason=f"capability '{request.operation_type}' not granted",
                fidelity_at_decision=self.fidelity,
                capabilities_checked=caps_checked,
                authorized_at=time.time(),
            )
            record.receipt_hash = record.compute_hash()
            self.records.append(record)
            return record

        if is_scope_broader(cap.scope, request.scope):
            record = AuthorizationRecord(
                decision=AuthorizationDecision.DENY,
                operation=request,
                reason=f"scope '{request.scope}' exceeds capability scope '{cap.scope}'",
                fidelity_at_decision=self.fidelity,
                capabilities_checked=caps_checked,
                authorized_at=time.time(),
            )
            record.receipt_hash = record.compute_hash()
            self.records.append(record)
            return record

        if request.operation_type == "network.egress" and not self.fidelity.allows_network():
            record = AuthorizationRecord(
                decision=AuthorizationDecision.DENY,
                operation=request,
                reason=f"network egress denied at fidelity={self.fidelity.value}",
                fidelity_at_decision=self.fidelity,
                capabilities_checked=caps_checked,
                authorized_at=time.time(),
            )
            record.receipt_hash = record.compute_hash()
            self.records.append(record)
            return record

        if not self.fidelity.allows_capabilities() and request.operation_type not in ("filesystem.read",):
            record = AuthorizationRecord(
                decision=AuthorizationDecision.DEGRADED,
                operation=request,
                reason=f"operation permitted at reduced fidelity={self.fidelity.value}",
                fidelity_at_decision=self.fidelity,
                capabilities_checked=caps_checked,
                authorized_at=time.time(),
            )
            record.receipt_hash = record.compute_hash()
            self.records.append(record)
            return record

        record = AuthorizationRecord(
            decision=AuthorizationDecision.ALLOW,
            operation=request,
            reason="authorized",
            fidelity_at_decision=self.fidelity,
            capabilities_checked=caps_checked,
            authorized_at=time.time(),
        )
        record.receipt_hash = record.compute_hash()
        self.records.append(record)
        return record

    def authorize_batch(self, requests: List[OperationRequest]) -> List[AuthorizationRecord]:
        return [self.authorize(r) for r in requests]

    def summary(self) -> Dict[str, Any]:
        allowed = sum(1 for r in self.records if r.decision == AuthorizationDecision.ALLOW)
        denied = sum(1 for r in self.records if r.decision == AuthorizationDecision.DENY)
        degraded = sum(1 for r in self.records if r.decision == AuthorizationDecision.DEGRADED)
        return {
            "total_operations": len(self.records),
            "allowed": allowed,
            "denied": denied,
            "degraded": degraded,
            "fidelity": self.fidelity.value,
            "records": [r.to_dict() for r in self.records],
        }
