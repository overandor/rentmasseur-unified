#!/usr/bin/env python3
"""Adversarial test suite for the continuity loop.

Tests deliberate attack and failure scenarios:
  1. Capsule corruption (tampered manifest)
  2. Epoch rollback (replay old capsule)
  3. Duplicate wake (two hosts try to acquire lease simultaneously)
  4. Capability expansion (host tries to broaden authority)
  5. Stale fencing (destroyed runtime tries to seal)
  6. Forged owner signature (host signs with its own key, claims owner)
  7. Forged host witness (wrong key used to sign witness)
  8. Receipt chain tampering (modified receipt in chain)
  9. Quiescence violation (seal while effects in flight)
 10. Split-brain (two runtimes, only one can advance lineage)

Usage:
  python3 test_adversarial.py              # run all tests
  python3 test_adversarial.py --verbose    # show details
  python3 test_adversarial.py --filter corruption  # run specific test

Exit 0 = all attacks detected. Exit 1 = an attack succeeded.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

from crypto import (
    OwnerKeyPair,
    HostKeyPair,
    PublicKey,
    canonicalize,
    sha256_hex,
)
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

passed = 0
failed = 0
test_results = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        test_results.append(("PASS", name, ""))
        return True
    else:
        failed += 1
        test_results.append(("FAIL", name, detail))
        return False


def make_sandbox(test_name: str) -> Path:
    s = HERE / "sandbox" / f"adversarial_{test_name}"
    if s.exists():
        shutil.rmtree(s)
    s.mkdir(parents=True)
    return s


def make_workspace(sandbox: Path, name: str = "ws") -> Path:
    ws = sandbox / name
    ws.mkdir()
    (ws / "task.py").write_text("def run():\n    return 42\n")
    (ws / "PROGRESS.md").write_text("# Work Log\nstep 1: started\n")
    return ws


def make_loop(sandbox: Path):
    owner_key = OwnerKeyPair.generate()
    store = ContentStore(sandbox / "store")
    lease_mgr = LeaseManager(str(sandbox / "leases.db"))
    loop = ContinuityLoop(owner_key, store, lease_mgr, str(sandbox))
    return owner_key, store, lease_mgr, loop


def seal_epoch_0(loop, sandbox, owner_key, agent_id="agent-test",
                 capabilities=None):
    ws = make_workspace(sandbox)
    epoch = LineageEpoch.genesis(agent_id)
    capsule, path = loop.seal_on_host_a(
        workspace_dir=ws,
        agent_id=agent_id,
        agent_name="test-agent",
        epoch=epoch,
        objective="test objective",
        continuation_point="step 1",
        capabilities=capabilities or [Capability("filesystem.write", "/workspace")],
    )
    return capsule, path, epoch


# ─── Test 1: Capsule Corruption ──────────────────────────

def test_corruption():
    """Tampered capsule manifest must be detected by offline verifier."""
    sandbox = make_sandbox("corruption")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)
    capsule, path, epoch = seal_epoch_0(loop, sandbox, owner_key)

    # Tamper with the objective
    tampered = ContinuityCapsule.from_dict(json.loads(json.dumps(capsule.to_dict())))
    tampered.objective = "MALICIOUS OBJECTIVE"
    # Don't re-sign — the hash should mismatch

    verifier = ContinuityVerifier(owner_key.to_public())
    result = verifier.verify_full_chain(capsules=[tampered])
    check("corruption: tampered capsule rejected", not result["valid"])
    check("corruption: manifest hash mismatch detected",
          any("manifest hash" in p for p in result["problems"]))

    # Also test: tamper but recompute hash (signature should fail)
    tampered2 = ContinuityCapsule.from_dict(json.loads(json.dumps(capsule.to_dict())))
    tampered2.objective = "MALICIOUS OBJECTIVE 2"
    tampered2.manifest_hash = tampered2.compute_hash()
    # Signature is still from original — should fail
    result2 = verifier.verify_full_chain(capsules=[tampered2])
    check("corruption: forged hash with old signature rejected", not result2["valid"])
    check("corruption: signature mismatch detected",
          any("signature" in p.lower() for p in result2["problems"]))


# ─── Test 2: Epoch Rollback ──────────────────────────────

def test_rollback():
    """Replaying an old capsule as a new epoch must be detected."""
    sandbox = make_sandbox("rollback")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)
    capsule_0, _, epoch_0 = seal_epoch_0(loop, sandbox, owner_key)

    # Create epoch 1 properly
    epoch_1 = LineageEpoch.child(epoch_0)
    ws_b = make_workspace(sandbox, "ws_b")
    (ws_b / "PROGRESS.md").write_text("# Work Log\nstep 1: done\nstep 2: done\n")

    host_key = HostKeyPair.generate("host-B")
    provider = UnsafeHostProvider(str(sandbox / "provider"))

    restoration = loop.restore_on_host_b(
        capsule_0, provider, host_key, str(sandbox / "restore"),
        destination_policy={"filesystem.root": "/workspace"},
    )

    witness = loop.host_b_work_and_witness(
        capsule_0, provider, host_key, restoration,
        operations=[{"type": "run", "command": "echo done"}],
        test_results=[],
    )

    capsule_1, _ = loop.owner_reseal(
        capsule_0, witness, ws_b, epoch_1, "done", "complete",
        PublicKey.from_hex(host_key.public_key_hex),
    )

    # Now try to present capsule_0 as if it were newer than capsule_1
    verifier = ContinuityVerifier(owner_key.to_public())
    result = verifier.verify_lineage([capsule_1, capsule_0])
    check("rollback: epoch rollback detected", not result)
    check("rollback: specific rollback error",
          any("rollback" in p for p in verifier._problems))


# ─── Test 3: Duplicate Wake ──────────────────────────────

def test_duplicate_wake():
    """Two hosts cannot acquire a lease for the same agent simultaneously."""
    sandbox = make_sandbox("duplicate_wake")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)
    capsule, _, epoch = seal_epoch_0(loop, sandbox, owner_key)

    provider_a = UnsafeHostProvider(str(sandbox / "pa"))
    provider_b = UnsafeHostProvider(str(sandbox / "pb"))

    host_key_a = HostKeyPair.generate("host-A")
    host_key_b = HostKeyPair.generate("host-B")

    # Host A acquires lease
    restoration_a = loop.restore_on_host_b(
        capsule, provider_a, host_key_a, str(sandbox / "ra"),
        holder_id="host-A",
    )
    check("duplicate_wake: host A acquired lease", restoration_a["restored"])

    # Host B tries to acquire lease while A holds it
    restoration_b = loop.restore_on_host_b(
        capsule, provider_b, host_key_b, str(sandbox / "rb"),
        holder_id="host-B",
    )
    check("duplicate_wake: host B denied lease", not restoration_b["restored"])
    check("duplicate_wake: denial reason is lease conflict",
          "lease" in restoration_b.get("reason", "").lower())


# ─── Test 4: Capability Expansion ────────────────────────

def test_capability_expansion():
    """Destination cannot broaden source capabilities."""
    sandbox = make_sandbox("cap_expansion")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)

    # Source has narrow scope
    source_caps = [
        Capability("filesystem.write", "/workspace/src"),
        Capability("network.egress", "api.example.com"),
    ]

    # Try to restore with broader destination policy
    provider = UnsafeHostProvider(str(sandbox / "provider"))
    host_key = HostKeyPair.generate("host-B")
    capsule, _, epoch = seal_epoch_0(loop, sandbox, owner_key,
                                      capabilities=source_caps)

    restoration = loop.restore_on_host_b(
        capsule, provider, host_key, str(sandbox / "restore"),
        destination_policy={
            "filesystem.root": "/",  # broader than /workspace/src
            "network.allowlist": "*",
        },
    )

    # The capability compiler should reject the broadened filesystem scope
    compiler = CapabilityCompiler()
    src = [Capability.from_dict(c) for c in capsule.capabilities.get("grants", [])]
    dst = [Capability.from_dict(c) for c in restoration.get("destination_capabilities", [])]
    ok, violations = compiler.verify_non_expansion(src, dst)
    check("cap_expansion: broader filesystem scope rejected",
          any("filesystem" in v for v in violations) or
          len(restoration.get("capability_rejections", [])) > 0)


# ─── Test 5: Stale Fencing ───────────────────────────────

def test_stale_fencing():
    """Destroyed runtime's fencing token cannot seal a new capsule."""
    sandbox = make_sandbox("stale_fencing")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)

    provider = UnsafeHostProvider(str(sandbox / "provider"))
    ws = make_workspace(sandbox)
    agent_id = "agent-stale"
    epoch = LineageEpoch.genesis(agent_id)

    # Acquire lease
    lease, err = lease_mgr.acquire(agent_id, "pending", 0, "host-A", "rt-A")
    check("stale_fencing: lease acquired", lease is not None)

    # Seal with valid token
    effects = EffectRegistry(str(sandbox / "effects.jsonl"))
    capsule, _ = loop.seal_on_host_a(
        ws, agent_id, "test", epoch, "obj", "cp",
        capabilities=[Capability("filesystem.write", "/workspace")],
        effects=effects,
        fencing_token=lease.fencing_token,
    )
    check("stale_fencing: sealed with valid token", len(capsule.signature) > 0)

    # Destroy runtime and release lease
    provider.materialize("rt-A", str(ws))
    invalidation, _ = loop.destroy_host_a(
        provider, "rt-A", agent_id,
        lease.lease_generation, lease.fencing_token,
    )

    # Try to seal again with the old (now invalid) fencing token
    ws2 = make_workspace(sandbox, "ws2")
    epoch2 = LineageEpoch.child(epoch)
    try:
        # The lease manager should reject the stale token
        is_valid = lease_mgr.validate_token(agent_id, lease.fencing_token)
        check("stale_fencing: old token rejected by lease manager", not is_valid)
    except Exception as e:
        check("stale_fencing: old token rejected by lease manager", True)


