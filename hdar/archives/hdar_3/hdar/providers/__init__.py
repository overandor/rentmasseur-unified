"""Execution providers for the Hardware-Detached Agent Runtime."""

from .base import ProviderBase, RuntimeRecord, ExecutionResult
from .unsafe_host import UnsafeHostProvider

__all__ = [
    "ProviderBase", "RuntimeRecord", "ExecutionResult",
    "UnsafeHostProvider",
]

# AppleContainerProvider and RemoteSSHProvider require external deps
# Import them explicitly when available:
#   from providers.apple_container import AppleContainerProvider
#   from providers.remote_ssh import RemoteSSHProvider
