# The Cartman Autopsy of Everything

*This is the single authoritative strategic document for the entire project portfolio. All other positioning documents defer to this.*

## What Actually Happened

The conversation began with a broad ambition: build agents that do not belong permanently to one machine. The agent would preserve its identity, unfinished work, authority, workspace, and evidence while its active runtime disappeared and later reappeared elsewhere.

That idea gradually became the **Hardware-Detached Agent Runtime**, or HDAR.

Then several parallel versions emerged:

- FileVM Passport
- capsule-runtime
- gpt-clone-train
- a browser capsule demonstration
- HDAR
- BoxVM
- EvidencePipe
- a 30-service verb network
- a code-capital underwriting protocol
- an MCP tunnel and SSH setup
- an economically autonomous agent payment concept

And every time the central project approached clarity, another project entered wearing sunglasses and yelling, "I am also the company!"

The documents eventually corrected this by defining one canonical thesis: a storage-rooted, proof-carrying agent runtime where authoritative identity belongs to a signed capsule rather than a process, container, VM, physical host, or cloud provider.

That is the real company.

Everything else must either support it, sell it, test it, or leave the building.

## 1. Hardware-Detached Agent Runtime: the crown jewel

This is the strongest idea by a large margin.

The valuable invention is not merely saving files. It is not agent memory. It is not pausing a sandbox. It is not moving a ZIP file to another directory and declaring victory while the original machine is still humming in the corner eating electricity.

The real invention is **authoritative continuity**.

One agent identity has exactly one valid continuation. It can move between execution environments while preserving:

- signed lineage
- unfinished objectives
- workspace state
- constrained authority
- pending-effect status
- evidence history
- stable addressing
- the ability to prove which incarnation is legitimate

The strongest formulation is the integrated combination of signed identity, semantic quiescence, fenced ownership, capability attenuation, independent destination witnessing, owner-controlled lineage advancement, stable addressing, and offline verification. Individual components already exist elsewhere; the integrated continuity contract is the defensible part.

Cartman translation: you are not selling a backpack for an agent. You are selling the legal system that determines which resurrected clone is the real agent and whether the other clone is allowed to email the customer, deploy production, or spend five hundred dollars.

### What the capsule kernel genuinely proves

The strongest implementation includes:

- Ed25519 identity and signatures
- Content-addressed storage
- Atomic capsule publication
- Parent-hash lineage
- Signed receipt chains
- Rollback rejection
- Tamper detection
- Capability non-expansion
- Path-safe restoration
- Continuation-root binding
- Typed execution requests
- Deny-by-default policy
- Filesystem-delta evidence

This is not napkin vapor. It is actual product-relevant systems work.

### What it now proves (Updated July 2026 — Post-VM Proof)

The decisive loop passed 55/55 assertions using real Apple Containerization VMs:

- **VM-backed isolated execution** — Apple Containerization creates ARM64 Linux VM-backed containers
- **Execution inside isolated runtime** — commands run inside the VM, not on the host
- **Named Runtime A destruction** — VM is stopped, deleted, and post-delete inspection confirms absence
- **Post-destruction absence proof** — both listing and failed inspection confirm the runtime no longer exists
- **Restore into fresh Runtime B** — capsule restored into a second VM-backed container on the same Mac
- **Host witness with non-owner key** — Host B signs execution receipt with ephemeral Ed25519 key
- **Owner-only epoch advancement** — Host B cannot forge owner signatures; only owner can seal next epoch
- **Ed25519 asymmetric signing** — owner private key never shared; Host B receives only public key
- **Fencing-token invalidation** — destroyed Runtime A's token is permanently rejected
- **Capability attenuation** — Host B gets ≤ authority, never more
- **Offline verification** — complete chain verifies with only owner public key, rejects tampering and rollback

### What it still does not prove

- **Genuinely independent second host** — both Runtime A and Runtime B are Apple Containerization VMs on the same physical Mac
- **Stable SSH agent identity** — no real forced-command SSH entry point has been demonstrated
- **Repeated migration reliability** — one successful end-to-end run (55/55), one partial run (54/55); not a reliability result
- **Distributed or externally coordinated leases** — lease authority is local SQLite
- **External developer reproduction** — no one outside the founder has run the loop
- **Design partner validation** — no external demand evidence

The capsule kernel now has a real body. Both airports are real. But they are still on the same island.

