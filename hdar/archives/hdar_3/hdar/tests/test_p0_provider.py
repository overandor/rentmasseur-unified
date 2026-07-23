"""Tests for P0 #4: provider interface + lifecycle controller."""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from providers.unsafe_host import UnsafeHostProvider
from providers.base import ProviderBase, RuntimeRecord, ExecutionResult
from lifecycle.state_machine import AgentState
from lifecycle.effects import EffectRegistry
from lifecycle.lease import LeaseManager
from lifecycle.controller import LifecycleController


def test_provider_materialize_execute_destroy():
    """Provider can materialize, execute, and destroy a runtime."""
    tmp = Path(tempfile.mkdtemp())
    provider = UnsafeHostProvider(str(tmp / "provider_sandbox"))

    ws = tmp / "workspace"
    ws.mkdir()
    (ws / "task.py").write_text("print('hello from runtime')\n")

    # Materialize
    record = provider.materialize("rt-test-1", str(ws))
    assert record.provider == "unsafe-host"
    assert record.exists
    assert record.runtime_id == "rt-test-1"
    assert "rt-test-1" in provider.list_runtimes()

    # Execute
    result = provider.execute("rt-test-1", "read", "python3 task.py")
    assert result.success
    assert "hello from runtime" in result.stdout

    # Stop + destroy
    provider.stop("rt-test-1")
    destroy = provider.destroy("rt-test-1")
    assert not destroy.exists
    assert destroy.delete_timestamp is not None

    # Verify destruction
    assert provider.verify_destruction("rt-test-1")
    assert "rt-test-1" not in provider.list_runtimes()
    print("[PASS] Provider: materialize → execute → destroy → verify ✓")

    shutil.rmtree(tmp)


def test_provider_destruction_verified():
    """verify_destruction returns False when runtime still exists."""
    tmp = Path(tempfile.mkdtemp())
    provider = UnsafeHostProvider(str(tmp / "sandbox"))

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("x")

    provider.materialize("rt-1", str(ws))
    assert not provider.verify_destruction("rt-1"), "should exist → not destroyed"

    provider.destroy("rt-1")
    assert provider.verify_destruction("rt-1"), "should be gone → destroyed"
    print("[PASS] Provider: destruction verification works ✓")

    shutil.rmtree(tmp)


def test_controller_full_lifecycle():
    """Full lifecycle: wake → run → quiesce → collapse → dormant."""
    tmp = Path(tempfile.mkdtemp())

    provider = UnsafeHostProvider(str(tmp / "sandbox"))
    lease_mgr = LeaseManager(str(tmp / "leases.db"))
    effects = EffectRegistry(str(tmp / "effects.jsonl"))

    ws = tmp / "workspace"
    ws.mkdir()
    (ws / "solve.py").write_text("def solve(n):\n    return sum(range(1, n+1))\n")
    (ws / "test.py").write_text("from solve import solve\nassert solve(5)==15\nprint('ok')\n")

    controller = LifecycleController(
        agent_id="agent-lc-test",
        provider=provider,
        lease_manager=lease_mgr,
        effect_registry=effects,
        state_dir=str(tmp / "state"),
    )

    # Wake
    result = controller.wake(
        capsule_hash="hash-abc",
        epoch=1,
        workspace_path=str(ws),
        holder_id="host-A",
    )
    assert result["woke"]
    assert result["state"] == "RUNNING"
    assert result["runtime_id"] is not None
    print(f"[PASS] Controller: wake → RUNNING (runtime={result['runtime_id']}) ✓")

    # Execute work
    exec_result = controller.execute("test", "python3 test.py")
    assert exec_result.success
    assert "ok" in exec_result.stdout
    print(f"[PASS] Controller: execute test → success ✓")

    # Collapse (no pending effects)
    collapse = controller.collapse()
    assert collapse["collapsed"]
    assert collapse["runtime_destroyed"]
    assert collapse["destruction_verified"]
    assert collapse["active_compute"] == "zero — dormant storage only"
    assert controller.sm.is_dormant()
    print(f"[PASS] Controller: collapse → dormant, runtime destroyed ✓")

    # Verify runtime is gone
    assert provider.verify_destruction(result["runtime_id"])
    assert controller.lease is None
    print(f"[PASS] Controller: post-collapse runtime gone, lease released ✓")

    shutil.rmtree(tmp)


