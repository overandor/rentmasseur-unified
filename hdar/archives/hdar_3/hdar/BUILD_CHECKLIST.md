# Investor-Sendable Build Checklist

*This is not another roadmap document. It is the bridge between "tested constitutional prototype" and "observable infrastructure company."*

## Where we are (July 2026 — Post-VM Proof)

- **Decisive loop passed 55/55** — `demo_continuity.py` with real Apple Containerization VMs
- **Real VM-backed runtime lifecycle proven** — creation, execution, destruction, absence proof
- **Ed25519 asymmetric signing proven** — owner private key never shared, host witness with ephemeral key
- **Same-host A→B migration proven** — two VM-backed containers, owner-only lineage, offline verification
- **Stable SSH not yet evidenced** — no real forced-command entry point
- **Independent host not yet evidenced** — both VMs on same physical Mac
- **Reliability not yet established** — one 55/55 run, one 54/55 run; not a reliability result
- **Economic machinery simulated** — mandate, governor, collateral, revenue waterfall tested but not connected to real money
- **Pre-seed case ~75-80% assembled** — visually and technically demonstrable
- **Seed case ~65-70% technical, ~50-55% as complete financing case**

## Updated readiness assessment (July 2026)

| Dimension                        | Position |
| -------------------------------- | -------: |
| Protocol and architecture coherence |   ~90% |
| HDAR technical prototype |   ~70-75% (55/55 decisive loop with real VMs) |
| Local decisive demonstration |   ~90% (missing only real SSH entry point) |
| Genuine two-host demonstration |   ~60% (protocol proven, same-host only) |
| $1M pre-seed case |   ~75-80% assembled |
| $2-3M seed case (technical) |   ~65-70% |
| $2-3M seed case (complete financing) |   ~50-55% |
| Production readiness (Layer 1) |   ~30-40% |
| Asset-backed financing readiness |   ~5-10% |

### Component-level status

| Component                         | Status |
| --------------------------------- | ------ |
| Content-addressed store           | Passed |
| Capsule sealing                   | Passed with Ed25519 |
| Receipt chain and lineage         | Passed |
| Fencing tokens                    | Passed in SQLite scope |
| Effect registry and quiescence    | Passed |
| Capability attenuation            | Passed |
| Offline verification              | Passed |
| Apple VM-backed runtime creation  | **Passed** |
| Execution inside isolated runtime | **Passed** |
| Named Runtime A destruction       | **Passed** |
| Post-destruction absence proof    | **Passed** |
| Restore into fresh Runtime B      | **Passed on same physical Mac** |
| Host witness with non-owner key   | **Passed** |
| Owner-only epoch advancement      | **Passed** |
| Stable SSH identity               | Not yet evidenced |
| Genuinely independent second host | Not yet evidenced |
| 100 automated migrations          | Not yet evidenced |
| External developer reproduction   | Not yet evidenced |
| Design partners                   | Not yet evidenced |

The 55/55 decisive loop proves **real VM-backed continuity**, not production readiness. It establishes that the protocol binds to real isolated runtimes. It does not establish provider independence, distributed contention behavior, operational security, customer demand, payment causality, or legal enforceability.

## Four things to finish

Each item has a definition of done, the code that exists, and what's missing.

When all four pass in one uninterrupted loop (the 18-step decisive sequence), the discussion changes from "interesting architecture" to "this machine disappeared, the agent continued elsewhere, the old incarnation could no longer act, and the entire transition is independently provable."

---

## 1. ~~Real isolated Runtime A creation and verified destruction~~ — PASSED

**Status: PASSED.** Apple Containerization creates ARM64 Linux VM-backed containers, executes commands inside them, stops and deletes them, and post-delete inspection confirms absence. Demonstrated in the 55/55 decisive loop run.

**What was proven:**
- Named runtime created through `container` CLI
- Command executed inside isolated VM
- Runtime stopped and deleted
- Post-delete listing confirms absence
- Post-delete inspection confirms `exists: False`
- Termination receipt signed and verified

**What remains for production:**
- [ ] Repeated creation/destruction cycles (100+) with published metrics
- [ ] Concurrent creation/destruction under load
- [ ] Failure injection during destruction
- [ ] Resource cleanup verification (no orphaned VMs, no leaked memory)

---

## 2. Atomic leased ownership with stale fencing-token rejection — PARTIALLY PASSED

**Status: Partially passed.** The decisive loop demonstrated fencing-token invalidation: Runtime A's token is permanently rejected after destruction, and Runtime B acquires a new lease generation. SQLite compare-and-swap lease authority works within single-process scope.

