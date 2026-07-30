"""Tests for P0 additions: state machine, effect registry, fenced leases."""

import os
import shutil
import tempfile
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lifecycle.state_machine import LifecycleStateMachine, AgentState
from lifecycle.effects import EffectRegistry, ExternalEffect
from lifecycle.lease import LeaseManager, Lease


# ─── State Machine ───────────────────────────────────────

def test_state_machine_happy_path():
    """Full lifecycle: DORMANT → ... → DORMANT."""
    sm = LifecycleStateMachine("agent-test")

    assert sm.state == AgentState.DORMANT
    assert sm.transition(AgentState.ACQUIRING_LEASE, "wake requested")
    assert sm.transition(AgentState.MATERIALIZING, "provider selected")
    assert sm.transition(AgentState.VERIFYING_INPUT, "container started")
    assert sm.transition(AgentState.RUNNING, "capsule verified")
    assert sm.transition(AgentState.QUIESCING, "task paused")
    assert sm.can_seal(), "should be able to seal from QUIESCING"
    assert sm.transition(AgentState.SEALING, "quiescence confirmed")
    assert sm.transition(AgentState.DESTROYING, "capsule sealed")
    assert sm.transition(AgentState.DORMANT, "runtime destroyed")
    assert sm.is_dormant()
    assert len(sm.history) == 8
    print("[PASS] State machine: full happy path ✓")


def test_state_machine_rejects_invalid_transition():
    """Cannot jump from DORMANT directly to RUNNING."""
    sm = LifecycleStateMachine("agent-test")
    assert not sm.transition(AgentState.RUNNING, "skip steps")
    assert sm.state == AgentState.DORMANT
    print("[PASS] State machine: invalid transition rejected ✓")


def test_state_machine_cannot_seal_from_running():
    """Sealing is only allowed from QUIESCING or SEALING."""
    sm = LifecycleStateMachine("agent-test")
    sm.transition(AgentState.ACQUIRING_LEASE)
    sm.transition(AgentState.MATERIALIZING)
    sm.transition(AgentState.VERIFYING_INPUT)
    sm.transition(AgentState.RUNNING)
    assert not sm.can_seal(), "should NOT be able to seal from RUNNING"
    sm.transition(AgentState.QUIESCING)
    assert sm.can_seal(), "should be able to seal from QUIESCING"
    print("[PASS] State machine: cannot seal from RUNNING ✓")


def test_state_machine_failure_states():
    """Failure states are reachable and recoverable."""
    sm = LifecycleStateMachine("agent-test")
    sm.transition(AgentState.ACQUIRING_LEASE)
    sm.transition(AgentState.LEASE_LOST, "lease expired")
    assert sm.is_failure()
    sm.transition(AgentState.DORMANT, "lease released")
    assert sm.is_dormant()
    print("[PASS] State machine: failure states work ✓")


def test_state_machine_unknown_effect():
    """UNKNOWN_EFFECT is reachable from RUNNING and QUIESCING."""
    sm = LifecycleStateMachine("agent-test")
    sm.transition(AgentState.ACQUIRING_LEASE)
    sm.transition(AgentState.MATERIALIZING)
    sm.transition(AgentState.VERIFYING_INPUT)
    sm.transition(AgentState.RUNNING)
    sm.transition(AgentState.UNKNOWN_EFFECT, "payment status unknown")
    assert sm.is_failure()
    assert not sm.can_seal()
    sm.transition(AgentState.QUIESCING, "effect reconciled")
    assert sm.can_seal()
    print("[PASS] State machine: UNKNOWN_EFFECT path ✓")


# ─── Effect Registry ─────────────────────────────────────

def test_effect_registry_blocks_seal():
    """Cannot seal while an effect is in a blocking state."""
    tmp = Path(tempfile.mkdtemp())
    registry = EffectRegistry(str(tmp / "effects.jsonl"))

    # Register a payment intent
    effect = registry.register("agent-1", "payment", b"pay $500 to vendor")
    assert effect.status == "starting"
    assert effect.is_blocking()

    # Submit to provider
    registry.submit("agent-1", effect.operation_id)

    q = registry.check_quiescence("agent-1")
    assert not q["quiescent"]
    assert "REFUSE TO SEAL" in q["verdict"]
    print(f"[PASS] Effect registry: blocks seal while submitted ✓")

    shutil.rmtree(tmp)


def test_effect_registry_quiescent_after_commit():
    """Agent is quiescent after all effects are committed."""
    tmp = Path(tempfile.mkdtemp())
    registry = EffectRegistry(str(tmp / "effects.jsonl"))

    effect = registry.register("agent-1", "payment", b"pay $500")
    registry.submit("agent-1", effect.operation_id)
    registry.commit("agent-1", effect.operation_id,
                    provider_receipt={"stripe_id": "ch_123"})

    q = registry.check_quiescence("agent-1")
    assert q["quiescent"]
    assert q["verdict"] == "SAFE TO SEAL"
    print("[PASS] Effect registry: quiescent after commit ✓")

    shutil.rmtree(tmp)