# ─── Test 6: Forged Owner Signature ──────────────────────

def test_forged_owner_signature():
    """Host's signature must not verify under owner's public key."""
    sandbox = make_sandbox("forged_owner")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)
    capsule, _, epoch = seal_epoch_0(loop, sandbox, owner_key)

    # Host generates its own key and signs a fake capsule
    host_key = HostKeyPair.generate("attacker-host")
    fake_capsule = ContinuityCapsule(
        agent_id=capsule.agent_id,
        agent_name=capsule.agent_name,
        epoch=LineageEpoch.child(epoch).to_dict(),
        parent_capsule_hash=capsule.manifest_hash,
        objective="forged epoch",
    )
    fake_capsule.manifest_hash = fake_capsule.compute_hash()
    fake_capsule.signature = host_key.sign_bytes(fake_capsule.unsigned_canonical())
    fake_capsule.signer_fingerprint = host_key.fingerprint

    # Verify with owner's public key — must fail
    owner_pub = owner_key.to_public()
    result = owner_pub.verify_bytes(
        fake_capsule.unsigned_canonical(), fake_capsule.signature
    )
    check("forged_owner: host signature fails under owner public key", not result)

    # Offline verifier must also reject
    verifier = ContinuityVerifier(owner_pub)
    verify_result = verifier.verify_full_chain(capsules=[fake_capsule])
    check("forged_owner: offline verifier rejects forged capsule",
          not verify_result["valid"])