**What was proven:**
- First lease acquired successfully
- Second concurrent lease refused (lease held)
- Stale fencing token rejected after release
- New fencing token valid for new lease generation
- Token invalidation signed as evidence receipt

**What remains:**
- [ ] Write integration test: two threads attempt concurrent acquire simultaneously
- [ ] Verify stale holder cannot call `controller.collapse()` (fencing token check)
- [ ] Verify stale holder cannot commit effects (fencing token check in effect registry)
- [ ] Add fencing token validation to `EffectRegistry.commit_effect()`
- [ ] Add fencing token validation to `CapsuleSealer.seal()` (reject stale generation)
- [ ] Distributed or externally coordinated lease authority (beyond local SQLite)

**Key invariant:** At most one lease generation may advance the authoritative agent state.

---

## 3. Independent Host B restoration and signed execution witnessing — PARTIALLY PASSED (same-host)

**Status: Protocol proven on same physical Mac.** The decisive loop demonstrated full A→B migration: capsule sealed on Runtime A, Runtime A destroyed, capsule restored into fresh Runtime B (second VM), workspace verified, capabilities attenuated, work continued, host witness signed with ephemeral key, owner verified witness and resealed next epoch. Host B could not forge owner signature.

**What was proven:**
- Capsule sealed with Ed25519 owner signature
- Runtime A destroyed, fencing invalidated
- Runtime B (fresh VM) restores capsule with owner's PUBLIC key only
- Workspace hash matches after restoration
- Capabilities attenuated (scope narrowed)
- Host B signs execution witness with ephemeral key (not owner key)
- Host B CANNOT create next authoritative epoch (signature doesn't verify under owner public key)
- Owner verifies witness and reseals epoch 1
- Offline verifier validates complete chain

**The critical distinction:** Both Runtime A and Runtime B are Apple Containerization VMs on the same physical Mac. This is **two real isolated VMs**, not **two independent hosts**.

**What remains for genuine independent host:**
- [ ] Provision a VPS (any Linux x86_64, $5/month) or second Mac
- [ ] Configure SSH key access to remote host
- [ ] Install Python 3 on remote host
- [ ] Copy `hdar/` source to remote host
- [ ] Write test: export capsule locally, transfer archive to remote host
- [ ] Write test: remote host imports capsule, verifies signature, restores workspace
- [ ] Write test: remote host executes work under attenuated capabilities
- [ ] Write test: remote host signs execution receipt with ephemeral key
- [ ] Write test: remote host attempts to sign next epoch → fails (no owner key)
- [ ] Write test: owner verifies remote receipt, re-seals next epoch
- [ ] Write test: offline verifier validates complete A→remote→A chain
- [ ] Integrate real cross-host migration into demo

**What Host B receives:**
```
capsule archive
owner public key (NOT private key)
expected agent_id
expected epoch
lease and fencing token
attenuated capability set
```

**What Host B signs:**
```
input capsule hash
host OS and architecture
runtime/session identity
owner-signature verification result
restored workspace root
operations performed
test results
output workspace root
returned delta hash
fencing token used
```

---

## 4. Stable SSH reconnection plus offline verification — PARTIALLY PASSED (offline verification only)

**Status: Offline verification passed. SSH entry point not yet real.**

The decisive loop demonstrated offline verification of the complete chain (18 checks passed), tamper detection (modified capsule rejected), and rollback detection (epoch rollback rejected). The logical SSH gateway (`gateway/forced_command.py`) resolves agent identity and materializes runtime in simulation.

**What was proven:**
- Offline verifier validates complete A→B chain with only owner public key
- Tampered capsule detected and rejected
- Epoch rollback detected and rejected
- Stale fencing token rejected
- Host witness signature verified with host public key
- Fencing invalidation verified offline

**What remains for real SSH:**
- [ ] Configure real sshd with `Match User capsule-agent` block
- [ ] Install `capsule-ssh-gateway` as ForceCommand
- [ ] Write test: SSH connect → gateway resolves agent → materializes runtime
- [ ] Write test: SSH disconnect → runtime collapses → returns to dormant
- [ ] Write test: SSH reconnect after migration → same agent, completed task
- [ ] Write test: tamper one filesystem byte → verifier fails
- [ ] Write test: tamper parent capsule hash → verifier fails
- [ ] Write test: tamper owner signature → verifier fails
- [ ] Write test: tamper fencing token → verifier fails
- [ ] Write test: tamper Host B signature → verifier fails

**SSH configuration:**
```sshconfig
Match User capsule-agent
    ForceCommand /usr/local/bin/capsule-ssh-gateway
    DisableForwarding yes
    PermitTTY yes
    X11Forwarding no
    PermitTunnel no
```

---

## When all four pass in one uninterrupted loop

The 18-step decisive sequence (status after 55/55 run):

1. ✅ Launch a named isolated Runtime A *(Item 1 — PASSED)*
2. ✅ Record its identity and allocated resources *(Item 1 — PASSED)*
3. ✅ Begin a real unfinished task *(Item 1 — PASSED)*
4. ✅ Reach semantic quiescence *(existing — PASSED)*
5. ✅ Seal the signed capsule *(existing — PASSED with Ed25519)*
6. ✅ Invalidate Runtime A's fence *(existing — PASSED)*
7. ✅ Destroy Runtime A *(Item 1 — PASSED)*
8. ✅ Independently prove that Runtime A is absent *(Item 1 — PASSED)*
9. ✅ Transfer the capsule to fresh Runtime B *(Item 3 — PASSED same-host)*
10. ✅ Verify using public information only *(Item 3 — PASSED)*
11. ✅ Restore under reduced or equal authority *(Item 3 — PASSED)*
12. ✅ Continue the unfinished task *(Item 3 — PASSED)*
13. ✅ Produce a destination witness receipt *(Item 3 — PASSED)*
14. ✅ Return the result to the owner *(Item 3 — PASSED)*
15. ✅ Owner advances the authoritative lineage *(existing — PASSED)*
16. ⬜ Reconnect through the same stable SSH identity *(Item 4 — not yet real)*
17. ✅ Verify the complete chain offline *(Item 4 — PASSED)*
18. ⬜ Repeat the entire process many times, including deliberate failures *(reliability campaign — not started)*

**Item 2 (concurrent fencing)** is exercised implicitly at steps 5-6 and 9-11: it guarantees that if two incarnations try to act, only one can publish.

When that works: "This machine disappeared, the agent continued elsewhere, the old incarnation could no longer act, and the entire transition is independently provable."

## For the $1M pre-seed

The case is ~75-80% assembled. The proof is now visually and technically demonstrable:
- 55/55 decisive loop with real Apple Containerization VMs
- Ed25519 owner signing, ephemeral host witness, owner-only lineage
- Real VM creation, execution, destruction, and absence proof
- Same-host A→B migration with capability attenuation and offline verification
- Clear thesis (authoritative agent continuity)
- Strong founder narrative
- This build checklist as the milestone plan

A $1M raise is plausibly supportable with the current proof, a focused pitch, the source repository, reproducible instructions, and a serious milestone plan.

## For the $2-3M technical seed, add

The project is ~65-70% ready technically, ~50-55% as a complete financing case. The gap is concentrated on external evidence:

- [x] A real isolated runtime is created, used, destroyed, and independently shown to be absent
- [ ] The same stable SSH agent identity wakes a newly materialized runtime
- [ ] The capsule crosses to an operationally independent Host B, continues work, returns through owner-controlled lineage
- [ ] The lifecycle survives repeated migration, corruption, rollback, duplicate-wake, crash-during-seal, and provider-failure tests
- [ ] External developers reproduce it without founder intervention
- [ ] Two design partners identify a costly continuity problem and use the system against it
- [ ] Repeated migration benchmarks (100+ cycles) with published metrics
- [ ] External security review
- [ ] Open protocol specification + independent verifier

## The investor-safe statement

> We built a VM-backed continuity prototype for autonomous agents. A running agent completes part of a task inside an isolated Linux VM, reaches semantic quiescence, seals its workspace and unfinished state into an owner-signed Ed25519 capsule, invalidates the old fencing token, destroys the original VM, and proves that runtime absent. The capsule is restored into a fresh VM under attenuated capabilities, the task continues, the destination signs an execution witness without receiving owner authority, the destination VM is destroyed, and the owner verifies the witness and advances the authoritative lineage. The complete chain verifies offline and rejects tampering, rollback, and stale authority. Independent-host migration and stable SSH routing are the next gates.

## The honest distinction

> We demonstrated cryptographically governed semantic continuation across two freshly materialized and independently destroyed VM-backed Linux runtimes on one Apple-silicon host.

Do not yet say:

> We migrated across independent compute providers or separate hosts.

That final distinction matters because a same-host control-plane failure could potentially affect the store, provider, leases, owner process, and both runtime incarnations. A remote VPS or second Mac would establish an administrative, network, and failure-domain boundary.

## On reliability

The first decisive-loop run produced 54/55 (one reconnect assertion failure). The second run produced 55/55. This shows the harness can report failures rather than painting every condition green. But it also means there is one recorded partial failure and one recorded success — a functional demonstration, not a reliability result.

Do not publish "100% reliable." Publish:

> The corrected end-to-end run passed 55/55 assertions; repeated migration testing is next.
