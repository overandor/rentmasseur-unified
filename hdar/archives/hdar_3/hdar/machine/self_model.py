"""Self-modeling local machine introspection.

A machine models its own state: hardware, load, available models,
active runtimes, and capability surface. This is not static metadata —
it is a live snapshot that changes as the machine executes work.

The self-model is the foundation for semantic machine selectors:
before an agent migrates to a host, the host's self-model answers
"can I run this agent?" with evidence, not guesses.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ModelAvailability:
    """A model present on this machine, identified by digest."""
    model_id: str
    digest: str
    path: str
    size_bytes: int
    quantization: str = ""
    tokenizer_id: str = ""
    tokenizer_digest: str = ""
    loaded: bool = False

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "digest": self.digest,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "quantization": self.quantization,
            "tokenizer_id": self.tokenizer_id,
            "tokenizer_digest": self.tokenizer_digest,
            "loaded": self.loaded,
        }


@dataclass
class MachineState:
    """Live snapshot of machine state at a point in time."""
    hostname: str = ""
    os: str = ""
    os_version: str = ""
    arch: str = ""
    cpu_count: int = 0
    cpu_load: float = 0.0
    memory_total_bytes: int = 0
    memory_available_bytes: int = 0
    disk_total_bytes: int = 0
    disk_available_bytes: int = 0
    models: List[ModelAvailability] = field(default_factory=list)
    active_runtimes: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    timestamp: float = 0.0
    state_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "hostname": self.hostname,
            "os": self.os,
            "os_version": self.os_version,
            "arch": self.arch,
            "cpu_count": self.cpu_count,
            "cpu_load": self.cpu_load,
            "memory_total_bytes": self.memory_total_bytes,
            "memory_available_bytes": self.memory_available_bytes,
            "disk_total_bytes": self.disk_total_bytes,
            "disk_available_bytes": self.disk_available_bytes,
            "models": [m.to_dict() for m in self.models],
            "active_runtimes": self.active_runtimes,
            "capabilities": self.capabilities,
            "timestamp": self.timestamp,
            "state_hash": self.state_hash,
        }

    def compute_hash(self) -> str:
        d = self.to_dict()
        d.pop("state_hash", None)
        d.pop("timestamp", None)
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


class SelfModel:
    """Introspects the local machine and maintains a live state model.

    Call `snapshot()` to capture the current state. The snapshot is
    content-hashed so that identical states produce identical hashes,
    enabling change detection and selective re-querying.
    """

    def __init__(self, model_registry_path: Optional[str] = None):
        self.model_registry_path = Path(model_registry_path) if model_registry_path else None
        self._last_state: Optional[MachineState] = None

    def snapshot(self, active_runtimes: Optional[List[str]] = None) -> MachineState:
        """Capture current machine state."""
        state = MachineState()
        state.hostname = platform.node()
        state.os = platform.system()
        state.os_version = platform.release()
        state.arch = platform.machine()
        state.cpu_count = os.cpu_count() or 1
        state.cpu_load = self._get_cpu_load()
        mem = self._get_memory()
        state.memory_total_bytes = mem.get("total", 0)
        state.memory_available_bytes = mem.get("available", 0)
        disk = self._get_disk()
        state.disk_total_bytes = disk.get("total", 0)
        state.disk_available_bytes = disk.get("available", 0)
        state.models = self._scan_models()
        state.active_runtimes = active_runtimes or []
        state.capabilities = self._detect_capabilities()
        state.timestamp = time.time()
        state.state_hash = state.compute_hash()
        self._last_state = state
        return state

    def _get_cpu_load(self) -> float:
        try:
            load = os.getloadavg()[0]
            return round(load / max(self.cpu_count_safe(), 1), 3)
        except (AttributeError, OSError):
            return 0.0

    def cpu_count_safe(self) -> int:
        return os.cpu_count() or 1

    def _get_memory(self) -> Dict[str, int]:
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
            )
            total = int(result.stdout.strip()) if result.returncode == 0 else 0
            # Get pressure via vm_stat
            vm = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=5
            )
            available = 0
            if vm.returncode == 0:
                for line in vm.stdout.split("\n"):
                    if "free" in line.lower() or "inactive" in line.lower():
                        parts = line.split(":")
                        if len(parts) == 2:
                            pages = parts[1].strip().rstrip(".")
                            available += int(pages) * 4096
            return {"total": total, "available": available}
        except Exception:
            return {"total": 0, "available": 0}

    def _get_disk(self) -> Dict[str, int]:
        try:
            usage = shutil.disk_usage("/")
            return {"total": usage.total, "available": usage.free}
        except Exception:
            return {"total": 0, "available": 0}

    def _scan_models(self) -> List[ModelAvailability]:
        """Scan for locally available models."""
        models: List[ModelAvailability] = []
        if not self.model_registry_path or not self.model_registry_path.exists():
            return models

        for path in self.model_registry_path.rglob("*.gguf"):
            try:
                stat = path.stat()
                digest = self._hash_file_head(path)
                model_id = path.stem
                models.append(ModelAvailability(
                    model_id=model_id,
                    digest=digest,
                    path=str(path),
                    size_bytes=stat.st_size,
                    quantization=self._detect_quant(path.name),
                ))
            except Exception:
                continue

        for path in self.model_registry_path.rglob("*.safetensors"):
            try:
                stat = path.stat()
                digest = self._hash_file_head(path)
                model_id = path.parent.name
                models.append(ModelAvailability(
                    model_id=model_id,
                    digest=digest,
                    path=str(path),
                    size_bytes=stat.st_size,
                ))
            except Exception:
                continue

        return models

    def _hash_file_head(self, path: Path, head_bytes: int = 65536) -> str:
        """Hash the first 64KB of a file for fast identification."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read(head_bytes))
        return h.hexdigest()

    def _detect_quant(self, filename: str) -> str:
        lower = filename.lower()
        for q in ["q4_k_m", "q4_k_s", "q5_k_m", "q5_k_s", "q8_0", "f16", "f32", "q4_0", "q4_1"]:
            if q in lower:
                return q
        return ""

    def _detect_capabilities(self) -> List[str]:
        """Detect what this machine can do."""
        caps = []
        if shutil.which("container"):
            caps.append("apple-containerization")
        if shutil.which("python3"):
            caps.append("python3")
        if shutil.which("ssh"):
            caps.append("ssh")
        if shutil.which("git"):
            caps.append("git")
        if shutil.which("docker"):
            caps.append("docker")
        if platform.machine() == "arm64":
            caps.append("metal-gpu")
        return caps

    def can_satisfy(self, requirements: dict) -> tuple:
        """Check if this machine can satisfy a set of requirements.

        Returns (satisfied: bool, reasons: list[str]).
        """
        reasons: List[str] = []
        state = self._last_state or self.snapshot()

        # CPU arch
        req_arch = requirements.get("cpu_arch", "")
        if req_arch and req_arch != "any" and state.arch != req_arch:
            reasons.append(f"arch mismatch: need {req_arch}, have {state.arch}")

        # Memory
        req_ram = requirements.get("min_ram_bytes", 0)
        if req_ram and state.memory_available_bytes < req_ram:
            reasons.append(f"insufficient RAM: need {req_ram}, have {state.memory_available_bytes}")

        # Model
        req_model = requirements.get("model_id", "")
        req_model_digest = requirements.get("model_digest", "")
        if req_model:
            found = False
            for m in state.models:
                if m.model_id == req_model:
                    found = True
                    if req_model_digest and m.digest != req_model_digest:
                        reasons.append(
                            f"model {req_model} found but digest mismatch: "
                            f"need {req_model_digest[:16]}, have {m.digest[:16]}"
                        )
                    break
            if not found:
                reasons.append(f"model not found: {req_model}")

        # Tools
        req_tools = requirements.get("required_tools", [])
        for tool in req_tools:
            if tool not in state.capabilities:
                reasons.append(f"tool not available: {tool}")

        return (len(reasons) == 0, reasons)
