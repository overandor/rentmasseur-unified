"""Tests for the identity protocol layer over real HDAR components.

Uses:
  - hdar_core.capsule.store.ContentStore (real on-disk SHA-256)
  - hdar_core.crypto.OwnerKeyPair (real Ed25519)
  - hdar_core.lifecycle.lease.LeaseManager (real SQLite atomic CAS)
  - hdar_core.lifecycle.effects.EffectRegistry (real quiescence)
  - hdar_core.capsule.identity.AgentIdentity / LineageEpoch
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

from hdar_core.capsule.store import ContentStore
from hdar_core.crypto import OwnerKeyPair, PublicKey
from hdar_core.lifecycle.lease import LeaseManager
from hdar_core.lifecycle.effects import EffectRegistry
from hdar_core.capsule.identity import AgentIdentity, LineageEpoch

from identity_protocol import (
    MemoryClass,
    PartitionedMemoryStore,
    PartitionedMemoryRoot,
    MemoryEntry,
    PolicySet,
    ForkPolicyType,
    IdentityRecord,
    ObjectiveSet,
    ForkArbiter,
    Fork,
    MergeRecord,
)


@pytest.fixture
def tmpdirs():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        yield {
            "root": d,
            "store": d / "content_store",
            "lease_db": str(d / "lease.db"),
            "effects": str(d / "effects.jsonl"),
            "workspace": d / "workspace",
        }


@pytest.fixture
def owner_key():
    return OwnerKeyPair.generate()


@pytest.fixture
def store(tmpdirs):
    return ContentStore(tmpdirs["store"])


@pytest.fixture
def partitioned_store(store):
    return PartitionedMemoryStore(store)


@pytest.fixture
def lease_manager(tmpdirs):
    return LeaseManager(tmpdirs["lease_db"])


@pytest.fixture
def effects(tmpdirs, lease_manager):
    return EffectRegistry(tmpdirs["effects"], lease_manager, "agent-test")


@pytest.fixture
def policy():
    return PolicySet(fork_policy=ForkPolicyType.SINGLE_WRITER)


class TestPartitionedMemoryStore:
    def test_seven_classes_supported(self, partitioned_store):
        for mc in MemoryClass:
            partitioned_store.put_bytes(
                f"data-{mc.value}".encode(), mc
            )

        for mc in MemoryClass:
            entries = partitioned_store.by_class(mc)
            assert len(entries) == 1
            assert entries[0].memory_class == mc

    def test_content_goes_through_real_store(self, partitioned_store, store):
        entry = partitioned_store.put_bytes(
            b"real content", MemoryClass.OBSERVED
        )
        blob = store.get(entry.content_hash)
        assert blob == b"real content"

    def test_root_hash_changes_on_add(self, partitioned_store):
        root1 = partitioned_store.compute_root()
        partitioned_store.put_bytes(b"new", MemoryClass.DERIVED)
        root2 = partitioned_store.compute_root()
        assert root1.root_hash != root2.root_hash

    def test_class_roots_are_independent(self, partitioned_store):
        partitioned_store.put_bytes(b"a", MemoryClass.OBSERVED)
        partitioned_store.put_bytes(b"b", MemoryClass.OBSERVED)
        root1 = partitioned_store.compute_root()

        partitioned_store.put_bytes(b"c", MemoryClass.DERIVED)
        root2 = partitioned_store.compute_root()

        assert root1.class_roots.get("observed") == root2.class_roots.get("observed")
        assert root1.class_roots.get("derived") != root2.class_roots.get("derived")

    def test_identity_critical_root_isolated(self, partitioned_store):
        partitioned_store.put_bytes(b"objective-1", MemoryClass.IDENTITY_CRITICAL)
        partitioned_store.put_bytes(b"observation-1", MemoryClass.OBSERVED)

        ic_root = partitioned_store.identity_critical_root()
        assert ic_root != ""

        partitioned_store.put_bytes(b"observation-2", MemoryClass.OBSERVED)
        ic_root2 = partitioned_store.identity_critical_root()
        assert ic_root == ic_root2

    def test_index_persists_across_instances(self, store, partitioned_store):
        partitioned_store.put_bytes(b"persistent", MemoryClass.COMMITTED)
        store2 = ContentStore(store.root)
        pms2 = PartitionedMemoryStore(store2)
        assert len(pms2.all_entries()) == 1

    def test_put_file_uses_real_content_store(self, partitioned_store, store, tmpdirs):
        ws = tmpdirs["workspace"]
        ws.mkdir()
        f = ws / "test.txt"
        f.write_text("file content")

        entry = partitioned_store.put_file(f, MemoryClass.SHARED)
        assert entry.size == len("file content")
        blob = store.get(entry.content_hash)
        assert blob == b"file content"


class TestIdentityRecord:
    def test_sign_and_verify(self, owner_key):
        record = IdentityRecord(
            agent_id="agent-test",
            epoch=0,
            parent_state_hash=None,
            memory_root_hash="abc123",
            objective_root_hash="def456",
            policy_hash="ghi789",
            authority_key=owner_key.public_key_hex,
        )
        record.sign(owner_key)

        assert record.state_hash != ""
        assert record.signature != ""
        assert record.verify(owner_key.to_public())

    def test_tamper_detected(self, owner_key):
        record = IdentityRecord(
            agent_id="agent-test",
            epoch=0,
            parent_state_hash=None,
            memory_root_hash="abc123",
            objective_root_hash="def456",
            policy_hash="ghi789",
            authority_key=owner_key.public_key_hex,
        )
        record.sign(owner_key)

        record.memory_root_hash = "tampered"
        assert not record.verify(owner_key.to_public())

    def test_wrong_key_rejected(self, owner_key):
        other_key = OwnerKeyPair.generate()
        record = IdentityRecord(
            agent_id="agent-test",
            epoch=0,
            parent_state_hash=None,
            memory_root_hash="abc123",
            objective_root_hash="def456",
            policy_hash="ghi789",
            authority_key=owner_key.public_key_hex,
        )
        record.sign(owner_key)

        assert not record.verify(other_key.to_public())


class TestObjectiveSet:
    def test_root_hash_changes_on_modify(self):
        obj1 = ObjectiveSet(objectives={"goal": "build"})
        obj2 = ObjectiveSet(objectives={"goal": "build", "constraint": "safe"})
        assert obj1.root_hash() != obj2.root_hash()

    def test_empty_set_has_deterministic_hash(self):
        obj1 = ObjectiveSet()
        obj2 = ObjectiveSet()
        assert obj1.root_hash() == obj2.root_hash()


class TestPolicySet:
    def test_hash_changes_on_policy_change(self):
        p1 = PolicySet(fork_policy=ForkPolicyType.SINGLE_WRITER)
        p2 = PolicySet(fork_policy=ForkPolicyType.CONSENSUS)
        assert p1.root_hash() != p2.root_hash()

    def test_quiescence_flag_affects_hash(self):
        p1 = PolicySet(quiescence_required=True)
        p2 = PolicySet(quiescence_required=False)
        assert p1.root_hash() != p2.root_hash()


class TestForkArbiter:
    def test_single_writer_rejects_fork(self, owner_key, policy):
        arbiter = ForkArbiter(policy)

        r1 = IdentityRecord(
            agent_id="agent-test",
            epoch=1,
            parent_state_hash="parent-abc",
            memory_root_hash="m1",
            objective_root_hash="o1",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r1.sign(owner_key)

        r2 = IdentityRecord(
            agent_id="agent-test",
            epoch=1,
            parent_state_hash="parent-abc",
            memory_root_hash="m2",
            objective_root_hash="o2",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r2.sign(owner_key)

        fork = arbiter.detect_fork([r1, r2])
        assert fork is not None
        assert len(fork.branches) == 2

        with pytest.raises(ValueError, match="lease violation"):
            arbiter.arbitrate(fork)

    def test_fork_and_merge_creates_merge(self, owner_key):
        policy = PolicySet(fork_policy=ForkPolicyType.FORK_AND_MERGE)
        arbiter = ForkArbiter(policy)

        r1 = IdentityRecord(
            agent_id="agent-test",
            epoch=1,
            parent_state_hash="parent-abc",
            memory_root_hash="m1",
            objective_root_hash="o1",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r1.sign(owner_key)

        r2 = IdentityRecord(
            agent_id="agent-test",
            epoch=1,
            parent_state_hash="parent-abc",
            memory_root_hash="m2",
            objective_root_hash="o2",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r2.sign(owner_key)

        fork = arbiter.detect_fork([r1, r2])
        assert fork is not None

        canonical, merge = arbiter.arbitrate(fork, owner_key=owner_key)
        assert merge is not None
        assert len(merge.merged_branches) == 2
        assert merge.merge_hash != ""
        assert merge.signature != ""

    def test_no_fork_when_single_branch(self, owner_key, policy):
        arbiter = ForkArbiter(policy)

        r1 = IdentityRecord(
            agent_id="agent-test",
            epoch=0,
            parent_state_hash=None,
            memory_root_hash="m0",
            objective_root_hash="o0",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r1.sign(owner_key)

        r2 = IdentityRecord(
            agent_id="agent-test",
            epoch=1,
            parent_state_hash=r1.state_hash,
            memory_root_hash="m1",
            objective_root_hash="o1",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r2.sign(owner_key)

        fork = arbiter.detect_fork([r1, r2])
        assert fork is None

    def test_consensus_resolves_with_enough_approvals(self, owner_key):
        policy = PolicySet(
            fork_policy=ForkPolicyType.CONSENSUS,
            consensus_threshold=2,
            consensus_parties=["alice", "bob"],
        )
        arbiter = ForkArbiter(policy)

        r1 = IdentityRecord(
            agent_id="agent-test",
            epoch=1,
            parent_state_hash="parent",
            memory_root_hash="m1",
            objective_root_hash="o1",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r1.sign(owner_key)

        r2 = IdentityRecord(
            agent_id="agent-test",
            epoch=1,
            parent_state_hash="parent",
            memory_root_hash="m2",
            objective_root_hash="o2",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r2.sign(owner_key)

        fork = arbiter.detect_fork([r1, r2])
        assert fork is not None

        canonical, merge = arbiter.arbitrate(fork, approvals=["alice", "bob"])
        assert canonical is not None
        assert merge is None

    def test_consensus_insufficient_approvals(self, owner_key):
        policy = PolicySet(
            fork_policy=ForkPolicyType.CONSENSUS,
            consensus_threshold=2,
            consensus_parties=["alice", "bob"],
        )
        arbiter = ForkArbiter(policy)

        r1 = IdentityRecord(
            agent_id="agent-test",
            epoch=1,
            parent_state_hash="parent",
            memory_root_hash="m1",
            objective_root_hash="o1",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r1.sign(owner_key)

        r2 = IdentityRecord(
            agent_id="agent-test",
            epoch=1,
            parent_state_hash="parent",
            memory_root_hash="m2",
            objective_root_hash="o2",
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
        )
        r2.sign(owner_key)

        fork = arbiter.detect_fork([r1, r2])
        canonical, merge = arbiter.arbitrate(fork, approvals=["alice"])
        assert canonical is None
        assert merge is None


class TestRealLeaseIntegration:
    def test_lease_acquire_and_validate(self, lease_manager):
        lease, err = lease_manager.acquire(
            agent_id="agent-test",
            capsule_hash="hash-abc",
            epoch=0,
            holder_id="host-A",
            destination_runtime="rt-A",
        )
        assert err is None
        assert lease is not None
        assert lease.fencing_token != ""

        assert lease_manager.validate_token("agent-test", lease.fencing_token)

    def test_stale_token_rejected(self, lease_manager):
        lease1, _ = lease_manager.acquire(
            "agent-test", "hash-abc", 0, "host-A", "rt-A"
        )
        lease_manager.release("agent-test", lease1.fencing_token)

        lease2, _ = lease_manager.acquire(
            "agent-test", "hash-def", 1, "host-B", "rt-B"
        )

        assert not lease_manager.validate_token("agent-test", lease1.fencing_token)
        assert lease_manager.validate_token("agent-test", lease2.fencing_token)

    def test_concurrent_lease_denied(self, lease_manager):
        lease1, err1 = lease_manager.acquire(
            "agent-test", "hash-abc", 0, "host-A", "rt-A"
        )
        assert err1 is None

        lease2, err2 = lease_manager.acquire(
            "agent-test", "hash-def", 1, "host-B", "rt-B"
        )
        assert lease2 is None
        assert "held by" in err2


class TestRealEffectsIntegration:
    def test_quiescence_blocks_seal(self, effects, lease_manager):
        lease, _ = lease_manager.acquire(
            "agent-test", "hash-abc", 0, "host-A", "rt-A"
        )

        effects.register(
            agent_id="agent-test",
            capability_used="payment",
            request_payload=b'{"amount": 100}',
            fencing_token=lease.fencing_token,
        )

        q = effects.check_quiescence("agent-test")
        assert not q["quiescent"]
        assert "REFUSE TO SEAL" in q["verdict"]

    def test_quiescence_passes_after_commit(self, effects, lease_manager):
        lease, _ = lease_manager.acquire(
            "agent-test", "hash-abc", 0, "host-A", "rt-A"
        )

        effect = effects.register(
            agent_id="agent-test",
            capability_used="payment",
            request_payload=b'{"amount": 100}',
            fencing_token=lease.fencing_token,
        )
        effects.commit(
            "agent-test", effect.operation_id,
            fencing_token=lease.fencing_token,
        )

        q = effects.check_quiescence("agent-test")
        assert q["quiescent"]

    def test_stale_fencing_cannot_register_effects(self, effects, lease_manager):
        lease1, _ = lease_manager.acquire(
            "agent-test", "hash-abc", 0, "host-A", "rt-A"
        )
        lease_manager.release("agent-test", lease1.fencing_token)

        lease2, _ = lease_manager.acquire(
            "agent-test", "hash-def", 1, "host-B", "rt-B"
        )

        with pytest.raises(ValueError, match="stale"):
            effects.register(
                agent_id="agent-test",
                capability_used="payment",
                request_payload=b'{"amount": 200}',
                fencing_token=lease1.fencing_token,
            )


class TestEndToEndWithRealComponents:
    def test_full_identity_advancement(
        self, tmpdirs, owner_key, store, partitioned_store, lease_manager, policy
    ):
        """End-to-end: create identity, add memory, acquire lease, advance."""
        agent = AgentIdentity.create("test-agent")

        partitioned_store.put_bytes(
            b"initial observation", MemoryClass.OBSERVED
        )
        partitioned_store.put_bytes(
            b"objective: build the thing", MemoryClass.IDENTITY_CRITICAL
        )

        objectives = ObjectiveSet(objectives={"goal": "build"})
        memory_root = partitioned_store.compute_root()

        lease, err = lease_manager.acquire(
            agent_id=agent.agent_id,
            capsule_hash=memory_root.root_hash,
            epoch=0,
            holder_id="host-A",
            destination_runtime="rt-A",
        )
        assert err is None

        record = IdentityRecord(
            agent_id=agent.agent_id,
            epoch=0,
            parent_state_hash=None,
            memory_root_hash=memory_root.root_hash,
            objective_root_hash=objectives.root_hash(),
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
            writer_lease_id=lease.lease_id if hasattr(lease, 'lease_id') else "",
            fencing_token=lease.fencing_token,
        )
        record.sign(owner_key)

        assert record.verify(owner_key.to_public())
        assert record.state_hash != ""

        lease_manager.release(agent.agent_id, lease.fencing_token)

        lease2, err2 = lease_manager.acquire(
            agent_id=agent.agent_id,
            capsule_hash=memory_root.root_hash,
            epoch=1,
            holder_id="host-B",
            destination_runtime="rt-B",
        )
        assert err2 is None

        partitioned_store.put_bytes(
            b"new derived insight", MemoryClass.DERIVED
        )
        memory_root2 = partitioned_store.compute_root()

        record2 = IdentityRecord(
            agent_id=agent.agent_id,
            epoch=1,
            parent_state_hash=record.state_hash,
            memory_root_hash=memory_root2.root_hash,
            objective_root_hash=objectives.root_hash(),
            policy_hash=policy.root_hash(),
            authority_key=owner_key.public_key_hex,
            writer_lease_id="",
            fencing_token=lease2.fencing_token,
        )
        record2.sign(owner_key)

        assert record2.verify(owner_key.to_public())
        assert record2.parent_state_hash == record.state_hash
        assert record2.memory_root_hash != record.memory_root_hash

        fork = ForkArbiter(policy).detect_fork([record, record2])
        assert fork is None

        lease_manager.release(agent.agent_id, lease2.fencing_token)
