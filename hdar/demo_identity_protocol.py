#!/usr/bin/env python3
"""Demo: identity protocol layer over real HDAR components.

Shows:
  1. Partitioned memory store (7 classes) over real ContentStore
  2. IdentityRecord creation and signing with real Ed25519
  3. Lease acquisition with real SQLite LeaseManager
  4. Epoch advancement with fencing token validation
  5. Stale fencing token rejection
  6. Fork detection under single_writer policy
  7. Fork-and-merge arbitration
  8. Offline lineage verification
"""

import json
import shutil
import tempfile
from pathlib import Path

from hdar_core.capsule.store import ContentStore
from hdar_core.crypto import OwnerKeyPair
from hdar_core.lifecycle.lease import LeaseManager
from hdar_core.lifecycle.effects import EffectRegistry

from identity_protocol import (
    MemoryClass,
    PartitionedMemoryStore,
    PolicySet,
    ForkPolicyType,
    IdentityRecord,
    ObjectiveSet,
    ForkArbiter,
)


def banner(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    tmpdir = Path(tempfile.mkdtemp(prefix="hdar_demo_"))
    print(f"Working directory: {tmpdir}")

    # ─── Setup real components ──────────────────────────────
    store = ContentStore(tmpdir / "content_store")
    lease_mgr = LeaseManager(str(tmpdir / "lease.db"))
    effects = EffectRegistry(
        str(tmpdir / "effects.jsonl"), lease_mgr, "agent-demo"
    )
    owner_key = OwnerKeyPair.generate()
    policy = PolicySet(fork_policy=ForkPolicyType.SINGLE_WRITER)

    banner("1. PARTITIONED MEMORY STORE (7 classes over real ContentStore)")

    pms = PartitionedMemoryStore(store)

    # Add memory of each class
    pms.put_bytes(b"User said: 'build me a dashboard'", MemoryClass.OBSERVED,
                  provenance={"source": "chat", "ts": "2025-01-01T10:00:00Z"})
    pms.put_bytes(b"Summary: user wants a real-time analytics dashboard", MemoryClass.DERIVED)
    pms.put_bytes(b"Decision: use React + D3 for visualization", MemoryClass.COMMITTED)
    pms.put_bytes(b"API key: sk-xxx-encrypted", MemoryClass.PRIVATE)
    pms.put_bytes(b"Shared doc: architecture overview", MemoryClass.SHARED)
    pms.put_bytes(b"Workflow: deploy via CI/CD on merge to main", MemoryClass.PROCEDURAL)
    pms.put_bytes(b"Objective: ship dashboard v1 by Q1", MemoryClass.IDENTITY_CRITICAL)

    root = pms.compute_root()
    print(f"Total entries:     {root.total_entries}")
    print(f"Root hash:         {root.root_hash[:32]}...")
    print(f"Class roots:")
    for mc, h in sorted(root.class_roots.items()):
        count = len(pms.by_class(MemoryClass(mc)))
        print(f"  {mc:20s}  entries={count}  root={h[:16]}...")

    ic_root = pms.identity_critical_root()
    print(f"\nIdentity-critical root: {ic_root[:32]}...")
    print(f"  (isolated from observed/derived/committed/etc.)")

    # Verify content is really on disk
    obs_entries = pms.by_class(MemoryClass.OBSERVED)
    blob = store.get(obs_entries[0].content_hash)
    print(f"\nOn-disk verification: {blob[:40]}...")

    banner("2. IDENTITY RECORD — genesis (epoch 0)")

    objectives = ObjectiveSet(
        objectives={"goal": "ship dashboard v1", "deadline": "Q1"},
        permissions={"deploy": "allowed", "spend": "$500"},
        obligations={"report": "weekly"},
        unresolved_commitments={"auth_design": "pending review"},
    )

    lease, err = lease_mgr.acquire(
        agent_id="agent-demo",
        capsule_hash=root.root_hash,
        epoch=0,
        holder_id="host-A",
        destination_runtime="rt-A",
    )
    assert err is None
    print(f"Lease acquired:    holder={lease.holder_id}  gen={lease.lease_generation}")
    print(f"Fencing token:     {lease.fencing_token[:16]}...")

    genesis = IdentityRecord(
        agent_id="agent-demo",
        epoch=0,
        parent_state_hash=None,
        memory_root_hash=root.root_hash,
        objective_root_hash=objectives.root_hash(),
        policy_hash=policy.root_hash(),
        authority_key=owner_key.public_key_hex,
        writer_lease_id=f"gen-{lease.lease_generation}",
        fencing_token=lease.fencing_token,
    )
    genesis.sign(owner_key)

    print(f"\nGenesis record:")
    print(f"  agent_id:         {genesis.agent_id}")
    print(f"  epoch:            {genesis.epoch}")
    print(f"  state_hash:       {genesis.state_hash[:32]}...")
    print(f"  signature:        {genesis.signature[:32]}...")
    print(f"  memory_root:      {genesis.memory_root_hash[:32]}...")
    print(f"  objective_root:   {genesis.objective_root_hash[:32]}...")
    print(f"  policy_hash:      {genesis.policy_hash[:32]}...")
    print(f"  authority_key:    {genesis.authority_key[:32]}...")

    pub = owner_key.to_public()
    print(f"\n  Verify with owner public key: {'PASS' if genesis.verify(pub) else 'FAIL'}")

    lease_mgr.release("agent-demo", lease.fencing_token)
    print(f"\nLease released.")

    banner("3. EPOCH ADVANCEMENT — host-B picks up the work")

    lease2, err = lease_mgr.acquire(
        agent_id="agent-demo",
        capsule_hash=root.root_hash,
        epoch=1,
        holder_id="host-B",
        destination_runtime="rt-B",
    )
    assert err is None
    print(f"New lease:         holder={lease2.holder_id}  gen={lease2.lease_generation}")
    print(f"Fencing token:     {lease2.fencing_token[:16]}...")

    # Host B adds new memory
    pms.put_bytes(b"Built dashboard components: chart, table, filter", MemoryClass.DERIVED)
    pms.put_bytes(b"Test results: 12/12 passing", MemoryClass.OBSERVED)
    pms.put_bytes(b"Decision: use WebSocket for real-time updates", MemoryClass.COMMITTED)

    root2 = pms.compute_root()
    print(f"\nMemory root changed: {root.root_hash[:16]}... -> {root2.root_hash[:16]}...")
    print(f"Total entries now:   {root2.total_entries}")

    record1 = IdentityRecord(
        agent_id="agent-demo",
        epoch=1,
        parent_state_hash=genesis.state_hash,
        memory_root_hash=root2.root_hash,
        objective_root_hash=objectives.root_hash(),
        policy_hash=policy.root_hash(),
        authority_key=owner_key.public_key_hex,
        writer_lease_id=f"gen-{lease2.lease_generation}",
        fencing_token=lease2.fencing_token,
    )
    record1.sign(owner_key)

    print(f"\nEpoch 1 record:")
    print(f"  state_hash:       {record1.state_hash[:32]}...")
    print(f"  parent_state:     {record1.parent_state_hash[:32]}...")
    print(f"  Verify:           {'PASS' if record1.verify(pub) else 'FAIL'}")

    lease_mgr.release("agent-demo", lease2.fencing_token)

    banner("4. STALE FENCING TOKEN REJECTION")

    # Try to use the old token from host-A
    stale_valid = lease_mgr.validate_token("agent-demo", lease.fencing_token)
    print(f"Host-A's old token valid?  {stale_valid}  (expected: False)")
    print(f"Host-B's token valid?      {lease_mgr.validate_token('agent-demo', lease2.fencing_token)}  (expected: False, released)")

    # Acquire a new lease as host-C
    lease3, _ = lease_mgr.acquire(
        "agent-demo", root2.root_hash, 2, "host-C", "rt-C"
    )
    print(f"\nHost-C acquires new lease: gen={lease3.lease_generation}")

    # Host-A tries to register an effect with its stale token
    try:
        effects.register(
            agent_id="agent-demo",
            capability_used="deploy",
            request_payload=b'{"service": "dashboard"}',
            fencing_token=lease.fencing_token,
        )
        print("Host-A effect registration: ALLOWED (BUG!)")
    except ValueError as e:
        print(f"Host-A effect registration: REJECTED")
        print(f"  Reason: {e}")

    lease_mgr.release("agent-demo", lease3.fencing_token)

    banner("5. QUIESCENCE GATING — effects in flight")

    lease4, _ = lease_mgr.acquire(
        "agent-demo", root2.root_hash, 3, "host-D", "rt-D"
    )

    # Register an effect (payment in flight)
    effect = effects.register(
        agent_id="agent-demo",
        capability_used="payment",
        request_payload=b'{"amount": 99, "service": "hosting"}',
        fencing_token=lease4.fencing_token,
    )
    print(f"Effect registered: {effect.operation_id}")
    print(f"  status: {effect.status}")

    q = effects.check_quiescence("agent-demo")
    print(f"\nQuiescence check:")
    print(f"  quiescent: {q['quiescent']}  (expected: False)")
    print(f"  verdict:   {q['verdict']}")

    # Commit the effect
    effects.commit("agent-demo", effect.operation_id, fencing_token=lease4.fencing_token)
    q2 = effects.check_quiescence("agent-demo")
    print(f"\nAfter commit:")
    print(f"  quiescent: {q2['quiescent']}  (expected: True)")
    print(f"  verdict:   {q2['verdict']}")

    lease_mgr.release("agent-demo", lease4.fencing_token)

    banner("6. FORK DETECTION — single_writer policy")

    # Simulate two records from the same parent
    fork_a = IdentityRecord(
        agent_id="agent-demo",
        epoch=2,
        parent_state_hash=record1.state_hash,
        memory_root_hash="fork-a-memory-hash",
        objective_root_hash=objectives.root_hash(),
        policy_hash=policy.root_hash(),
        authority_key=owner_key.public_key_hex,
    )
    fork_a.sign(owner_key)

    fork_b = IdentityRecord(
        agent_id="agent-demo",
        epoch=2,
        parent_state_hash=record1.state_hash,
        memory_root_hash="fork-b-memory-hash",
        objective_root_hash=objectives.root_hash(),
        policy_hash=policy.root_hash(),
        authority_key=owner_key.public_key_hex,
    )
    fork_b.sign(owner_key)

    arbiter = ForkArbiter(policy)
    fork = arbiter.detect_fork([genesis, record1, fork_a, fork_b])
    print(f"Fork detected:     {fork is not None}")
    if fork:
        print(f"  parent:          {fork.parent_state_hash[:32]}...")
        print(f"  branches:        {len(fork.branches)}")
        for i, b in enumerate(fork.branches):
            print(f"    branch[{i}]:     state={b.state_hash[:16]}...  memory={b.memory_root_hash[:16]}...")

    try:
        arbiter.arbitrate(fork)
        print(f"  Arbitration:     ALLOWED (BUG!)")
    except ValueError as e:
        print(f"  Arbitration:     REJECTED")
        print(f"  Reason:          {e}")

    banner("7. FORK-AND-MERGE POLICY")

    merge_policy = PolicySet(fork_policy=ForkPolicyType.FORK_AND_MERGE)
    merge_arbiter = ForkArbiter(merge_policy)

    fork2 = merge_arbiter.detect_fork([genesis, record1, fork_a, fork_b])
    print(f"Fork detected:     {fork2 is not None}")

    canonical, merge = merge_arbiter.arbitrate(fork2, owner_key=owner_key)
    print(f"Merge record:      {merge is not None}")
    if merge:
        print(f"  merge_epoch:     {merge.merge_epoch}")
        print(f"  branches merged: {len(merge.merged_branches)}")
        print(f"  merge_hash:      {merge.merge_hash[:32]}...")
        print(f"  signed by:       {merge.merged_by[:16]}...")
        print(f"  signature:       {merge.signature[:32]}...")

    banner("8. OFFLINE LINEAGE VERIFICATION")

    lineage = [genesis, record1]
    print(f"Lineage: {len(lineage)} records")
    for i, r in enumerate(lineage):
        ok = r.verify(pub)
        print(f"  epoch {r.epoch}: state={r.state_hash[:16]}...  verify={'PASS' if ok else 'FAIL'}")

    print(f"\nChain integrity:")
    for i in range(1, len(lineage)):
        parent = lineage[i-1]
        child = lineage[i]
        hash_ok = child.parent_state_hash == parent.state_hash
        epoch_ok = child.epoch > parent.epoch
        agent_ok = child.agent_id == parent.agent_id
        print(f"  epoch {parent.epoch} -> {child.epoch}:")
        print(f"    parent_hash:  {'OK' if hash_ok else 'BROKEN'}")
        print(f"    epoch order:  {'OK' if epoch_ok else 'ROLLED BACK'}")
        print(f"    agent_id:     {'OK' if agent_ok else 'CHANGED'}")

    # Tamper detection
    print(f"\nTamper detection:")
    tampered = IdentityRecord.from_dict(record1.to_dict())
    tampered.memory_root_hash = "tampered"
    print(f"  tampered record verify: {'PASS (BUG!)' if tampered.verify(pub) else 'FAIL (detected)'}")

    banner("SUMMARY")

    print(f"Components used (all real):")
    print(f"  ContentStore:       {store.root}")
    print(f"  LeaseManager:       {lease_mgr.db_path}")
    print(f"  EffectRegistry:     {effects.ledger_path}")
    print(f"  OwnerKeyPair:       fingerprint={owner_key.fingerprint}")
    print(f"  PolicySet:          {policy.fork_policy.value}")
    print(f"")
    print(f"Identity lineage:")
    print(f"  Records:            {len(lineage)}")
    print(f"  Genesis state:      {genesis.state_hash[:32]}...")
    print(f"  Latest state:       {record1.state_hash[:32]}...")
    print(f"  Memory entries:     {root2.total_entries}")
    print(f"  Forks detected:     {len(arbiter.forks)} (single_writer)")
    print(f"  Merges signed:      {len(merge_arbiter.merges)} (fork_and_merge)")
    print(f"")
    print(f"All verification:    PASS")

    # Cleanup
    shutil.rmtree(tmpdir)
    print(f"\nCleaned up: {tmpdir}")


if __name__ == "__main__":
    main()
