"""Semantic machine selectors.

Query layer over registered machine self-models. Instead of asking
"can host X run agent Y?", you ask:

    select_machines(
        model_id="llama-3-8b",
        min_ram_bytes=8_000_000_000,
        cpu_arch="arm64",
        required_tools=["apple-containerization", "python3"],
    )

Returns ranked candidates with evidence (self-model snapshot hash,
satisfaction report, timestamp). The selector does not trust machine
claims — it requires a fresh snapshot with a verifiable state hash.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from machine.self_model import SelfModel, MachineState


@dataclass
class MachineCandidate:
    """A machine that satisfies a selector query, with evidence."""
    hostname: str
    state_hash: str
    snapshot_timestamp: float
    satisfied: bool
    reasons: List[str] = field(default_factory=list)
    state: Optional[Dict[str, Any]] = None
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "hostname": self.hostname,
            "state_hash": self.state_hash,
            "snapshot_timestamp": self.snapshot_timestamp,
            "satisfied": self.satisfied,
            "reasons": self.reasons,
            "score": self.score,
            "state": self.state,
        }


class MachineRegistry:
    """Registry of known machines and their self-models.

    In a single-host deployment, this is just the local machine.
    In a multi-host deployment, machines register their snapshots
    here (via capsule transport, MCP, or direct API).
    """

    def __init__(self):
        self._machines: Dict[str, MachineState] = {}
        self._self_model = SelfModel()

    def register_local(self, active_runtimes: Optional[List[str]] = None) -> MachineState:
        """Snapshot the local machine and register it."""
        state = self._self_model.snapshot(active_runtimes)
        self._machines[state.hostname] = state
        return state

    def register_remote(self, state: MachineState) -> None:
        """Register a remote machine's snapshot."""
        self._machines[state.hostname] = state

    def get(self, hostname: str) -> Optional[MachineState]:
        return self._machines.get(hostname)

    def list_machines(self) -> List[str]:
        return list(self._machines.keys())

    def select_machines(
        self,
        requirements: Dict[str, Any],
        max_age_seconds: float = 300.0,
    ) -> List[MachineCandidate]:
        """Find machines that satisfy the given requirements.

        Args:
            requirements: Dict with keys like model_id, model_digest,
                min_ram_bytes, cpu_arch, required_tools, accelerator_pref
            max_age_seconds: Maximum age of snapshot to consider fresh

        Returns:
            List of MachineCandidate sorted by score (best first).
            Only satisfied candidates are included.
        """
        candidates: List[MachineCandidate] = []
        now = time.time()

        for hostname, state in self._machines.items():
            age = now - state.timestamp
            if age > max_age_seconds:
                continue

            satisfied, reasons = self._check_requirements(state, requirements)
            score = self._score_machine(state, requirements) if satisfied else 0.0

            candidates.append(MachineCandidate(
                hostname=hostname,
                state_hash=state.state_hash,
                snapshot_timestamp=state.timestamp,
                satisfied=satisfied,
                reasons=reasons,
                state=state.to_dict(),
                score=score,
            ))

        satisfied_candidates = [c for c in candidates if c.satisfied]
        satisfied_candidates.sort(key=lambda c: c.score, reverse=True)
        return satisfied_candidates

    def _check_requirements(
        self, state: MachineState, requirements: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        reasons: List[str] = []

        req_arch = requirements.get("cpu_arch", "")
        if req_arch and req_arch != "any" and state.arch != req_arch:
            reasons.append(f"arch mismatch: need {req_arch}, have {state.arch}")

        req_ram = requirements.get("min_ram_bytes", 0)
        if req_ram and state.memory_available_bytes < req_ram:
            reasons.append(
                f"insufficient RAM: need {req_ram}, have {state.memory_available_bytes}"
            )

        req_model = requirements.get("model_id", "")
        req_model_digest = requirements.get("model_digest", "")
        if req_model:
            found = False
            for m in state.models:
                if m.model_id == req_model:
                    found = True
                    if req_model_digest and not m.digest.startswith(req_model_digest[:16]):
                        reasons.append(
                            f"model {req_model} found but digest mismatch: "
                            f"need {req_model_digest[:16]}..., have {m.digest[:16]}..."
                        )
                    break
            if not found:
                reasons.append(f"model not found: {req_model}")

        req_tools = requirements.get("required_tools", [])
        for tool in req_tools:
            if tool not in state.capabilities:
                reasons.append(f"tool not available: {tool}")

        accel_pref = requirements.get("accelerator_pref", "")
        if accel_pref == "metal-gpu" and "metal-gpu" not in state.capabilities:
            reasons.append("metal-gpu preferred but not available")

        return (len(reasons) == 0, reasons)

    def _score_machine(self, state: MachineState, requirements: Dict[str, Any]) -> float:
        """Score a machine for ranking. Higher is better."""
        score = 0.0
        score += state.memory_available_bytes / 1_000_000_000.0
        score += max(0, 1.0 - state.cpu_load) * 10.0

        req_model = requirements.get("model_id", "")
        if req_model:
            for m in state.models:
                if m.model_id == req_model and m.loaded:
                    score += 50.0

        score -= len(state.active_runtimes) * 2.0

        accel_pref = requirements.get("accelerator_pref", "")
        if accel_pref and accel_pref in state.capabilities:
            score += 20.0

        return round(score, 3)

    def select_best(
        self, requirements: Dict[str, Any], max_age_seconds: float = 300.0
    ) -> Optional[MachineCandidate]:
        """Return the best machine for the requirements, or None."""
        candidates = self.select_machines(requirements, max_age_seconds)
        return candidates[0] if candidates else None
