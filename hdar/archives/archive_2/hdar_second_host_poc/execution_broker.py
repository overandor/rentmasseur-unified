#!/usr/bin/env python3
"""HDAR Execution Broker — dispatches signed capsules to available execution environments.

The broker accepts a signed capsule and dispatches it to an available provider
(local, colab, ssh, custom) based on the capsule's declared requirements.
The provider returns a successor capsule and evidence packet.

The broker keeps the protocol consistent regardless of where execution occurred.

Usage:
    python3 execution_broker.py --capsule transport_capsule_epoch_1_signed.tar.gz \\
        --host-a-report host_a_build_report.json \\
        --owner-public-key <hex> \\
        --provider local|colab|ssh \\
        --out ./broker_output

    python3 execution_broker.py --capsule ... --provider ssh \\
        --ssh-host user@host --ssh-key ~/.ssh/id_rsa

    python3 execution_broker.py --capsule ... --provider colab \\
        --colab-notebook hdar_host_b_colab.ipynb
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProviderResult:
    """Result from a provider execution."""
    success: bool
    provider_name: str
    provider_platform: str
    host_b_report_path: Optional[Path] = None
    evidence_packet_path: Optional[Path] = None
    successor_capsule_path: Optional[Path] = None
    host_b_public_key: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    raw_output: str = ""


@dataclass
class Provider:
    """Base provider interface."""
    name: str
    description: str
    capabilities: list = field(default_factory=list)

    def execute(self, capsule_path: Path, host_a_report: Path,
                owner_public_key: str, runner_path: Path,
                runner_hash: str, out_dir: Path) -> ProviderResult:
        raise NotImplementedError


class LocalProvider(Provider):
    """Execute on the local machine."""

    def __init__(self):
        super().__init__(
            name="local",
            description="Execute on local machine",
            capabilities=["linux", "macos", "deterministic-tasks"]
        )

    def execute(self, capsule_path: Path, host_a_report: Path,
                owner_public_key: str, runner_path: Path,
                runner_hash: str, out_dir: Path) -> ProviderResult:
        start = time.time()
        result = ProviderResult(
            success=False,
            provider_name=self.name,
            provider_platform=f"local-{sys.platform}",
        )

        cmd = [
            sys.executable, str(runner_path),
            "--out", str(out_dir / "host_b_output"),
            "--host-label", "broker-local-provider",
            "--host-a-report", str(host_a_report),
            "--verify-runner-hash", runner_hash,
            "--owner-public-key", owner_public_key,
            "--operator-identity", "execution-broker-local",
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            result.raw_output = proc.stdout + proc.stderr
            result.duration_seconds = time.time() - start

            if proc.returncode != 0:
                result.error = f"Runner exited with code {proc.returncode}"
                return result

            report_path = out_dir / "host_b_output" / "host_b_report.json"
            if report_path.exists():
                report = json.loads(report_path.read_text())
                result.host_b_report_path = report_path
                result.evidence_packet_path = out_dir / "host_b_output" / "host_b_evidence_packet.json"
                result.successor_capsule_path = out_dir / "host_b_output" / "successor_capsule_epoch_2.tar.gz"
                result.host_b_public_key = report.get("host_b_public_key", "")
                result.provider_platform = report.get("host_b_platform", "")
                result.success = True
            else:
                result.error = "host_b_report.json not found after execution"
        except subprocess.TimeoutExpired:
            result.error = "Execution timed out (120s)"
            result.duration_seconds = time.time() - start
        except Exception as e:
            result.error = str(e)
            result.duration_seconds = time.time() - start

        return result


class SSHProvider(Provider):
    """Execute on a remote host via SSH/SCP."""

    def __init__(self, ssh_host: str, ssh_key: str = "", ssh_port: int = 22):
        super().__init__(
            name="ssh",
            description=f"Execute on remote host {ssh_host} via SSH",
            capabilities=["remote", "linux", "macos", "deterministic-tasks"]
        )
        self.ssh_host = ssh_host
        self.ssh_key = ssh_key
        self.ssh_port = ssh_port

    def execute(self, capsule_path: Path, host_a_report: Path,
                owner_public_key: str, runner_path: Path,
                runner_hash: str, out_dir: Path) -> ProviderResult:
        start = time.time()
        result = ProviderResult(
            success=False,
            provider_name=self.name,
            provider_platform=f"ssh-{self.ssh_host}",
        )

        remote_dir = f"/tmp/hdar-broker-{int(time.time())}"
        ssh_opts = []
        if self.ssh_key:
            ssh_opts.extend(["-i", self.ssh_key])
        ssh_opts.extend(["-p", str(self.ssh_port), "-o", "StrictHostKeyChecking=accept-new"])

        try:
            # Create remote directory
            subprocess.run(["ssh"] + ssh_opts + [self.ssh_host, f"mkdir -p {remote_dir}"],
                         check=True, capture_output=True, timeout=30)

            # Copy files to remote
            for local_file, remote_name in [
                (runner_path, "run_on_host_b.py"),
                (host_a_report, "host_a_build_report.json"),
            ]:
                subprocess.run(["scp"] + ssh_opts + [str(local_file), f"{self.ssh_host}:{remote_dir}/{remote_name}"],
                             check=True, capture_output=True, timeout=60)

            # Execute remotely
            remote_cmd = (
                f"cd {remote_dir} && "
                f"python3 run_on_host_b.py "
                f"--out {remote_dir}/output "
                f"--host-label broker-ssh-provider "
                f"--host-a-report {remote_dir}/host_a_build_report.json "
                f"--verify-runner-hash {runner_hash} "
                f"--owner-public-key {owner_public_key} "
                f"--operator-identity execution-broker-ssh"
            )
            proc = subprocess.run(
                ["ssh"] + ssh_opts + [self.ssh_host, remote_cmd],
                capture_output=True, text=True, timeout=180
            )
            result.raw_output = proc.stdout + proc.stderr
            result.duration_seconds = time.time() - start

            if proc.returncode != 0:
                result.error = f"Remote execution failed (exit {proc.returncode}): {proc.stderr[:500]}"
                return result

            # Copy results back
            local_output = out_dir / "host_b_output"
            local_output.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["scp"] + ssh_opts + ["-r", f"{self.ssh_host}:{remote_dir}/output/", str(local_output)],
                check=True, capture_output=True, timeout=60
            )

            report_path = local_output / "output" / "host_b_report.json"
            if not report_path.exists():
                report_path = local_output / "host_b_report.json"
            if report_path.exists():
                report = json.loads(report_path.read_text())
                result.host_b_report_path = report_path
                result.evidence_packet_path = report_path.parent / "host_b_evidence_packet.json"
                result.successor_capsule_path = report_path.parent / "successor_capsule_epoch_2.tar.gz"
                result.host_b_public_key = report.get("host_b_public_key", "")
                result.provider_platform = report.get("host_b_platform", "")
                result.success = True
            else:
                result.error = "host_b_report.json not found after SCP"

            # Cleanup remote
            subprocess.run(["ssh"] + ssh_opts + [self.ssh_host, f"rm -rf {remote_dir}"],
                         capture_output=True, timeout=30)

        except subprocess.TimeoutExpired:
            result.error = "SSH execution timed out"
            result.duration_seconds = time.time() - start
        except subprocess.CalledProcessError as e:
            result.error = f"SSH command failed: {e.stderr or e}"
            result.duration_seconds = time.time() - start
        except Exception as e:
            result.error = str(e)
            result.duration_seconds = time.time() - start

        return result


class ColabProvider(Provider):
    """Execute on Google Colab (manual step — generates notebook for user to run)."""

    def __init__(self, notebook_path: str = ""):
        super().__init__(
            name="colab",
            description="Generate Colab notebook for manual execution on Google's Linux runtime",
            capabilities=["linux", "x86_64", "gpu-available", "ephemeral"]
        )
        self.notebook_path = notebook_path

    def execute(self, capsule_path: Path, host_a_report: Path,
                owner_public_key: str, runner_path: Path,
                runner_hash: str, out_dir: Path) -> ProviderResult:
        result = ProviderResult(
            success=False,
            provider_name=self.name,
            provider_platform="colab-linux-x86_64 (manual)",
        )

        # Generate a dispatch record for manual Colab execution
        dispatch = {
            "provider": "colab",
            "status": "manual_dispatch_required",
            "instructions": [
                f"1. Upload {capsule_path.name} and {runner_path.name} to Google Colab",
                f"2. Upload {host_a_report.name} to Colab",
                "3. Run the Colab notebook (hdar_host_b_colab.ipynb)",
                "4. Download host_b_report.json, host_b_evidence_packet.json, successor_capsule_epoch_2.tar.gz",
                f"5. Place downloaded files in {out_dir}/host_b_output/",
                "6. Re-run broker with --provider local --verify-only to complete",
            ],
            "capsule_sha256": sha256_file(capsule_path),
            "runner_sha256": runner_hash,
            "owner_public_key": owner_public_key,
            "expected_outputs": [
                "host_b_report.json",
                "host_b_evidence_packet.json",
                "successor_capsule_epoch_2.tar.gz",
            ],
            "notebook": self.notebook_path or "hdar_host_b_colab.ipynb",
            "dispatch_timestamp": utc_now_iso(),
        }

        dispatch_path = out_dir / "colab_dispatch.json"
        dispatch_path.write_text(json.dumps(dispatch, indent=2))

        result.raw_output = json.dumps(dispatch, indent=2)
        result.error = "Colab requires manual execution — see colab_dispatch.json for instructions"
        return result


class ExecutionBroker:
    """Dispatches signed capsules to available execution environments."""

    def __init__(self):
        self.providers: dict[str, Provider] = {}
        self.register_provider(LocalProvider())

    def register_provider(self, provider: Provider):
        self.providers[provider.name] = provider

    def list_providers(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "description": p.description,
                "capabilities": p.capabilities,
            }
            for p in self.providers.values()
        ]

    def resolve_provider(self, requested: str) -> Provider:
        if requested not in self.providers:
            available = ", ".join(self.providers.keys())
            raise ValueError(f"Unknown provider '{requested}'. Available: {available}")
        return self.providers[requested]

    def dispatch(self, capsule_path: Path, host_a_report: Path,
                 owner_public_key: str, runner_path: Path,
                 provider_name: str, out_dir: Path) -> dict:
        """Dispatch capsule to provider and return broker record."""
        broker_start = time.time()

        # Verify inputs exist
        if not capsule_path.exists():
            raise FileNotFoundError(f"Capsule not found: {capsule_path}")
        if not runner_path.exists():
            raise FileNotFoundError(f"Runner not found: {runner_path}")
        if not host_a_report.exists():
            raise FileNotFoundError(f"Host A report not found: {host_a_report}")

        runner_hash = sha256_file(runner_path)
        capsule_hash = sha256_file(capsule_path)

        # Load Host A report to cross-check
        ha_report = json.loads(host_a_report.read_text())
        expected_runner = ha_report.get("transport_bundle", {}).get("sha256", "")
        expected_capsule = ha_report.get("transport_capsule_tar", {}).get("sha256", "")

        pre_checks = {
            "runner_hash_matches_host_a": runner_hash == expected_runner if expected_runner else "no_expected_hash",
            "capsule_hash_matches_host_a": capsule_hash == expected_capsule if expected_capsule else "no_expected_hash",
        }

        # Resolve provider
        provider = self.resolve_provider(provider_name)

        # Execute
        out_dir.mkdir(parents=True, exist_ok=True)
        result = provider.execute(
            capsule_path=capsule_path,
            host_a_report=host_a_report,
            owner_public_key=owner_public_key,
            runner_path=runner_path,
            runner_hash=runner_hash,
            out_dir=out_dir,
        )

        broker_record = {
            "schema": "hdar.execution-broker/v0.1",
            "broker_timestamp": utc_now_iso(),
            "broker_duration_seconds": round(time.time() - broker_start, 3),
            "provider": {
                "name": provider.name,
                "description": provider.description,
                "capabilities": provider.capabilities,
            },
            "input": {
                "capsule_path": str(capsule_path),
                "capsule_sha256": capsule_hash,
                "runner_path": str(runner_path),
                "runner_sha256": runner_hash,
                "host_a_report_path": str(host_a_report),
                "owner_public_key": owner_public_key[:16] + "...",
            },
            "pre_checks": pre_checks,
            "result": {
                "success": result.success,
                "provider_name": result.provider_name,
                "provider_platform": result.provider_platform,
                "error": result.error,
                "duration_seconds": round(result.duration_seconds, 3),
                "host_b_public_key": result.host_b_public_key,
                "outputs": {
                    "host_b_report": str(result.host_b_report_path) if result.host_b_report_path else None,
                    "evidence_packet": str(result.evidence_packet_path) if result.evidence_packet_path else None,
                    "successor_capsule": str(result.successor_capsule_path) if result.successor_capsule_path else None,
                },
            },
            "protocol_transition": "AUTHENTICATED -> EXECUTED -> CONTINUED -> SUCCESSOR_CREATED" if result.success else "AUTHENTICATED -> FAILED",
        }

        # Save broker record
        record_path = out_dir / "broker_record.json"
        record_path.write_text(json.dumps(broker_record, indent=2, sort_keys=True))

        return broker_record


def main() -> int:
    ap = argparse.ArgumentParser(description="HDAR Execution Broker")
    ap.add_argument("--capsule", required=True, help="Path to signed transport capsule tar.gz")
    ap.add_argument("--runner", required=True, help="Path to run_on_host_b.py")
    ap.add_argument("--host-a-report", required=True, help="Path to host_a_build_report.json")
    ap.add_argument("--owner-public-key", required=True, help="Owner Ed25519 public key hex")
    ap.add_argument("--provider", default="local", choices=["local", "ssh", "colab"],
                    help="Execution provider to use")
    ap.add_argument("--out", default="./broker_output", help="Output directory")
    # SSH options
    ap.add_argument("--ssh-host", default="", help="SSH host (user@host) for SSH provider")
    ap.add_argument("--ssh-key", default="", help="SSH private key path for SSH provider")
    ap.add_argument("--ssh-port", default=22, type=int, help="SSH port")
    # Colab options
    ap.add_argument("--colab-notebook", default="", help="Path to Colab notebook for Colab provider")
    # Listing
    ap.add_argument("--list-providers", action="store_true", help="List available providers and exit")
    args = ap.parse_args()

    broker = ExecutionBroker()

    if args.ssh_host:
        broker.register_provider(SSHProvider(args.ssh_host, args.ssh_key, args.ssh_port))
    if args.colab_notebook or args.provider == "colab":
        broker.register_provider(ColabProvider(args.colab_notebook))

    if args.list_providers:
        providers = broker.list_providers()
        print(json.dumps(providers, indent=2))
        return 0

    try:
        record = broker.dispatch(
            capsule_path=Path(args.capsule),
            host_a_report=Path(args.host_a_report),
            owner_public_key=args.owner_public_key,
            runner_path=Path(args.runner),
            provider_name=args.provider,
            out_dir=Path(args.out),
        )

        print(json.dumps(record, indent=2, sort_keys=True))

        if record["result"]["success"]:
            print(f"\nBroker: execution succeeded via {args.provider}")
            print(f"  Duration: {record['result']['duration_seconds']}s")
            print(f"  Platform: {record['result']['provider_platform']}")
            print(f"  Outputs in: {args.out}")
            return 0
        else:
            print(f"\nBroker: execution failed via {args.provider}")
            print(f"  Error: {record['result']['error']}")
            return 1

    except Exception as e:
        print(f"Broker error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
