"""Tests for transport layer + execution/termination receipts + host attestation."""

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from capsule.store import ContentStore
from capsule.identity import AgentIdentity, LineageEpoch
from capsule.seal import CapsuleSealer
from transport.export import CapsuleExporter, CapsuleImporter, DeltaExporter, TransportReceipt
from evidence.execution_receipt import ExecutionReceipt, ExecutionReceiptBuilder
from evidence.termination_receipt import TerminationReceipt, build_termination_receipt
from evidence.host_attestation import HostAttestation, build_host_attestation

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


# ─── Transport ───────────────────────────────────────────

def test_export_import_roundtrip():
    """Export a capsule, import it, verify blocks match."""
    tmp = Path(tempfile.mkdtemp())

    # Create a capsule
    store = ContentStore(tmp / "source_store")
    identity = AgentIdentity.create(name="agent-transport")
    epoch = LineageEpoch.genesis(identity.agent_id)
    sealer = CapsuleSealer(store, identity)

    ws = tmp / "workspace"
    ws.mkdir()
    (ws / "task.py").write_text("def solve(n): return sum(range(1, n+1))\n")
    (ws / "data.txt").write_text("important data\n")

    manifest, _ = sealer.seal(workspace_dir=ws, epoch=epoch, objective="transport test")
    capsule_path = tmp / "capsule.json"
    sealer.write_capsule(manifest, capsule_path)

    # Export
    exporter = CapsuleExporter(str(tmp / "source_store"))
    archive_path, export_receipt = exporter.export_capsule(
        str(capsule_path), str(tmp / "capsule.tar.gz"), source_host="host-A"
    )
    assert export_receipt.capsule_hash == manifest.manifest_hash
    assert export_receipt.block_count > 0
    assert Path(archive_path).exists()
    print(f"[PASS] Transport: export creates archive ({export_receipt.block_count} blocks) ✓")

    # Import
    importer = CapsuleImporter(str(tmp / "dest_store"))
    imported_path, import_receipt = importer.import_capsule(
        archive_path, expected_archive_hash=export_receipt.archive_hash,
        destination_host="host-B"
    )
    assert import_receipt.verified
    assert import_receipt.capsule_hash == manifest.manifest_hash
    assert import_receipt.transferred_blocks > 0
    print(f"[PASS] Transport: import verifies blocks ({import_receipt.transferred_blocks} transferred) ✓")

    # Verify imported capsule
    imported_manifest = json.loads(Path(imported_path).read_text())
    assert imported_manifest["manifest_hash"] == manifest.manifest_hash
    print("[PASS] Transport: imported capsule hash matches ✓")

    shutil.rmtree(tmp)


def test_transport_hash_mismatch_rejected():
    """Import rejects an archive with wrong hash."""
    tmp = Path(tempfile.mkdtemp())

    store = ContentStore(tmp / "store")
    identity = AgentIdentity.create(name="agent-hash")
    epoch = LineageEpoch.genesis(identity.agent_id)
    sealer = CapsuleSealer(store, identity)

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("x")
    manifest, _ = sealer.seal(workspace_dir=ws, epoch=epoch)
    capsule_path = tmp / "cap.json"
    sealer.write_capsule(manifest, capsule_path)

    exporter = CapsuleExporter(str(tmp / "store"))
    archive_path, receipt = exporter.export_capsule(str(capsule_path), str(tmp / "arch.tar.gz"))

    importer = CapsuleImporter(str(tmp / "dest"))
    try:
        importer.import_capsule(archive_path, expected_archive_hash="wrong_hash_123")
        assert False, "should have raised"
    except ValueError as e:
        assert "hash mismatch" in str(e).lower()
        print("[PASS] Transport: archive hash mismatch rejected ✓")

    shutil.rmtree(tmp)


def test_delta_computation():
    """Delta exporter identifies new vs unchanged blocks."""
    manifest1 = {
        "workspace_manifest": {
            "files": [
                {"content_hash": "aaa", "path": "a.txt"},
                {"content_hash": "bbb", "path": "b.txt"},
            ]
        }
    }
    manifest2 = {
        "workspace_manifest": {
            "files": [
                {"content_hash": "aaa", "path": "a.txt"},
                {"content_hash": "ccc", "path": "c.txt"},
            ]
        }
    }

    delta = DeltaExporter.compute_delta(manifest2, manifest1)
    assert "ccc" in delta["new"]
    assert "aaa" in delta["unchanged"]
    assert "bbb" in delta["removed"]
    print(f"[PASS] Transport: delta computed ({len(delta['new'])} new, {len(delta['unchanged'])} unchanged, {len(delta['removed'])} removed) ✓")


