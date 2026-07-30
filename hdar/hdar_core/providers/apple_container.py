"""Apple container provider — real isolated Linux VM execution.

Uses Apple's `container` CLI (https://github.com/apple/container) to
create lightweight VM-backed Linux containers on Apple silicon.

Each container runs in its own lightweight VM with explicit CPU and
memory limits. This provider records real runtime identity, resource
allocation, and post-destruction absence proof.

Requires:
    brew install container
    container system kernel set --recommended
    container image pull ubuntu:24.04

The provider will raise RuntimeError if the CLI is not available.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from typing import Optional

from .base import ProviderBase, RuntimeRecord, ExecutionResult


class AppleContainerProvider(ProviderBase):
    """Real Apple container provider — VM-backed Linux isolation.

    Each container is a lightweight VM running Linux on Apple silicon.
    The provider records:
      - Real VM identity (IP, OS, arch from inspect)
      - Resource allocation (CPU, memory)
      - Post-destruction absence proof (inspect returns not-found)
    """

    def __init__(self):
        self._cli = self._find_cli()
        self._runtimes: dict[str, RuntimeRecord] = {}

    def _find_cli(self) -> str:
        path = shutil.which("container")
        if not path:
            raise RuntimeError(
                "Apple 'container' CLI not found. Install with: brew install container"
            )
        return path

    @property
    def name(self) -> str:
        return "apple-container"

    def _run_cli(self, args: list, timeout: int = 120) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self._cli] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def materialize(
        self,
        runtime_id: str,
        workspace_path: str,
        image: str = "ubuntu:24.04",
        cpu_limit: str = "2",
        memory_limit: str = "512m",
        network_policy: str = "default",
    ) -> RuntimeRecord:
        """Create and start a real VM-backed container.

        Uses `container run -d` with `sleep infinity` as init process
        to keep the VM alive for exec commands.
        """
        run_args = [
            "run",
            "--name", runtime_id,
            "-c", str(cpu_limit),
            "-m", memory_limit,
            "-d",
        ]

        if workspace_path:
            run_args.extend(["-v", f"{workspace_path}:/workspace"])

        if network_policy == "none":
            run_args.extend(["--network", "none"])

        run_args.extend([image, "sleep", "infinity"])

        result = self._run_cli(run_args, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(
                f"container run failed: {result.stderr.strip()}"
            )

        info = self.inspect(runtime_id)

        record = RuntimeRecord(
            provider=self.name,
            runtime_id=runtime_id,
            image_digest=image,
            vm_identity=info.get("id", runtime_id),
            cpu_limit=str(cpu_limit),
            memory_limit=memory_limit,
            workspace_mount=workspace_path,
            network_policy=network_policy,
            start_timestamp=time.time(),
            exists=True,
        )
        self._runtimes[runtime_id] = record
        return record

    def execute(
        self,
        runtime_id: str,
        operation_type: str,
        command: str,
        timeout: int = 60,
    ) -> ExecutionResult:
        """Execute a command inside the running container."""
        if runtime_id not in self._runtimes:
            return ExecutionResult(
                operation_type=operation_type,
                command=command,
                exit_code=-1,
                stderr="runtime not found",
                success=False,
            )

        start = time.time()
        result = self._run_cli(
            ["exec", runtime_id, "sh", "-c", command],
            timeout=timeout,
        )
        duration = (time.time() - start) * 1000

        return ExecutionResult(
            operation_type=operation_type,
            command=command,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=duration,
            success=result.returncode == 0,
        )

    def stop(self, runtime_id: str) -> RuntimeRecord:
        if runtime_id not in self._runtimes:
            return RuntimeRecord(
                provider=self.name, runtime_id=runtime_id, exists=False
            )
        self._run_cli(["stop", runtime_id])
        record = self._runtimes[runtime_id]
        record.stop_timestamp = time.time()
        return record

    def destroy(self, runtime_id: str) -> RuntimeRecord:
        """Destroy the container and record absence proof."""
        if runtime_id not in self._runtimes:
            return RuntimeRecord(
                provider=self.name, runtime_id=runtime_id, exists=False
            )
        record = self._runtimes[runtime_id]

        if record.stop_timestamp is None:
            self.stop(runtime_id)

        self._run_cli(["rm", runtime_id])
        record.delete_timestamp = time.time()
        record.exists = False
        record.post_delete_inspection = self.inspect(runtime_id)
        del self._runtimes[runtime_id]
        return record

    def inspect(self, runtime_id: str) -> dict:
        """Query provider for runtime state. Returns {"exists": False} if gone."""
        result = self._run_cli(["inspect", runtime_id])
        if result.returncode != 0:
            return {
                "exists": False,
                "provider": self.name,
                "runtime_id": runtime_id,
                "error": result.stderr.strip(),
            }
        try:
            data = json.loads(result.stdout)
            if isinstance(data, list) and len(data) > 0:
                entry = data[0]
                return {
                    "exists": True,
                    "id": entry.get("id", runtime_id),
                    "state": entry.get("status", {}).get("state", "unknown"),
                    "image": entry.get("configuration", {}).get("image", {}).get("reference", ""),
                    "os": entry.get("configuration", {}).get("platform", {}).get("os", ""),
                    "arch": entry.get("configuration", {}).get("platform", {}).get("architecture", ""),
                    "cpus": entry.get("configuration", {}).get("resources", {}).get("cpus", 0),
                    "memory": entry.get("configuration", {}).get("resources", {}).get("memoryInBytes", 0),
                    "started": entry.get("status", {}).get("startedDate", ""),
                    "raw": entry,
                }
            return {"exists": True, "raw": data}
        except json.JSONDecodeError:
            return {
                "exists": True,
                "provider": self.name,
                "runtime_id": runtime_id,
                "raw": result.stdout,
            }

    def list_runtimes(self) -> list:
        """List all containers (running and stopped)."""
        result = self._run_cli(["ls", "-a"])
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:
            return []
        ids = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                ids.append(parts[0])
        return ids

    def verify_destruction(self, runtime_id: str) -> bool:
        """Verify runtime no longer exists — the absence proof."""
        listing = self.list_runtimes()
        if runtime_id in listing:
            return False
        inspection = self.inspect(runtime_id)
        return not inspection.get("exists", False)
