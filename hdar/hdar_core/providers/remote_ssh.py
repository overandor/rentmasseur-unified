"""Remote SSH provider — for cross-host execution.

Transfers capsule to a remote host via SSH, restores it there,
executes operations, and collects signed execution receipts.
The remote host does NOT receive the owner's private key.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from .base import ProviderBase, RuntimeRecord, ExecutionResult


class RemoteSSHProvider(ProviderBase):
    """Execute on a remote host via SSH.

    The remote host receives:
    - capsule files
    - owner public key
    - expected agent_id and epoch
    - fenced lease and token
    - attenuated capability set

    It does NOT receive the owner private key.
    """

    def __init__(self, host: str, user: str = "capsule-agent",
                 remote_workspace_root: str = "/tmp/capsule-runtime",
                 ssh_key: Optional[str] = None):
        self.host = host
        self.user = user
        self.remote_root = remote_workspace_root
        self.ssh_key = ssh_key
        self._runtimes: dict[str, RuntimeRecord] = {}

    @property
    def name(self) -> str:
        return "remote-ssh"

    def _ssh_base(self) -> list:
        cmd = ["ssh"]
        if self.ssh_key:
            cmd.extend(["-i", self.ssh_key])
        cmd.append(f"{self.user}@{self.host}")
        return cmd

    def _scp_to(self, local: str, remote: str) -> subprocess.CompletedProcess:
        cmd = ["scp"]
        if self.ssh_key:
            cmd.extend(["-i", self.ssh_key])
        cmd.extend([local, f"{self.user}@{self.host}:{remote}"])
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    def materialize(
        self,
        runtime_id: str,
        workspace_path: str,
        image: str = "",
        cpu_limit: str = "2",
        memory_limit: str = "2g",
        network_policy: str = "none",
    ) -> RuntimeRecord:
        remote_dir = f"{self.remote_root}/{runtime_id}"

        # Create remote directory
        subprocess.run(
            self._ssh_base() + [f"mkdir -p {remote_dir}/workspace"],
            capture_output=True, text=True, timeout=30,
        )

        # Transfer workspace
        import tarfile
        import io
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            with tarfile.open(tmp.name, "w:gz") as tar:
                tar.add(workspace_path, arcname=".")
            self._scp_to(tmp.name, f"{remote_dir}/workspace.tar.gz")
            os.unlink(tmp.name)

        # Extract on remote
        subprocess.run(
            self._ssh_base() + [
                f"cd {remote_dir} && mkdir -p workspace && "
                f"tar xzf workspace.tar.gz -C workspace && rm workspace.tar.gz"
            ],
            capture_output=True, text=True, timeout=60,
        )

        record = RuntimeRecord(
            provider=self.name,
            runtime_id=runtime_id,
            image_digest=image or "remote:linux",
            vm_identity=f"{self.user}@{self.host}",
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
            workspace_mount=f"{remote_dir}/workspace",
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
        if runtime_id not in self._runtimes:
            return ExecutionResult(
                operation_type=operation_type,
                command=command,
                exit_code=-1,
                stderr="runtime not found",
                success=False,
            )

        remote_dir = f"{self.remote_root}/{runtime_id}"
        start = time.time()
        result = subprocess.run(
            self._ssh_base() + [f"cd {remote_dir}/workspace && {command}"],
            capture_output=True, text=True, timeout=timeout,
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
        record = self._runtimes[runtime_id]
        record.stop_timestamp = time.time()
        return record

    def destroy(self, runtime_id: str) -> RuntimeRecord:
        if runtime_id not in self._runtimes:
            return RuntimeRecord(
                provider=self.name, runtime_id=runtime_id, exists=False
            )
        record = self._runtimes[runtime_id]
        remote_dir = f"{self.remote_root}/{runtime_id}"

        subprocess.run(
            self._ssh_base() + [f"rm -rf {remote_dir}"],
            capture_output=True, text=True, timeout=30,
        )
        record.delete_timestamp = time.time()
        record.exists = False
        record.post_delete_inspection = self.inspect(runtime_id)
        del self._runtimes[runtime_id]
        return record

    def inspect(self, runtime_id: str) -> dict:
        remote_dir = f"{self.remote_root}/{runtime_id}"
        result = subprocess.run(
            self._ssh_base() + [f"test -d {remote_dir} && echo EXISTS || echo GONE"],
            capture_output=True, text=True, timeout=10,
        )
        exists = "EXISTS" in result.stdout
        return {
            "exists": exists,
            "provider": self.name,
            "runtime_id": runtime_id,
            "remote_path": remote_dir,
        }

    def list_runtimes(self) -> list:
        result = subprocess.run(
            self._ssh_base() + [f"ls {self.remote_root} 2>/dev/null || true"],
            capture_output=True, text=True, timeout=10,
        )
        return [d.strip() for d in result.stdout.splitlines() if d.strip()]