def test_transport_deduplication():
    """Importing a second capsule reuses existing blocks."""
    tmp = Path(tempfile.mkdtemp())

    store = ContentStore(tmp / "store")
    identity = AgentIdentity.create(name="agent-dedup")
    epoch = LineageEpoch.genesis(identity.agent_id)
    sealer = CapsuleSealer(store, identity)

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "shared.txt").write_text("shared content\n")
    (ws / "unique1.txt").write_text("unique to epoch 1\n")
    manifest1, _ = sealer.seal(workspace_dir=ws, epoch=epoch, objective="dedup test 1")
    cap1 = tmp / "cap1.json"
    sealer.write_capsule(manifest1, cap1)

    # Export and import first capsule
    exporter = CapsuleExporter(str(tmp / "store"))
    arch1, receipt1 = exporter.export_capsule(str(cap1), str(tmp / "arch1.tar.gz"))
    importer = CapsuleImporter(str(tmp / "dest"))
    _, import1 = importer.import_capsule(arch1, expected_archive_hash=receipt1.archive_hash)

    # Second capsule with shared + new file
    (ws / "unique2.txt").write_text("unique to epoch 2\n")
    epoch2 = LineageEpoch.child(epoch)
    manifest2, _ = sealer.seal(workspace_dir=ws, epoch=epoch2, objective="dedup test 2",
                                parent_capsule_hash=manifest1.manifest_hash)
    cap2 = tmp / "cap2.json"
    sealer.write_capsule(manifest2, cap2)

    arch2, receipt2 = exporter.export_capsule(str(cap2), str(tmp / "arch2.tar.gz"))
    _, import2 = importer.import_capsule(arch2, expected_archive_hash=receipt2.archive_hash)

    assert import2.skipped_blocks > 0, "should have skipped duplicate blocks"
    print(f"[PASS] Transport: deduplication skipped {import2.skipped_blocks} blocks ✓")

    shutil.rmtree(tmp)


# ─── Execution Receipt ───────────────────────────────────

def test_execution_receipt_sign_verify():
    """Destination host signs an execution receipt; owner verifies it."""
    ephemeral_key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    builder = ExecutionReceiptBuilder(ephemeral_key)

    receipt = builder.build(
        input_capsule_hash="abc123",
        owner_signature_verified=True,
        agent_id="agent-1",
        epoch_sequence=2,
        host_os="Linux",
        host_arch="x86_64",
        runtime_id="rt-remote-1",
        workspace_root_hash="root456",
        restoration_class="semantic",
        operations=[{"type": "test", "command": "python3 test.py", "exit_code": 0}],
        test_results=[{"test": "solve", "passed": True}],
        output_workspace_root_hash="root789",
        delta_hash="delta012",
        fencing_token_used="token-xyz",
    )

    assert receipt.signature != ""
    assert receipt.receipt_hash != ""

    # Verify with the ephemeral key's public key
    assert receipt.verify(ephemeral_key.public_key())
    print("[PASS] Execution receipt: signed and verified ✓")

    # Wrong key fails
    wrong_key = Ed25519PrivateKey.from_private_bytes(os.urandom(32)).public_key()
    assert not receipt.verify(wrong_key)
    print("[PASS] Execution receipt: wrong key rejected ✓")


def test_execution_receipt_tamper_detected():
    """Modifying the receipt invalidates the signature."""
    ephemeral_key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    builder = ExecutionReceiptBuilder(ephemeral_key)

    receipt = builder.build(
        input_capsule_hash="abc123",
        owner_signature_verified=True,
        agent_id="agent-1",
        epoch_sequence=2,
        host_os="Linux",
        host_arch="x86_64",
        runtime_id="rt-1",
        workspace_root_hash="root456",
    )

    # Tamper
    receipt.host_os = "Darwin"
    assert not receipt.verify(ephemeral_key.public_key())
    print("[PASS] Execution receipt: tamper detected ✓")


# ─── Termination Receipt ─────────────────────────────────

def test_termination_receipt():
    """Termination receipt proves runtime was destroyed."""
    key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    receipt = build_termination_receipt(
        runtime_id="rt-destroyed",
        provider="unsafe-host",
        agent_id="agent-1",
        capsule_hash="hash123",
        epoch=1,
        stop_ts=1000.0,
        delete_ts=1001.0,
        inspection={"exists": False},
        fencing_token="token-old",
        listing_excludes=True,
        signing_key=key,
    )

    assert receipt.destruction_verified
    assert receipt.verify(key.public_key())
    print("[PASS] Termination receipt: signed and verified ✓")

    # Tamper
    receipt.runtime_id = "rt-different"
    assert not receipt.verify(key.public_key())
    print("[PASS] Termination receipt: tamper detected ✓")


def test_termination_receipt_destruction_unconfirmed():
    """Termination receipt reports when destruction is unconfirmed."""
    key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    receipt = build_termination_receipt(
        runtime_id="rt-still-alive",
        provider="apple-container",
        agent_id="agent-1",
        capsule_hash="hash123",
        epoch=1,
        stop_ts=1000.0,
        delete_ts=1001.0,
        inspection={"exists": True},  # still exists!
        fencing_token="token-old",
        listing_excludes=False,  # still in listing
        signing_key=key,
    )

    assert not receipt.destruction_verified
    print("[PASS] Termination receipt: unconfirmed destruction reported ✓")


