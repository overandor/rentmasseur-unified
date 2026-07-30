"""Dual exact/semantic restoration contract.

Explicitly distinguishes:
  - Exact restoration: compatible process, memory, and runtime state
  - Semantic restoration: reconstructed task continuity on incompatible hardware
  - Degraded: partial restoration with known losses

The system must report what was resumed, replayed, translated, or discarded.
This prevents the industry habit of calling every reload a "restoration."
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class RestorationClass(Enum):
    EXACT = "exact"
    SEMANTIC = "semantic"
    DEGRADED = "degraded"


@dataclass
class CompatibilityProfile:
    """Describes what a source and destination runtime can preserve."""
    # Source environment
    source_os: str = ""
    source_arch: str = ""
    source_runtime: str = ""        # e.g. "apple-container", "unsafe-host"
    source_model_engine: str = ""   # e.g. "mlx", "vllm", "llama.cpp"

    # Destination environment
    dest_os: str = ""
    dest_arch: str = ""
    dest_runtime: str = ""
    dest_model_engine: str = ""

    # What can be preserved exactly
    filesystem_exact: bool = True       # content-addressed blocks are portable
    identity_exact: bool = True         # cryptographic identity is portable
    lineage_exact: bool = True          # epoch chain is portable
    capabilities_exact: bool = True     # capability grants are portable
    receipts_exact: bool = True         # signed receipts are portable
    goals_exact: bool = True            # structured task state is portable

    # What may NOT be preserved exactly
    process_state_exact: bool = False   # live process memory, registers
    kv_cache_exact: bool = False        # model attention cache
    sampling_state_exact: bool = False  # RNG state for generation
    network_sessions_exact: bool = False  # TCP/TLS/WebSocket connections
    open_file_handles_exact: bool = False  # file descriptors
    shared_memory_exact: bool = False   # IPC shared memory
    gpu_state_exact: bool = False       # accelerator memory/compute state

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: dict) -> "CompatibilityProfile":
        return cls(**{k: d.get(k) for k in [
            "source_os", "source_arch", "source_runtime", "source_model_engine",
            "dest_os", "dest_arch", "dest_runtime", "dest_model_engine",
            "filesystem_exact", "identity_exact", "lineage_exact",
            "capabilities_exact", "receipts_exact", "goals_exact",
            "process_state_exact", "kv_cache_exact", "sampling_state_exact",
            "network_sessions_exact", "open_file_handles_exact",
            "shared_memory_exact", "gpu_state_exact",
        ]})


@dataclass
class RestorationReport:
    """Reports exactly what was restored, reconstructed, or discarded."""
    restoration_class: RestorationClass
    compatible: bool

    # What was preserved exactly
    preserved_exact: List[str] = field(default_factory=list)

    # What was reconstructed semantically
    reconstructed: List[str] = field(default_factory=list)

    # What was discarded (cannot be restored)
    discarded: List[str] = field(default_factory=list)

    # Whether numerical divergence is possible
    divergence_possible: bool = False
    divergence_notes: str = ""

    # Whether user approval is required before continuing
    user_approval_required: bool = False

    # Compatibility details
    source_profile: Optional[dict] = None
    dest_profile: Optional[dict] = None

    # Workspace verification
    workspace_hash_matches: bool = False
    identity_verified: bool = False
    lineage_verified: bool = False

    def to_dict(self) -> dict:
        return {
            "restoration_class": self.restoration_class.value,
            "compatible": self.compatible,
            "preserved_exact": self.preserved_exact,
            "reconstructed": self.reconstructed,
            "discarded": self.discarded,
            "divergence_possible": self.divergence_possible,
            "divergence_notes": self.divergence_notes,
            "user_approval_required": self.user_approval_required,
            "source_profile": self.source_profile,
            "dest_profile": self.dest_profile,
            "workspace_hash_matches": self.workspace_hash_matches,
            "identity_verified": self.identity_verified,
            "lineage_verified": self.lineage_verified,
        }


class RestorationContract:
    """Determines and reports the restoration class for a migration.

    The contract never falsely claims that semantic restoration is
    bit-identical. It states what was restored exactly, what was
    reconstructed, what was translated, what was discarded, whether
    numerical divergence is possible, and whether user approval is required.
    """

    def __init__(self):
        pass

    def classify(
        self,
        source: CompatibilityProfile,
        dest: CompatibilityProfile,
    ) -> RestorationClass:
        """Determine the restoration class from compatibility profiles."""
        # Check if everything is exact
        all_exact = all([
            source.filesystem_exact and dest.filesystem_exact,
            source.identity_exact and dest.identity_exact,
            source.lineage_exact and dest.lineage_exact,
            source.capabilities_exact and dest.capabilities_exact,
            source.receipts_exact and dest.receipts_exact,
            source.goals_exact and dest.goals_exact,
            source.process_state_exact and dest.process_state_exact,
            source.kv_cache_exact and dest.kv_cache_exact,
            source.sampling_state_exact and dest.sampling_state_exact,
            source.network_sessions_exact and dest.network_sessions_exact,
            source.open_file_handles_exact and dest.open_file_handles_exact,
            source.shared_memory_exact and dest.shared_memory_exact,
            source.gpu_state_exact and dest.gpu_state_exact,
        ])

        if all_exact:
            # Also check environment compatibility
            if (source.source_os == dest.dest_os and
                source.source_arch == dest.dest_arch and
                source.source_runtime == dest.dest_runtime and
                source.source_model_engine == dest.dest_model_engine):
                return RestorationClass.EXACT

        # Check if at least the durable truth layer is preserved
        durable_ok = all([
            source.filesystem_exact and dest.filesystem_exact,
            source.identity_exact and dest.identity_exact,
            source.lineage_exact and dest.lineage_exact,
            source.capabilities_exact and dest.capabilities_exact,
            source.receipts_exact and dest.receipts_exact,
            source.goals_exact and dest.goals_exact,
        ])

        if durable_ok:
            return RestorationClass.SEMANTIC

        return RestorationClass.DEGRADED

    def report(
        self,
        source: CompatibilityProfile,
        dest: CompatibilityProfile,
        workspace_hash_matches: bool = False,
        identity_verified: bool = False,
        lineage_verified: bool = False,
    ) -> RestorationReport:
        """Generate a detailed restoration report."""
        cls = self.classify(source, dest)

        preserved: List[str] = []
        reconstructed: List[str] = []
        discarded: List[str] = []
        divergence_possible = False
        divergence_notes = ""
        user_approval_required = False

        # Durable truth layer — always portable via content addressing
        durable_fields = [
            ("filesystem_exact", "workspace files (content-addressed blocks)"),
            ("identity_exact", "agent cryptographic identity"),
            ("lineage_exact", "epoch lineage and parent capsule hash"),
            ("capabilities_exact", "capability grants"),
            ("receipts_exact", "signed receipt chain"),
            ("goals_exact", "pending goals and continuation point"),
        ]

        for field_name, label in durable_fields:
            if getattr(source, field_name) and getattr(dest, field_name):
                preserved.append(label)
            elif getattr(dest, field_name):
                reconstructed.append(label)
            else:
                discarded.append(label)

        # Runtime state — may not survive cross-provider migration
        runtime_fields = [
            ("process_state_exact", "live process memory and registers"),
            ("kv_cache_exact", "model KV cache and attention state"),
            ("sampling_state_exact", "sampling RNG state"),
            ("network_sessions_exact", "active TCP/TLS/WebSocket sessions"),
            ("open_file_handles_exact", "open file descriptors"),
            ("shared_memory_exact", "IPC shared memory segments"),
            ("gpu_state_exact", "accelerator compute and memory state"),
        ]

        for field_name, label in runtime_fields:
            if getattr(source, field_name) and getattr(dest, field_name):
                preserved.append(label)
            elif cls == RestorationClass.SEMANTIC:
                discarded.append(label)
                divergence_possible = True
            else:
                discarded.append(label)

        if cls == RestorationClass.SEMANTIC:
            divergence_notes = (
                "Runtime state (process memory, KV cache, network sessions, "
                "GPU state) was discarded. The agent's durable identity, "
                "workspace, goals, capabilities, and evidence are preserved "
                "exactly. Inference will resume from the continuation point, "
                "not from the exact token position. Generated output may "
                "diverge from what the original runtime would have produced."
            )
            user_approval_required = True

        if cls == RestorationClass.DEGRADED:
            divergence_notes = (
                "Some durable truth layer components could not be restored. "
                "The agent may not be a trustworthy continuation. Manual "
                "review required before proceeding."
            )
            user_approval_required = True

        return RestorationReport(
            restoration_class=cls,
            compatible=cls != RestorationClass.DEGRADED,
            preserved_exact=preserved,
            reconstructed=reconstructed,
            discarded=discarded,
            divergence_possible=divergence_possible,
            divergence_notes=divergence_notes,
            user_approval_required=user_approval_required,
            source_profile=source.to_dict(),
            dest_profile=dest.to_dict(),
            workspace_hash_matches=workspace_hash_matches,
            identity_verified=identity_verified,
            lineage_verified=lineage_verified,
        )

    def same_runtime_profile(
        self, os_name: str, arch: str, runtime: str, engine: str
    ) -> CompatibilityProfile:
        """Create a profile where source and destination are identical."""
        return CompatibilityProfile(
            source_os=os_name, source_arch=arch,
            source_runtime=runtime, source_model_engine=engine,
            dest_os=os_name, dest_arch=arch,
            dest_runtime=runtime, dest_model_engine=engine,
            process_state_exact=True,
            kv_cache_exact=True,
            sampling_state_exact=True,
            network_sessions_exact=True,
            open_file_handles_exact=True,
            shared_memory_exact=True,
            gpu_state_exact=True,
        )

    def cross_provider_profile(
        self,
        src_os: str, src_arch: str, src_engine: str,
        dst_os: str, dst_arch: str, dst_engine: str,
    ) -> Tuple[CompatibilityProfile, CompatibilityProfile]:
        """Create source and dest profiles for a cross-provider migration."""
        source = CompatibilityProfile(
            source_os=src_os, source_arch=src_arch,
            source_runtime="source", source_model_engine=src_engine,
            dest_os=src_os, dest_arch=src_arch,
            dest_runtime="source", dest_model_engine=src_engine,
            process_state_exact=True,
            kv_cache_exact=True,
            sampling_state_exact=True,
        )
        dest = CompatibilityProfile(
            source_os=src_os, source_arch=src_arch,
            source_runtime="source", source_model_engine=src_engine,
            dest_os=dst_os, dest_arch=dst_arch,
            dest_runtime="destination", dest_model_engine=dst_engine,
            # Durable truth layer is always portable
            filesystem_exact=True,
            identity_exact=True,
            lineage_exact=True,
            capabilities_exact=True,
            receipts_exact=True,
            goals_exact=True,
            # Runtime state is NOT portable across providers
            process_state_exact=False,
            kv_cache_exact=False,
            sampling_state_exact=False,
        )
        return source, dest