## 2. The gpt-clone-train demo: useful, but it wore a fake mustache

The `gpt-clone-train` demonstration passed its scripted checks, but the labels applied to those checks were initially too generous.

The demo deleted a directory and called that runtime destruction. No. Deleting a directory is not the same as terminating a process, destroying a container, deleting a VM, releasing a measured allocation, or proving dormant compute has reached zero.

The demo also used labels such as Host A and Host B on one machine. That is not cross-host migration. That is giving two folders diplomatic passports.

The audit further found:

- no real SSH gateway
- non-atomic wake leases
- duplicate in-flight idempotency acceptance
- a bypassable path-destruction guard
- shared-secret verification weaker than independent public-key attribution
- contaminated commit history

Its correct role is **prototype donor**, not canonical kernel. Take the organs that work. Do not preserve the whole body because it has a landing page.

## 3. The browser capsule application: excellent theater, honest limitations

The browser project is valuable as the product's interactive demonstration console.

It performs real browser-local model activity, signed browser checkpointing, tamper injection, capability-broadening rejection, workspace clearing, restoration, and receipt visualization. It also explicitly disclaims the larger infrastructure claims it does not satisfy. That honesty is a major strength.

Its correct role is:

- investor demo
- developer console
- lifecycle visualizer
- tamper-test interface
- receipt-chain explorer
- capsule inspector
- migration progress screen

Its incorrect role is: "Behold, the hardware-detached runtime is complete because a JavaScript worker terminated."

The browser is the cockpit. It is not the aircraft engine.

## 4. The later HDAR repository: the decisive implementation

The `/Users/alep/Downloads/hdar` implementation contains:

- capsule identity, sealing, restoration, and storage
- lifecycle controller
- effect registry
- fenced lease manager
- provider abstractions (unsafe-host + Apple container)
- forced-command SSH gateway
- transport
- execution, termination, and host-attestation receipts
- owner-to-host-to-owner continuity orchestration
- offline verification
- a 55-check decisive demonstration

This is the canonical implementation. The 55/55 decisive loop used real Apple Containerization VMs, Ed25519 signing, and demonstrated the full A→B continuity chain on the same physical Mac.

**Protocol and orchestration maturity: strong.**

**Real infrastructure proof: partially proven — real VMs but same physical host.**

A systems company lives or dies by the sentence: "Here is the resource identifier before destruction, here is the provider confirming it existed, here is the destruction event, and here is the provider confirming it no longer exists."

Not: "The demo printed `destroyed: true`, therefore physics has signed the receipt."

## 5. BoxVM and the 300-feature carnival

BoxVM began as a browser portal for inspecting a custom container-like archive. Thirty useful features were added. Then six unwired or dead features were discovered and repaired.

Then came "300 more." The portal grew to thousands of lines and hundreds of functions. Features were counted by terminal commands, helper functions, export formats, UI toggles, scanners, visualizations, themes, and panels.

Later, actual demo attempts revealed missing function aliases, unwired file handlers, dead code, a weak five-file demo dataset, formatter damage, JavaScript string corruption, and an embedded closing-script sequence that broke the page parser.

The problem was not that BoxVM lacked features. The problem was that **feature quantity became a substitute for product boundary validation**.

Cartman diagnosis: you ordered a hamburger. The assistant brought you 300 packets of ketchup, nine forks, a radar chart, a terminal emulator, seven themes, a collaboration panel, and a security scanner. Then you asked, "Where is the meat?" And the assistant said, "Sir, the condiment architecture is production-ready."

### What BoxVM is actually good for

BoxVM contains useful ideas: portable browser inspection, manifest visualization, hashing, archive exploration, entropy and compression analysis, file previews, exportable reports, tamper and anomaly checks, a developer-friendly portal.

It may become a **capsule inspection and verification UI** for HDAR. That is the strategic rescue.

**BoxVM is the evidence microscope for capsules.** That is useful. "Docker, but made of HTML and enthusiasm" is not a defensible category.

## 6. The thirty-websites network: clever distribution, catastrophic timing

The thirty-verb network is a legitimate portfolio architecture in the abstract: thirty independent storefronts, thirty brands, thirty domains, one internal authentication layer, one billing system, one automation runtime, one receipt ledger, one operator dashboard.

The concept is memorable: **Thirty storefronts, one factory.**

