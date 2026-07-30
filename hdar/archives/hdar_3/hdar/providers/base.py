"""Provider base interface.

Every execution provider implements this interface. The lifecycle
controller calls these methods to materialize, observe, and destroy
runtimes. A provider receipt is returned for each operation and
enters the capsule's evidence chain.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RuntimeRecord:
    """Evidence of a runtime's existence and configuration."""
    provider: str
    runtime_id: str
    image_digest: str = ""
    vm_identity: str = ""
    cpu_limit: str = ""
    memory_limit: str = ""
    workspace_mount: str = ""
    network_policy: str = "none"
    start_timestamp: float = 0.0
    stop_timestamp: Optional[float] = None
    delete_timestamp: Optional[float] = None
    post_delete_inspection: Optional[Dict[str, Any]] = None
    exists: bool = True

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "runtime_id": self.runtime_id,
            "image_digest": self.image_digest,
            "vm_identity": self.vm_identity,
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "workspace_mount": self.workspace_mount,
            "network_policy": self.network_policy,
            "start_timestamp": self.start_timestamp,
            "stop_timestamp": self.stop_timestamp,
            "delete_timestamp": self.delete_timestamp,
            "post_delete_inspection": self.post_delete_inspection,
            "exists": self.exists,
        }


@dataclass
class ExecutionResult:
    """Result of running a typed operation inside a provider runtime."""
    operation_type: str
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    files_changed: list = field(default_factory=list)
    success: bool = False

    def to_dict(self) -> dict:
        return {
            "operation_type": self.operation_type,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "files_changed": self.files_changed,
            "success": self.success,
        }


class ProviderBase(ABC):
    """Abstract base for execution providers."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def materialize(
        self,
        runtime_id: str,
        workspace_path: str,
        image: str = "",
        cpu_limit: str = "2",
        memory_limit: str = "2g",
        network_policy: str = "none",
    ) -> RuntimeRecord:
        """Create and start a named isolated runtime with the workspace mounted."""
        ...

    @abstractmethod
    def execute(
        self,
        runtime_id: str,
        operation_type: str,
        command: str,
        timeout: int = 60,
    ) -> ExecutionResult:
        """Run a typed operation inside the runtime."""
        ...

    @abstractmethod
    def stop(self, runtime_id: str) -> RuntimeRecord:
        """Stop the runtime (process exit, container stop)."""
        ...

    @abstractmethod
    def destroy(self, runtime_id: str) -> RuntimeRecord:
        """Delete the runtime and all its resources."""
        ...

    @abstractmethod
    def inspect(self, runtime_id: str) -> dict:
        """Query the provider for the runtime's current state."""
        ...

    @abstractmethod
    def list_runtimes(self) -> list:
        """List all runtimes known to this provider."""
        ...

    def verify_destruction(self, runtime_id: str) -> bool:
        """Verify that a runtime no longer exists.

        The destruction gate passes only when:
        - process exited
        - container stopped
        - container deleted
        - provider listing no longer contains the runtime identity
        """
        listing = self.list_runtimes()
        if runtime_id in listing:
            return False
        inspection = self.inspect(runtime_id)
        return not inspection.get("exists", False)
