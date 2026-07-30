"""Lifecycle controller — orchestrates the full agent lifecycle.

Ties together:
  - State machine (P0 #1)
  - Effect registry (P0 #2)
  - Fenced lease manager (P0 #3)
  - Execution provider (P0 #4)

Enforces the rule: a capsule may seal only after quiescence and
effect reconciliation. Runtime destruction must be verified before
returning to DORMANT.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from .state_machine import LifecycleStateMachine, AgentState
from .effects import EffectRegistry
from .lease import LeaseManager
from providers.base import ProviderBase, RuntimeRecord, ExecutionResult


class LifecycleController:
    """Orchestrates: wake → run → quiesce → seal → destroy → dormant."""

    def __init__(
        self,
        agent_id: str,
        provider: ProviderBase,
        lease_manager: LeaseManager,
        effect_registry: EffectRegistry,
        state_dir: str,
    ):
        self.agent_id = agent_id
        self.provider = provider
        self.lease_manager = lease_manager
        self.effects = effect_registry
        self.sm = LifecycleStateMachine(agent_id)
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.lease = None
        self.runtime_id: Optional[str] = None
        self.runtime_record: Optional[RuntimeRecord] = None

    def wake(
        self,
        capsule_hash: str,
        epoch: int,
        workspace_path: str,
        holder_id: str = "local",
        image: str = "",
        cpu_limit: str = "2",
        memory_limit: str = "2g",
    ) -> dict:
        """Wake the agent: acquire lease, materialize runtime, verify."""
        if not self.sm.transition(AgentState.ACQUIRING_LEASE, "wake requested"):
            return {"woke": False, "reason": f"cannot wake from {self.sm.state.name}"}

        # Acquire exclusive lease
        self.lease, err = self.lease_manager.acquire(
            self.agent_id, capsule_hash, epoch, holder_id, "pending"
        )
        if err:
            self.sm.transition(AgentState.LEASE_LOST, err)
            return {"woke": False, "reason": f"lease denied: {err}"}

        # Materialize runtime
        if not self.sm.transition(AgentState.MATERIALIZING, "provider selected"):
            return {"woke": False, "reason": "state machine rejected materialize"}

        self.runtime_id = f"rt-{uuid.uuid4().hex[:8]}"
        self.runtime_record = self.provider.materialize(
            runtime_id=self.runtime_id,
            workspace_path=workspace_path,
            image=image,
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
        )

        # Verify input
        if not self.sm.transition(AgentState.VERIFYING_INPUT, "runtime materialized"):
            return {"woke": False, "reason": "state machine rejected verify"}

        # Check runtime exists
        inspection = self.provider.inspect(self.runtime_id)
        if not inspection.get("exists"):
            self.sm.transition(AgentState.RESTORE_REJECTED, "runtime not found after materialize")
            return {"woke": False, "reason": "runtime not found after materialize"}

        # Running
        self.sm.transition(AgentState.RUNNING, "capsule verified, runtime active")
        return {
            "woke": True,
            "agent_id": self.agent_id,
            "runtime_id": self.runtime_id,
            "lease_generation": self.lease.lease_generation,
            "fencing_token": self.lease.fencing_token,
            "provider": self.provider.name,
            "state": self.sm.state.name,
        }

    def execute(self, operation_type: str, command: str, timeout: int = 60) -> ExecutionResult:
        """Execute a typed operation inside the runtime."""
        if not self.sm.is_running():
            return ExecutionResult(
                operation_type=operation_type, command=command,
                exit_code=-1, stderr="agent not running", success=False,
            )
        return self.provider.execute(self.runtime_id, operation_type, command, timeout)

    def register_effect(self, capability: str, payload: bytes,
                        operation_id: Optional[str] = None):
        """Register an external effect before executing it."""
        return self.effects.register(
            self.agent_id, capability, payload, operation_id=operation_id
        )

    def commit_effect(self, operation_id: str, provider_receipt: Optional[dict] = None):
        """Mark an external effect as committed."""
        return self.effects.commit(self.agent_id, operation_id, provider_receipt=provider_receipt)

    def mark_effect_unknown(self, operation_id: str):
        """Mark an external effect as unknown (e.g. crash before confirmation)."""
        return self.effects.mark_unknown(self.agent_id, operation_id)

    def reconcile_effects(self, probe_fn) -> dict:
        """Reconcile unknown effects on wake."""
        return self.effects.reconcile(self.agent_id, probe_fn)

    def collapse(self, force: bool = False, fencing_token: str = "") -> dict:
        """Collapse: quiesce → seal → destroy → dormant.

        GATED on semantic quiescence. Refuses to seal while external
        effects are in flight, unless force=True (for emergencies).

        When a fencing token is provided, it is validated against the
        current lease. A stale runtime cannot collapse or release the lease.
        """
        if fencing_token and self.lease:
            if not self.lease_manager.validate_token(self.agent_id, fencing_token):
                self.sm.transition(AgentState.LEASE_LOST,
                                   "stale fencing token — cannot collapse")
                return {
                    "collapsed": False,
                    "reason": "stale or invalid fencing token — this runtime's lease is no longer authoritative",
                    "runtime_id": self.runtime_id,
                }
        # Allow collapse from RUNNING or UNKNOWN_EFFECT (after reconciliation)
        if self.sm.state not in (AgentState.RUNNING, AgentState.UNKNOWN_EFFECT):
            return {"collapsed": False, "reason": f"agent is {self.sm.state.name}, not running or quiescible"}

        # If in UNKNOWN_EFFECT, transition back to QUIESCING after reconciliation
        if self.sm.state == AgentState.UNKNOWN_EFFECT:
            if not self.sm.transition(AgentState.QUIESCING, "effects reconciled, retrying collapse"):
                return {"collapsed": False, "reason": "cannot transition from UNKNOWN_EFFECT to QUIESCING"}
        else:
            # Quiesce from RUNNING
            self.sm.transition(AgentState.QUIESCING, "collapse requested")

        # Check quiescence
        q = self.effects.check_quiescence(self.agent_id)
        if not q["quiescent"] and not force:
            self.sm.transition(AgentState.UNKNOWN_EFFECT, q["verdict"])
            return {
                "collapsed": False,
                "reason": q["verdict"],
                "blocking_effects": q["blocking_effects"],
            }

        # Seal
        self.sm.transition(AgentState.SEALING, "quiescence confirmed")

        # Destroy runtime
        self.sm.transition(AgentState.DESTROYING, "sealing complete")
        if self.runtime_id:
            self.provider.stop(self.runtime_id)
            destroy_record = self.provider.destroy(self.runtime_id)

            # Verify destruction
            destroyed = self.provider.verify_destruction(self.runtime_id)
            if not destroyed:
                self.sm.transition(AgentState.DESTRUCTION_UNCONFIRMED,
                                   "runtime still exists after destroy")
                return {
                    "collapsed": False,
                    "reason": "DESTRUCTION UNCONFIRMED — runtime still exists",
                    "runtime_id": self.runtime_id,
                }

        # Release lease
        if self.lease:
            self.lease_manager.release(self.agent_id, self.lease.fencing_token)
            self.lease = None

        self.runtime_id = None
        self.runtime_record = None
        self.sm.transition(AgentState.DORMANT, "runtime destroyed, lease released")

        return {
            "collapsed": True,
            "agent_id": self.agent_id,
            "runtime_destroyed": True,
            "destruction_verified": True,
            "active_compute": "zero — dormant storage only",
            "state": self.sm.state.name,
        }

    def status(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "state": self.sm.state.name,
            "is_running": self.sm.is_running(),
            "is_dormant": self.sm.is_dormant(),
            "runtime_id": self.runtime_id,
            "provider": self.provider.name,
            "lease_generation": self.lease.lease_generation if self.lease else None,
            "transitions": len(self.sm.history),
        }
