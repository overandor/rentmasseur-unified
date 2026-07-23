"""SSH gateway integration with the continuity loop.

Wires the existing forced_command.py gateway to use:
  - Ed25519 crypto (not HMAC)
  - Provider factory (auto-detect apple-container)
  - Continuity loop for seal/restore/witness/reseal
  - Lease-gated secret access
  - Observability (structured logging + metrics)

The gateway maps a stable SSH identity to the latest authoritative
capsule, restores it on a fresh runtime, and collapses back to
dormant when the SSH session disconnects.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from crypto import OwnerKeyPair, HostKeyPair, PublicKey
from capsule.store import ContentStore
from capsule.identity import LineageEpoch
from lifecycle.lease import LeaseManager
from lifecycle.effects import EffectRegistry
from lifecycle.observability import (
    StructuredLogger, MetricsCollector, EventStream, ContinuityObserver,
)
from provider_factory import create_provider, ProviderType
from continuity import ContinuityLoop, ContinuityCapsule, ContinuityVerifier
from gateway.forced_command import SSHGateway as BaseSSHGateway, AgentRegistration


@dataclass
class ContinuitySSHGateway:
    """SSH gateway wired to the continuity loop.

    In production, this is invoked by sshd ForceCommand. The gateway:
      1. Resolves SSH identity → agent_id → latest capsule
      2. Acquires a lease
      3. Materializes a runtime via the provider factory
      4. Restores the capsule workspace
      5. Attaches the SSH session to the runtime
      6. On disconnect: seals a new capsule, destroys runtime, releases lease
    """

    owner_key: OwnerKeyPair
    store: ContentStore
    lease_manager: LeaseManager
    state_dir: str
    logger: StructuredLogger = field(default_factory=lambda: StructuredLogger("ssh-gateway"))
    metrics: MetricsCollector = field(default_factory=MetricsCollector)
    event_stream: Optional[EventStream] = None
    _registrations: Dict[str, AgentRegistration] = field(default_factory=dict)
    _sessions: Dict[str, dict] = field(default_factory=dict)

    def __post_init__(self):
        self.observer = ContinuityObserver(
            self.logger, self.metrics, self.event_stream
        )
        self.loop = ContinuityLoop(
            self.owner_key, self.store, self.lease_manager, self.state_dir,
        )
        self.verifier = ContinuityVerifier(self.owner_key.to_public())

    def register_agent(
        self,
        ssh_user: str,
        agent_id: str,
        capsule_path: str,
        epoch: int,
        workspace_path: str = "",
    ):
        """Map an SSH user to an agent and its latest capsule."""
        self._registrations[ssh_user] = AgentRegistration(
            agent_id=agent_id,
            capsule_hash=capsule_path,  # store path, not hash
            epoch=epoch,
            workspace_path=workspace_path,
        )
        self.logger.info("agent_registered", f"registered {ssh_user} → {agent_id}",
                         agent_id=agent_id, ssh_user=ssh_user)

    def connect(self, ssh_user: str, holder_id: Optional[str] = None) -> dict:
        """Handle an SSH connection: restore the agent.

        This is what ForceCommand invokes.
        """
        start = time.time()
        reg = self._registrations.get(ssh_user)
        if reg is None:
            self.logger.warn("unknown_identity", f"unknown SSH user: {ssh_user}")
            return {"connected": False, "reason": f"unknown SSH identity: {ssh_user}"}

        # Load the latest capsule
        capsule_path = reg.capsule_hash
        if not os.path.exists(capsule_path):
            return {"connected": False, "reason": f"capsule not found: {capsule_path}"}

        with open(capsule_path) as f:
            capsule = ContinuityCapsule.from_dict(json.load(f))

        # Verify the capsule offline
        verify_result = self.verifier.verify_full_chain(capsules=[capsule])
        if not verify_result["valid"]:
            self.logger.error("capsule_verification_failed",
                              f"capsule verification failed for {reg.agent_id}",
                              agent_id=reg.agent_id)
            return {"connected": False, "reason": "capsule verification failed",
                    "problems": verify_result["problems"]}

        # Create provider via factory
        provider = create_provider(ProviderType.AUTO,
                                   str(Path(self.state_dir) / f"provider_{ssh_user}"))

        # Generate host key for this session
        host_key = HostKeyPair.generate(f"ssh-{ssh_user}")

        # Restore on a fresh runtime
        workspace = str(Path(self.state_dir) / f"workspace_{ssh_user}")
        restoration = self.loop.restore_on_host_b(
            capsule, provider, host_key, workspace,
            holder_id=holder_id or f"ssh-{ssh_user}",
        )

        duration_ms = (time.time() - start) * 1000
        self.observer.on_restore(reg.agent_id, holder_id or ssh_user,
                                 restoration["restored"], duration_ms)

        if not restoration["restored"]:
            return {"connected": False, "reason": restoration.get("reason", ""),
                    "agent_id": reg.agent_id}

        self._sessions[ssh_user] = {
            "agent_id": reg.agent_id,
            "runtime_id": restoration["runtime_id"],
            "fencing_token": restoration["fencing_token"],
            "provider": provider,
            "host_key": host_key,
            "capsule": capsule,
            "workspace": workspace,
            "connected_at": time.time(),
        }

        self.logger.info("agent_connected", f"agent {reg.agent_id} woke via SSH",
                         agent_id=reg.agent_id, ssh_user=ssh_user,
                         runtime_id=restoration["runtime_id"])

        return {
            "connected": True,
            "ssh_user": ssh_user,
            "agent_id": reg.agent_id,
            "runtime_id": restoration["runtime_id"],
            "lease_generation": restoration["lease_generation"],
            "workspace": workspace,
        }

    def execute(self, ssh_user: str, command: str) -> dict:
        """Execute a command in the agent's runtime."""
        session = self._sessions.get(ssh_user)
        if session is None:
            return {"executed": False, "reason": "no active session"}

        provider = session["provider"]
        runtime_id = session["runtime_id"]
        original = os.environ.get("SSH_ORIGINAL_COMMAND", command)

        result = provider.execute(runtime_id, "shell", original)

        return {
            "executed": True,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.success,
        }

    def disconnect(self, ssh_user: str) -> dict:
        """Handle SSH disconnect: seal, destroy, release."""
        session = self._sessions.get(ssh_user)
        if session is None:
            return {"disconnected": False, "reason": "no active session"}

        agent_id = session["agent_id"]
        provider = session["provider"]
        runtime_id = session["runtime_id"]
        host_key = session["host_key"]
        capsule = session["capsule"]
        workspace = Path(session["workspace"])

        # Seal a new capsule with the current workspace state
        effects = EffectRegistry(str(Path(self.state_dir) / f"effects_{ssh_user}.jsonl"))
        q = effects.check_quiescence(agent_id)
        if q["quiescent"]:
            new_epoch = LineageEpoch.child(
                LineageEpoch.from_dict(capsule.epoch) if hasattr(LineageEpoch, 'from_dict')
                else LineageEpoch.genesis(agent_id)
            )
            try:
                new_capsule, cap_path = self.loop.seal_on_host_a(
                    workspace, agent_id, "agent",
                    new_epoch, capsule.objective, "ssh session complete",
                    effects=effects,
                    fencing_token=session["fencing_token"],
                )
                self.observer.on_seal(agent_id, new_epoch.sequence,
                                      new_capsule.manifest_hash, 0)
            except Exception as e:
                self.logger.error("seal_failed", f"failed to seal on disconnect: {e}",
                                  agent_id=agent_id)

        # Destroy the runtime
        provider.stop(runtime_id)
        provider.destroy(runtime_id)
        self.lease_manager.release(agent_id, session["fencing_token"])

        self.observer.on_destroy(agent_id, runtime_id, 0)

        del self._sessions[ssh_user]

        self.logger.info("agent_disconnected", f"agent {agent_id} collapsed to dormant",
                         agent_id=agent_id, ssh_user=ssh_user)

        return {
            "disconnected": True,
            "agent_id": agent_id,
            "runtime_destroyed": True,
        }

    def status(self) -> dict:
        """Show all registered agents and their connection state."""
        return {
            ssh_user: {
                "agent_id": reg.agent_id,
                "epoch": reg.epoch,
                "connected": ssh_user in self._sessions,
            }
            for ssh_user, reg in self._registrations.items()
        }