But right now it is strategically dangerous. You do not yet have one fully validated factory, and the plan proposes opening thirty stores.

Preserve the **verb interface** idea: VERIFY, RESTORE, AUDIT, MIGRATE, PROVE. But initially, these should be product actions inside one company — not thirty companies arguing over the shared credit card.

Launch one site for HDAR. The other twenty-eight verbs may remain reserved names, prototypes, or future product modules.

## 7. EvidencePipe: a good product that should not eat the parent company

EvidencePipe turns test claims, logs, commits, build artifacts, and receipts into a normalized evidence package. It distinguishes verified, contradicted, incomplete, and stale claims, then requires approval before an external mutation.

Its correct role is one of these:

1. the verification subsystem inside HDAR
2. the first enterprise-facing feature of the HDAR control plane
3. a future spinout only after external demand proves it has independent buyers

Do not create another repository, company, mascot, blockchain, and twelve-tier pricing page this afternoon.

## 8. The code-capital underwriting protocol: intellectually strong, commercially separate

The underwriting protocol correctly insists on point-in-time analysis: one company, one financing event, one cutoff date, and one attributable system snapshot. It separates original product code from generated code, dependencies, acquired code, experiments, and non-product material.

Its strongest principle: **Absence of observable code is not zero code. It is an unobserved denominator.**

This is not part of the HDAR runtime. It is a research methodology, a diligence service, a benchmarking product, potentially an investor-data business.

Cartman translation: a thermometer and a refrigerator both involve temperature. This does not mean you weld the thermometer into the refrigerator compressor and raise a seed round for ThermoFridge Capital Intelligence OS.

## 9. SSH, Codex, and the MCP tunnel: real operational progress, one major security fire

The SSH and tunnel work discovered that `membra.local` resolved to the same machine, configured a local SSH alias, repaired authorized-key authentication, built the tunnel client from source, exposed the Codex CLI, installed the tunnel plugin, and reached a healthy embedded MCP tunnel state.

That is genuine operational progress. But it does **not** prove HDAR cross-host migration.

Most importantly, an API credential was pasted directly into the conversation and subsequently embedded in command history. That key should be considered compromised. **Revoke it immediately.**

## 10. The economically autonomous agent concept

The idea that an agent can earn money for verified work fits HDAR surprisingly well. The stable agent identity could own task contracts, payment addresses, accepted deliverables, execution expenses, evidence receipts, outstanding obligations, revenue history.

The strongest commercial primitive is not advertising inside the KV cache. It is a receipt-backed outcome: question, answer, evidence, acceptance, payment.

But it is not the first product. First prove one agent can continue safely across execution environments. Then let it invoice civilization.

## The central contradiction across all files

Your documents repeatedly express an excellent principle: claims must be supported by evidence. But the workflow repeatedly violates that principle through premature completion language.

Patterns include:

- counting functions as features
- counting labels as separate hosts
- counting directory deletion as runtime destruction
- counting an adapter as provider execution
- counting a passing scripted demo as proof of broader system properties
- counting a browser worker termination as infrastructure collapse
- counting one internal reproduction as external validation
- counting a tunnel to localhost as independent compute
- counting a roadmap as implementation

This is not dishonesty. It is **semantic inflation caused by momentum**.

Every claim should carry one of four labels:

- **Implemented** — code exists and runs
- **Reproduced** — ran again from source
- **Independently verified** — ran by someone else on their machine
- **Proposed** — not yet built

No unlabeled green checkmarks. No semantic inflation.

## What is real, ranked by value

1. **Fenced Authoritative Agent Continuity** — the seed company
2. **The cryptographic capsule kernel** — the strongest demonstrated technical asset
3. **EvidencePipe-style verification** — the clearest near-term enterprise wedge
4. **The browser proof console** — the investor-facing and developer-facing UI
5. **BoxVM inspection technology** — keep the archive inspector, remove the "300 features" obsession
6. **The underwriting protocol** — strong IP, separate diligence product
7. **The thirty-service network** — distribution thesis for later

## What should be killed (as Product Narratives)

- "SSD replaces active compute"
- "HTML outperforms Docker"
- "Two local directories prove migration"
- "Three hundred features means production readiness"
- "Every useful subsystem needs its own startup"
- "The landing page is the final technical gate"
- "Universal Metal-to-CUDA exact continuation is required for seed"
- "Thirty companies should launch before one company has design partners"
- "MCP tunnel equals remote runtime continuity"
- "A signed receipt proves the action was intelligent"