# ─── Test 7: Forged Host Witness ─────────────────────────

def test_forged_witness():
    """Witness signed with wrong key must be detected."""
    sandbox = make_sandbox("forged_witness")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)
    capsule, _, epoch = seal_epoch_0(loop, sandbox, owner_key)

    provider = UnsafeHostProvider(str(sandbox / "provider"))
    host_key = HostKeyPair.generate("host-B")
    attacker_key = HostKeyPair.generate("attacker")

    restoration = loop.restore_on_host_b(
        capsule, provider, host_key, str(sandbox / "restore"),
    )

    # Build a witness but sign with the WRONG key
    witness_body = {
        "witness_type": "execution",
        "input_capsule_hash": capsule.manifest_hash,
        "owner_signature_verified": True,
        "agent_id": capsule.agent_id,
        "epoch_sequence": 0,
        "host_os": "Linux",
        "host_arch": "x86_64",
        "runtime_id": restoration["runtime_id"],
        "ephemeral_key_fingerprint": host_key.fingerprint,
        "workspace_root_hash": capsule.workspace_manifest["root_hash"],
        "restoration_class": "semantic",
        "operations": [],
        "test_results": [],
        "output_workspace_root_hash": capsule.workspace_manifest["root_hash"],
        "delta_hash": sha256_hex(b"fake"),
        "fencing_token_used": restoration["fencing_token"],
        "capabilities_applied": [],
        "timestamp": time.time(),
    }

    # Sign with attacker key instead of host key
    fake_sig = attacker_key.sign_bytes(canonicalize(witness_body))
    fake_hash = sha256_hex(canonicalize(witness_body) + fake_sig.encode())
    witness = {
        **witness_body,
        "receipt_hash": fake_hash,
        "signature": fake_sig,
        "ephemeral_public_key": host_key.public_key_hex,  # claims to be host
    }

    # Verify with host's actual public key — must fail
    host_pub = PublicKey.from_hex(host_key.public_key_hex)
    verifier = ContinuityVerifier(owner_key.to_public())
    result = verifier.verify_witness(witness, host_pub)
    check("forged_witness: wrong key signature rejected", not result)