def test_effect_registry_duplicate_prevention():
    """Re-registering a committed effect returns committed, not re-executed."""
    tmp = Path(tempfile.mkdtemp())
    registry = EffectRegistry(str(tmp / "effects.jsonl"))

    op_id = "op-fixed-001"
    effect = registry.register("agent-1", "payment", b"pay $500", operation_id=op_id)
    registry.commit("agent-1", op_id)

    # Try to register again with same operation_id
    effect2 = registry.register("agent-1", "payment", b"pay $500", operation_id=op_id)
    assert effect2.status == "committed"
    assert registry.is_duplicate("agent-1", op_id)
    print("[PASS] Effect registry: duplicate prevention ✓")

    shutil.rmtree(tmp)


def test_effect_registry_reconcile_unknown():
    """Unknown effects are reconciled on wake."""
    tmp = Path(tempfile.mkdtemp())
    registry = EffectRegistry(str(tmp / "effects.jsonl"))

    effect = registry.register("agent-1", "payment", b"pay $500")
    registry.submit("agent-1", effect.operation_id)
    registry.mark_unknown("agent-1", effect.operation_id)

    q = registry.check_quiescence("agent-1")
    assert not q["quiescent"]

    # Reconcile: provider says it was committed
    def probe(op_id, eff):
        return "committed"

    result = registry.reconcile("agent-1", probe)
    assert result["reconciled"] == 1
    assert result["now_quiescent"]
    assert result["results"][0]["action"] == "do NOT re-execute"
    print("[PASS] Effect registry: reconcile unknown → committed ✓")

    shutil.rmtree(tmp)


def test_effect_registry_reconcile_not_started():
    """Unknown effect proven not started → safe to retry."""
    tmp = Path(tempfile.mkdtemp())
    registry = EffectRegistry(str(tmp / "effects.jsonl"))

    effect = registry.register("agent-1", "email", b"send welcome email")
    registry.mark_unknown("agent-1", effect.operation_id)

    def probe(op_id, eff):
        return "proven_not_started"

    result = registry.reconcile("agent-1", probe)
    assert result["results"][0]["action"] == "safe to retry"
    assert result["now_quiescent"]
    print("[PASS] Effect registry: reconcile unknown → not started ✓")

    shutil.rmtree(tmp)


# ─── Fenced Lease Manager ────────────────────────────────

def test_lease_acquire_and_release():
    """Basic acquire and release cycle."""
    tmp = Path(tempfile.mkdtemp())
    lm = LeaseManager(str(tmp / "leases.db"))

    lease, err = lm.acquire("agent-1", "hash-abc", 1, "host-A", "runtime-1")
    assert err is None
    assert lease is not None
    assert lease.lease_generation == 1
    assert lease.fencing_token != ""

    # Release
    assert lm.release("agent-1", lease.fencing_token)
    assert lm.get_current("agent-1") is None
    print("[PASS] Lease: acquire and release ✓")

    shutil.rmtree(tmp)


def test_lease_blocks_concurrent_acquire():
    """Second acquire while first is active must fail."""
    tmp = Path(tempfile.mkdtemp())
    lm = LeaseManager(str(tmp / "leases.db"))

    lease1, err1 = lm.acquire("agent-1", "hash-abc", 1, "host-A", "runtime-1")
    assert err1 is None

    lease2, err2 = lm.acquire("agent-1", "hash-abc", 1, "host-B", "runtime-2")
    assert lease2 is None
    assert "lease held by" in err2
    print(f"[PASS] Lease: concurrent acquire refused ({err2}) ✓")

    shutil.rmtree(tmp)


def test_lease_stale_token_rejected():
    """Old fencing token is rejected after a new lease is acquired."""
    tmp = Path(tempfile.mkdtemp())
    lm = LeaseManager(str(tmp / "leases.db"))

    lease1, _ = lm.acquire("agent-1", "hash-abc", 1, "host-A", "runtime-1")
    old_token = lease1.fencing_token

    # Release and re-acquire
    lm.release("agent-1", old_token)
    lease2, _ = lm.acquire("agent-1", "hash-abc", 1, "host-B", "runtime-2")

    # Old token should be rejected
    assert not lm.validate_token("agent-1", old_token)
    assert lm.validate_token("agent-1", lease2.fencing_token)
    assert lm.reject_stale("agent-1", old_token)
    print("[PASS] Lease: stale fencing token rejected ✓")

    shutil.rmtree(tmp)


