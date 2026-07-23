"""Tests for capability compiler + offline verifier."""

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from capsule.capabilities import Capability, CapabilityCompiler
from capsule.store import ContentStore
from capsule.identity import AgentIdentity, LineageEpoch
from capsule.seal import CapsuleSealer, CapsuleManifest
from evidence.offline_verify import OfflineVerifier


# ─── Capability Compiler ─────────────────────────────────

def test_capability_preserves_scope():
    """Capabilities with matching scope are preserved."""
    compiler = CapabilityCompiler()
    src = [Capability("filesystem.write", "/workspace")]
    dst, rejections = compiler.compile(src, {"filesystem.root": "/workspace"})
    assert len(dst) == 1
    assert dst[0].name == "filesystem.write"
    assert len(rejections) == 0
    print("[PASS] Capability: matching scope preserved ✓")


def test_capability_narrows_scope():
    """Narrower destination scope is allowed (attenuation)."""
    compiler = CapabilityCompiler()
    src = [Capability("filesystem.write", "/workspace")]
    dst, rejections = compiler.compile(src, {"filesystem.root": "/workspace/src"})
    assert len(dst) == 1
    assert len(rejections) == 0
    print("[PASS] Capability: scope narrowed (attenuation) ✓")


def test_capability_rejects_broadening():
    """Broader destination scope is rejected."""
    compiler = CapabilityCompiler()
    src = [Capability("filesystem.write", "/workspace")]
    dst, rejections = compiler.compile(src, {"filesystem.root": "/"})
    assert len(dst) == 0
    assert len(rejections) == 1
    assert "broadening" in rejections[0].lower()
    print(f"[PASS] Capability: scope broadening rejected ({rejections[0]}) ✓")


def test_capability_budget_rejects_increase():
    """Higher budget in destination is rejected."""
    compiler = CapabilityCompiler()
    src = [Capability("budget.spend", "$5")]
    dst, rejections = compiler.compile(src, {"budget.max": "$50"})
    assert len(dst) == 0
    assert len(rejections) == 1
    assert "exceeds" in rejections[0].lower()
    print("[PASS] Capability: budget increase rejected ✓")


def test_capability_budget_allows_decrease():
    """Lower budget in destination is allowed."""
    compiler = CapabilityCompiler()
    src = [Capability("budget.spend", "$50")]
    dst, rejections = compiler.compile(src, {"budget.max": "$5"})
    assert len(dst) == 1
    assert dst[0].scope == "$5"
    print("[PASS] Capability: budget decrease allowed ✓")


def test_capability_deploy_denied_by_default():
    """Deploy is denied unless explicitly allowed."""
    compiler = CapabilityCompiler()
    src = [Capability("deploy", "staging")]
    dst, rejections = compiler.compile(src, {})
    assert len(dst) == 0
    assert "deploy not allowed" in rejections[0]
    print("[PASS] Capability: deploy denied by default ✓")


def test_capability_deploy_allowed_when_explicit():
    """Deploy is allowed when destination policy explicitly permits."""
    compiler = CapabilityCompiler()
    src = [Capability("deploy", "staging")]
    dst, rejections = compiler.compile(src, {"deploy.allowed": "true"})
    assert len(dst) == 1
    print("[PASS] Capability: deploy allowed when explicit ✓")


def test_capability_unknown_denied():
    """Unknown capability types are denied by default."""
    compiler = CapabilityCompiler()
    src = [Capability("unknown.capability", "something")]
    dst, rejections = compiler.compile(src, {})
    assert len(dst) == 0
    assert "unknown" in rejections[0].lower()
    print("[PASS] Capability: unknown type denied by default ✓")


def test_capability_non_expansion_verification():
    """verify_non_expansion catches authority expansion."""
    compiler = CapabilityCompiler()
    src = [Capability("filesystem.write", "/workspace")]
    dst = [Capability("filesystem.write", "/")]  # broader
    ok, violations = compiler.verify_non_expansion(src, dst)
    assert not ok
    assert len(violations) == 1
    assert "expanded" in violations[0].lower()
    print(f"[PASS] Capability: non-expansion violation detected ✓")


def test_capability_non_expansion_ok():
    """verify_non_expansion passes when authority is preserved or reduced."""
    compiler = CapabilityCompiler()
    src = [Capability("filesystem.write", "/workspace")]
    dst = [Capability("filesystem.write", "/workspace/src")]  # narrower
    ok, violations = compiler.verify_non_expansion(src, dst)
    assert ok
    assert len(violations) == 0
    print("[PASS] Capability: non-expansion passes for attenuation ✓")


# ─── Offline Verifier ────────────────────────────────────

def _make_capsule(tmp, identity, epoch, parent_hash=None):
    """Helper: create a real signed capsule."""
    store = ContentStore(tmp / "store")
    sealer = CapsuleSealer(store, identity)

    ws = tmp / f"ws_{epoch.sequence}"
    ws.mkdir()
    (ws / "task.py").write_text(f"# epoch {epoch.sequence}\nprint('working')\n")

    manifest, chain = sealer.seal(
        workspace_dir=ws, epoch=epoch,
        objective="test task",
        continuation_point="step 1",
        parent_capsule_hash=parent_hash,
    )
    return manifest


