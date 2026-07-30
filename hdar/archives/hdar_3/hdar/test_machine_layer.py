#!/usr/bin/env python3
"""Test: self-modeling machine with model-addressed mailboxes,
semantic selectors, per-operation authorization, and perception receipts.

This test proves the full architecture:
  1. Machine snapshots itself (self-model)
  2. Capsule is addressed to a model (mailbox)
  3. Selector finds a compatible machine
  4. Every operation is independently authorized
  5. Perception receipt records what the model was permitted to perceive
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from machine import (
    SelfModel, MachineRegistry, Mailbox, MailboxRouter, ModelRequirement,
    FidelityLevel, AuthorizationGate, OperationRequest, AuthorizationDecision,
    PerceptionLedger,
)
from capsule.capabilities import Capability
from crypto import HostKeyPair, OwnerKeyPair

PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")

def main():
    print()
    print("=" * 72)
    print("  SELF-MODELING MACHINE + MODEL-ADDRESSED MAILBOXES")
    print("  Semantic Selectors + Per-Op Auth + Perception Receipts")
    print("=" * 72)
    print()

    # ─── 1. Self-model ─────────────────────────────────────────
    print("[1/7] Self-model: machine introspects its own state")
    model = SelfModel()
    state = model.snapshot(active_runtimes=["rt-test-1"])
    check("hostname captured", len(state.hostname) > 0)
    check("OS captured", len(state.os) > 0)
    check("arch captured", len(state.arch) > 0)
    check("CPU count > 0", state.cpu_count > 0)
    check("memory total > 0", state.memory_total_bytes > 0)
    check("active runtimes tracked", "rt-test-1" in state.active_runtimes)
    check("capabilities detected", len(state.capabilities) > 0)
    check("state hash is 64 chars", len(state.state_hash) == 64)
    check("state hash deterministic", state.compute_hash() == state.state_hash)
    print()

    # ─── 2. Machine registry + semantic selectors ─────────────
    print("[2/7] Semantic selectors: query for compatible machines")
    registry = MachineRegistry()
    local_state = registry.register_local(active_runtimes=[])
    check("machine registered", local_state.hostname in registry.list_machines())

    # Query for a machine with python3
    candidates = registry.select_machines({
        "required_tools": ["python3"],
        "cpu_arch": "arm64",
    })
    check("selector found candidates", len(candidates) > 0)
    check("candidate is satisfied", candidates[0].satisfied)
    check("candidate has score", candidates[0].score > 0)
    check("candidate has state hash", len(candidates[0].state_hash) == 64)

    # Query for impossible requirements
    impossible = registry.select_machines({
        "model_id": "nonexistent-model-xyz",
        "min_ram_bytes": 999_999_999_999,
    })
    check("impossible requirements return empty", len(impossible) == 0)
    print()

    # ─── 3. Model-addressed mailbox ────────────────────────────
    print("[3/7] Model-addressed mailbox with explicit fidelity and atomic expiry")
    req = ModelRequirement(
        model_id="test-model-7b",
        model_digest="abc123def456",
        min_ram_bytes=4_000_000_000,
        cpu_arch="arm64",
        required_tools=["python3"],
        acceptable_substitutes=["test-model-3b"],
        degradation_policy="degraded",
    )
    mailbox = Mailbox(
        mailbox_id="mb-001",
        capsule_hash="hash123",
        addressed_model=req,
        sealed_at=time.time(),
        ttl_seconds=100.0,
    )

    check("mailbox starts at FULL", mailbox.current_fidelity() == FidelityLevel.FULL)

    # Simulate aging; fidelity does not change before expiry.
    mailbox.sealed_at = time.time() - 85  # 85% of 100s TTL
    check("mailbox remains FULL at 80%", mailbox.current_fidelity() == FidelityLevel.FULL)

    mailbox.sealed_at = time.time() - 92
    check("mailbox remains FULL at 90%", mailbox.current_fidelity() == FidelityLevel.FULL)

    mailbox.fidelity = FidelityLevel.DEGRADED
    check("owner can explicitly select DEGRADED", mailbox.current_fidelity() == FidelityLevel.DEGRADED)

    mailbox.sealed_at = time.time() - 101
    check("mailbox expires at 100%", mailbox.current_fidelity() == FidelityLevel.EXPIRED)
    check("expired cannot execute", not FidelityLevel.EXPIRED.can_execute())
    print()

    # ─── 4. Mailbox routing ────────────────────────────────────
    print("[4/7] Mailbox router: route to compatible machine")
    # Fresh mailbox — no model_id so it matches any machine with the right tools
    fresh_mb = Mailbox(
        mailbox_id="mb-002",
        capsule_hash="hash456",
        addressed_model=ModelRequirement(
            model_id="",  # no model requirement — just tools and arch
            cpu_arch="arm64",
            required_tools=["python3"],
            degradation_policy="degraded",
        ),
        sealed_at=time.time(),
        ttl_seconds=3600.0,
    )

    router = MailboxRouter(registry)
    # Refresh registry snapshot
    registry.register_local()

    result = router.route(fresh_mb)
    check("fresh mailbox routed", result["accepted"])
    check("routed to local host", len(result["hostname"]) > 0)
    check("routed at FULL fidelity", result["fidelity"] == "full")

    # Expired mailbox
    expired_mb = Mailbox(
        mailbox_id="mb-003",
        capsule_hash="hash789",
        addressed_model=ModelRequirement(
            model_id="test-model-7b",
            cpu_arch="arm64",
            required_tools=["python3"],
        ),
        sealed_at=time.time() - 999999,
        ttl_seconds=1.0,
    )
    result_expired = router.route(expired_mb)
    check("expired mailbox rejected", not result_expired["accepted"])
    check("expired reason given", "expired" in result_expired["reasons"][0])
    print()

    # ─── 5. Per-operation authorization ────────────────────────
    print("[5/7] Per-operation authorization: every op independently checked")
    caps = [
        Capability("filesystem.write", "/workspace"),
        Capability("filesystem.read", "/workspace"),
        Capability("shell.exec", "/workspace"),
    ]

    gate = AuthorizationGate(
        capabilities=caps,
        fidelity=FidelityLevel.FULL,
        destination_policy={"filesystem.root": "/workspace"},
    )

    # Allowed: write within scope
    r1 = gate.authorize(OperationRequest(
        operation_type="filesystem.write",
        scope="/workspace/output.txt",
        command="",
    ))
    check("write within scope: ALLOW", r1.decision == AuthorizationDecision.ALLOW)

    # Denied: write outside scope
    r2 = gate.authorize(OperationRequest(
        operation_type="filesystem.write",
        scope="/etc/passwd",
        command="",
    ))
    check("write outside scope: DENY", r2.decision == AuthorizationDecision.DENY)

    # Denied: ungranted capability
    r3 = gate.authorize(OperationRequest(
        operation_type="network.egress",
        scope="api.example.com",
        command="",
    ))
    check("ungranted network: DENY", r3.decision == AuthorizationDecision.DENY)

    # Each record has a receipt hash
    check("auth record has hash", len(r1.receipt_hash) == 64)
    check("auth records retained", len(gate.records) == 3)

    # Summary
    s = gate.summary()
    check("summary: 1 allowed", s["allowed"] == 1)
    check("summary: 2 denied", s["denied"] == 2)
    print()

    # ─── 6. Fidelity-gated authorization ───────────────────────
    print("[6/7] Fidelity gates authorization: degraded fidelity restricts ops")
    degraded_gate = AuthorizationGate(
        capabilities=caps + [Capability("network.egress", "api.example.com")],
        fidelity=FidelityLevel.DEGRADED,
        destination_policy={"filesystem.root": "/workspace"},
    )

    # Network denied at degraded
    r_net = degraded_gate.authorize(OperationRequest(
        operation_type="network.egress",
        scope="api.example.com",
    ))
    check("network denied at DEGRADED", r_net.decision == AuthorizationDecision.DENY)

    # File write still allowed at degraded
    r_write = degraded_gate.authorize(OperationRequest(
        operation_type="filesystem.write",
        scope="/workspace/file.txt",
    ))
    check("file write allowed at DEGRADED", r_write.decision == AuthorizationDecision.ALLOW)
    print()

    # ─── 7. Perception receipts ────────────────────────────────
    print("[7/7] Perception receipts: cryptographic record of permitted perception")
    host_key = HostKeyPair.generate("host-test")

    ledger = PerceptionLedger(
        session_id="session-001",
        agent_id="agent-test",
        model_used="test-model-7b",
        addressed_model="test-model-7b",
        fidelity=FidelityLevel.FULL,
    )

    # Record perceptions
    ledger.record_perception("file.read", "/workspace/data.txt", permitted=True)
    ledger.record_perception("file.read", "/etc/shadow", permitted=False)
    ledger.record_perception("env.var", "HOME", permitted=True)
    ledger.record_perception("env.var", "AWS_SECRET_KEY", permitted=False)
    ledger.record_perception("model.inference", "test-model-7b", permitted=True)

    # Link authorization records
    ledger.record_authorization(r1)
    ledger.record_authorization(r2)

    # Finalize with host key
    receipt = ledger.finalize(host_key)

    check("receipt has session ID", receipt.session_id == "session-001")
    check("receipt has 5 perceptions", receipt.perception_count == 5)
    check("receipt has 3 permitted", receipt.permitted_count == 3)
    check("receipt has 2 denied", receipt.denied_count == 2)
    check("receipt has receipt hash", len(receipt.receipt_hash) == 64)
    check("receipt has signature", len(receipt.signature) > 0)
    check("receipt has host fingerprint", len(receipt.host_fingerprint) > 0)
    check("receipt hash is deterministic", receipt.compute_hash() == receipt.receipt_hash)

    # Verify signature
    from crypto import PublicKey
    host_pub = PublicKey.from_hex(host_key.public_key_hex)
    receipt_body = {k: v for k, v in receipt.to_dict().items()
                    if k not in ("signature", "receipt_hash")}
    check("receipt signature verifies", host_pub.verify(receipt_body, receipt.signature))

    # Live summary
    live = ledger.summary()
    check("live summary has perceptions", live["total_perceptions"] == 5)
    print()

    # ─── Result ────────────────────────────────────────────────
    print("=" * 72)
    print(f"  RESULT: {PASS} passed, {FAIL} failed")
    print()
    print("  Proven:")
    print("    - Self-modeling machine introspects state (CPU, RAM, models, caps)")
    print("    - Semantic selectors query for compatible machines with evidence")
    print("    - Model-addressed mailboxes with owner-selected fidelity and atomic expiry")
    print("    - Per-operation authorization: every op independently checked")
    print("    - Fidelity gates authorization (network denied at degraded)")
    print("    - Perception receipts: signed record of what model was permitted to perceive")
    print("=" * 72)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
