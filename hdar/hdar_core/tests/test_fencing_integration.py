"""Tests for fencing token integration across effect registry and capsule sealer.

Verifies the core invariant: a stale runtime cannot register effects,
commit effects, or seal a successor capsule.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from capsule.store import ContentStore
from capsule.identity import AgentIdentity, LineageEpoch
from capsule.seal import CapsuleSealer
from lifecycle.effects import EffectRegistry
from lifecycle.lease import LeaseManager


def test_stale_runtime_cannot_register_effect():
    """A stale fencing token cannot register new effects."""
    tmp = Path(tempfile.mkdtemp())
    lease_mgr = LeaseManager(str(tmp / "leases.db"))
    identity = AgentIdentity.create(name="fence-test")

    effects = EffectRegistry(
        str(tmp / "effects.jsonl"),
        lease_manager=lease_mgr,
        agent_id=identity.agent_id,
    )

    # Acquire lease
    lease, err = lease_mgr.acquire(
        identity.agent_id, "capsule-hash-1", 0,
        "runtime-A", "apple-container"
    )
    assert lease is not None
    valid_token = lease.fencing_token

    # Register with valid token → succeeds
    eff = effects.register(
        identity.agent_id, "deploy", b"deploy payload",
        fencing_token=valid_token,
    )
    assert eff.status == "starting"
    print("[PASS] Fencing: valid token can register effect ✓")

    # Release and acquire new lease (simulates migration)
    lease_mgr.release(identity.agent_id, valid_token)
    lease2, _ = lease_mgr.acquire(
        identity.agent_id, "capsule-hash-1", 1,
        "runtime-B", "remote-ssh"
    )
    assert lease2 is not None
    new_token = lease2.fencing_token

    # Old token is now stale
    try:
        effects.register(
            identity.agent_id, "deploy", b"another deploy",
            fencing_token=valid_token,  # stale!
        )
        assert False, "stale token should have been rejected"
    except ValueError as e:
        assert "stale" in str(e).lower()
        print("[PASS] Fencing: stale token cannot register effect ✓")

    # New token works
    eff2 = effects.register(
        identity.agent_id, "deploy", b"another deploy",
        fencing_token=new_token,
    )
    assert eff2.status == "starting"
    print("[PASS] Fencing: new token can register effect ✓")

    import shutil
    shutil.rmtree(tmp)


def test_stale_runtime_cannot_commit_effect():
    """A stale fencing token cannot commit effects."""
    tmp = Path(tempfile.mkdtemp())
    lease_mgr = LeaseManager(str(tmp / "leases.db"))
    identity = AgentIdentity.create(name="fence-commit")

    effects = EffectRegistry(
        str(tmp / "effects.jsonl"),
        lease_manager=lease_mgr,
        agent_id=identity.agent_id,
    )

    # Runtime A acquires lease and registers effect
    lease_a, _ = lease_mgr.acquire(
        identity.agent_id, "hash-1", 0, "rt-A", "apple-container"
    )
    eff = effects.register(
        identity.agent_id, "email", b"send email",
        fencing_token=lease_a.fencing_token,
    )

    # Migration: release A, acquire B
    lease_mgr.release(identity.agent_id, lease_a.fencing_token)
    lease_b, _ = lease_mgr.acquire(
        identity.agent_id, "hash-1", 1, "rt-B", "remote-ssh"
    )

    # Runtime A tries to commit with stale token → rejected
    try:
        effects.commit(
            identity.agent_id, eff.operation_id,
            fencing_token=lease_a.fencing_token,  # stale!
        )
        assert False, "stale token should not commit"
    except ValueError as e:
        assert "stale" in str(e).lower()
        print("[PASS] Fencing: stale token cannot commit effect ✓")

    # Runtime B commits with valid token
    eff_committed = effects.commit(
        identity.agent_id, eff.operation_id,
        fencing_token=lease_b.fencing_token,
    )
    assert eff_committed.status == "committed"
    print("[PASS] Fencing: new token can commit effect ✓")

    import shutil
    shutil.rmtree(tmp)


def test_stale_runtime_cannot_seal_capsule():
    """A stale fencing token cannot seal a successor capsule."""
    tmp = Path(tempfile.mkdtemp())
    lease_mgr = LeaseManager(str(tmp / "leases.db"))
    identity = AgentIdentity.create(name="fence-seal")
    store = ContentStore(tmp / "store")

    sealer = CapsuleSealer(store, identity, lease_manager=lease_mgr)
    epoch = LineageEpoch.genesis(identity.agent_id)

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "task.py").write_text("print('hello')\n")

    # Runtime A acquires lease
    lease_a, _ = lease_mgr.acquire(
        identity.agent_id, "hash-init", 0, "rt-A", "apple-container"
    )

    # Seal with valid token → succeeds
    manifest_a, _ = sealer.seal(
        workspace_dir=ws, epoch=epoch,
        objective="test task",
        fencing_token=lease_a.fencing_token,
    )
    assert manifest_a.manifest_hash != ""
    print("[PASS] Fencing: valid token can seal capsule ✓")

    # Migration: release A, acquire B
    lease_mgr.release(identity.agent_id, lease_a.fencing_token)
    lease_b, _ = lease_mgr.acquire(
        identity.agent_id, manifest_a.manifest_hash, 1, "rt-B", "remote-ssh"
    )

    # Runtime A tries to seal with stale token → rejected
    epoch2 = LineageEpoch.child(epoch)
    try:
        sealer.seal(
            workspace_dir=ws, epoch=epoch2,
            objective="stale seal attempt",
            parent_capsule_hash=manifest_a.manifest_hash,
            fencing_token=lease_a.fencing_token,  # stale!
        )
        assert False, "stale token should not seal"
    except ValueError as e:
        assert "stale" in str(e).lower()
        print("[PASS] Fencing: stale token cannot seal capsule ✓")

    # Runtime B seals with valid token
    manifest_b, _ = sealer.seal(
        workspace_dir=ws, epoch=epoch2,
        objective="valid seal",
        parent_capsule_hash=manifest_a.manifest_hash,
        fencing_token=lease_b.fencing_token,
    )
    assert manifest_b.manifest_hash != ""
    print("[PASS] Fencing: new token can seal capsule ✓")

    import shutil
    shutil.rmtree(tmp)


def test_no_fencing_when_lease_manager_absent():
    """Without lease_manager, fencing tokens are not checked (backward compat)."""
    tmp = Path(tempfile.mkdtemp())
    identity = AgentIdentity.create(name="no-fence")
    store = ContentStore(tmp / "store")
    sealer = CapsuleSealer(store, identity)  # no lease_manager

    epoch = LineageEpoch.genesis(identity.agent_id)
    ws = tmp / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("x")

    # No fencing token, no lease manager → works fine
    manifest, _ = sealer.seal(workspace_dir=ws, epoch=epoch)
    assert manifest.manifest_hash != ""
    print("[PASS] Fencing: no lease_manager → backward compatible ✓")

    import shutil
    shutil.rmtree(tmp)


def test_concurrent_restore_only_one_can_seal():
    """Two runtimes restore; only the one with the newest token can seal."""
    tmp = Path(tempfile.mkdtemp())
    lease_mgr = LeaseManager(str(tmp / "leases.db"))
    identity = AgentIdentity.create(name="concurrent")
    store = ContentStore(tmp / "store")
    sealer = CapsuleSealer(store, identity, lease_manager=lease_mgr)

    epoch = LineageEpoch.genesis(identity.agent_id)
    ws = tmp / "ws"
    ws.mkdir()
    (ws / "task.py").write_text("x = 1\n")

    # First lease
    lease_a, _ = lease_mgr.acquire(
        identity.agent_id, "hash-1", 0, "rt-A", "apple-container"
    )

    # A seals epoch 1
    m1, _ = sealer.seal(ws, epoch, fencing_token=lease_a.fencing_token)

    # A releases, B acquires
    lease_mgr.release(identity.agent_id, lease_a.fencing_token)
    lease_b, _ = lease_mgr.acquire(
        identity.agent_id, m1.manifest_hash, 1, "rt-B", "remote-ssh"
    )

    # Now suppose A's process is still alive and tries to seal epoch 2
    epoch2 = LineageEpoch.child(epoch)
    try:
        sealer.seal(ws, epoch2,
                    parent_capsule_hash=m1.manifest_hash,
                    fencing_token=lease_a.fencing_token)
        assert False, "stale A should not seal"
    except ValueError:
        pass

    # B seals epoch 2 successfully
    m2, _ = sealer.seal(ws, epoch2,
                        parent_capsule_hash=m1.manifest_hash,
                        fencing_token=lease_b.fencing_token)
    assert m2.manifest_hash != ""
    print("[PASS] Fencing: concurrent restore — only newest token can seal ✓")

    import shutil
    shutil.rmtree(tmp)


if __name__ == "__main__":
    test_stale_runtime_cannot_register_effect()
    test_stale_runtime_cannot_commit_effect()
    test_stale_runtime_cannot_seal_capsule()
    test_no_fencing_when_lease_manager_absent()
    test_concurrent_restore_only_one_can_seal()
    print(f"\n=== All 5 fencing integration tests passed ===")
