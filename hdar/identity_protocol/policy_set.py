"""PolicySet — explicit policy object governing identity advancement.

Makes the implicit policies in ContinuityLoop explicit and hashable.
The policy hash enters the IdentityRecord, so any policy change is
cryptographically detectable in the lineage.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class ForkPolicyType(Enum):
    SINGLE_WRITER = "single_writer"
    CONSENSUS = "consensus"
    FORK_AND_MERGE = "fork_and_merge"


def _canonicalize(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


@dataclass
class PolicySet:
    """Active policies governing identity advancement.

    Includes fork resolution policy, quiescence requirements,
    capability attenuation rules, and consensus parameters.
    """
    fork_policy: ForkPolicyType = ForkPolicyType.SINGLE_WRITER
    quiescence_required: bool = True
    capability_attenuation: bool = True
    max_concurrent_writers: int = 1
    consensus_threshold: int = 1
    consensus_parties: list = field(default_factory=list)
    custom_rules: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "fork_policy": self.fork_policy.value,
            "quiescence_required": self.quiescence_required,
            "capability_attenuation": self.capability_attenuation,
            "max_concurrent_writers": self.max_concurrent_writers,
            "consensus_threshold": self.consensus_threshold,
            "consensus_parties": self.consensus_parties,
            "custom_rules": self.custom_rules,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PolicySet":
        return cls(
            fork_policy=ForkPolicyType(d.get("fork_policy", "single_writer")),
            quiescence_required=d.get("quiescence_required", True),
            capability_attenuation=d.get("capability_attenuation", True),
            max_concurrent_writers=d.get("max_concurrent_writers", 1),
            consensus_threshold=d.get("consensus_threshold", 1),
            consensus_parties=d.get("consensus_parties", []),
            custom_rules=d.get("custom_rules", {}),
        )

    def root_hash(self) -> str:
        return hashlib.sha256(_canonicalize(self.to_dict())).hexdigest()
