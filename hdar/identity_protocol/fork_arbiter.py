"""Fork detection and arbitration over real IdentityRecords.

When two hosts wake from the same memory and both continue independently,
the lineage forks:

             -> M2A
    M0 -> M1
             -> M2B

Both branches may be authentic descendants, but neither automatically
becomes canonical. Three policies are supported:

  - single_writer:  only one active lease may advance identity.
                     Forks indicate a lease violation.
  - consensus:      several authorized parties approve the next epoch.
  - fork_and_merge: branches remain explicit and are reconciled
                     through a signed merge epoch.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from hdar_core.crypto import sha256_hex, canonicalize

from .identity_record import IdentityRecord
from .policy_set import PolicySet, ForkPolicyType


@dataclass
class Fork:
    """A detected fork in the lineage."""
    parent_state_hash: str
    branches: List[IdentityRecord] = field(default_factory=list)
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "parent_state_hash": self.parent_state_hash,
            "branches": [b.to_dict() for b in self.branches],
            "detected_at": self.detected_at,
        }


@dataclass
class MergeRecord:
    """A signed merge of two or more forks into a single canonical epoch."""
    merge_epoch: int
    merged_branches: List[str] = field(default_factory=list)
    merge_policy: str = "fork_and_merge"
    merged_at: float = field(default_factory=time.time)
    merged_by: str = ""
    signature: str = ""
    merge_hash: str = ""

    def unsigned_canonical(self) -> bytes:
        return canonicalize({
            "merge_epoch": self.merge_epoch,
            "merged_branches": self.merged_branches,
            "merge_policy": self.merge_policy,
            "merged_at": self.merged_at,
            "merged_by": self.merged_by,
        })

    def compute_hash(self) -> str:
        return sha256_hex(self.unsigned_canonical() + self.signature.encode())

    def sign(self, owner_key) -> None:
        self.signature = owner_key.sign_bytes(self.unsigned_canonical())
        self.merge_hash = self.compute_hash()

    def to_dict(self) -> dict:
        return {
            "merge_epoch": self.merge_epoch,
            "merged_branches": self.merged_branches,
            "merge_policy": self.merge_policy,
            "merged_at": self.merged_at,
            "merged_by": self.merged_by,
            "signature": self.signature,
            "merge_hash": self.merge_hash,
        }


class ForkArbiter:
    """Detects forks and arbitrates canonical advancement.

    Uses the real PolicySet to determine resolution strategy.
    """

    def __init__(self, policy: PolicySet):
        self.policy = policy
        self._forks: List[Fork] = []
        self._merges: List[MergeRecord] = []

    def detect_fork(
        self, records: List[IdentityRecord]
    ) -> Optional[Fork]:
        """Check if the latest records constitute a fork.

        A fork exists when two or more records share the same
        parent_state_hash but have different state_hashes.
        """
        by_parent: dict = {}
        for r in records:
            by_parent.setdefault(r.parent_state_hash or "", []).append(r)

        for parent_hash, branches in by_parent.items():
            if len(branches) > 1:
                state_hashes = {b.state_hash for b in branches}
                if len(state_hashes) > 1:
                    fork = Fork(
                        parent_state_hash=parent_hash,
                        branches=branches,
                    )
                    self._forks.append(fork)
                    return fork

        return None

    def arbitrate(
        self,
        fork: Fork,
        approvals: Optional[List[str]] = None,
        owner_key=None,
    ) -> Tuple[Optional[IdentityRecord], Optional[MergeRecord]]:
        """Arbitrate a fork according to the active policy.

        Returns (canonical_record, merge_record) if resolved,
        or (None, None) if the fork cannot be resolved yet.
        """
        if self.policy.fork_policy == ForkPolicyType.SINGLE_WRITER:
            raise ValueError(
                "FORK DETECTED under single_writer policy — "
                "this indicates a lease violation. Only one writer "
                "may advance identity at a time."
            )

        if self.policy.fork_policy == ForkPolicyType.CONSENSUS:
            if approvals is None:
                return None, None

            approved_branches = [
                b for b in fork.branches
                if any(a in self.policy.consensus_parties for a in approvals)
            ]

            if len(approvals) >= self.policy.consensus_threshold and approved_branches:
                return approved_branches[0], None
            return None, None

        if self.policy.fork_policy == ForkPolicyType.FORK_AND_MERGE:
            if owner_key is None:
                return None, None

            max_epoch = max(b.epoch for b in fork.branches)
            merge = MergeRecord(
                merge_epoch=max_epoch + 1,
                merged_branches=[b.state_hash for b in fork.branches],
                merge_policy="fork_and_merge",
                merged_by=owner_key.fingerprint,
            )
            merge.sign(owner_key)
            self._merges.append(merge)

            return None, merge

        return None, None

    @property
    def forks(self) -> List[Fork]:
        return list(self._forks)

    @property
    def merges(self) -> List[MergeRecord]:
        return list(self._merges)