def test_offline_verifier_single_capsule():
    """Offline verifier validates a single capsule."""
    tmp = Path(tempfile.mkdtemp())
    identity = AgentIdentity.create(name="agent-test")
    epoch = LineageEpoch.genesis(identity.agent_id)
    manifest = _make_capsule(tmp, identity, epoch)

    verifier = OfflineVerifier(identity.public_key)
    result = verifier.verify_chain([manifest])
    assert result.valid
    assert result.checks_failed == 0
    assert result.checks_passed > 0
    print(f"[PASS] Offline verifier: single capsule valid ({result.checks_passed} checks) ✓")

    shutil.rmtree(tmp)


def test_offline_verifier_lineage():
    """Offline verifier validates epoch lineage across capsules."""
    tmp = Path(tempfile.mkdtemp())
    identity = AgentIdentity.create(name="agent-lineage")
    epoch1 = LineageEpoch.genesis(identity.agent_id)
    manifest1 = _make_capsule(tmp, identity, epoch1)

    epoch2 = LineageEpoch.child(epoch1)
    manifest2 = _make_capsule(tmp, identity, epoch2, parent_hash=manifest1.manifest_hash)

    verifier = OfflineVerifier(identity.public_key)
    result = verifier.verify_chain([manifest1, manifest2])
    assert result.valid
    assert result.chain_length == 2
    print(f"[PASS] Offline verifier: lineage valid across {result.chain_length} capsules ✓")

    shutil.rmtree(tmp)


def test_offline_verifier_detects_tamper():
    """Offline verifier detects a tampered manifest."""
    tmp = Path(tempfile.mkdtemp())
    identity = AgentIdentity.create(name="agent-tamper")
    epoch = LineageEpoch.genesis(identity.agent_id)
    manifest = _make_capsule(tmp, identity, epoch)

    # Tamper with the objective
    manifest.objective = "TAMPERED"

    verifier = OfflineVerifier(identity.public_key)
    result = verifier.verify_chain([manifest])
    assert not result.valid
    assert result.checks_failed > 0
    assert any("hash" in p.lower() or "signature" in p.lower() for p in result.problems)
    print(f"[PASS] Offline verifier: tamper detected ({result.problems}) ✓")

    shutil.rmtree(tmp)


def test_offline_verifier_detects_rollback():
    """Offline verifier detects epoch rollback."""
    tmp = Path(tempfile.mkdtemp())
    identity = AgentIdentity.create(name="agent-rollback")
    epoch1 = LineageEpoch.genesis(identity.agent_id)
    manifest1 = _make_capsule(tmp, identity, epoch1)

    epoch2 = LineageEpoch.child(epoch1)
    manifest2 = _make_capsule(tmp, identity, epoch2, parent_hash=manifest1.manifest_hash)

    # Create a fake rollback: epoch 1 capsule claiming to follow epoch 2
    manifest1.parent_capsule_hash = manifest2.manifest_hash
    # Recompute hash to make it internally consistent but wrong lineage
    manifest1.manifest_hash = manifest1.compute_hash()
    manifest1.signature = identity.sign(manifest1.canonical_bytes()).hex()

    verifier = OfflineVerifier(identity.public_key)
    result = verifier.verify_chain([manifest2, manifest1])  # reversed order
    assert not result.valid
    assert any("rollback" in p.lower() for p in result.problems)
    print(f"[PASS] Offline verifier: epoch rollback detected ✓")

    shutil.rmtree(tmp)


def test_offline_verifier_capability_non_expansion():
    """Offline verifier checks capability non-expansion."""
    tmp = Path(tempfile.mkdtemp())
    identity = AgentIdentity.create(name="agent-cap")
    epoch = LineageEpoch.genesis(identity.agent_id)
    manifest = _make_capsule(tmp, identity, epoch)

    source_caps = [{"name": "filesystem.write", "scope": "/workspace", "granted": True}]
    dest_caps = [{"name": "filesystem.write", "scope": "/", "granted": True}]  # broader

    verifier = OfflineVerifier(identity.public_key)
    result = verifier.verify_chain([manifest], source_caps=source_caps, dest_caps=dest_caps)
    assert not result.valid
    assert any("expansion" in p.lower() for p in result.problems)
    print(f"[PASS] Offline verifier: capability expansion detected ✓")

    shutil.rmtree(tmp)


def test_offline_verifier_wrong_key_fails():
    """Offline verifier fails with wrong key."""
    tmp = Path(tempfile.mkdtemp())
    identity = AgentIdentity.create(name="agent-key")
    epoch = LineageEpoch.genesis(identity.agent_id)
    manifest = _make_capsule(tmp, identity, epoch)

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    wrong_key = Ed25519PublicKey.from_public_bytes(os.urandom(32))
    verifier = OfflineVerifier(wrong_key)
    result = verifier.verify_chain([manifest])
    assert not result.valid
    assert any("signature" in p.lower() for p in result.problems)
    print("[PASS] Offline verifier: wrong key rejected ✓")

    shutil.rmtree(tmp)


if __name__ == "__main__":
    test_capability_preserves_scope()
    test_capability_narrows_scope()
    test_capability_rejects_broadening()
    test_capability_budget_rejects_increase()
    test_capability_budget_allows_decrease()
    test_capability_deploy_denied_by_default()
    test_capability_deploy_allowed_when_explicit()
    test_capability_unknown_denied()
    test_capability_non_expansion_verification()
    test_capability_non_expansion_ok()

    test_offline_verifier_single_capsule()
    test_offline_verifier_lineage()
    test_offline_verifier_detects_tamper()
    test_offline_verifier_detects_rollback()
    test_offline_verifier_capability_non_expansion()
    test_offline_verifier_wrong_key_fails()

    print(f"\n=== All 16 capability + verifier tests passed ===")
