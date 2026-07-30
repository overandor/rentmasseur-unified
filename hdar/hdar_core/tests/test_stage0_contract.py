"""Validation for the frozen HDAR Stage 0 product contract."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "contracts" / "stage0_contract_v0.1.json"


def _contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _catalog_ids(path: Path, prefix_pattern: str):
    text = path.read_text(encoding="utf-8")
    return set(re.findall(prefix_pattern, text))


def test_stage0_contract_is_frozen_and_versioned():
    contract = _contract()
    assert contract["contract_version"] == "0.1.0"
    assert contract["status"] == "frozen"
    assert "signed capsule" in contract["promise"]
    assert "destroy its runtime" in contract["promise"]
    assert "SSH identity" in contract["promise"]


def test_stage0_required_documents_exist_and_name_version():
    contract = _contract()
    for rel_path in contract["required_documents"]:
        path = ROOT / rel_path
        assert path.is_file(), f"missing Stage 0 document: {rel_path}"
        text = path.read_text(encoding="utf-8")
        assert "v0.1" in text, f"document does not identify v0.1: {rel_path}"


def test_restoration_classes_are_complete_and_non_ambiguous():
    contract = _contract()
    classes = contract["restoration_classes"]
    assert set(classes) == {"exact", "semantic", "degraded"}
    assert classes["exact"]["durable_state"] == "verified_byte_identical"
    assert classes["exact"]["approval_required"] is False
    assert classes["semantic"]["approval_required"] is True
    assert classes["degraded"]["approval_required"] is True
    assert "missing_required_block" in contract["integrity_failures_are_never_degraded"]
    assert "invalid_owner_signature" in contract["integrity_failures_are_never_degraded"]


def test_capability_contract_is_deny_by_default_and_non_expanding():
    rules = _contract()["capability_rules"]
    assert rules["default"] == "deny"
    assert set(rules["destination_may"]) == {"preserve", "attenuate"}
    assert {"broaden_scope", "increase_budget", "add_capability"}.issubset(
        rules["destination_may_not"]
    )
    assert rules["broader_authority_requires"] == "new_owner_signed_grant"


def test_acceptance_catalog_matches_machine_readable_contract():
    contract_ids = set(_contract()["acceptance_ids"])
    catalog_ids = _catalog_ids(
        ROOT / "contracts" / "ACCEPTANCE_TESTS_V0_1.md",
        r"\b(?:S0|CAP|RESTORE|AUTH|EFFECT|LEASE|DESTROY|MIGRATE|SSH)-[A-Z0-9-]+-\d{3}\b",
    )
    assert len(contract_ids) == len(_contract()["acceptance_ids"]), "duplicate acceptance ID"
    assert contract_ids == catalog_ids


def test_unsupported_catalog_matches_machine_readable_contract():
    contract_ids = set(_contract()["unsupported_ids"])
    catalog_ids = _catalog_ids(
        ROOT / "contracts" / "UNSUPPORTED_FEATURES_V0_1.md",
        r"\bUNSUP-\d{3}\b",
    )
    assert len(contract_ids) == len(_contract()["unsupported_ids"]), "duplicate unsupported ID"
    assert contract_ids == catalog_ids


def test_current_evidence_boundary_does_not_claim_future_gates():
    boundary = _contract()["current_evidence_boundary"]
    assert boundary["accepted"] == "same_host_vm_backed_semantic_continuation"
    assert "physical_second_host_restoration" in boundary["not_accepted"]
    assert "stable_public_ssh_restoration" in boundary["not_accepted"]
    assert "exact_live_process_restoration" in boundary["not_accepted"]