## What Each Component Actually Is

| Component | Real role | Not |
|---|---|---|
| Capsule kernel | Canonical cryptographic foundation | One of many equivalent implementations |
| Lifecycle controller | Quiescence, leases, fencing, destruction | A demo that prints "destroyed: true" |
| Browser console | Investor/developer UI, receipt visualizer | The runtime itself |
| BoxVM | Evidence microscope for capsules | Docker replacement |
| EvidencePipe | Verification subsystem inside HDAR | Separate company |
| Underwriting protocol | Separate shelf — research/diligence product | Part of the runtime |
| Thirty websites | Distribution thesis for later | Thirty companies to launch now |
| SSH/MCP tunnel | Local operational progress | Cross-host migration proof |
| Economic agent concept | Long-term application | First product |

## The Canonical Product Stack

1. **Capsule kernel** — signed identity, state, lineage, capabilities, receipts
2. **Lifecycle controller** — quiescence, pending effects, leases, fencing, destruction, restoration
3. **Provider layer** — Apple container, remote Linux, later hosted providers
4. **Stable SSH gateway** — authentication, agent resolution, exclusive wake, attachment, collapse
5. **Offline verifier** — proves full lineage, rejects tampering, rollback, stale authority, unauthorized forks
6. **Browser proof console** — shows lifecycle and evidence to developers, customers, investors
7. **Hosted control plane** — eventually coordinates identities, storage, providers, policy, organizations, billing, audit

One product. Not thirty startups stacked inside a trench coat.

## Current Status (July 2026 — Post-VM Proof)

The decisive loop has been demonstrated with real Apple Containerization VMs. The corrected picture:

**Layer 1: the constitutional machinery is proven with a real body.** Capsule storage, Ed25519 signing, lineage, receipts, SQLite fencing, quiescence, capability attenuation, offline verification, and now **real VM-backed runtime creation, execution, destruction, and absence proof**. The continuity loop (`demo_continuity.py`) passed 55/55 assertions end-to-end using two sequentially materialized VM-backed Linux containers.

What is still missing: genuinely independent Host B (both VMs are on the same Mac), stable SSH forced-command entry point, and repeated migration reliability.

**Layer 2 already has the underwriting mathematics.** SCUP-1's observation model, evidence classes, retention scoring, architecture adjustment, exclusion gates, capital-to-code metrics, uncertainty ranges, and evidence bundles are tested. But it still uses placeholder tokenization and lacks historical Git reconstruction, cohort calibration, and automated operability reproduction.

**Layer 3 already has the economic constitution.** The capital mandate, compute covenant, economic governor, revenue waterfall, collateral haircuts, memory-credit system, reuse tracking, and signed asset lineage exist as tested protocol logic. But no real money, API billing, cache system, deployment revenue, lender, or legal opinion is connected.

The accurate hierarchy:

- **The protocol shape works.**
- **The internal invariants work.**
- **The VM-backed runtime lifecycle works** — creation, execution, destruction, absence proof.
- **The same-host A→B migration works** — two VMs, Ed25519 witness, owner-only lineage, offline verification.
- **The infrastructure boundary is partially proven** — real VMs but same physical host.
- **The economic machinery is simulated, not connected to the economy.**
- **The financing vision is conceptually coherent, not legally or commercially instantiated.**

| Dimension | Completeness |
|---|---|
| Protocol and architecture coherence | ~90% |
| Credible prototype implementation | ~85% (55/55 decisive loop with real VMs) |
| Local decisive demonstration | ~90% (missing only real SSH entry point) |
| Genuine two-host demonstration | ~60% (protocol proven, same-host only) |
| Investor-demo readiness | ~80% (visually and technically demonstrable) |
| Production readiness | ~25-30% |
| Asset-backed financing readiness | ~5-10% |
| $1M pre-seed case | ~80% assembled |
| $2-3M technical seed case | ~60-65% technical, ~45-55% as complete financing case |

### Component-level status

