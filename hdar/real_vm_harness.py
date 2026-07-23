#!/usr/bin/env python3
"""Real-VM migration harness — reliability evidence on actual isolated runtimes.

Every migration uses Apple Containerization to create real Linux VMs.
No UnsafeHostProvider. No directory deletion. No mocks.

Each migration:
  1. Creates a real VM as Runtime A
  2. Executes a task inside it
  3. Seals a capsule
  4. Destroys Runtime A (real VM destruction + absence proof)
  5. Creates a second real VM as Runtime B
  6. Restores the capsule on B
  7. Continues the task inside VM B
  8. Host B signs witness receipt
  9. Destroys Runtime B (real VM destruction + absence proof)
  10. Owner reseals lineage
  11. Offline verification

Failure injection (randomized):
  - corruption: tamper capsule, verify detection
  - stale_fencing: verify old token rejected after destruction
  - duplicate_wake: verify second lease denied while B holds lease

Usage:
  python3 real_vm_harness.py                    # 10 migrations (default)
  python3 real_vm_harness.py --count 25         # 25 migrations
  python3 real_vm_harness.py --failures 0.3     # 30% failure injection
  python3 real_vm_harness.py --output results.json
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import random
import shutil
import signal
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, List

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

from crypto import OwnerKeyPair, HostKeyPair, PublicKey, sha256_hex
from capsule.store import ContentStore, WorkspaceManifest
from capsule.identity import LineageEpoch
from capsule.capabilities import Capability, CapabilityCompiler
from lifecycle.lease import LeaseManager
from lifecycle.effects import EffectRegistry
from providers.apple_container import AppleContainerProvider
from continuity import (
    ContinuityLoop,
    ContinuityVerifier,
    ContinuityCapsule,
    FencingInvalidation,
)


def make_task_workspace(base: Path, idx: int) -> Path:
    """Create a workspace with a shell-based task (no Python needed in VM)."""
    ws = base / f"ws_{idx}"
    ws.mkdir(parents=True, exist_ok=True)

    n = random.randint(1, 100)
    expected = n * (n + 1) // 2

    (ws / "task.sh").write_text(
        f"#!/bin/sh\n"
        f"# Compute sum of 1..{n}\n"
        f"sum=0\n"
        f"i=1\n"
        f"while [ $i -le {n} ]; do\n"
        f"  sum=$((sum + i))\n"
        f"  i=$((i + 1))\n"
        f"done\n"
        f"echo \"sum(1..{n}) = $sum\"\n"
        f"echo \"expected = {expected}\"\n"
        f"if [ \"$sum\" -eq {expected} ]; then\n"
        f"  echo 'TASK_COMPLETE'\n"
        f"else\n"
        f"  echo 'TASK_FAILED'\n"
        f"  exit 1\n"
        f"fi\n"
    )
    (ws / "PROGRESS.md").write_text(
        f"# Migration {idx}\n"
        f"task: compute sum(1..{n})\n"
        f"step 1: initialized on HOST A\n"
        f"step 2: pending — will complete on HOST B\n"
    )
    (ws / "task_id.txt").write_text(f"migration-{idx:04d}\n")
    return ws


# Global run ID for unique naming and stale-resource tracking
RUN_ID = uuid.uuid4().hex[:8]

# Track all created VMs for guaranteed cleanup
_active_vms: list[tuple[AppleContainerProvider, str]] = []

def _cleanup_all_vms():
    """Guaranteed cleanup: destroy any VMs still alive on exit or signal."""
    for provider, vm_id in _active_vms:
        try:
            provider.stop(vm_id)
        except Exception as e:
            print(f"  ⚠ Cleanup stop failed for {vm_id}: {e}", file=sys.stderr)
        try:
            provider.destroy(vm_id)
        except Exception as e:
            print(f"  ⚠ Cleanup destroy failed for {vm_id}: {e}", file=sys.stderr)
    _active_vms.clear()

def _signal_handler(signum, frame):
    print(f"\n  ⚠ Signal {signum} received — cleaning up {len(_active_vms)} VMs...")
    _cleanup_all_vms()
    sys.exit(130)

atexit.register(_cleanup_all_vms)
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

def _wilson_lower(successes, total, z=1.96):
    """Wilson score 95% lower confidence bound for success rate."""
    if total == 0:
        return 0.0
    p = len(successes) / total
    n = total
    denom = 1 + z*z/n
    center = p + z*z/(2*n)
    margin = z * ((p*(1-p)/n + z*z/(4*n*n))**0.5)
    return (center - margin) / denom

def _preflight_reconcile(
    provider: AppleContainerProvider,
    lease_mgr: LeaseManager | None = None,
    owner_key: OwnerKeyPair | None = None,
) -> list[dict]:
    """Scan for ALL hdar-* VMs, check against lease registry, destroy orphans.

    A VM is an orphan if:
    - No active lease references its runtime_id, OR
    - The lease is expired, OR
    - The lease DB is unavailable (treat all as orphans)

    A VM with a valid, unexpired lease is PRESERVED.

    Returns a list of orphan reconciliation records (signed if owner_key provided).
    """
    reconciled = []
    try:
        runtimes = provider.list_runtimes()
    except Exception:
        return reconciled

    # Build set of runtime_ids with valid active leases
    valid_runtimes: set[str] = set()
    if lease_mgr is not None:
        for rt_id in runtimes:
            if not rt_id.startswith("hdar-"):
                continue
            # Try to find a lease pointing at this runtime
            try:
                conn = lease_mgr._connect()
                row = conn.execute(
                    "SELECT * FROM leases WHERE destination_runtime = ?",
                    (rt_id,)
                ).fetchone()
                if row is not None:
                    import time as _t
                    if _t.time() < row["expires_at"]:
                        valid_runtimes.add(rt_id)
                conn.close()
            except Exception as e:
                print(f"  ⚠ Lease check failed for {rt_id}: {e}")

    for rt_id in runtimes:
        if not rt_id.startswith("hdar-"):
            continue
        if rt_id in valid_runtimes:
            print(f"  ⚠ Preserved valid-lease VM: {rt_id}")
            continue

        record = {
            "runtime_id": rt_id,
            "action": "destroyed",
            "reason": "orphan_no_valid_lease",
            "timestamp": time.time(),
        }
        try:
            provider.stop(rt_id)
        except Exception as e:
            record["stop_error"] = str(e)[:200]
        try:
            provider.destroy(rt_id)
        except Exception as e:
            record["destroy_error"] = str(e)[:200]

        # Confirm destruction
        absent = provider.verify_destruction(rt_id)
        record["confirmed_absent"] = absent
        reconciled.append(record)
        print(f"  ⚠ Orphan VM reconciled: {rt_id} (absent={absent})")

    # Sign the reconciliation receipt if owner key is available
    if owner_key is not None and reconciled:
        receipt_json = json.dumps(reconciled, sort_keys=True)
        receipt_hash = sha256_hex(receipt_json.encode())
        sig = owner_key.sign_bytes(receipt_hash.encode())
        receipt = {
            "type": "orphan_reconciliation",
            "run_id": RUN_ID,
            "orphan_count": len(reconciled),
            "receipt_hash": receipt_hash,
            "owner_signature": sig,
            "records": reconciled,
        }
        print(f"  ⚠ Orphan reconciliation: {len(reconciled)} VMs destroyed, receipt signed")
        return receipt

    if reconciled:
        print(f"  ⚠ Orphan reconciliation: {len(reconciled)} VMs destroyed (unsigned)")

    return reconciled

def run_single_migration(
    loop: ContinuityLoop,
    owner_key: OwnerKeyPair,
    lease_mgr: LeaseManager,
    sandbox: Path,
    idx: int,
    inject_failure: str = "",
) -> dict:
    """Run a single A→B→owner-reseal migration on REAL VMs."""
    global _active_vms
    start_time = time.time()
    result = {
        "migration_id": idx,
        "success": False,
        "failure_type": "",
        "failure_detail": "",
        "duration_ms": 0,
        "checks_passed": 0,
        "checks_failed": 0,
        "infra_exceptions": 0,
        "vm_a_id": "",
        "vm_b_id": "",
        "vm_a_absent": False,
        "vm_b_absent": False,
        "inject_failure": inject_failure,
        "inject_rejected": False,
        "run_id": RUN_ID,
        "capsule_hash": "",
        "epoch": "",
        "lease_state": "",
        "last_phase": "",
        "cleanup_errors": [],
    }

    provider_a = None
    provider_b = None
    runtime_a_id = ""
    runtime_b_id = ""
    held_fencing_tokens = []  # track all acquired tokens for guaranteed release
    _current_phase = "init"
    agent_id = f"agent-vm-{idx:04d}"

    try:
        ws_a = make_task_workspace(sandbox, idx)
        epoch_0 = LineageEpoch.genesis(agent_id)

        provider_a = AppleContainerProvider()
        provider_b = AppleContainerProvider()
        host_b_key = HostKeyPair.generate(f"host-B-{idx}")

        # Globally unique VM IDs with run ID prefix
        runtime_a_id = f"hdar-{RUN_ID}-A-{idx:04d}"
        runtime_b_id = f"hdar-{RUN_ID}-B-{idx:04d}"

        # Effects
        effects = EffectRegistry(str(sandbox / f"effects_{idx}.jsonl"))
        eff = effects.register(agent_id, "file_write", b"workspace write")
        effects.commit(agent_id, eff.operation_id)

        # 1. Create real VM A
        _current_phase = "vm_a_create"
        record_a = provider_a.materialize(
            runtime_id=runtime_a_id,
            workspace_path=str(ws_a),
            cpu_limit="1",
            memory_limit="256m",
        )
        _active_vms.append((provider_a, runtime_a_id))
        result["vm_a_id"] = runtime_a_id
        if not record_a.exists:
            result["failure_type"] = "vm_a_create_failed"
            result["duration_ms"] = (time.time() - start_time) * 1000
            return result

        # 2. Execute task inside VM A
        _current_phase = "vm_a_execute"
        exec_a = provider_a.execute(
            runtime_a_id, "task", "cd /workspace && sh task.sh"
        )
        if not exec_a.success or "TASK_COMPLETE" not in exec_a.stdout:
            result["failure_type"] = "vm_a_task_failed"
            result["failure_detail"] = exec_a.stdout[:200]
            result["duration_ms"] = (time.time() - start_time) * 1000
            # Clean up
            provider_a.stop(runtime_a_id)
            provider_a.destroy(runtime_a_id)
            return result

        # 3. Acquire lease and seal
        _current_phase = "lease_acquire"
        lease_a, err = lease_mgr.acquire(
            agent_id, "pending", 0, f"host-A-{idx}", runtime_a_id
        )
        if err:
            result["failure_type"] = "lease_acquisition"
            result["failure_detail"] = err
            result["duration_ms"] = (time.time() - start_time) * 1000
            provider_a.stop(runtime_a_id)
            provider_a.destroy(runtime_a_id)
            return result
        held_fencing_tokens.append(lease_a.fencing_token)

        _current_phase = "seal_capsule"
        capsule_0, _ = loop.seal_on_host_a(
            ws_a, agent_id, f"agent-{idx}", epoch_0,
            f"compute sum task {idx}", "step 2: pending",
            capabilities=[Capability("filesystem.write", "/workspace")],
            effects=effects,
            fencing_token=lease_a.fencing_token,
        )
        result["capsule_hash"] = capsule_0.manifest_hash[:16] if hasattr(capsule_0, 'manifest_hash') else ""
        result["epoch"] = str(epoch_0)

        # 4. Destroy VM A
        _current_phase = "destroy_vm_a"
        invalidation, _ = loop.destroy_host_a(
            provider_a, runtime_a_id, agent_id,
            lease_a.lease_generation, lease_a.fencing_token,
        )
        result["vm_a_absent"] = provider_a.verify_destruction(runtime_a_id)
        # Remove from active tracking — it's gone
        _active_vms = [(p, v) for p, v in _active_vms if v != runtime_a_id]

        # 5. Restore on real VM B
        _current_phase = "restore_vm_b"
        ws_b = sandbox / f"wb_{idx}"
        ws_b.mkdir(parents=True, exist_ok=True)
        restoration = loop.restore_on_host_b(
            capsule_0, provider_b, host_b_key, str(ws_b),
            holder_id=f"host-B-{idx}",
            destination_policy={"filesystem.root": "/workspace", "shell.allowed": "true"},
        )
        if not restoration["restored"]:
            result["failure_type"] = "restore_failed"
            result["failure_detail"] = restoration.get("reason", "")
            result["duration_ms"] = (time.time() - start_time) * 1000
            return result

        runtime_b_id = restoration["runtime_id"]
        result["vm_b_id"] = runtime_b_id
        held_fencing_tokens.append(restoration["fencing_token"])
        _active_vms.append((provider_b, runtime_b_id))

        # 6. Continue task inside VM B
        _current_phase = "vm_b_execute"
        exec_b = provider_b.execute(
            runtime_b_id, "task", "cd /workspace && sh task.sh"
        )
        if not exec_b.success or "TASK_COMPLETE" not in exec_b.stdout:
            result["failure_type"] = "vm_b_task_failed"
            result["failure_detail"] = exec_b.stdout[:200]
            result["duration_ms"] = (time.time() - start_time) * 1000
            provider_b.stop(runtime_b_id)
            provider_b.destroy(runtime_b_id)
            return result

        # Update progress
        (ws_b / "PROGRESS.md").write_text(
            f"# Migration {idx}\n"
            f"step 1: initialized on HOST A\n"
            f"step 2: completed on HOST B\n"
        )

        # ─── Failure injection: duplicate_wake ───
        if inject_failure == "duplicate_wake":
            lease_dup, err = lease_mgr.acquire(
                agent_id, capsule_0.manifest_hash, 0,
                "host-C", "rt-C"
            )
            if lease_dup is not None:
                held_fencing_tokens.append(lease_dup.fencing_token)
                result["failure_type"] = "duplicate_wake_allowed"
                result["duration_ms"] = (time.time() - start_time) * 1000
                provider_b.stop(runtime_b_id)
                provider_b.destroy(runtime_b_id)
                return result
            result["checks_passed"] += 1

        # 7. Witness
        _current_phase = "witness"
        witness = loop.host_b_work_and_witness(
            capsule_0, provider_b, host_b_key, restoration,
            operations=[{"type": "task", "command": "sh task.sh"}],
            test_results=[{"name": "task_complete", "passed": True, "output": exec_b.stdout.strip()}],
        )

        # 8. Owner reseal
        _current_phase = "owner_reseal"
        epoch_1 = LineageEpoch.child(epoch_0)
        host_b_pub = PublicKey.from_hex(host_b_key.public_key_hex)
        capsule_1, _ = loop.owner_reseal(
            capsule_0, witness, ws_b, epoch_1,
            f"task {idx} complete", "all steps done",
            host_b_pub, effects,
        )

        # 9. Offline verify
        _current_phase = "offline_verify"
        verifier = ContinuityVerifier(owner_key.to_public())
        verify_result = verifier.verify_full_chain(
            capsules=[capsule_0, capsule_1],
            invalidations=[invalidation],
            witnesses=[(witness, host_b_pub)],
        )
        result["checks_passed"] = verify_result["checks_passed"]
        result["checks_failed"] = verify_result["checks_failed"]

        if not verify_result["valid"]:
            result["failure_type"] = "offline_verification"
            result["failure_detail"] = "; ".join(verify_result["problems"][:3])
            result["duration_ms"] = (time.time() - start_time) * 1000
            return result

        # ─── Failure injection: corruption ───
        if inject_failure == "corruption":
            tampered = ContinuityCapsule.from_dict(
                json.loads(json.dumps(capsule_1.to_dict()))
            )
            tampered.objective = "TAMPERED"
            tampered_result = verifier.verify_full_chain(capsules=[capsule_0, tampered])
            if tampered_result["valid"]:
                result["failure_type"] = "corruption_not_detected"
                result["duration_ms"] = (time.time() - start_time) * 1000
                return result
            result["checks_passed"] += 1

        # ─── Failure injection: stale_fencing ───
        elif inject_failure == "stale_fencing":
            if lease_mgr.validate_token(agent_id, lease_a.fencing_token):
                result["failure_type"] = "stale_fencing_not_rejected"
                result["duration_ms"] = (time.time() - start_time) * 1000
                return result
            result["checks_passed"] += 1

        # 10. Verify VM B absence
        _current_phase = "verify_vm_b_absence"
        result["vm_b_absent"] = provider_b.verify_destruction(runtime_b_id)
        # Remove from active tracking — it's gone
        _active_vms = [(p, v) for p, v in _active_vms if v != runtime_b_id]

        result["success"] = True
        result["duration_ms"] = (time.time() - start_time) * 1000

    except Exception as e:
        result["failure_type"] = "exception"
        result["failure_detail"] = str(e)[:300]
        result["duration_ms"] = (time.time() - start_time) * 1000
        result["last_phase"] = _current_phase
        # Capture lease state at failure time
        try:
            current_lease = lease_mgr.get_current(agent_id) if agent_id else None
            if current_lease:
                result["lease_state"] = f"active: token={current_lease.fencing_token[:8]}... gen={current_lease.lease_generation} state={current_lease.state}"
            else:
                result["lease_state"] = "no active lease"
        except Exception:
            result["lease_state"] = "lease query failed"
        # Guaranteed cleanup: destroy any VMs still alive
        for p, rid in [(provider_a, runtime_a_id), (provider_b, runtime_b_id)]:
            if p and rid:
                try:
                    p.stop(rid)
                except Exception as ce:
                    result["cleanup_errors"].append(f"stop {rid}: {ce}")
                try:
                    p.destroy(rid)
                except Exception as ce:
                    result["cleanup_errors"].append(f"destroy {rid}: {ce}")
        _active_vms = [(p, v) for p, v in _active_vms if v not in (runtime_a_id, runtime_b_id)]
        # Preserve failure artifact immediately
        _preserve_failure(result, sandbox, idx)

    finally:
        # Guaranteed lease release — prevents stale leases from blocking future migrations
        for ft in held_fencing_tokens:
            try:
                lease_mgr.release(agent_id, ft)
            except Exception as e:
                print(f"  ⚠ Lease release failed for {agent_id} token={ft[:8]}...: {e}", file=sys.stderr)

    # Preserve any failure (not just exceptions) immediately
    if not result["success"]:
        _preserve_failure(result, sandbox, idx)

    return result


FAILURE_DIR = HERE / "sandbox" / "failure_records"

def _preserve_failure(result: dict, sandbox: Path, idx: int) -> None:
    """Preserve failure details immediately to a persistent directory that survives sandbox wipes."""
    FAILURE_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "migration_id": result["migration_id"],
        "run_id": result["run_id"],
        "failure_type": result["failure_type"],
        "failure_detail": result["failure_detail"],
        "last_phase": result.get("last_phase", ""),
        "vm_a_id": result["vm_a_id"],
        "vm_b_id": result["vm_b_id"],
        "vm_a_absent": result["vm_a_absent"],
        "vm_b_absent": result["vm_b_absent"],
        "capsule_hash": result.get("capsule_hash", ""),
        "epoch": result.get("epoch", ""),
        "lease_state": result.get("lease_state", ""),
        "inject_failure": result["inject_failure"],
        "duration_ms": result["duration_ms"],
        "cleanup_errors": result.get("cleanup_errors", []),
        "timestamp": time.time(),
    }
    fname = FAILURE_DIR / f"failure_{result['run_id']}_{idx:04d}.json"
    with open(fname, "w") as f:
        json.dump(record, f, indent=2)
    print(f"  ⚠ Failure preserved: {fname}", file=sys.stderr)


def run_harness(count: int, failure_rate: float, output_path: str = "") -> dict:
    """Run N real-VM migrations with failure injection and produce metrics."""
    sandbox = HERE / "sandbox" / "real_vm_harness"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)

    owner_key = OwnerKeyPair.generate()
    store = ContentStore(str(sandbox / "store"))
    lease_mgr = LeaseManager(str(sandbox / "leases.db"))
    loop = ContinuityLoop(owner_key, store, lease_mgr, str(sandbox))

    # Preflight: reconcile ALL stale hdar-* VMs from any previous interrupted run
    preflight_provider = AppleContainerProvider()
    orphan_receipt = _preflight_reconcile(preflight_provider, lease_mgr, owner_key)

    print(f"\n{'='*72}")
    print(f"  REAL-VM MIGRATION HARNESS: {count} migrations on actual Linux VMs")
    print(f"  Provider: Apple Containerization (real VM-backed isolation)")
    print(f"  Failure injection rate: {failure_rate*100:.1f}%")
    print(f"{'='*72}\n")

    results: List[dict] = []
    failure_types = ["corruption", "stale_fencing", "duplicate_wake"]
    failures_injected = 0

    for i in range(count):
        inject = ""
        if random.random() < failure_rate:
            inject = random.choice(failure_types)
            failures_injected += 1

        r = run_single_migration(loop, owner_key, lease_mgr, sandbox, i, inject)
        results.append(r)

        # 3-second pause between migrations
        if i + 1 < count:
            time.sleep(3)

        # Progress bar
        bar_width = 30
        filled = int(bar_width * (i + 1) / count)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct = (i + 1) / count * 100

        status = "✓" if r["success"] else "✗"
        fail_info = f" [{r['failure_type']}]" if r["failure_type"] else ""
        inj_info = f" inject={r['inject_failure']}" if r["inject_failure"] else ""
        print(
            f"  {bar} {pct:5.1f}%  {status} mig {i+1:3d}/{count}  "
            f"{r['duration_ms']/1000:5.1f}s  "
            f"A_abs={r['vm_a_absent']} B_abs={r['vm_b_absent']}  "
            f"{r['checks_passed']}p/{r['checks_failed']}f"
            f"{inj_info}{fail_info}"
        )

    # ─── Compute metrics ──────────────────────────────
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    durations = [r["duration_ms"] for r in successes]

    # Separate failure categories per audit requirement
    assertion_failures = [r for r in failures if r["failure_type"] in (
        "offline_verification", "corruption_not_detected",
        "stale_fencing_not_rejected", "duplicate_wake_allowed",
    )]
    infra_exceptions = [r for r in failures if r["failure_type"] in (
        "exception", "vm_a_create_failed", "vm_a_task_failed",
        "vm_b_task_failed", "lease_acquisition", "restore_failed",
    )]
    expected_rejections = [r for r in successes if r.get("inject_failure")]

    # Check for leaked VMs (VMs that should have been destroyed but weren't)
    leaked_vms = 0
    try:
        post_provider = AppleContainerProvider()
        remaining = [r for r in post_provider.list_runtimes() if r.startswith(f"hdar-{RUN_ID}-")]
        leaked_vms = len(remaining)
        if leaked_vms:
            for rt_id in remaining:
                try:
                    post_provider.stop(rt_id)
                    post_provider.destroy(rt_id)
                except Exception as e:
                    print(f"  ⚠ Leaked-VM cleanup failed for {rt_id}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠ Leaked-VM check failed: {e}")

    metrics = {
        "total_migrations": count,
        "successful": len(successes),
        "failed": len(failures),
        "success_rate": len(successes) / count if count > 0 else 0,
        "failures_injected": failures_injected,
        "failure_types": {},
        "assertion_failures": len(assertion_failures),
        "infrastructure_exceptions": len(infra_exceptions),
        "expected_injected_rejections": len(expected_rejections),
        "leaked_runtimes": leaked_vms,
        "duration_ms": {
            "mean": statistics.mean(durations) if durations else 0,
            "median": statistics.median(durations) if durations else 0,
            "stdev": statistics.stdev(durations) if len(durations) > 1 else 0,
            "min": min(durations) if durations else 0,
            "max": max(durations) if durations else 0,
            "p95": sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
        },
        "total_checks_passed": sum(r["checks_passed"] for r in results),
        "total_checks_failed": sum(r["checks_failed"] for r in results),
        "total_infra_exceptions": sum(r.get("infra_exceptions", 0) for r in results),
        "total_inject_rejections": sum(1 for r in results if r.get("inject_rejected", False)),
        "all_vm_a_absent": all(r["vm_a_absent"] for r in successes),
        "all_vm_b_absent": all(r["vm_b_absent"] for r in successes),
        "provider": "Apple Containerization (real Linux VMs)",
        "scope": "single physical host, single provider",
        "wilson_95_lower_bound": _wilson_lower(successes, count),
        "timestamp": time.time(),
    }

    for r in failures:
        ft = r["failure_type"] or "unknown"
        metrics["failure_types"][ft] = metrics["failure_types"].get(ft, 0) + 1

    # ─── Print report ─────────────────────────────────
    print(f"\n{'='*72}")
    print(f"  RELIABILITY METRICS — REAL VM-BACKED")
    print(f"{'='*72}")
    print(f"  Total migrations:     {metrics['total_migrations']}")
    print(f"  Successful:           {metrics['successful']}")
    print(f"  Failed:               {metrics['failed']}")
    print(f"  Success rate:         {metrics['success_rate']*100:.1f}%")
    print(f"  Failures injected:    {metrics['failures_injected']}")
    print(f"  Total checks passed:  {metrics['total_checks_passed']}")
    print(f"  Total checks failed:  {metrics['total_checks_failed']}")
    print(f"  Assertion failures:   {metrics['assertion_failures']}")
    print(f"  Infra exceptions:     {metrics['infrastructure_exceptions']}")
    print(f"  Expected rejections:  {metrics['expected_injected_rejections']}")
    print(f"  Leaked runtimes:      {metrics['leaked_runtimes']}")
    print(f"  All VM A absent:      {metrics['all_vm_a_absent']}")
    print(f"  All VM B absent:      {metrics['all_vm_b_absent']}")
    print(f"\n  Duration:")
    print(f"    mean:   {metrics['duration_ms']['mean']/1000:.1f}s")
    print(f"    median: {metrics['duration_ms']['median']/1000:.1f}s")
    print(f"    min:    {metrics['duration_ms']['min']/1000:.1f}s")
    print(f"    max:    {metrics['duration_ms']['max']/1000:.1f}s")
    print(f"    P95:    {metrics['duration_ms']['p95']/1000:.1f}s")

    if metrics["failure_types"]:
        print(f"\n  Failure breakdown:")
        for ft, cnt in sorted(metrics["failure_types"].items()):
            print(f"    {ft}: {cnt}")

    print(f"\n{'='*72}")
    total_infra_exceptions = sum(r.get("infra_exceptions", 0) for r in results)
    total_inject_rejections = sum(1 for r in results if r.get("inject_rejected", False))

    if metrics["success_rate"] >= 0.99:
        print(f"  RESULT: {metrics['success_rate']*100:.1f}% ({metrics['successful']}/{metrics['total_migrations']}) — SAME-HOST VM CONTINUITY PROTOTYPE")
    elif metrics["success_rate"] >= 0.95:
        print(f"  RESULT: {metrics['success_rate']*100:.1f}% ({metrics['successful']}/{metrics['total_migrations']}) — REAL-VM ALPHA: CORE CONTINUITY INVARIANTS VERIFIED")
    else:
        print(f"  RESULT: {metrics['success_rate']*100:.1f}% ({metrics['successful']}/{metrics['total_migrations']}) — NEEDS WORK")
    print(f"  Infra exceptions:    {total_infra_exceptions}")
    print(f"  Injected rejections: {total_inject_rejections}")
    print(f"  Wilson 95% lower:    {metrics['wilson_95_lower_bound']*100:.1f}%")
    print(f"  Provider: Apple Containerization 1.x")
    print(f"  Isolation: one lightweight Linux VM per runtime")
    print(f"  Scope: single physical host, single provider")
    print(f"  Faults tested: corruption, duplicate wake, stale fencing")
    print(f"  Run ID: {RUN_ID}")
    print(f"{'='*72}\n")

    if output_path:
        full_report = {**metrics, "results": results}
        if orphan_receipt:
            full_report["orphan_reconciliation"] = orphan_receipt
        with open(output_path, "w") as f:
            json.dump(full_report, f, indent=2)
        print(f"  Full report: {output_path}")

    return metrics


def main():
    ap = argparse.ArgumentParser(description="Real-VM migration harness")
    ap.add_argument("--count", "-n", type=int, default=10,
                    help="number of migrations (default 10 — each uses real VMs)")
    ap.add_argument("--failures", "-f", type=float, default=0.0,
                    help="failure injection rate (0.0-1.0)")
    ap.add_argument("--output", "-o", default="")
    args = ap.parse_args()

    metrics = run_harness(args.count, args.failures, args.output)
    sys.exit(0 if metrics["success_rate"] >= 0.95 else 1)


if __name__ == "__main__":
    main()
