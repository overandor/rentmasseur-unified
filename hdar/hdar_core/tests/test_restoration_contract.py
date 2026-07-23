"""Tests for dual exact/semantic restoration contract."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from capsule.restoration_contract import (
    RestorationClass, CompatibilityProfile, RestorationContract, RestorationReport,
)


def test_exact_restoration_same_runtime():
    """Same OS, arch, engine → EXACT restoration."""
    contract = RestorationContract()
    profile = contract.same_runtime_profile("Linux", "arm64", "apple-container", "mlx")

    cls = contract.classify(profile, profile)
    assert cls == RestorationClass.EXACT
    print("[PASS] Restoration: same runtime → EXACT ✓")


def test_semantic_restoration_cross_provider():
    """Different OS/arch/engine → SEMANTIC restoration."""
    contract = RestorationContract()
    source, dest = contract.cross_provider_profile(
        "Darwin", "arm64", "mlx",
        "Linux", "x86_64", "vllm",
    )

    cls = contract.classify(source, dest)
    assert cls == RestorationClass.SEMANTIC
    print("[PASS] Restoration: cross-provider → SEMANTIC ✓")


def test_degraded_when_durable_layer_broken():
    """If durable truth layer can't be preserved → DEGRADED."""
    contract = RestorationContract()
    source = CompatibilityProfile(
        source_os="Linux", dest_os="Linux",
        source_arch="arm64", dest_arch="arm64",
        identity_exact=True, lineage_exact=True,
        capabilities_exact=True, receipts_exact=True, goals_exact=True,
        filesystem_exact=True,
    )
    dest = CompatibilityProfile(
        source_os="Linux", dest_os="Linux",
        source_arch="arm64", dest_arch="arm64",
        # Durable layer broken
        identity_exact=False, lineage_exact=False,
        capabilities_exact=False, receipts_exact=False, goals_exact=False,
        filesystem_exact=False,
    )

    cls = contract.classify(source, dest)
    assert cls == RestorationClass.DEGRADED
    print("[PASS] Restoration: broken durable layer → DEGRADED ✓")


def test_report_lists_preserved_and_discarded():
    """Report explicitly lists what was preserved and what was discarded."""
    contract = RestorationContract()
    source, dest = contract.cross_provider_profile(
        "Darwin", "arm64", "mlx",
        "Linux", "x86_64", "vllm",
    )

    report = contract.report(source, dest)
    assert report.restoration_class == RestorationClass.SEMANTIC

    # Durable truth layer must be in preserved_exact
    assert any("workspace files" in p for p in report.preserved_exact)
    assert any("agent cryptographic identity" in p for p in report.preserved_exact)
    assert any("epoch lineage" in p for p in report.preserved_exact)
    assert any("capability grants" in p for p in report.preserved_exact)
    assert any("signed receipt chain" in p for p in report.preserved_exact)

    # Runtime state must be in discarded
    assert any("process memory" in d for d in report.discarded)
    assert any("KV cache" in d for d in report.discarded)
    assert any("TCP" in d or "network" in d or "session" in d for d in report.discarded)

    print(f"[PASS] Restoration: report lists {len(report.preserved_exact)} preserved, "
          f"{len(report.discarded)} discarded ✓")


def test_report_divergence_warning():
    """Semantic restoration warns about possible divergence."""
    contract = RestorationContract()
    source, dest = contract.cross_provider_profile(
        "Darwin", "arm64", "mlx",
        "Linux", "x86_64", "vllm",
    )

    report = contract.report(source, dest)
    assert report.divergence_possible
    assert "diverge" in report.divergence_notes.lower()
    assert report.user_approval_required
    print("[PASS] Restoration: divergence warning present ✓")


def test_exact_report_no_divergence():
    """Exact restoration reports no divergence."""
    contract = RestorationContract()
    profile = contract.same_runtime_profile("Linux", "arm64", "apple-container", "mlx")

    report = contract.report(profile, profile)
    assert not report.divergence_possible
    assert not report.user_approval_required
    assert report.restoration_class == RestorationClass.EXACT
    print("[PASS] Restoration: exact → no divergence ✓")


def test_exact_rejected_when_any_declared_volatile_state_is_lost():
    """One volatile-state loss downgrades an otherwise exact restore."""
    contract = RestorationContract()
    source = contract.same_runtime_profile("Linux", "arm64", "apple-container", "mlx")
    dest = contract.same_runtime_profile("Linux", "arm64", "apple-container", "mlx")
    dest.network_sessions_exact = False

    report = contract.report(source, dest)
    assert report.restoration_class == RestorationClass.SEMANTIC
    assert report.divergence_possible
    assert any("TCP" in item for item in report.discarded)


def test_exact_rejected_when_runtime_provider_differs():
    """Matching OS, arch, and model engine cannot hide a runtime mismatch."""
    contract = RestorationContract()
    source = contract.same_runtime_profile("Linux", "arm64", "apple-container", "mlx")
    dest = contract.same_runtime_profile("Linux", "arm64", "remote-ssh", "mlx")

    assert contract.classify(source, dest) == RestorationClass.SEMANTIC


def test_degraded_report_requires_approval():
    """Degraded restoration requires user approval."""
    contract = RestorationContract()
    source = CompatibilityProfile(
        source_os="Linux", dest_os="Linux",
        source_arch="arm64", dest_arch="arm64",
        filesystem_exact=True, identity_exact=True,
        lineage_exact=True, capabilities_exact=True,
        receipts_exact=True, goals_exact=True,
    )
    dest = CompatibilityProfile(
        source_os="Linux", dest_os="Linux",
        source_arch="arm64", dest_arch="arm64",
        filesystem_exact=False, identity_exact=False,
        lineage_exact=False, capabilities_exact=False,
        receipts_exact=False, goals_exact=False,
    )

    report = contract.report(source, dest)
    assert report.restoration_class == RestorationClass.DEGRADED
    assert report.user_approval_required
    assert "manual review" in report.divergence_notes.lower()
    print("[PASS] Restoration: degraded → requires approval ✓")


def test_report_serializable():
    """Report can be serialized to dict for capsule inclusion."""
    contract = RestorationContract()
    source, dest = contract.cross_provider_profile(
        "Darwin", "arm64", "mlx",
        "Linux", "x86_64", "vllm",
    )

    report = contract.report(source, dest)
    d = report.to_dict()
    assert d["restoration_class"] == "semantic"
    assert isinstance(d["preserved_exact"], list)
    assert isinstance(d["discarded"], list)
    assert isinstance(d["divergence_possible"], bool)
    print("[PASS] Restoration: report serializable ✓")


def test_cross_engine_same_arch_is_semantic():
    """Same arch but different inference engine → SEMANTIC (KV cache lost)."""
    contract = RestorationContract()
    source, dest = contract.cross_provider_profile(
        "Linux", "arm64", "mlx",
        "Linux", "arm64", "vllm",  # same OS+arch, different engine
    )

    cls = contract.classify(source, dest)
    assert cls == RestorationClass.SEMANTIC
    report = contract.report(source, dest)
    assert any("KV cache" in d for d in report.discarded)
    print("[PASS] Restoration: same arch, different engine → SEMANTIC ✓")


if __name__ == "__main__":
    test_exact_restoration_same_runtime()
    test_semantic_restoration_cross_provider()
    test_degraded_when_durable_layer_broken()
    test_report_lists_preserved_and_discarded()
    test_report_divergence_warning()
    test_exact_report_no_divergence()
    test_degraded_report_requires_approval()
    test_report_serializable()
    test_cross_engine_same_arch_is_semantic()
    print(f"\n=== All 9 restoration contract tests passed ===")