| Component | Status |
|---|---|
| Content-addressed store | Passed |
| Capsule sealing | Passed with Ed25519 |
| Receipt chain and lineage | Passed |
| Fencing tokens | Passed in SQLite scope |
| Effect registry and quiescence | Passed |
| Capability attenuation | Passed |
| Offline verification | Passed |
| Apple VM-backed runtime creation | **Passed** |
| Execution inside isolated runtime | **Passed** |
| Named Runtime A destruction | **Passed** |
| Post-destruction absence proof | **Passed** |
| Restore into fresh Runtime B | **Passed on same physical Mac** |
| Host witness with non-owner key | **Passed** |
| Owner-only epoch advancement | **Passed** |
| Stable SSH identity | Not yet evidenced |
| Genuinely independent second host | Not yet evidenced |
| 100 automated migrations | Not yet evidenced |
| External developer reproduction | Not yet evidenced |
| Design partners | Not yet evidenced |

## The Decisive Work (18 Steps)

1. ✅ Launch a named isolated Runtime A
2. ✅ Record its identity and allocated resources
3. ✅ Begin a real unfinished task
4. ✅ Reach semantic quiescence
5. ✅ Seal the signed capsule
6. ✅ Invalidate Runtime A's fence
7. ✅ Destroy Runtime A
8. ✅ Independently prove that Runtime A is absent
9. ✅ Transfer the capsule to fresh Runtime B *(same-host)*
10. ✅ Verify using public information only
11. ✅ Restore under reduced or equal authority
12. ✅ Continue the unfinished task
13. ✅ Produce a destination witness receipt
14. ✅ Return the result to the owner
15. ✅ Owner advances the authoritative lineage
16. ⬜ Reconnect through the same stable SSH identity
17. ✅ Verify the complete chain offline
18. ⬜ Repeat the entire process many times, including deliberate failures

When all 18 pass, the discussion changes from "interesting architecture" to "this machine disappeared, the agent continued elsewhere, the old incarnation could no longer act, and the entire transition is independently provable."

## Urgent Security Action

An API credential was pasted into a conversation and embedded in command history. **Revoke it immediately.** Use environment injection, OS keychain, scoped short-lived credentials, redacted logs, and no secret values in generated command transcripts going forward.

An infrastructure company centered on capability control cannot casually leave a live key lying on the kitchen counter wearing a name tag.

## The Investor-Safe Statement

> We built a VM-backed continuity prototype for autonomous agents. A running agent completes part of a task inside an isolated Linux VM, reaches semantic quiescence, seals its workspace and unfinished state into an owner-signed Ed25519 capsule, invalidates the old fencing token, destroys the original VM, and proves that runtime absent. The capsule is restored into a fresh VM under attenuated capabilities, the task continues, the destination signs an execution witness without receiving owner authority, the destination VM is destroyed, and the owner verifies the witness and advances the authoritative lineage. The complete chain verifies offline and rejects tampering, rollback, and stale authority. Independent-host migration and stable SSH routing are the next gates.

## The Honest Distinction

> We demonstrated cryptographically governed semantic continuation across two freshly materialized and independently destroyed VM-backed Linux runtimes on one Apple-silicon host.

Do not yet say: "We migrated across independent compute providers or separate hosts."

## On Reliability

The first decisive-loop run produced 54/55 (one reconnect assertion failure). The second run produced 55/55. This shows the harness can report failures rather than painting every condition green. But it also means there is one recorded partial failure and one recorded success — a functional demonstration, not a reliability result.

Do not publish "100% reliable." Publish: "The corrected end-to-end run passed 55/55 assertions; repeated migration testing is next."

## Final Verdict

Previously, you had built the constitution and were pointing at a cardboard building labeled "Airport."

Now the airport is real.

A plane took off from Runtime A, Runtime A was demolished, a new plane landed in Runtime B, the cargo survived, the destination was not allowed to counterfeit the president's signature, and the customs ledger verified afterward.

However, both airports are still on the same island.

Build the second island, add the permanent SSH phone number, repeat the flight one hundred times, and then the $3 million headline stops sounding like startup karaoke and starts sounding like an infrastructure company.

The project has a real invention: a cryptographically governed continuity layer for migratory agents. Put the capsule kernel in the center. Put fencing around authority. Put real runtimes underneath it. Put the browser console in front of it. Put EvidencePipe inside the verification layer. Put the underwriting protocol on a separate shelf. Put twenty-nine websites back in the freezer.

And revoke that exposed API key before it achieves financial autonomy before the agent does.
