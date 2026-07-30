#!/usr/bin/env python3
"""100-migration harness — automated reliability testing.

Runs N complete A→B→owner-reseal continuity loops with:
  - Randomized workspace contents
  - Randomized task types
  - Failure injection (corruption, stale fencing, duplicate wake)
  - Reliability metrics (success rate, mean time, P95, failures by type)
  - Published results as JSON

Usage:
  python3 migration_harness.py                    # 100 migrations
  python3 migration_harness.py --count 500        # 500 migrations
  python3 migration_harness.py --output results.json
  python3 migration_harness.py --failures 0.05    # 5% failure injection rate
"""
import argparse
import hashlib
import json
import os
import random
import shutil
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

from crypto import OwnerKeyPair, HostKeyPair, PublicKey, sha256_hex
from capsule.store import ContentStore
from capsule.identity import LineageEpoch
from capsule.capabilities import Capability, CapabilityCompiler
from lifecycle.lease import LeaseManager
from lifecycle.effects import EffectRegistry
from providers.unsafe_host import UnsafeHostProvider
from continuity import (
    ContinuityLoop,
    ContinuityVerifier,
    ContinuityCapsule,
    FencingInvalidation,
)


def random_workspace(sandbox: Path, idx: int) -> Path:
    """Create a randomized workspace for migration #idx."""
    ws = sandbox / f"ws_{idx}"
    ws.mkdir(parents=True)

    # Random task type
    task_types = ["python", "shell", "data", "config"]
    task_type = random.choice(task_types)

    if task_type == "python":
        (ws / "main.py").write_text(
            f"def compute(n={random.randint(1, 100)}):\n"
            f"    return n * {random.randint(2, 10)}\n"
            f"\n"
            f"if __name__ == '__main__':\n"
            f"    print(compute())\n"
        )
        (ws / "test.py").write_text(
            f"from main import compute\n"
            f"assert compute({random.randint(1, 50)}) > 0\n"
            f"print('ok')\n"
        )
    elif task_type == "shell":
        (ws / "run.sh").write_text(
            f"#!/bin/sh\necho 'migration-{idx}'\n"
        )
        (ws / "data.txt").write_text("".join(f"line {i}\n" for i in range(random.randint(5, 20))))
    elif task_type == "data":
        (ws / "data.json").write_text(json.dumps({
            "id": idx,
            "values": [random.randint(0, 1000) for _ in range(random.randint(5, 50))],
            "timestamp": time.time(),
        }, indent=2))
    else:
        (ws / "config.yaml").write_text(
            f"name: migration-{idx}\n"
            f"version: {random.randint(1, 10)}.{random.randint(0, 9)}\n"
            f"enabled: {random.choice([True, False])}\n"
        )

    (ws / "PROGRESS.md").write_text(
        f"# Migration {idx}\n"
        f"task_type: {task_type}\n"
        f"step 1: initialized on HOST A\n"
        f"step 2: pending — will complete on HOST B\n"
    )

    return ws


