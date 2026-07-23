"""Capability continuity — authority mapping between providers.

The central invariant: migration may preserve or reduce authority,
but it may never silently expand it.

Capabilities are typed, deny-by-default. Each capability has:
  - name: e.g. "filesystem.write", "network.egress", "budget.spend"
  - scope: e.g. "/workspace", "api.example.com", "$5"
  - granted: bool

The compiler maps source capabilities to destination capabilities.
Any mapping that would broaden authority is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Capability:
    """A single typed capability grant."""
    name: str          # e.g. "filesystem.write"
    scope: str         # e.g. "/workspace" or "api.example.com"
    granted: bool = True
    constraints: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "scope": self.scope,
            "granted": self.granted,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Capability":
        return cls(
            name=d["name"],
            scope=d["scope"],
            granted=d.get("granted", True),
            constraints=d.get("constraints", {}),
        )


# ─── Scope comparison ─────────────────────────────────────

def is_scope_broader(src_scope: str, dst_scope: str) -> bool:
    """Returns True if dst_scope is broader than src_scope."""
    if dst_scope == "*" and src_scope != "*":
        return True
    if src_scope == "/workspace" and dst_scope == "/":
        return True
    if src_scope == "/workspace" and dst_scope == "*":
        return True
    # Exact match or narrower is fine
    if dst_scope == src_scope:
        return False
    # Subdirectory is narrower
    if dst_scope.startswith(src_scope + "/"):
        return False
    # Everything else is broader
    if not src_scope.startswith(dst_scope + "/"):
        return True
    return False


def is_budget_higher(src: str, dst: str) -> bool:
    """Compare budget scopes. Returns True if dst allows more than src."""
    def parse(s: str) -> float:
        s = s.replace("$", "").replace(",", "").strip()
        try:
            return float(s)
        except ValueError:
            return 0.0
    return parse(dst) > parse(src)


# ─── Capability compiler ─────────────────────────────────

class CapabilityCompiler:
    """Maps source capabilities to destination provider capabilities.

    Enforces the invariant: authority may be preserved or reduced,
    but never silently increased.
    """

    def __init__(self):
        self._rules: Dict[str, callable] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default mapping rules for known capability types."""
        self._rules["filesystem.read"] = self._map_filesystem
        self._rules["filesystem.write"] = self._map_filesystem
        self._rules["network.egress"] = self._map_network
        self._rules["budget.spend"] = self._map_budget
        self._rules["deploy"] = self._map_deploy
        self._rules["shell.exec"] = self._map_shell

    def compile(
        self,
        source_caps: List[Capability],
        destination_policy: Dict[str, str],
    ) -> Tuple[List[Capability], List[str]]:
        """Map source capabilities to destination.

        Returns (destination_caps, rejections).
        Each rejection explains why a capability was denied.
        """
        dest_caps: List[Capability] = []
        rejections: List[str] = []

        for src_cap in source_caps:
            if not src_cap.granted:
                continue

            rule = self._rules.get(src_cap.name)
            if rule is None:
                # Unknown capability — deny by default
                rejections.append(
                    f"unknown capability '{src_cap.name}' — denied by default"
                )
                continue

            dst_cap, reason = rule(src_cap, destination_policy)
            if dst_cap is not None:
                dest_caps.append(dst_cap)
            else:
                rejections.append(reason)

        return dest_caps, rejections

    def _map_filesystem(self, src: Capability, policy: Dict) -> Tuple[Optional[Capability], str]:
        dst_scope = policy.get("filesystem.root", "/workspace")
        if is_scope_broader(src.scope, dst_scope):
            return None, (
                f"filesystem scope '{dst_scope}' is broader than source '{src.scope}' "
                f"— capability broadening rejected"
            )
        return Capability(
            name=src.name,
            scope=dst_scope,
            granted=True,
            constraints=src.constraints,
        ), ""

    def _map_network(self, src: Capability, policy: Dict) -> Tuple[Optional[Capability], str]:
        allowlist = policy.get("network.allowlist", "")
        if allowlist and src.scope != "*":
            # Check if source scope is in the allowlist
            allowed = [a.strip() for a in allowlist.split(",")]
            if src.scope not in allowed and "*" not in allowed:
                return None, (
                    f"network scope '{src.scope}' not in destination allowlist "
                    f"[{allowlist}] — capability denied"
                )
        if allowlist == "" and src.scope == "*":
            return None, "wildcard network not allowed in destination — denied"
        return Capability(
            name=src.name,
            scope=src.scope,
            granted=True,
            constraints={"allowlist": allowlist} if allowlist else {},
        ), ""

    def _map_budget(self, src: Capability, policy: Dict) -> Tuple[Optional[Capability], str]:
        dst_budget = policy.get("budget.max", src.scope)
        if is_budget_higher(src.scope, dst_budget):
            return None, (
                f"budget '{dst_budget}' exceeds source '{src.scope}' "
                f"— capability broadening rejected"
            )
        return Capability(
            name=src.name,
            scope=dst_budget,
            granted=True,
        ), ""

    def _map_deploy(self, src: Capability, policy: Dict) -> Tuple[Optional[Capability], str]:
        deploy_allowed = policy.get("deploy.allowed", "false")
        if deploy_allowed != "true":
            return None, "deploy not allowed in destination policy — denied"
        return Capability(
            name=src.name,
            scope=src.scope,
            granted=True,
        ), ""

    def _map_shell(self, src: Capability, policy: Dict) -> Tuple[Optional[Capability], str]:
        shell_allowed = policy.get("shell.allowed", "false")
        if shell_allowed != "true":
            return None, "shell not allowed in destination policy — denied"
        return Capability(
            name=src.name,
            scope=src.scope,
            granted=True,
        ), ""

    def verify_non_expansion(
        self,
        source_caps: List[Capability],
        dest_caps: List[Capability],
    ) -> Tuple[bool, List[str]]:
        """Verify that destination capabilities do not expand source."""
        violations: List[str] = []
        src_map = {c.name: c for c in source_caps if c.granted}

        for dst in dest_caps:
            if not dst.granted:
                continue
            src = src_map.get(dst.name)
            if src is None:
                violations.append(
                    f"destination grants '{dst.name}' not present in source — expansion"
                )
                continue
            if dst.name.startswith("filesystem"):
                if is_scope_broader(src.scope, dst.scope):
                    violations.append(
                        f"filesystem scope expanded: '{src.scope}' → '{dst.scope}'"
                    )
            elif dst.name == "budget.spend":
                if is_budget_higher(src.scope, dst.scope):
                    violations.append(
                        f"budget expanded: '{src.scope}' → '{dst.scope}'"
                    )

        return len(violations) == 0, violations
