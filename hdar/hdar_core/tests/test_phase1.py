"""Phase one pass-condition test.

Verifies:
  workspace → sealed capsule → original workspace deleted → restored workspace matches its recorded root hash

Also tests:
  - Manifest signature verification
  - Receipt chain verification
  - Tamper detection
  - Cross-identity verification (Host B verifies without owner key)
"""

import json
import shutil
import tempfile
import hashlib
from pathlib import Path

# Allow running both as module and as script
try:
    from capsule import (
        ContentStore, AgentIdentity, LineageEpoch,
        ReceiptChain, CapsuleSealer, CapsuleRestorer,
    )
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from capsule import (
        ContentStore, AgentIdentity, LineageEpoch,
        ReceiptChain, CapsuleSealer, CapsuleRestorer,
    )


def test_phase1_seal_restore():
    """Core pass condition: seal → delete → restore → verify hash match."""
    tmp = Path(tempfile.mkdtemp(prefix="hdar-phase1-"))

    # --- Setup ---
    store_dir = tmp / "store"
    workspace = tmp / "workspace"
    workspace.mkdir()
    (workspace / "solve.py").write_text("def solve(n):\n    return sum(range(1, n + 1))\n")
    (workspace / "PROGRESS.md").write_text("# agent-seed01 work log\nstep 1 of 3: analyzed the problem   [done on HOST A]\nstep 2 of 3: implement solve()      [pending]\nstep 3 of 3: verify                 [pending]\n")

    store = ContentStore(store_dir)
    identity = AgentIdentity.create(name="agent-seed01")
    epoch = LineageEpoch.genesis(identity.agent_id)
    sealer = CapsuleSealer(store, identity)

    # --- Seal ---
    manifest, chain = sealer.seal(
        workspace_dir=workspace,
        epoch=epoch,
        objective="Implement and verify solve(n) = sum(1..n)",
        continuation_point="step 2 of 3: implement solve()",
        working_summary="Problem analyzed. solve() needs to return sum of 1..n.",
        capabilities={"filesystem": "rw", "network": "none"},
        capability_note="capability grants travel here; never broaden on restore",
    )

    capsule_path = tmp / "capsule.json"
    sealer.write_capsule(manifest, capsule_path)

    assert manifest.workspace_manifest is not None
    assert manifest.workspace_manifest["root_hash"] != ""
    assert len(chain) == 1
    assert chain.verify()
    print(f"[SEAL] root_hash={manifest.workspace_manifest['root_hash'][:16]}... receipts={len(chain)}")

    # --- Delete original workspace ---
    shutil.rmtree(workspace)
    assert not workspace.exists()
    print(f"[DELETE] original workspace destroyed")

    # --- Restore on "Host B" ---
    restorer = CapsuleRestorer(store)
    report = restorer.restore(
        capsule_path,
        workspace,  # restore to same path
        owner_public_key=identity.public_key,
    )

    assert report["workspace_hash_matches"], "restored workspace hash does not match!"
    assert report["signature_valid"], "manifest signature invalid!"
    assert report["receipts_valid"], "receipt chain invalid!"
    print(f"[RESTORE] hash_matches={report['workspace_hash_matches']} sig_valid={report['signature_valid']}")

    # --- Verify file contents ---
    assert (workspace / "solve.py").exists()
    assert (workspace / "PROGRESS.md").exists()
    expected_solve = "def solve(n):\n    return sum(range(1, n + 1))\n"
    assert (workspace / "solve.py").read_text() == expected_solve
    print(f"[VERIFY] file contents match original")

    # --- Run the restored code ---
    exec((workspace / "solve.py").read_text(), globals())
    result = solve(10)
    assert result == 55, f"solve(10) returned {result}, expected 55"
    print(f"[EXEC] solve(10) = {result}")

    # Cleanup
    shutil.rmtree(tmp)
    print("\n[PASS] Phase one: seal → delete → restore → verify ✓")


def test_tamper_detection():
    """Tampering with the capsule JSON must be detected."""
    tmp = Path(tempfile.mkdtemp(prefix="hdar-tamper-"))
    store = ContentStore(tmp / "store")
    identity = AgentIdentity.create(name="tamper-test")
    epoch = LineageEpoch.genesis(identity.agent_id)
    sealer = CapsuleSealer(store, identity)

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "data.txt").write_text("original content\n")

    manifest, _ = sealer.seal(workspace_dir=ws, epoch=epoch, objective="tamper test")
    capsule_path = tmp / "capsule.json"
    sealer.write_capsule(manifest, capsule_path)

    # Tamper with the capsule JSON
    data = json.loads(capsule_path.read_text())
    data["objective"] = "tampered objective"
    capsule_path.write_text(json.dumps(data))

    # Verification must fail
    restorer = CapsuleRestorer(store)
    report = restorer.restore(capsule_path, tmp / "restored", owner_public_key=identity.public_key)
    assert not report["signature_valid"], "tampered capsule passed signature verification!"
    print("[PASS] Tamper detection: tampered capsule rejected ✓")

    shutil.rmtree(tmp)


def test_cross_host_no_key():
    """Host B without the owner key can restore content but cannot verify signature."""
    tmp = Path(tempfile.mkdtemp(prefix="hdar-crosshost-"))
    store = ContentStore(tmp / "store")
    identity = AgentIdentity.create(name="cross-host-test")
    epoch = LineageEpoch.genesis(identity.agent_id)
    sealer = CapsuleSealer(store, identity)

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "task.py").write_text("print('hello from host A')\n")

    manifest, _ = sealer.seal(workspace_dir=ws, epoch=epoch, objective="cross-host test")
    capsule_path = tmp / "capsule.json"
    sealer.write_capsule(manifest, capsule_path)

    shutil.rmtree(ws)

    # Restore without owner key (Host B doesn't have it)
    restorer = CapsuleRestorer(store)
    report = restorer.restore(capsule_path, ws, owner_public_key=None)

    assert report["workspace_hash_matches"], "content hash should match even without key"
    assert report["signature_valid"] is None, "signature should be unverified without key"
    assert report["receipts_valid"] is None, "receipts should be unverified without key"
    print(f"[PASS] Cross-host: content verified, signature unverified (no key) ✓")

    shutil.rmtree(tmp)


def test_lineage_chain():
    """Genesis → child epoch lineage is correct."""
    identity = AgentIdentity.create(name="lineage-test")
    genesis = LineageEpoch.genesis(identity.agent_id)
    child = LineageEpoch.child(genesis)

    assert child.sequence == 1
    assert child.parent_epoch == genesis.epoch_id
    assert child.agent_id == genesis.agent_id
    print("[PASS] Lineage: genesis → child epoch correct ✓")


if __name__ == "__main__":
    test_phase1_seal_restore()
    test_tamper_detection()
    test_cross_host_no_key()
    test_lineage_chain()
    print("\n=== All Phase one tests passed ===")