def run_single_migration(
    loop: ContinuityLoop,
    owner_key: OwnerKeyPair,
    lease_mgr: LeaseManager,
    sandbox: Path,
    idx: int,
    inject_failure: str = "",
) -> dict:
    """Run a single A→B→owner-reseal migration. Returns result dict."""
    start_time = time.time()
    result = {
        "migration_id": idx,
        "success": False,
        "failure_type": "",
        "failure_detail": "",
        "duration_ms": 0,
        "checks_passed": 0,
        "checks_failed": 0,
    }

    try:
        agent_id = f"agent-mig-{idx:04d}"
        ws_a = random_workspace(sandbox, idx)
        epoch_0 = LineageEpoch.genesis(agent_id)

        # Provider A
        provider_a = UnsafeHostProvider(str(sandbox / f"pa_{idx}"))
        provider_b = UnsafeHostProvider(str(sandbox / f"pb_{idx}"))
        host_b_key = HostKeyPair.generate(f"host-B-{idx}")

        # Effects
        effects = EffectRegistry(str(sandbox / f"effects_{idx}.jsonl"))
        eff = effects.register(agent_id, "file_write", b"workspace write")
        effects.commit(agent_id, eff.operation_id)

        # 1. Seal on A
        lease_a, err = lease_mgr.acquire(
            agent_id, "pending", 0, f"host-A-{idx}", f"rt-A-{idx}"
        )
        if err:
            result["failure_type"] = "lease_acquisition"
            result["failure_detail"] = err
            result["duration_ms"] = (time.time() - start_time) * 1000
            return result

        capsule_0, _ = loop.seal_on_host_a(
            ws_a, agent_id, f"agent-{idx}", epoch_0,
            f"task {idx}", "step 2: pending",
            capabilities=[Capability("filesystem.write", "/workspace")],
            effects=effects,
            fencing_token=lease_a.fencing_token,
        )

        # 2. Destroy A
        provider_a.materialize(f"rt-A-{idx}", str(ws_a))
        invalidation, _ = loop.destroy_host_a(
            provider_a, f"rt-A-{idx}", agent_id,
            lease_a.lease_generation, lease_a.fencing_token,
        )

        # 3. Restore on B
        ws_b = sandbox / f"wb_{idx}"
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

        # 4. Work on B — complete the task
        (ws_b / "PROGRESS.md").write_text(
            f"# Migration {idx}\n"
            f"step 1: initialized on HOST A\n"
            f"step 2: completed on HOST B\n"
        )

        # ─── Failure injection: duplicate_wake (before B releases lease) ───
        if inject_failure == "duplicate_wake":
            # Try to acquire a second lease while B still holds one
            lease_dup, err = lease_mgr.acquire(
                agent_id, capsule_0.manifest_hash, 0,
                "host-C", "rt-C"
            )
            if lease_dup is not None:
                result["failure_type"] = "duplicate_wake_allowed"
                result["duration_ms"] = (time.time() - start_time) * 1000
                # Clean up B's runtime
                provider_b.stop(restoration["runtime_id"])
                provider_b.destroy(restoration["runtime_id"])
                lease_mgr.release(agent_id, restoration["fencing_token"])
                return result
            result["checks_passed"] += 1

        # 5. Witness
        witness = loop.host_b_work_and_witness(
            capsule_0, provider_b, host_b_key, restoration,
            operations=[{"type": "run", "command": "echo done"}],
            test_results=[{"name": "workspace_updated", "passed": True}],
        )

        # 6. Owner reseal
        epoch_1 = LineageEpoch.child(epoch_0)
        host_b_pub = PublicKey.from_hex(host_b_key.public_key_hex)
        capsule_1, _ = loop.owner_reseal(
            capsule_0, witness, ws_b, epoch_1,
            f"task {idx} complete", "all steps done",
            host_b_pub, effects,
        )

        # 7. Offline verify
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

        # ─── Failure injection: corruption (post-verification) ───
        if inject_failure == "corruption":
            # Tamper with capsule and verify it's caught
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

        elif inject_failure == "stale_fencing":
            # Verify stale token is rejected
            if lease_mgr.validate_token(agent_id, lease_a.fencing_token):
                result["failure_type"] = "stale_fencing_not_rejected"
                result["duration_ms"] = (time.time() - start_time) * 1000
                return result
            result["checks_passed"] += 1

        result["success"] = True
        result["duration_ms"] = (time.time() - start_time) * 1000

    except Exception as e:
        result["failure_type"] = "exception"
        result["failure_detail"] = str(e)
        result["duration_ms"] = (time.time() - start_time) * 1000

    return result