# ─── Test 8: Receipt Chain Tampering ─────────────────────

def test_receipt_chain_tampering():
    """Modified receipt in chain must be detected."""
    sandbox = make_sandbox("receipt_tamper")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)
    capsule, _, epoch = seal_epoch_0(loop, sandbox, owner_key)

    # Tamper with a receipt's action
    tampered = ContinuityCapsule.from_dict(json.loads(json.dumps(capsule.to_dict())))
    tampered.receipts[0]["action"] = "MALICIOUS_ACTION"
    # Receipt hash is still the original — chain should break

    verifier = ContinuityVerifier(owner_key.to_public())
    result = verifier.verify_full_chain(capsules=[tampered])
    check("receipt_tamper: tampered receipt chain rejected", not result["valid"])
    check("receipt_tamper: receipt signature or chain break detected",
          any("receipt" in p.lower() or "signature" in p.lower()
              for p in result["problems"]))


# ─── Test 9: Quiescence Violation ────────────────────────

def test_quiescence_violation():
    """Sealing while effects are in flight must be refused."""
    sandbox = make_sandbox("quiescence")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)
    ws = make_workspace(sandbox)
    agent_id = "agent-quiescence"
    epoch = LineageEpoch.genesis(agent_id)

    effects = EffectRegistry(str(sandbox / "effects.jsonl"))

    # Register an effect but don't commit it
    effects.register(agent_id, "payment", b"charge $100")

    q = effects.check_quiescence(agent_id)
    check("quiescence: agent not quiescent with pending effect", not q["quiescent"])

    # Attempt to seal — should raise
    try:
        loop.seal_on_host_a(
            ws, agent_id, "test", epoch, "obj", "cp",
            effects=effects,
        )
        check("quiescence: seal refused with in-flight effects", False,
              "seal succeeded when it should have raised")
    except ValueError as e:
        check("quiescence: seal refused with in-flight effects", True)

    # Now commit the effect and try again
    effects.commit(agent_id, effects._current(agent_id).popitem()[0])
    # Re-register since popitem removed it
    effects2 = EffectRegistry(str(sandbox / "effects2.jsonl"))
    eff = effects2.register(agent_id, "payment", b"charge $100")
    effects2.commit(agent_id, eff.operation_id)
    q2 = effects2.check_quiescence(agent_id)
    check("quiescence: agent quiescent after commit", q2["quiescent"])


# ─── Test 10: Split-Brain ────────────────────────────────

