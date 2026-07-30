"""Provider factory — auto-detects available execution providers.

Tries AppleContainerProvider first (real VM-backed isolation on Apple silicon).
Falls back to UnsafeHostProvider for development when the `container` CLI
is not installed.

Usage:
    from provider_factory import create_provider, ProviderType

    # Auto-detect best available
    provider = create_provider()

    # Force a specific type
    provider = create_provider(ProviderType.APPLE_CONTAINER)
    provider = create_provider(ProviderType.UNSAFE_HOST)
"""

from __future__ import annotations

import enum
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from providers.base import ProviderBase
from providers.unsafe_host import UnsafeHostProvider


class ProviderType(enum.Enum):
    AUTO = "auto"
    APPLE_CONTAINER = "apple-container"
    UNSAFE_HOST = "unsafe-host"


def is_container_cli_available() -> bool:
    """Check if Apple's `container` CLI is installed."""
    return shutil.which("container") is not None


def create_provider(
    provider_type: ProviderType = ProviderType.AUTO,
    sandbox_root: str = "/tmp/hdar_sandbox",
) -> ProviderBase:
    """Create an execution provider.

    Args:
        provider_type: AUTO tries apple-container first, falls back to unsafe-host.
        sandbox_root: Root directory for unsafe-host sandbox.

    Returns:
        A ProviderBase implementation.

    Raises:
        RuntimeError: If apple-container is explicitly requested but unavailable.
    """
    if provider_type == ProviderType.APPLE_CONTAINER:
        if not is_container_cli_available():
            raise RuntimeError(
                "Apple 'container' CLI not found. Install with: brew install container"
            )
        from providers.apple_container import AppleContainerProvider
        return AppleContainerProvider()

    if provider_type == ProviderType.UNSAFE_HOST:
        return UnsafeHostProvider(sandbox_root)

    # AUTO: try apple-container, fall back to unsafe-host
    if is_container_cli_available():
        try:
            from providers.apple_container import AppleContainerProvider
            return AppleContainerProvider()
        except Exception:
            pass

    return UnsafeHostProvider(sandbox_root)


def describe_available_providers() -> dict:
    """Return a dict describing which providers are available and why."""
    container_available = is_container_cli_available()
    return {
        "apple_container": {
            "available": container_available,
            "description": "VM-backed Linux isolation via Apple Containerization framework",
            "install_hint": "brew install container" if not container_available else None,
        },
        "unsafe_host": {
            "available": True,
            "description": "Direct subprocess execution (development only — NOT isolated)",
            "install_hint": None,
        },
    }