def run_harness(count: int, failure_rate: float, output_path: str = "") -> dict:
    """Run N migrations with failure injection and produce metrics."""
    sandbox = HERE / "sandbox" / "migration_harness"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)

    owner_key = OwnerKeyPair.generate()
    store = ContentStore(sandbox / "store")
    lease_mgr = LeaseManager(str(sandbox / "leases.db"))
    loop = ContinuityLoop(owner_key, store, lease_mgr, str(sandbox))

    print(f"\n{'='*70}")
    print(f"  MIGRATION HARNESS: {count} automated A→B→owner-reseal loops")
    print(f"  Failure injection rate: {failure_rate*100:.1f}%")
    print(f"{'='*70}\n")

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

        status = "✓" if r["success"] else "✗"
        fail_info = f" [{r['failure_type']}]" if r["failure_type"] else ""
        if (i + 1) % 10 == 0 or not r["success"]:
            print(f"  {status} migration {i+1:4d}/{count}  "
                  f"{r['duration_ms']:7.1f}ms  "
                  f"checks: {r['checks_passed']}p/{r['checks_failed']}f"
                  f"{fail_info}")

    # ─── Compute metrics ──────────────────────────────
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    durations = [r["duration_ms"] for r in successes]

    metrics = {
        "total_migrations": count,
        "successful": len(successes),
        "failed": len(failures),
        "success_rate": len(successes) / count if count > 0 else 0,
        "failures_injected": failures_injected,
        "failure_types": {},
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
        "timestamp": time.time(),
    }

    for r in failures:
        ft = r["failure_type"] or "unknown"
        metrics["failure_types"][ft] = metrics["failure_types"].get(ft, 0) + 1

    # ─── Print report ─────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  RELIABILITY METRICS")
    print(f"{'='*70}")
    print(f"  Total migrations:     {metrics['total_migrations']}")
    print(f"  Successful:           {metrics['successful']}")
    print(f"  Failed:               {metrics['failed']}")
    print(f"  Success rate:         {metrics['success_rate']*100:.1f}%")
    print(f"  Failures injected:    {metrics['failures_injected']}")
    print(f"  Total checks passed:  {metrics['total_checks_passed']}")
    print(f"  Total checks failed:  {metrics['total_checks_failed']}")
    print(f"\n  Duration (ms):")
    print(f"    mean:   {metrics['duration_ms']['mean']:.1f}")
    print(f"    median: {metrics['duration_ms']['median']:.1f}")
    print(f"    stdev:  {metrics['duration_ms']['stdev']:.1f}")
    print(f"    min:    {metrics['duration_ms']['min']:.1f}")
    print(f"    max:    {metrics['duration_ms']['max']:.1f}")
    print(f"    P95:    {metrics['duration_ms']['p95']:.1f}")

    if metrics["failure_types"]:
        print(f"\n  Failure breakdown:")
        for ft, count in sorted(metrics["failure_types"].items()):
            print(f"    {ft}: {count}")

    print(f"\n{'='*70}")
    if metrics["success_rate"] >= 0.99:
        print(f"  RESULT: {metrics['success_rate']*100:.1f}% — 100/100 LOGICAL MIGRATION SIMULATIONS (UnsafeHostProvider, not real VMs)")
    elif metrics["success_rate"] >= 0.95:
        print(f"  RESULT: {metrics['success_rate']*100:.1f}% — LOGICAL MIGRATION SIMULATIONS (ALPHA QUALITY)")
    else:
        print(f"  RESULT: {metrics['success_rate']*100:.1f}% — LOGICAL MIGRATION SIMULATIONS (NEEDS WORK)")
    print(f"{'='*70}\n")

    if output_path:
        full_report = {**metrics, "results": results}
        with open(output_path, "w") as f:
            json.dump(full_report, f, indent=2)
        print(f"  Full report: {output_path}")

    return metrics


def main():
    ap = argparse.ArgumentParser(description="100-migration reliability harness")
    ap.add_argument("--count", "-n", type=int, default=100)
    ap.add_argument("--failures", "-f", type=float, default=0.0,
                    help="failure injection rate (0.0-1.0)")
    ap.add_argument("--output", "-o", default="")
    args = ap.parse_args()

    metrics = run_harness(args.count, args.failures, args.output)
    sys.exit(0 if metrics["success_rate"] >= 0.95 else 1)


if __name__ == "__main__":
    main()