def test_controller_refuses_collapse_mid_payment():
    """Controller refuses to collapse while a payment is in flight."""
    tmp = Path(tempfile.mkdtemp())

    provider = UnsafeHostProvider(str(tmp / "sandbox"))
    lease_mgr = LeaseManager(str(tmp / "leases.db"))
    effects = EffectRegistry(str(tmp / "effects.jsonl"))

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("working")

    controller = LifecycleController(
        agent_id="agent-pay-test",
        provider=provider,
        lease_manager=lease_mgr,
        effect_registry=effects,
        state_dir=str(tmp / "state"),
    )

    controller.wake("hash-abc", 1, str(ws), "host-A")

    # Register a payment and mark unknown
    effect = controller.register_effect("payment", b"pay $500 to vendor")
    controller.mark_effect_unknown(effect.operation_id)

    # Attempt collapse — must refuse
    collapse = controller.collapse()
    assert not collapse["collapsed"]
    assert "REFUSE TO SEAL" in collapse["reason"]
    assert len(collapse["blocking_effects"]) > 0
    print(f"[PASS] Controller: collapse REFUSED mid-payment ✓")

    # Reconcile: provider says committed
    def probe(op_id, eff):
        return "committed"
    result = controller.reconcile_effects(probe)
    assert result["now_quiescent"]

    # Now collapse should succeed
    collapse2 = controller.collapse()
    assert collapse2["collapsed"]
    assert collapse2["runtime_destroyed"]
    print(f"[PASS] Controller: collapse succeeds after reconcile ✓")

    shutil.rmtree(tmp)


def test_controller_duplicate_payment_prevented():
    """Agent tries to pay twice across a migration — second attempt blocked."""
    tmp = Path(tempfile.mkdtemp())

    provider = UnsafeHostProvider(str(tmp / "sandbox"))
    lease_mgr = LeaseManager(str(tmp / "leases.db"))
    effects = EffectRegistry(str(tmp / "effects.jsonl"))

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("working")

    controller = LifecycleController(
        agent_id="agent-dup-test",
        provider=provider,
        lease_manager=lease_mgr,
        effect_registry=effects,
        state_dir=str(tmp / "state"),
    )

    controller.wake("hash-abc", 1, str(ws), "host-A")

    # First payment: register, submit, crash (unknown)
    op_id = "op-payment-001"
    effect = controller.register_effect("payment", b"pay $500", operation_id=op_id)
    controller.mark_effect_unknown(op_id)

    # Reconcile: provider says committed
    def probe(op_id, eff):
        return "committed"
    controller.reconcile_effects(probe)

    # Collapse and seal
    controller.collapse()

    # Wake again (migration)
    controller2 = LifecycleController(
        agent_id="agent-dup-test",
        provider=provider,
        lease_manager=lease_mgr,
        effect_registry=effects,  # same registry
        state_dir=str(tmp / "state"),
    )
    controller2.wake("hash-def", 2, str(ws), "host-B")

    # Try to pay again with same operation_id
    effect2 = controller2.register_effect("payment", b"pay $500", operation_id=op_id)
    assert effect2.status == "committed"
    assert effects.is_duplicate("agent-dup-test", op_id)
    print(f"[PASS] Controller: duplicate payment across migration PREVENTED ✓")

    controller2.collapse()
    shutil.rmtree(tmp)


def test_controller_concurrent_wake_refused():
    """Two concurrent wake attempts — second must be refused."""
    tmp = Path(tempfile.mkdtemp())

    provider = UnsafeHostProvider(str(tmp / "sandbox"))
    lease_mgr = LeaseManager(str(tmp / "leases.db"))
    effects = EffectRegistry(str(tmp / "effects.jsonl"))

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("x")

    c1 = LifecycleController("agent-concurrent", provider, lease_mgr, effects, str(tmp / "s1"))
    c2 = LifecycleController("agent-concurrent", provider, lease_mgr, effects, str(tmp / "s2"))

    r1 = c1.wake("hash-abc", 1, str(ws), "host-A")
    assert r1["woke"]

    r2 = c2.wake("hash-abc", 1, str(ws), "host-B")
    assert not r2["woke"]
    assert "lease denied" in r2["reason"]
    print(f"[PASS] Controller: concurrent wake refused ({r2['reason']}) ✓")

    c1.collapse()
    shutil.rmtree(tmp)


def test_controller_state_history():
    """State machine history records all transitions."""
    tmp = Path(tempfile.mkdtemp())

    provider = UnsafeHostProvider(str(tmp / "sandbox"))
    lease_mgr = LeaseManager(str(tmp / "leases.db"))
    effects = EffectRegistry(str(tmp / "effects.jsonl"))

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("x")

    controller = LifecycleController("agent-hist", provider, lease_mgr, effects, str(tmp / "s"))
    controller.wake("hash", 1, str(ws), "host-A")
    controller.collapse()

    sm_dict = controller.sm.to_dict()
    transitions = sm_dict["transitions"]
    # DORMANT → ACQUIRING_LEASE → MATERIALIZING → VERIFYING_INPUT → RUNNING
    # → QUIESCING → SEALING → DESTROYING → DORMANT = 8 transitions
    assert len(transitions) == 8
    assert transitions[0]["from"] == "DORMANT"
    assert transitions[-1]["to"] == "DORMANT"
    print(f"[PASS] Controller: state history has {len(transitions)} transitions ✓")

    shutil.rmtree(tmp)


if __name__ == "__main__":
    test_provider_materialize_execute_destroy()
    test_provider_destruction_verified()
    test_controller_full_lifecycle()
    test_controller_refuses_collapse_mid_payment()
    test_controller_duplicate_payment_prevented()
    test_controller_concurrent_wake_refused()
    test_controller_state_history()
    print(f"\n=== All 7 P0#4 tests passed ===")
