"""Unsafe host provider — development and testing only.

Executes operations directly on the host filesystem inside a
sandboxed directory. NOT a real isolated runtime. Used for
testing the lifecycle controller without a container runtime.

The provider receipt honestly records provider="unsafe-host" so
no one mistakes this for isolated execution.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from .base import ProviderBase, RuntimeRecord, ExecutionResult


class UnsafeHostProvider(ProviderBase):
    """Development provider — no isolation. For testing only."""

    def __init__(self, sandbox_root: str):
        self.sandbox_root = Path(sandbox_root)
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self._runtimes: dict[str, RuntimeRecord] = {}

    @property
    def name(self) -> str:
        return "unsafe-host"

    def materialize(
        self,
        runtime_id: str,
        workspace_path: str,
        image: str = "",
        cpu_limit: str = "2",
        memory_limit: str = "2g",
        network_policy: str = "none",
    ) -> RuntimeRecord:
        runtime_dir = self.sandbox_root / runtime_id
        runtime_dir.mkdir(parents=True, exist_ok=True)

        # Copy workspace into runtime
        ws = Path(workspace_path)
        if ws.exists():
            dest = runtime_dir / "workspace"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(ws, dest)

        record = RuntimeRecord(
            provider=self.name,
            runtime_id=runtime_id,
            image_digest=image or "unsafe-host:latest",
            vm_identity=f"process-{os.getpid()}",
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
            workspace_mount=str(runtime_dir / "workspace"),
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

        ws = self.sandbox_root / runtime_id / "workspace"
        start = time.time()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(ws),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = (time.time() - start) * 1000
            return ExecutionResult(
                operation_type=operation_type,
                command=command,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration,
                success=proc.returncode == 0,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                operation_type=operation_type,
                command=command,
                exit_code=-1,
                stderr=f"timeout after {timeout}s",
                duration_ms=timeout * 1000,
                success=False,
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
        runtime_dir = self.sandbox_root / runtime_id
        if runtime_dir.exists():
            shutil.rmtree(runtime_dir)
        record.delete_timestamp = time.time()
        record.exists = False
        record.post_delete_inspection = self.inspect(runtime_id)
        del self._runtimes[runtime_id]
        return record

    def inspect(self, runtime_id: str) -> dict:
        if runtime_id in self._runtimes:
            return {"exists": True, **self._runtimes[runtime_id].to_dict()}
        runtime_dir = self.sandbox_root / runtime_id
        return {
            "exists": runtime_dir.exists(),
            "provider": self.name,
            "runtime_id": runtime_id,
        }

    def list_runtimes(self) -> list:
        return list(self._runtimes.keys())