def test_lease_generation_increments():
    """Each new lease gets a higher generation number."""
    tmp = Path(tempfile.mkdtemp())
    lm = LeaseManager(str(tmp / "leases.db"))

    lease1, _ = lm.acquire("agent-1", "hash-abc", 1, "host-A", "runtime-1")
    assert lease1.lease_generation == 1
    lm.release("agent-1", lease1.fencing_token)

    lease2, _ = lm.acquire("agent-1", "hash-abc", 1, "host-B", "runtime-2")
    assert lease2.lease_generation == 2
    lm.release("agent-1", lease2.fencing_token)

    lease3, _ = lm.acquire("agent-1", "hash-def", 2, "host-C", "runtime-3")
    assert lease3.lease_generation == 3
    print("[PASS] Lease: generation increments ✓")

    shutil.rmtree(tmp)


def test_lease_expired_can_be_reclaimed():
    """An expired lease can be reclaimed by a new holder."""
    tmp = Path(tempfile.mkdtemp())
    lm = LeaseManager(str(tmp / "leases.db"), ttl=1)  # 1 second TTL

    lease1, _ = lm.acquire("agent-1", "hash-abc", 1, "host-A", "runtime-1")
    time.sleep(1.5)  # let it expire

    lease2, err2 = lm.acquire("agent-1", "hash-abc", 1, "host-B", "runtime-2")
    assert err2 is None
    assert lease2.lease_generation == 2
    print("[PASS] Lease: expired lease reclaimed ✓")

    shutil.rmtree(tmp)


def test_lease_release_wrong_token_fails():
    """Releasing with the wrong fencing token fails."""
    tmp = Path(tempfile.mkdtemp())
    lm = LeaseManager(str(tmp / "leases.db"))

    lease, _ = lm.acquire("agent-1", "hash-abc", 1, "host-A", "runtime-1")
    wrong_token = "deadbeef" * 8
    assert not lm.release("agent-1", wrong_token)
    # Correct token still works
    assert lm.release("agent-1", lease.fencing_token)
    print("[PASS] Lease: wrong token release rejected ✓")

    shutil.rmtree(tmp)


# ─── Integration: State Machine + Effects ────────────────

def test_integration_seal_refused_during_inflight_effect():
    """Full integration: state machine + effects refuse sealing mid-payment."""
    tmp = Path(tempfile.mkdtemp())
    registry = EffectRegistry(str(tmp / "effects.jsonl"))
    sm = LifecycleStateMachine("agent-int")

    # Agent runs
    sm.transition(AgentState.ACQUIRING_LEASE)
    sm.transition(AgentState.MATERIALIZING)
    sm.transition(AgentState.VERIFYING_INPUT)
    sm.transition(AgentState.RUNNING)

    # Agent starts a payment
    effect = registry.register("agent-int", "payment", b"pay $500")
    registry.submit("agent-int", effect.operation_id)

    # Crash: effect status becomes unknown
    registry.mark_unknown("agent-int", effect.operation_id)
    sm.transition(AgentState.UNKNOWN_EFFECT, "payment status unknown")

    # Attempt to seal — must be refused
    q = registry.check_quiescence("agent-int")
    assert not q["quiescent"]
    assert not sm.can_seal()

    # Reconcile: provider says committed
    def probe(op_id, eff):
        return "committed"
    result = registry.reconcile("agent-int", probe)
    assert result["now_quiescent"]

    # Now can quiesce and seal
    sm.transition(AgentState.QUIESCING, "effects reconciled")
    assert sm.can_seal()
    sm.transition(AgentState.SEALING)
    sm.transition(AgentState.DESTROYING)
    sm.transition(AgentState.DORMANT)
    assert sm.is_dormant()
    print("[PASS] Integration: seal refused mid-payment, allowed after reconcile ✓")

    shutil.rmtree(tmp)


if __name__ == "__main__":
    test_state_machine_happy_path()
    test_state_machine_rejects_invalid_transition()
    test_state_machine_cannot_seal_from_running()
    test_state_machine_failure_states()
    test_state_machine_unknown_effect()

    test_effect_registry_blocks_seal()
    test_effect_registry_quiescent_after_commit()
    test_effect_registry_duplicate_prevention()
    test_effect_registry_reconcile_unknown()
    test_effect_registry_reconcile_not_started()

    test_lease_acquire_and_release()
    test_lease_blocks_concurrent_acquire()
    test_lease_stale_token_rejected()
    test_lease_generation_increments()
    test_lease_expired_can_be_reclaimed()
    test_lease_release_wrong_token_fails()

    test_integration_seal_refused_during_inflight_effect()

    print(f"\n=== All {17} P0 tests passed ===")