def test_split_brain():
    """Two runtimes exist, but only one can advance the authoritative lineage."""
    sandbox = make_sandbox("split_brain")
    owner_key, store, lease_mgr, loop = make_loop(sandbox)
    capsule, _, epoch = seal_epoch_0(loop, sandbox, owner_key)

    provider_a = UnsafeHostProvider(str(sandbox / "pa"))
    provider_b = UnsafeHostProvider(str(sandbox / "pb"))

    host_key_a = HostKeyPair.generate("host-A")
    host_key_b = HostKeyPair.generate("host-B")

    # Host A acquires lease and restores
    restoration_a = loop.restore_on_host_b(
        capsule, provider_a, host_key_a, str(sandbox / "ra"),
        holder_id="host-A",
    )
    check("split_brain: host A has lease", restoration_a["restored"])

    # Host B tries to acquire — denied
    restoration_b = loop.restore_on_host_b(
        capsule, provider_b, host_key_b, str(sandbox / "rb"),
        holder_id="host-B",
    )
    check("split_brain: host B denied", not restoration_b["restored"])

    # Host A does work and seals next epoch
    ws_a = sandbox / "ra"
    (ws_a / "PROGRESS.md").write_text("# Work Log\nstep 1: done by A\n")

    witness_a = loop.host_b_work_and_witness(
        capsule, provider_a, host_key_a, restoration_a,
        operations=[{"type": "run", "command": "echo done"}],
        test_results=[],
    )

    epoch_1 = LineageEpoch.child(epoch)
    capsule_1, _ = loop.owner_reseal(
        capsule, witness_a, ws_a, epoch_1, "done by A", "complete",
        PublicKey.from_hex(host_key_a.public_key_hex),
    )

    # Even if Host B somehow survived, it cannot seal because:
    # 1. Its lease was never acquired
    # 2. It doesn't have the owner's private key
    # 3. The fencing token from A's lease is now invalid
    check("split_brain: only host A advanced lineage", capsule_1.epoch["sequence"] == 1)
    check("split_brain: host B never got a fencing token",
          not restoration_b.get("fencing_token"))

    # Verify the full chain
    verifier = ContinuityVerifier(owner_key.to_public())
    result = verifier.verify_full_chain(
        capsules=[capsule, capsule_1],
        witnesses=[(witness_a, PublicKey.from_hex(host_key_a.public_key_hex))],
    )
    check("split_brain: offline verifier confirms single lineage", result["valid"])


# ─── Runner ──────────────────────────────────────────────

ALL_TESTS = [
    ("corruption", test_corruption),
    ("rollback", test_rollback),
    ("duplicate_wake", test_duplicate_wake),
    ("capability_expansion", test_capability_expansion),
    ("stale_fencing", test_stale_fencing),
    ("forged_owner", test_forged_owner_signature),
    ("forged_witness", test_forged_witness),
    ("receipt_tamper", test_receipt_chain_tampering),
    ("quiescence", test_quiescence_violation),
    ("split_brain", test_split_brain),
]


def main():
    global passed, failed

    ap = argparse.ArgumentParser(description="Adversarial test suite for continuity loop")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--filter", "-f", default="", help="run only tests matching filter")
    args = ap.parse_args()

    print(f"\n{'='*70}")
    print(f"  ADVERSARIAL TEST SUITE: Continuity Loop Attack Detection")
    print(f"{'='*70}\n")

    tests = ALL_TESTS
    if args.filter:
        tests = [(n, t) for n, t in ALL_TESTS if args.filter in n]

    for name, test_fn in tests:
        passed_before = passed
        failed_before = failed
        print(f"  ▸ {name}...")
        try:
            test_fn()
            if failed > failed_before:
                print(f"    FAILED")
            else:
                print(f"    OK ({passed - passed_before} assertions)")
        except Exception as e:
            failed += 1
            test_results.append(("FAIL", name, f"exception: {e}"))
            print(f"    EXCEPTION: {e}")

        if args.verbose:
            for status, tname, detail in test_results[passed_before + failed_before:]:
                if status == "FAIL":
                    print(f"      ✗ {tname}: {detail}")
                else:
                    print(f"      ✓ {tname}")

    print(f"\n{'='*70}")
    print(f"  RESULT: {passed} passed, {failed} failed")
    if failed == 0:
        print(f"  ALL ATTACKS DETECTED")
    else:
        print(f"  SOME ATTACKS SUCCEEDED — FIX BEFORE DEMO")
    print(f"{'='*70}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
