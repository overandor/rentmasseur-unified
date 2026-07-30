"""SSH forced-command gateway — P0 #5.

Maps a stable SSH identity to the capsule resolver. OpenSSH's
ForceCommand routes every authenticated session through this
gateway, ignoring arbitrary client commands. The original request
is available through SSH_ORIGINAL_COMMAND.

SSH configuration:
    Match User capsule-agent
        ForceCommand /usr/local/bin/capsule-ssh-gateway
        DisableForwarding yes
        PermitTTY yes
        X11Forwarding no
        PermitTunnel no

The gateway resolves:
    authenticated SSH identity → agent_id
    → latest authoritative capsule
    → wake lease
    → provider selection
    → runtime materialization
    → session attachment
    → (on disconnect) collapse → dormant
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lifecycle.controller import LifecycleController
from lifecycle.lease import LeaseManager
from lifecycle.effects import EffectRegistry
from providers.base import ProviderBase
from providers.unsafe_host import UnsafeHostProvider


@dataclass
class AgentRegistration:
    """Maps an SSH identity to an agent and its capsule."""
    agent_id: str
    capsule_hash: str
    epoch: int
    workspace_path: str
    holder_id: str = "ssh-session"


class SSHGateway:
    """Forced-command gateway mapping SSH identity to agent lifecycle.

    In production, this is invoked by sshd ForceCommand. In testing,
    it can be called directly with simulate_connect().
    """

    def __init__(
        self,
        provider: ProviderBase,
        lease_manager: LeaseManager,
        effect_registry: EffectRegistry,
        state_dir: str,
    ):
        self.provider = provider
        self.lease_manager = lease_manager
        self.effect_registry = effect_registry
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._registrations: dict[str, AgentRegistration] = {}
        self._controllers: dict[str, LifecycleController] = {}

    def register_agent(
        self,
        ssh_user: str,
        agent_id: str,
        capsule_hash: str,
        epoch: int,
        workspace_path: str,
    ):
        """Map an SSH user to an agent identity."""
        self._registrations[ssh_user] = AgentRegistration(
            agent_id=agent_id,
            capsule_hash=capsule_hash,
            epoch=epoch,
            workspace_path=workspace_path,
        )

    def resolve(self, ssh_user: str) -> Optional[AgentRegistration]:
        """Resolve SSH identity to agent registration."""
        return self._registrations.get(ssh_user)

    def connect(self, ssh_user: str, holder_id: Optional[str] = None) -> dict:
        """Simulate an SSH connection: wake the agent.

        This is what ForceCommand would invoke. In production,
        ssh_user comes from $USER or the authenticated session.
        """
        reg = self.resolve(ssh_user)
        if reg is None:
            return {"connected": False, "reason": f"unknown SSH identity: {ssh_user}"}

        controller = LifecycleController(
            agent_id=reg.agent_id,
            provider=self.provider,
            lease_manager=self.lease_manager,
            effect_registry=self.effect_registry,
            state_dir=str(self.state_dir / reg.agent_id),
        )
        self._controllers[ssh_user] = controller

        result = controller.wake(
            capsule_hash=reg.capsule_hash,
            epoch=reg.epoch,
            workspace_path=reg.workspace_path,
            holder_id=holder_id or f"ssh-{ssh_user}",
        )
        return {
            "connected": result["woke"],
            "ssh_user": ssh_user,
            "agent_id": reg.agent_id,
            "runtime_id": result.get("runtime_id"),
            "lease_generation": result.get("lease_generation"),
            "reason": result.get("reason"),
        }

    def execute_command(self, ssh_user: str, command: str) -> dict:
        """Execute a command in the agent's runtime via SSH session."""
        controller = self._controllers.get(ssh_user)
        if controller is None or not controller.sm.is_running():
            return {"executed": False, "reason": "no active session for this user"}

        original = os.environ.get("SSH_ORIGINAL_COMMAND", command)
        result = controller.execute("shell", original)
        return {
            "executed": True,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.success,
        }

    def disconnect(self, ssh_user: str) -> dict:
        """Simulate SSH disconnect: collapse the agent back to dormant."""
        controller = self._controllers.get(ssh_user)
        if controller is None:
            return {"disconnected": False, "reason": "no active session"}

        result = controller.collapse()
        del self._controllers[ssh_user]
        return {
            "disconnected": result["collapsed"],
            "agent_id": controller.agent_id,
            "runtime_destroyed": result.get("runtime_destroyed", False),
            "active_compute": result.get("active_compute", "unknown"),
            "reason": result.get("reason"),
        }

    def status(self) -> dict:
        """Show all registered agents and their connection state."""
        return {
            ssh_user: {
                "agent_id": reg.agent_id,
                "epoch": reg.epoch,
                "connected": ssh_user in self._controllers,
            }
            for ssh_user, reg in self._registrations.items()
        }


# ─── Entry point for sshd ForceCommand ────────────────────

def main():
    """Entry point when invoked by sshd ForceCommand.

    Environment:
        SSH_ORIGINAL_COMMAND — the command the client requested
        USER                 — the authenticated SSH user

    In production, this would load registrations from a config file
    or database. Here it's a minimal shim showing the flow.
    """
    ssh_user = os.environ.get("USER", "unknown")
    original_command = os.environ.get("SSH_ORIGINAL_COMMAND", "")

    gateway = SSHGateway(
        provider=UnsafeHostProvider("/tmp/capsule-gateway"),
        lease_manager=LeaseManager("/tmp/capsule-gateway/leases.db"),
        effect_registry=EffectRegistry("/tmp/capsule-gateway/effects.jsonl"),
        state_dir="/tmp/capsule-gateway/state",
    )

    # In production: load registrations from config
    # gateway.register_agent(...)

    print(f"capsule-ssh-gateway: user={ssh_user} command={original_command!r}")
    print("Gateway ready. Register agents to begin.")
    print("(This is the ForceCommand shim. In production, it loads")
    print(" agent registrations and routes the session.)")


if __name__ == "__main__":
    main()