# ─── Host Attestation ────────────────────────────────────

def test_host_attestation():
    """Host attestation describes and signs the environment."""
    key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    attestation = build_host_attestation(
        host_id="host-B-remote",
        runtime_provider="remote-ssh",
        signing_key=key,
        memory_mb=4096,
        cpu_cores=4,
    )

    assert attestation.os_name != ""
    assert attestation.arch != ""
    assert attestation.verify(key.public_key())
    print(f"[PASS] Host attestation: signed ({attestation.os_name}/{attestation.arch}) ✓")

    # Tamper
    attestation.cpu_cores = 999
    assert not attestation.verify(key.public_key())
    print("[PASS] Host attestation: tamper detected ✓")


# ─── Integration: Full A→B→A chain ───────────────────────

def test_full_transport_and_receipt_chain():
    """Full chain: export → import → execute → receipt → verify."""
    tmp = Path(tempfile.mkdtemp())

    # Host A: create capsule
    store = ContentStore(tmp / "store_a")
    identity = AgentIdentity.create(name="agent-chain")
    epoch = LineageEpoch.genesis(identity.agent_id)
    sealer = CapsuleSealer(store, identity)

    ws = tmp / "ws"
    ws.mkdir()
    (ws / "task.py").write_text("def solve(n): return sum(range(1, n+1))\n")
    (ws / "test.py").write_text("from task import solve\nassert solve(5)==15\nprint('pass')\n")

    manifest, _ = sealer.seal(workspace_dir=ws, epoch=epoch, objective="chain test")
    cap_path = tmp / "capsule.json"
    sealer.write_capsule(manifest, cap_path)

    # Export from Host A
    exporter = CapsuleExporter(str(tmp / "store_a"))
    archive, export_receipt = exporter.export_capsule(str(cap_path), str(tmp / "arch.tar.gz"), "host-A")

    # Import on Host B
    dest_store = CapsuleImporter(str(tmp / "store_b"))
    imported_cap, import_receipt = dest_store.import_capsule(archive, export_receipt.archive_hash, "host-B")
    assert import_receipt.verified

    # Host B: build attestation
    host_b_key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    attestation = build_host_attestation("host-B", "remote-ssh", host_b_key, memory_mb=2048, cpu_cores=2)

    # Host B: build execution receipt
    exec_key = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    exec_builder = ExecutionReceiptBuilder(exec_key)
    exec_receipt = exec_builder.build(
        input_capsule_hash=manifest.manifest_hash,
        owner_signature_verified=True,
        agent_id=identity.agent_id,
        epoch_sequence=0,
        host_os=attestation.os_name,
        host_arch=attestation.arch,
        runtime_id="rt-host-b",
        workspace_root_hash=manifest.workspace_manifest["root_hash"],
        restoration_class="semantic",
        operations=[{"type": "test", "command": "python3 test.py", "exit_code": 0}],
        test_results=[{"test": "solve(5)", "passed": True}],
        output_workspace_root_hash=manifest.workspace_manifest["root_hash"],
        fencing_token_used="token-gen-2",
    )

    # Host A: verify Host B's receipts
    assert exec_receipt.verify(exec_key.public_key())
    assert attestation.verify(host_b_key.public_key())
    assert exec_receipt.owner_signature_verified
    assert exec_receipt.input_capsule_hash == manifest.manifest_hash
    print("[PASS] Integration: A→B→A receipt chain verified ✓")

    # Host A: build termination receipt for Host A's old runtime
    term_key = identity.signing_key
    term_receipt = build_termination_receipt(
        runtime_id="rt-host-a",
        provider="unsafe-host",
        agent_id=identity.agent_id,
        capsule_hash=manifest.manifest_hash,
        epoch=0,
        stop_ts=1000.0,
        delete_ts=1001.0,
        inspection={"exists": False},
        fencing_token="token-gen-1",
        listing_excludes=True,
        signing_key=term_key,
    )
    assert term_receipt.destruction_verified
    assert term_receipt.verify(term_key.public_key())
    print("[PASS] Integration: termination receipt for old runtime ✓")

    shutil.rmtree(tmp)


if __name__ == "__main__":
    test_export_import_roundtrip()
    test_transport_hash_mismatch_rejected()
    test_delta_computation()
    test_transport_deduplication()

    test_execution_receipt_sign_verify()
    test_execution_receipt_tamper_detected()

    test_termination_receipt()
    test_termination_receipt_destruction_unconfirmed()

    test_host_attestation()

    test_full_transport_and_receipt_chain()

    print(f"\n=== All 11 transport + evidence tests passed ===")
