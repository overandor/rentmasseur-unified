"""Model-addressed mailboxes with explicit execution fidelity.

A mailbox is a capsule addressed to a specific model (by ID + digest).
The mailbox has an owner-selected fidelity level that stays stable until the
lease expires atomically. Time never silently changes the execution contract.

When a host receives a mailbox, it checks:
  1. Can I run the addressed model? (self-model query)
  2. What fidelity level is the mailbox at?
  3. Can I accept it at that fidelity?

Reduced fidelity is allowed only when the owner selected it in the capsule
manifest. An old capsule never silently runs with a substitute model.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from machine.selectors import MachineRegistry, MachineCandidate


class FidelityLevel(Enum):
    FULL = "full"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    EXPIRED = "expired"

    @classmethod
    def from_string(cls, s: str) -> "FidelityLevel":
        try:
            return cls(s)
        except ValueError:
            return cls.EXPIRED

    def can_execute(self) -> bool:
        return self in (FidelityLevel.FULL, FidelityLevel.DEGRADED, FidelityLevel.MINIMAL)

    def allows_capabilities(self) -> bool:
        return self in (FidelityLevel.FULL, FidelityLevel.DEGRADED)

    def allows_network(self) -> bool:
        return self == FidelityLevel.FULL


@dataclass
class ModelRequirement:
    """What model the capsule needs to run."""
    model_id: str
    model_digest: str = ""
    tokenizer_id: str = ""
    tokenizer_digest: str = ""
    min_ram_bytes: int = 0
    cpu_arch: str = "any"
    accelerator_pref: str = ""
    runtime_version: str = ""
    required_tools: List[str] = field(default_factory=list)
    acceptable_substitutes: List[str] = field(default_factory=list)
    degradation_policy: str = "refuse"

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "model_digest": self.model_digest,
            "tokenizer_id": self.tokenizer_id,
            "tokenizer_digest": self.tokenizer_digest,
            "min_ram_bytes": self.min_ram_bytes,
            "cpu_arch": self.cpu_arch,
            "accelerator_pref": self.accelerator_pref,
            "runtime_version": self.runtime_version,
            "required_tools": self.required_tools,
            "acceptable_substitutes": self.acceptable_substitutes,
            "degradation_policy": self.degradation_policy,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModelRequirement":
        return cls(
            model_id=d.get("model_id", ""),
            model_digest=d.get("model_digest", ""),
            tokenizer_id=d.get("tokenizer_id", ""),
            tokenizer_digest=d.get("tokenizer_digest", ""),
            min_ram_bytes=d.get("min_ram_bytes", 0),
            cpu_arch=d.get("cpu_arch", "any"),
            accelerator_pref=d.get("accelerator_pref", ""),
            runtime_version=d.get("runtime_version", ""),
            required_tools=d.get("required_tools", []),
            acceptable_substitutes=d.get("acceptable_substitutes", []),
            degradation_policy=d.get("degradation_policy", "refuse"),
        )


@dataclass
class Mailbox:
    """A model-addressed capsule mailbox with explicit fidelity and TTL."""
    mailbox_id: str
    capsule_hash: str
    addressed_model: ModelRequirement
    fidelity: FidelityLevel = FidelityLevel.FULL
    sealed_at: float = 0.0
    ttl_seconds: float = 86400.0
    decay_at_seconds: Dict[str, float] = field(default_factory=dict)  # legacy input; ignored
    accepted_at: float = 0.0
    accepted_by: str = ""
    acceptance_fidelity: FidelityLevel = FidelityLevel.FULL
    model_substitute_used: str = ""

    def current_fidelity(self, now: Optional[float] = None) -> FidelityLevel:
        if self.sealed_at == 0:
            return FidelityLevel.EXPIRED
        now = time.time() if now is None else now
        age = now - self.sealed_at

        if age >= self.ttl_seconds:
            return FidelityLevel.EXPIRED
        return self.fidelity

    def to_dict(self) -> dict:
        return {
            "mailbox_id": self.mailbox_id,
            "capsule_hash": self.capsule_hash,
            "addressed_model": self.addressed_model.to_dict(),
            "fidelity": self.fidelity.value,
            "sealed_at": self.sealed_at,
            "ttl_seconds": self.ttl_seconds,
            "decay_at_seconds": self.decay_at_seconds,
            "accepted_at": self.accepted_at,
            "accepted_by": self.accepted_by,
            "acceptance_fidelity": self.acceptance_fidelity.value,
            "model_substitute_used": self.model_substitute_used,
        }


class MailboxRouter:
    """Routes model-addressed mailboxes to compatible machines."""

    def __init__(self, registry: MachineRegistry):
        self.registry = registry

    def route(
        self,
        mailbox: Mailbox,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Attempt to route a mailbox to a compatible machine."""
        now = now or time.time()
        fidelity = mailbox.current_fidelity(now)

        if not fidelity.can_execute():
            return {
                "accepted": False,
                "hostname": "",
                "fidelity": fidelity.value,
                "model_used": "",
                "reasons": [f"mailbox expired (fidelity={fidelity.value})"],
                "candidate": None,
            }

        req = mailbox.addressed_model

        requirements = {
            "model_id": req.model_id,
            "model_digest": req.model_digest,
            "min_ram_bytes": req.min_ram_bytes,
            "cpu_arch": req.cpu_arch,
            "accelerator_pref": req.accelerator_pref,
            "required_tools": req.required_tools,
        }

        candidate = self.registry.select_best(requirements)
        if candidate:
            return {
                "accepted": True,
                "hostname": candidate.hostname,
                "fidelity": fidelity.value,
                "model_used": req.model_id,
                "reasons": [],
                "candidate": candidate.to_dict(),
            }

        if fidelity in (FidelityLevel.DEGRADED, FidelityLevel.MINIMAL):
            for sub in req.acceptable_substitutes:
                sub_reqs = dict(requirements)
                sub_reqs["model_id"] = sub
                sub_reqs["model_digest"] = ""
                candidate = self.registry.select_best(sub_reqs)
                if candidate:
                    return {
                        "accepted": True,
                        "hostname": candidate.hostname,
                        "fidelity": fidelity.value,
                        "model_used": sub,
                        "reasons": [f"model substituted: {req.model_id} -> {sub}"],
                        "candidate": candidate.to_dict(),
                    }

        reasons = [f"no machine satisfies model requirements for {req.model_id}"]
        if req.degradation_policy == "refuse":
            reasons.append("degradation policy is 'refuse' - no substitute attempted")
        else:
            reasons.append(f"no substitutes available from: {req.acceptable_substitutes}")

        return {
            "accepted": False,
            "hostname": "",
            "fidelity": fidelity.value,
            "model_used": "",
            "reasons": reasons,
            "candidate": None,
        }

    def accept(
        self,
        mailbox: Mailbox,
        hostname: str,
        model_used: str,
        fidelity: FidelityLevel,
    ) -> Mailbox:
        """Record acceptance of a mailbox by a host."""
        mailbox.accepted_at = time.time()
        mailbox.accepted_by = hostname
        mailbox.acceptance_fidelity = fidelity
        mailbox.model_substitute_used = (
            model_used if model_used != mailbox.addressed_model.model_id else ""
        )
        return mailbox
