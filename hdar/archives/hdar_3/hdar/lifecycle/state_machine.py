"""Lifecycle state machine — P0 addition #1.

One authoritative state machine governing capsule lifecycle transitions.
A capsule may seal only after the state machine confirms quiescence and
effect reconciliation.

States:
    DORMANT → ACQUIRING_LEASE → MATERIALIZING → VERIFYING_INPUT
    → RUNNING → QUIESCING → SEALING → DESTROYING → DORMANT

Failure states:
    QUARANTINED, DEGRADED, UNKNOWN_EFFECT, LEASE_LOST,
    RESTORE_REJECTED, DESTRUCTION_UNCONFIRMED
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional


class AgentState(Enum):
    DORMANT = auto()
    ACQUIRING_LEASE = auto()
    MATERIALIZING = auto()
    VERIFYING_INPUT = auto()
    RUNNING = auto()
    QUIESCING = auto()
    SEALING = auto()
    DESTROYING = auto()
    # failure states
    QUARANTINED = auto()
    DEGRADED = auto()
    UNKNOWN_EFFECT = auto()
    LEASE_LOST = auto()
    RESTORE_REJECTED = auto()
    DESTRUCTION_UNCONFIRMED = auto()


# Valid forward transitions
TRANSITIONS: Dict[AgentState, List[AgentState]] = {
    AgentState.DORMANT: [AgentState.ACQUIRING_LEASE],
    AgentState.ACQUIRING_LEASE: [AgentState.MATERIALIZING, AgentState.LEASE_LOST, AgentState.DORMANT],
    AgentState.MATERIALIZING: [AgentState.VERIFYING_INPUT, AgentState.RESTORE_REJECTED, AgentState.QUARANTINED],
    AgentState.VERIFYING_INPUT: [AgentState.RUNNING, AgentState.RESTORE_REJECTED, AgentState.QUARANTINED],
    AgentState.RUNNING: [AgentState.QUIESCING, AgentState.UNKNOWN_EFFECT, AgentState.LEASE_LOST, AgentState.QUARANTINED],
    AgentState.QUIESCING: [AgentState.SEALED if False else AgentState.SEALING, AgentState.UNKNOWN_EFFECT],
    AgentState.SEALED if False else AgentState.SEALING: [AgentState.DESTROYING, AgentState.QUARANTINED],
    AgentState.DESTROYING: [AgentState.DORMANT, AgentState.DESTRUCTION_UNCONFIRMED],
    # failure states can transition to DORMANT after resolution
    AgentState.QUARANTINED: [AgentState.DORMANT],
    AgentState.DEGRADED: [AgentState.RUNNING, AgentState.DORMANT],
    AgentState.UNKNOWN_EFFECT: [AgentState.QUIESCING, AgentState.QUARANTINED],
    AgentState.LEASE_LOST: [AgentState.DORMANT],
    AgentState.RESTORE_REJECTED: [AgentState.DORMANT],
    AgentState.DESTRUCTION_UNCONFIRMED: [AgentState.DORMANT, AgentState.QUARANTINED],
}

# Fix the SEALING key (workaround for the conditional above)
TRANSITIONS[AgentState.QUIESCING] = [AgentState.SEALING, AgentState.UNKNOWN_EFFECT]
TRANSITIONS[AgentState.SEALING] = [AgentState.DESTROYING, AgentState.QUARANTINED]


@dataclass
class StateTransition:
    from_state: AgentState
    to_state: AgentState
    timestamp: float
    reason: str
    metadata: Dict = field(default_factory=dict)


class LifecycleStateMachine:
    """Authoritative state machine for one agent's runtime lifecycle.

    Enforces that transitions only happen along valid edges. Records
    every transition for audit. A capsule may seal only from QUIESCING
    or SEALING states.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.state = AgentState.DORMANT
        self.history: List[StateTransition] = []
        self._transition_time = time.time()

    def transition(self, to_state: AgentState, reason: str = "", metadata: Optional[dict] = None) -> bool:
        """Attempt a state transition. Returns True if valid."""
        allowed = TRANSITIONS.get(self.state, [])
        if to_state not in allowed:
            return False

        record = StateTransition(
            from_state=self.state,
            to_state=to_state,
            timestamp=time.time(),
            reason=reason,
            metadata=metadata or {},
        )
        self.history.append(record)
        self.state = to_state
        self._transition_time = record.timestamp
        return True

    def can_seal(self) -> bool:
        """A capsule may seal only from QUIESCING or SEALING."""
        return self.state in (AgentState.QUIESCING, AgentState.SEALING)

    def is_running(self) -> bool:
        return self.state == AgentState.RUNNING

    def is_dormant(self) -> bool:
        return self.state == AgentState.DORMANT

    def is_failure(self) -> bool:
        return self.state in (
            AgentState.QUARANTINED,
            AgentState.DEGRADED,
            AgentState.UNKNOWN_EFFECT,
            AgentState.LEASE_LOST,
            AgentState.RESTORE_REJECTED,
            AgentState.DESTRUCTION_UNCONFIRMED,
        )

    def time_in_state(self) -> float:
        return time.time() - self._transition_time

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "state": self.state.name,
            "transitions": [
                {
                    "from": t.from_state.name,
                    "to": t.to_state.name,
                    "timestamp": t.timestamp,
                    "reason": t.reason,
                    "metadata": t.metadata,
                }
                for t in self.history
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LifecycleStateMachine":
        sm = cls(d["agent_id"])
        sm.state = AgentState[d["state"]]
        for t in d.get("transitions", []):
            sm.history.append(StateTransition(
                from_state=AgentState[t["from"]],
                to_state=AgentState[t["to"]],
                timestamp=t["timestamp"],
                reason=t["reason"],
                metadata=t.get("metadata", {}),
            ))
        return sm
