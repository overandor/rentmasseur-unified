#!/usr/bin/env python3
"""HDAR one-command proof — a stranger runs this and verifies every claim.

No network, no cloud, no secrets, no container runtime required.

Usage:
  python3 demo.py              # full demo
  python3 demo.py --verbose    # with all intermediate output
  python3 demo.py --clean      # clean sandbox first

Exit 0 = every claim verified. Exit 1 = a claim failed.
"""
import argparse, hashlib, json, os, shutil, sys, time
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

from capsule.store import ContentStore
from capsule.identity import AgentIdentity, LineageEpoch
from capsule.receipt import ReceiptChain
from capsule.seal import CapsuleSealer
from capsule.restore import CapsuleRestorer
from capsule.capabilities import Capability, CapabilityCompiler
from capsule.restoration_contract import RestorationClass, RestorationContract
from lifecycle.state_machine import LifecycleStateMachine, AgentState
from lifecycle.effects import EffectRegistry
from lifecycle.lease import LeaseManager
from lifecycle.controller import LifecycleController
from providers.unsafe_host import UnsafeHostProvider
from gateway.forced_command import SSHGateway
from evidence.offline_verify import OfflineVerifier

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} — {detail}")

def banner(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def step(n, total, text):
    print(f"\n  [{n}/{total}] {text}")


def run_demo(verbose=False):
    global passed, failed
    passed = 0
    failed = 0

    sandbox = HERE / "sandbox" / "demo"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)

    banner("HDAR Demo: Hardware-Detached Agent Runtime")
    print(f"  Host: {os.uname().sysname} {os.uname().machine}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Sandbox: {sandbox}")
    print(f"  Provider: unsafe-host (development — NOT isolated runtime)")

    # ─── Setup ───────────────────────────────────────────
    store = ContentStore(sandbox / "store")
    identity = AgentIdentity.create(name="agent-demo-01")
    epoch = LineageEpoch.genesis(identity.agent_id)
    sealer = CapsuleSealer(store, identity)
    restorer = CapsuleRestorer(store)

    provider = UnsafeHostProvider(str(sandbox / "provider"))
    lease_mgr = LeaseManager(str(sandbox / "leases.db"))
    effects = EffectRegistry(str(sandbox / "effects.jsonl"))

    ws = sandbox / "workspace"
    ws.mkdir()
    (ws / "solve.py").write_text("def solve(n):\n    return sum(range(1, n + 1))\n")
    (ws / "PROGRESS.md").write_text(
        "# agent-demo-01 work log\n"
        "step 1 of 3: analyzed the problem   [done on HOST A]\n"
        "step 2 of 3: implement solve()      [pending]\n"
        "step 3 of 3: verify                 [pending]\n"
    )
    (ws / "test_solve.py").write_text(
        "from solve import solve\n"
        "assert solve(10) == 55, f'solve(10)={solve(10)}, expected 55'\n"
        "print('test passed: solve(10) = 55')\n"
    )

    total = 18

    # ─── 1. Capsule: seal → destroy → restore ────────────
    step(1, total, "CAPSULE: seal → destroy → restore")
    manifest, chain = sealer.seal(
        workspace_dir=ws, epoch=epoch,
        objective="Implement and verify solve(n) = sum(1..n)",
        continuation_point="step 2 of 3: implement solve()",
    )
    capsule_path = sandbox / "capsule.json"
    sealer.write_capsule(manifest, capsule_path)
    root_hash = manifest.workspace_manifest["root_hash"]

    shutil.rmtree(ws)
    report = restorer.restore(capsule_path, ws, owner_public_key=identity.public_key)
    check("capsule seals and restores byte-identical", report["workspace_hash_matches"])
    check("manifest signature valid", report["signature_valid"])
    check("receipt chain valid", report["receipts_valid"])

    # ─── 2. State machine: lifecycle ordering ────────────
    step(2, total, "STATE MACHINE: lifecycle ordering enforced")
    sm = LifecycleStateMachine("agent-demo-01")
    check("starts DORMANT", sm.state == AgentState.DORMANT)
    check("rejects jump DORMANT→RUNNING", not sm.transition(AgentState.RUNNING))
    sm.transition(AgentState.ACQUIRING_LEASE)
    sm.transition(AgentState.MATERIALIZING)
    sm.transition(AgentState.VERIFYING_INPUT)
    sm.transition(AgentState.RUNNING)
    check("cannot seal from RUNNING", not sm.can_seal())
    sm.transition(AgentState.QUIESCING)
    check("can seal from QUIESCING", sm.can_seal())

    # ─── 3. Quiescence: blocks seal mid-payment ──────────
    step(3, total, "QUIESCENCE: cannot seal while effect in flight")
    effects2 = EffectRegistry(str(sandbox / "effects2.jsonl"))
    effect = effects2.register("agent-demo-01", "payment", b"pay $500")
    effects2.submit("agent-demo-01", effect.operation_id)
    q = effects2.check_quiescence("agent-demo-01")
    check("blocks seal while submitted", not q["quiescent"])
    effects2.commit("agent-demo-01", effect.operation_id, provider_receipt={"id": "ch_123"})
    q2 = effects2.check_quiescence("agent-demo-01")
    check("quiescent after commit", q2["quiescent"])

    # ─── 4. Duplicate prevention across migration ────────
    step(4, total, "DUPLICATE PREVENTION: payment not re-executed")
    op_id = "op-payment-fixed"
    effects2.register("agent-demo-01", "payment", b"pay $500", operation_id=op_id)
    effects2.commit("agent-demo-01", op_id)
    dup = effects2.register("agent-demo-01", "payment", b"pay $500", operation_id=op_id)
    check("duplicate payment prevented", dup.status == "committed")

    # ─── 5. Reconcile unknown effect ─────────────────────
    step(5, total, "RECONCILE: unknown effect resolved on wake")
    effects3 = EffectRegistry(str(sandbox / "effects3.jsonl"))
    eff = effects3.register("agent-1", "email", b"send welcome")
    effects3.mark_unknown("agent-1", eff.operation_id)
    def probe(op_id, e): return "committed"
    result = effects3.reconcile("agent-1", probe)
    check("unknown reconciled to committed", result["results"][0]["resolved_to"] == "committed")
    check("now quiescent after reconcile", result["now_quiescent"])

    # ─── 6. Fenced lease: concurrent wake refused ────────
    step(6, total, "FENCED LEASE: concurrent wake refused")
    lm = LeaseManager(str(sandbox / "leases2.db"))
    l1, e1 = lm.acquire("agent-1", "hash", 1, "host-A", "rt-1")
    l2, e2 = lm.acquire("agent-1", "hash", 1, "host-B", "rt-2")
    check("first lease acquired", l1 is not None)
    check("second lease refused", l2 is None and "lease held" in (e2 or ""))

    # ─── 7. Stale fencing token rejected ─────────────────
    step(7, total, "FENCING: stale token rejected")
    old_token = l1.fencing_token
    lm.release("agent-1", old_token)
    l3, _ = lm.acquire("agent-1", "hash", 1, "host-C", "rt-3")
    check("new lease acquired", l3 is not None)
    check("old token rejected", not lm.validate_token("agent-1", old_token))
    check("new token valid", lm.validate_token("agent-1", l3.fencing_token))
    lm.release("agent-1", l3.fencing_token)

    # ─── 8. Full lifecycle: wake → run → collapse ────────
    step(8, total, "LIFECYCLE: wake → run → collapse → dormant")
    ws2 = sandbox / "ws2"
    ws2.mkdir()
    (ws2 / "task.py").write_text("x = 42\nprint(x)\n")

    ctrl = LifecycleController("agent-lc", provider, lease_mgr, effects, str(sandbox / "lc_state"))
    wake_result = ctrl.wake("hash-lc", 1, str(ws2), "host-A")
    check("agent wakes to RUNNING", wake_result["woke"] and wake_result["state"] == "RUNNING")

    exec_result = ctrl.execute("run", "python3 task.py")
    check("execution succeeds", exec_result.success and "42" in exec_result.stdout)

    collapse_result = ctrl.collapse()
    check("collapse destroys runtime", collapse_result["collapsed"] and collapse_result["runtime_destroyed"])
    check("destruction verified", collapse_result["destruction_verified"])
    check("compute goes to zero", collapse_result["active_compute"] == "zero — dormant storage only")

    # ─── 9. Collapse refused mid-payment ─────────────────
    step(9, total, "COLLAPSE: refused while payment in flight")
    ws3 = sandbox / "ws3"
    ws3.mkdir()
    (ws3 / "f.txt").write_text("working")
    ctrl2 = LifecycleController("agent-pay", provider, lease_mgr, effects, str(sandbox / "pay_state"))
    ctrl2.wake("hash-pay", 1, str(ws3), "host-A")
    eff = ctrl2.register_effect("payment", b"pay $500")
    ctrl2.mark_effect_unknown(eff.operation_id)
    collapse_refused = ctrl2.collapse()
    check("collapse REFUSED mid-payment", not collapse_refused["collapsed"] and "REFUSE" in collapse_refused["reason"])

    # Reconcile and collapse
    ctrl2.reconcile_effects(lambda op_id, e: "committed")
    collapse_ok = ctrl2.collapse()
    check("collapse succeeds after reconcile", collapse_ok["collapsed"])

    # ─── 10. SSH gateway: connect → execute → disconnect ─
    step(10, total, "SSH GATEWAY: stable identity → wake → collapse")
    ws4 = sandbox / "ws4"
    ws4.mkdir()
    (ws4 / "hello.py").write_text("print('hello from agent')\n")

    gateway = SSHGateway(provider, lease_mgr, effects, str(sandbox / "gw_state"))
    gateway.register_agent("capsule-agent", "agent-ssh", "hash-ssh", 1, str(ws4))

    conn = gateway.connect("capsule-agent", holder_id="ssh-session-1")
    check("SSH connect wakes agent", conn["connected"])

    exec_result = gateway.execute_command("capsule-agent", "python3 hello.py")
    check("SSH execute works", exec_result["executed"] and "hello from agent" in exec_result.get("stdout", ""))

    disconn = gateway.disconnect("capsule-agent")
    check("SSH disconnect collapses agent", disconn["disconnected"] and disconn["runtime_destroyed"])

    # ─── 11. Tamper detection ────────────────────────────
    step(11, total, "TAMPER: modified capsule rejected")
    import json as _json
    tampered = _json.loads(capsule_path.read_text())
    tampered["objective"] = "tampered"
    tampered_path = sandbox / "tampered.json"
    tampered_path.write_text(_json.dumps(tampered))
    tampered_report = restorer.restore(tampered_path, sandbox / "tampered_ws", owner_public_key=identity.public_key)
    check("tampered capsule signature rejected", not tampered_report["signature_valid"])

    # ─── 12. Lineage: epoch chain ────────────────────────
    step(12, total, "LINEAGE: genesis → child epoch")
    genesis = LineageEpoch.genesis(identity.agent_id)
    child = LineageEpoch.child(genesis)
    check("child epoch has sequence 1", child.sequence == 1)
    check("child references parent", child.parent_epoch == genesis.epoch_id)

    # ─── 13. Provider: destruction verification ──────────
    step(13, total, "PROVIDER: runtime destruction verified")
    ws5 = sandbox / "ws5"
    ws5.mkdir()
    (ws5 / "f.txt").write_text("x")
    provider2 = UnsafeHostProvider(str(sandbox / "prov2"))
    provider2.materialize("rt-dest", str(ws5))
    check("runtime exists before destroy", not provider2.verify_destruction("rt-dest"))
    provider2.destroy("rt-dest")
    check("runtime gone after destroy", provider2.verify_destruction("rt-dest"))
    check("runtime not in listing", "rt-dest" not in provider2.list_runtimes())

    # ─── 14. State machine: failure states ───────────────
    step(14, total, "FAILURE STATES: explicit and recoverable")
    sm2 = LifecycleStateMachine("agent-fail")
    sm2.transition(AgentState.ACQUIRING_LEASE)
    sm2.transition(AgentState.LEASE_LOST, "lease expired")
    check("LEASE_LOST is failure state", sm2.is_failure())
    sm2.transition(AgentState.DORMANT, "recovered")
    check("failure state recovers to DORMANT", sm2.is_dormant())

    # ─── 15. Capability continuity: non-expansion ─────
    step(15, total, "CAPABILITY: authority never expands on migration")
    cap_compiler = CapabilityCompiler()
    src_caps = [Capability("filesystem.write", "/workspace"), Capability("budget.spend", "$50")]
    dst_caps_ok, rej = cap_compiler.compile(src_caps, {"filesystem.root": "/workspace/src", "budget.max": "$5"})
    check("scope narrowed (attenuation allowed)", len(dst_caps_ok) == 2 and len(rej) == 0)
    dst_caps_bad, rej2 = cap_compiler.compile(src_caps, {"filesystem.root": "/", "budget.max": "$500"})
    check("scope broadened (rejected)", len(dst_caps_bad) == 0 and len(rej2) == 2)
    check("deploy denied by default", len(cap_compiler.compile([Capability("deploy", "staging")], {})[0]) == 0)

    # ─── 16. Offline verifier: full chain ───────────────
    step(16, total, "OFFLINE VERIFIER: full chain with no network")
    verifier = OfflineVerifier(identity.public_key)
    epoch_v1 = LineageEpoch.genesis(identity.agent_id)
    manifest_v1, _ = sealer.seal(workspace_dir=ws, epoch=epoch_v1, objective="verify test")
    epoch_v2 = LineageEpoch.child(epoch_v1)
    manifest_v2, _ = sealer.seal(workspace_dir=ws, epoch=epoch_v2,
                                  objective="verify test 2", parent_capsule_hash=manifest_v1.manifest_hash)
    chain_result = verifier.verify_chain([manifest_v1, manifest_v2])
    check("offline verifier validates chain", chain_result.valid)
    check(f"chain has {chain_result.checks_passed} checks", chain_result.checks_passed > 0 and chain_result.checks_failed == 0)

    # Tamper detection
    manifest_v1.objective = "TAMPERED"
    tampered_result = verifier.verify_chain([manifest_v1])
    check("offline verifier detects tamper", not tampered_result.valid)

    # ─── 17. Restoration contract: exact vs semantic ──
    step(17, total, "RESTORATION: exact vs semantic contract")
    rc = RestorationContract()
    same_profile = rc.same_runtime_profile("Linux", "arm64", "apple-container", "mlx")
    exact_cls = rc.classify(same_profile, same_profile)
    check("same runtime → EXACT", exact_cls == RestorationClass.EXACT)

    src_prof, dst_prof = rc.cross_provider_profile("Darwin", "arm64", "mlx", "Linux", "x86_64", "vllm")
    semantic_cls = rc.classify(src_prof, dst_prof)
    check("cross-provider → SEMANTIC", semantic_cls == RestorationClass.SEMANTIC)

    sem_report = rc.report(src_prof, dst_prof)
    check("semantic report warns about divergence", sem_report.divergence_possible)
    check("semantic report requires approval", sem_report.user_approval_required)
    check("durable layer preserved exactly", any("workspace files" in p for p in sem_report.preserved_exact))
    check("runtime state discarded", any("KV cache" in d for d in sem_report.discarded))

    # ─── 18. Final: solve(10) = 55 ───────────────────────
    step(18, total, "WORK: solve(10) = 55 after restoration")
    exec((ws / "solve.py").read_text(), globals())
    check("solve(10) = 55", solve(10) == 55)

    # ─── Result ──────────────────────────────────────────
    banner("RESULT")
    print(f"  {passed} passed, {failed} failed")
    if failed == 0:
        print("  ALL CLAIMS VERIFIED")
        print("  (unsafe-host provider — NOT isolated runtime; NOT second-host migration)")
    else:
        print("  SOME CLAIMS FAILED")
    return failed == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="HDAR one-command proof")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    success = run_demo(verbose=args.verbose)
    sys.exit(0 if success else 1)
