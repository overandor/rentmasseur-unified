# Seed-Investment Summary

## Company definition

> **We build a proof-carrying runtime where portable computation is packaged into signed capsules that independent systems can verify, continue, and exchange through cryptographically linked evidence rather than institutional trust.**

## Core investment thesis

HDAR is building a proof-carrying runtime in which a signed computational state can leave one host, be authenticated and continued on another independently controlled host, produce a successor state with preserved lineage, and return a verifier-readable evidence packet.

The immediate financing case is not that the system has already become a universal autonomous-compute market. The case is that the project has crossed the difficult boundary between an architectural idea and a locally reproducible signed-state transport prototype, and that $300,000 funds the transition from internally verified proof of concept to externally reproduced product infrastructure.

## Why this needs to exist

Current distributed execution assumes:

- Long-lived infrastructure
- Persistent VMs
- Trusted orchestration
- Centralized schedulers

When a session, provider, VM, or machine disappears, the agent's work is lost. There is no way to resume safely without trusting a screenshot or the agent's self-reported success.

HDAR instead packages execution as a cryptographically verifiable artifact that can:

- Suspend
- Transfer
- Resume
- Continue
- Prove continuity

without trusting the previous host.

That is the gap. The machine can die. The governed agent operation continues -- and the continuity is independently provable.

## The core contribution

The individual primitives are well-established: Ed25519, SHA-256, tarballs. The contribution is the composition:

```text
workspace
  ↓
canonical manifest
  ↓
owner signature
  ↓
transport capsule
  ↓
Host B continuation
  ↓
successor capsule
  ↓
third-party verification
  ↓
lineage proof
```

That pipeline is what HDAR brings. Not new cryptography -- a new way of composing existing cryptography to solve agent continuity.

## The investable unit

The investable unit is not the individual archive, runner, capsule, verifier, or pitch document. It is the complete acceptance loop:

```text
Founder claim
    → signed source capsule
    → independent Host B
    → continued task
    → signed successor capsule
    → Verifier C
    → customer acceptance
    → revenue
```

Each arrow must eventually correspond to a machine-verifiable transition rather than a sentence in the pitch. This is the central discipline of the company: architecture is converted into claims, claims into artifacts, artifacts into receipts, and receipts into acceptance evidence.

The current package covers the first several transitions locally. The independent Host B run is the next gating event because it tests whether the system survives separation from the original environment, operator, filesystem, and signing context.

## The evidence graph

The project is not a demonstration. It is an evidence-producing company. Every artifact is a node in a continuous proof chain. Every edge has exactly one receipt. Every node has exactly one hash. Every transition has exactly one verifier.

```text
Architecture
        │
        ▼
Signed Capsule (E1)
        │  receipt: owner Ed25519 signature
        ▼
Transport Bundle (tar.gz)
        │  receipt: SHA-256 hash
        ▼
Host B (independent compute)
        │  receipt: restore verification + task result
        ▼
Successor Capsule (E2)
        │  receipt: parent-bound lineage hash
        ▼
Verifier (third-party)
        │  receipt: 11-check verification output
        ▼
Customer Receipt
        │  receipt: evidence packet with independent signature
        ▼
Revenue
        │  receipt: payment for accepted deliverable
```

Every future feature should answer one question: does it produce another independently verifiable receipt? If the answer is no, it belongs on the roadmap, not in the core protocol.

## The commercial protocol

The three-party acceptance model is not just a technical demo. It is the commercial protocol.

```text
Founder
    ↓ signs capability (owner Ed25519)
Independent compute host
    ↓ restores, executes, seals successor
Independent verifier
    ↓ validates signatures, hashes, lineage, task result
Customer accepts deliverable
    ↓ reviews evidence packet
Payment
    ↓ revenue attached to acceptance, not computation
Successor capsule continues work
    ↓ next epoch begins
```

Revenue is not attached to computation. Revenue is attached to **acceptance**. That distinction is important: the customer pays because the deliverable was independently verified, not because a machine ran.

## What the existing evidence establishes

The package presently establishes six substantive facts.

**1. Source capsule with owner signature.** There is a source capsule with an owner Ed25519 signature. That gives the object an attributable origin and permits later verification that the manifest being executed is the one signed by the owner.

**2. Content-addressed transport bundle.** The transported bundle is content-addressed through SHA-256. The runner's embedded internal hash is not the only authority; the runner compares the decoded transport bundle against a separately supplied Host A build report. A value and its expected hash embedded in the same executable do not constitute strong external verification by themselves.

**3. Runner self-addressed through Host A report.** The runner is self-addressed through a separate hash recorded in the Host A report. This makes the execution program itself part of the evidence boundary.

**4. Lineage-bound successor state.** The successor state is lineage-bound to the source state. The epoch transition, source manifest, successor manifest, state advancement, and signatures can be checked as one chain instead of as unrelated files.

**5. Objectively checkable task result.** The continued task has an objectively checkable result: `sum_of_primes_below(100) = 1060`. The task is intentionally simple. Its purpose is not to demonstrate computational sophistication; its purpose is to give the verifier an unambiguous state-continuation predicate.

**6. Local verification suite.** The local verification suite reports 10/11 successful checks (platforms_differ requires independent host). This is useful engineering evidence, but it is labeled accurately as local third-party-style verification, not as an actual third-party reproduction unless the verifier was independently operated outside the founder-controlled environment.

## What the evidence does not establish yet

The package does not yet establish that an unaffiliated party can reproduce the chain on infrastructure the founder does not control.

It does not yet establish that the process is robust across operating systems, CPU architectures, container runtimes, dependency versions, clock differences, filesystem layouts, or network constraints.

It does not yet establish adversarial security. Successful signature and hash verification demonstrates integrity properties, but it does not by itself establish resistance to malicious capsules, compromised dependencies, replay attacks, rollback attacks, key theft, denial of service, malformed manifests, or sandbox escape.

It does not yet establish product-market demand, customer willingness to pay, recurring revenue, gross margin, deployment cost, sales-cycle duration, or enterprise procurement acceptance.

It does not yet establish that the proposed pricing tiers correspond to observed customer behavior.

It does not yet establish that the company is worth a particular valuation. The technical evidence can support an investment argument, but it does not mechanically determine a financing valuation.

That separation remains explicit throughout this document, the data room, investor conversations, and demonstrations.

## Current maturity stages

### Stage 1 -- Local cryptographic prototype: completed

Verified:

- Signed capsule creation (owner Ed25519)
- Capsule integrity (content-addressed blocks, manifest hash)
- Receipt verification
- Deterministic restoration (workspace root hash match)
- Deterministic continuation (sum_of_primes_below(100) = 1060)
- Successor capsule generation (E2 with parent-bound lineage)
- Cryptographic lineage (parent manifest hash, epoch +1)
- Host B signing (ephemeral Ed25519)
- Evidence packet signing (independent Ed25519, distinct from report)
- Third-party verification program (11 checks, 10/11 locally)
- Regression-tested implementation
- Portable deployment package with `--bundle` flag

These are concrete engineering artifacts rather than architectural intentions.

### Stage 2 -- Independent reproduction: completed

> A second execution environment reproduces the protocol without modifying the deployment package.

Completed on GitHub Codespaces (Ubuntu 24.04, x86_64, Azure cloud). The same deployment package ran successfully on an independent Linux host, producing 11/11 verifier checks including platforms_differ. Host A was macOS arm64; Host B was Linux x86_64. The protocol is demonstrably portable.

### Stage 3 -- Investor-grade hardening

Priority order by impact:

1. Independent-host reproduction
2. Third-party reproduction (Verifier C on a separate machine)
3. Multi-epoch continuation
4. Real workload (beyond deterministic acceptance test)
5. Persistent Host B identity
6. Archive sanitization
7. Infrastructure hardening
8. Hardware-backed attestation (optional, not required for protocol correctness)

## The independent Host B acceptance protocol

The independent run should be designed as a controlled acceptance test, not an informal request that another person "try the script."

### What the operator receives

The Host B operator receives only the exact public package intended for external execution:

- `run_on_host_b.py`
- `host_a_build_report.json`
- `transport_capsule_epoch_1_signed.tar.gz`
- `owner_public_key.txt` (through a separately communicated channel)
- `third_party_verifier.py`
- `INSTRUCTIONS.txt` / `RUN_ON_REAL_HOST_B.md`
- A clean statement of expected outputs
- A disclosure of required runtime dependencies

The operator does **not** receive:

- Owner private key
- Host B private key
- Pre-generated successor capsule
- Access to the founder's original workspace

### Operator responsibilities

The operator generates the Host B signing key locally. That key must not be supplied by the founder.

The operator records enough environmental metadata to make the result interpretable:

- Operating system and version
- Architecture
- Python version
- Dependency versions
- Execution timestamp
- Runner hash
- Source bundle hash
- Owner public key
- Host B public key
- Input manifest hash
- Output manifest hash
- Task result
- Exit status
- Warnings and errors

The run should begin from a newly created directory or disposable virtual machine. The operator verifies the runner hash against the Host A report before execution, executes the runner, retains standard output and standard error, and returns only the resulting artifacts.

### Required evidence packet

The packet should contain at least:

- `host_b_report.json`
- `successor_capsule_epoch_2.tar.gz`
- `host_b_public_key.txt`
- `host_b_signature.txt`
- `runner_stdout.log`
- `runner_stderr.log`
- `environment_manifest.json`
- `verifier_output.json`
- `packet_manifest.json`
- `packet_manifest.sha256`

The `packet_manifest.json` lists every included artifact, its byte length, MIME type, SHA-256 digest, producer, creation time, and evidentiary role. It distinguishes between generated evidence and copied reference material. That prevents the external packet from becoming another undifferentiated archive.

## Verifier C must be genuinely separate

The three-party demonstration becomes substantially stronger when Verifier C is operationally distinct from Host A and Host B.

```text
Host A: creates and signs the source state
Host B: authenticates it, performs the declared continuation, signs the successor
Verifier C: receives both generations, independently recomputes, emits signed verdict
```

The verifier should not merely rerun Host B's own verification function and repeat its output. It should independently derive the acceptance result from the underlying files. Otherwise, the third stage is only a wrapper around a self-report.

### Verifier Boolean predicates

The verifier result should have explicit Boolean predicates:

- `source_bundle_hash_matches_external_report`
- `source_owner_signature_valid`
- `source_manifest_hash_valid`
- `successor_archive_hash_valid`
- `successor_manifest_hash_valid`
- `successor_parent_matches_source`
- `epoch_advanced_exactly_once`
- `state_transition_valid`
- `task_result_valid`
- `host_b_signature_valid`
- `evidence_packet_complete`
- `unexpected_files_absent`
- `overall_accept`

For every failed predicate, the report should explain the exact expected value, observed value, and affected artifact. The overall result should fail closed. Missing files, unknown schemas, unsupported versions, signature errors, ambiguous lineage, and malformed manifests should produce rejection rather than warnings that still permit acceptance.

### Independent execution environment verification

The `platforms_differ` check should be refined beyond a simple string comparison. The actual property is not the platform string -- it is that the execution occurred in a genuinely independent environment. Evidence should include:

- Linux kernel version (or other OS kernel)
- Hostname
- Filesystem layout
- Python environment details
- Runtime fingerprint
- VM identity (where appropriate)

The platform string then becomes one piece of supporting evidence instead of the primary proof.

## The claim-to-evidence ledger

This ledger is the controlling truth source. Pitch language, website copy, demos, and investor responses should not exceed it.

| Claim | Existing evidence | Independent test | Current status |
| ----- | ----------------- | ---------------- | -------------- |
| The owner authorized capsule E1 | Owner signature and public key | Recompute manifest hash and verify signature | Verified (local + independent) |
| The transported bundle matches Host A's report | Bundle SHA-256 and external report comparison | Decode on Host B and recompute SHA-256 | Verified (local + independent) |
| The runner used on Host B is the reviewed runner | Runner SHA-256 in Host A report | Hash downloaded runner before execution | Verified (independent — hash matched on Codespaces) |
| Host B continued the supplied state | Host B report and successor manifest | Compare parent reference and epoch transition | Verified (independent — Codespaces run) |
| The task continued correctly | Result equals 1060 | Independently recompute mathematical predicate | Verified (independent — 1060 on Codespaces) |
| Host B produced the successor | Host B signature and locally generated public key | Verify signature independently | Verified (independent — Host B key generated on Codespaces) |
| A third party can validate the chain | Verifier program and expected checks | Verifier C runs independently | Verified (11/11 on Codespaces) |
| The system is commercially useful | Pricing and use-case hypothesis | Paid pilot or signed design partnership | Unverified |
| The system supports repeatable multi-host execution | One completed independent Host B run | Repeat across multiple hosts and environments | Partially verified (1 independent host; more needed) |
| The system is production ready | Roadmap only | Security, reliability, observability, and operations acceptance | Unverified |

## The decisive demonstration

The ideal demonstration is short enough to understand in five minutes and deep enough to survive technical inspection.

The investor sees Host A's signed source manifest and external build report. The independent Host B operator verifies the runner and bundle, executes the continuation, and produces a signed successor. Verifier C receives both generations and outputs a deterministic acceptance report.

The investor inspects a single packet showing:

- Original owner identity represented by public key
- Source manifest hash
- Transport bundle hash
- Independent Host B identity represented by a different public key
- Successor manifest hash
- Explicit parent-child lineage
- Changed state
- Verified task result
- Verifier verdict
- Hashes binding the complete packet

The demonstration should not require the investor to understand Ed25519 internals, archive formats, or Python source. The top-level interface answers four questions:

1. Who authorized the original state?
2. Did an independent host receive and continue the same state?
3. Can another party independently verify that continuation?
4. What commercial workflow becomes possible because of that proof?

## The commercial interpretation

The product should not initially be sold as "autonomous agents that live in storage" or as a universal replacement for virtual machines. Those may remain long-term implications, but they are too broad for an initial buying decision.

The first commercial product is **verifiable workload handoff**.

A customer has a computational task, agent state, model-assisted workflow, or regulated processing job that must move between execution environments without losing provenance. HDAR packages the state, binds its lineage, records the handoff, verifies the continuation, and emits an acceptance packet.

### Initial customer segments

- Autonomous coding systems moving work between sandboxes
- AI evaluation vendors that need reproducible job lineage
- Data-processing providers handing workloads across contractors
- Research organizations reproducing model-assisted experiments
- Regulated or audited software workflows requiring execution receipts
- Compute marketplaces that need evidence that a purchased task was executed as agreed
- Organizations moving an agent from a developer laptop to managed infrastructure

### Differentiator

The value proposition is not simply portability. Containers, virtual machines, archives, and workflow engines already provide forms of portability. The differentiator is the binding of identity, authorization, lineage, continuation, and independent verification into one compact protocol.

## Pricing should correspond to an acceptance boundary

The three pricing tiers are attached to increasingly consequential verification responsibilities.

| Tier | Pricing | Verification responsibility |
| ---- | ------- | --------------------------- |
| Developer | $1,500-$5,000 setup + $250-$1,000/month | Local packaging and self-verification: signed capsules, manifests, local verification, evidence exports |
| Team | $2,000-$10,000/month | Managed multi-host execution and independently generated acceptance packets: run history, policy gates, dashboards, retention |
| Enterprise | $25,000-$100,000/year | Enterprise verification infrastructure: customer-controlled keys, private deployment, policy enforcement, audit exports, service commitments, verifier separation |

### Customer development questions to answer during the 180-day period

- Which buyer owns the problem?
- Which budget pays for it?
- Which event triggers purchase?
- What does the customer currently do instead?
- How much does failure or manual verification cost?
- How often do workloads require handoff?
- What evidence must a customer retain?
- Does the buyer want software, managed service, or verification API?
- How quickly can a pilot reach acceptance?
- Will the customer pay before the platform is generalized?

The first commercial milestone should be a paid acceptance pilot, even if small. A paid pilot provides stronger evidence than broad interest, enthusiastic conversations, letters of support, or nonbinding claims about potential market size.

## The $300,000 allocation should purchase uncertainty reduction

Every budget line corresponds to a named risk being retired.

| Allocation | Amount | Risk retired | Deliverable | Acceptance test |
| ---------- | -----: | ------------ | ----------- | --------------- |
| Core runtime and protocol | $120K | State-portability and lineage risk | Versioned capsule protocol and runtime | Reproduces across supported hosts |
| Infrastructure | $55K | Founder-environment dependency | Hosted workers, GPUs, storage, observability | Multiple external host runs achieve required pass rate |
| Verification and security | $40K | Self-verification and adversarial risk | Independent verifier and threat model | Red-team and acceptance suite pass |
| Product and integrations | $35K | Prototype-to-workflow gap | API, dashboard, customer integration | Pilot completes real workload |
| Legal and company operations | $25K | Corporate and transaction risk | Entity, IP, contracts, offering documents | Counsel confirms readiness |
| Independent reproductions and design partners | $15K | Market and pricing risk | Interviews, design partners, paid pilot | Signed and paid customer evidence |
| Contingency | $10K | Execution interruption risk (failures discovered during external execution) | Protected operating period | Milestones delivered within runway |
| **Total** | **$300K** | | | |

## Milestone structure

### Day 30: Independent reproducibility -- COMPLETED

The Host A → Host B → Verifier C demonstration was completed outside the founder-controlled environment on GitHub Codespaces (Ubuntu 24.04, x86_64, Azure cloud).

Results:

- [x] At least one genuinely independent Host B (GitHub Codespaces)
- [x] Independently generated Host B keypair (ephemeral, generated on Codespaces)
- [x] Successful transport verification
- [x] Valid owner signature
- [x] Valid successor lineage
- [x] Valid Host B signature
- [x] Independently reproduced task result (1060)
- [x] Verifier C acceptance (11/11 checks)
- [x] Complete evidence packet
- [x] No private-key leakage
- [x] No founder filesystem path leakage
- [x] Documented failure modes
- [ ] Public or investor-safe demonstration recording (pending)

The target was a signed external reproduction packet. That target was met.

### Day 60: Repeatability across environments

The next phase determines whether the protocol is portable rather than merely repeatable once.

Acceptance criteria:

- Three or more independently controlled hosts
- At least two operating-system or runtime configurations
- Repeated clean-environment execution
- Documented dependency installation
- Deterministic manifest behavior
- Bounded variation where timestamps or host metadata differ
- Negative tests: corrupted bundle, wrong report, wrong public key, wrong parent, altered task result, replayed successor, missing evidence
- Defined schema-version compatibility rules
- Machine-readable verifier output
- Run-duration and failure-rate measurements

### Day 120: Productized pilot

By day 120, the system processes a real customer-shaped workload rather than only the prime-sum demonstration.

The workload should be bounded, safe, and objectively verifiable. Examples:

- Resume an interrupted coding agent
- Continue a software build
- Resume an evaluation pipeline
- Continue an autonomous research task
- Continue a data-processing workflow

Acceptance criteria:

- Identified buyer and use case
- Written pilot success conditions
- Customer-controlled or customer-approved keys
- Real workload capsule
- Independent receiving environment
- Completed successor state
- Customer-readable evidence packet
- Measured execution and verification time
- Customer assessment of usefulness
- Defined path to payment or paid pilot

### Day 180: Commercial and operational proof

The 180-day milestone establishes whether this is a company rather than only an elegant protocol.

Acceptance criteria:

- At least one paid pilot or equivalent contracted revenue
- Repeatable onboarding
- Measured cost per run
- Measured gross-margin assumptions
- Security review or defined remediation plan
- Customer retention or expansion signal
- Documented support burden
- Production incident process
- Versioned protocol
- Customer-facing service description
- Investor update showing achieved and missed targets

## Investor-facing KPIs

The KPI system separates engineering, verification, commercial, security, and capital-efficiency metrics. Investors should be able to inspect the underlying measurements. Composite scores can be useful internally but should not collapse these categories into a single number for investor reporting.

### Engineering KPIs

| KPI | Target |
| --- | ------ |
| Successful capsule creation rate | 100% |
| Successful independent restoration rate | >= 99% |
| Successful continuation rate | >= 99% |
| Median handoff time | Measured |
| p95 handoff time | Measured |
| Median verification time | Measured |
| p95 verification time | Measured |
| Deterministic-check pass rate | 100% |
| Cross-environment compatibility rate | Measured |
| Capsule size and transport overhead | Measured |
| Unresolved critical defects | 0 |
| Schema compatibility failures | 0 |

### Verification KPIs

| KPI | Target |
| --- | ------ |
| Percentage of runs independently verified | 100% |
| Signature-verification pass rate | 100% |
| Lineage-verification pass rate | 100% |
| Evidence-packet completeness | 100% |
| Negative-test rejection rate | 100% |
| False-acceptance count | 0 |
| False-rejection count | Measured |
| Verifier disagreement rate | 0% |
| Percentage of claims with direct machine-readable evidence | 100% |
| External reproduction count | >= 3 |

### Security KPIs

| KPI | Target |
| --- | ------ |
| Secret-scanner pass rate | 100% |
| Private-key exposure incidents | 0 |
| Path-leakage incidents | 0 |
| Dependency vulnerabilities by severity | Tracked |
| Malformed-capsule rejection rate | 100% |
| Replay rejection rate | 100% |
| Unauthorized mutation detection rate | 100% |
| Time to remediate critical findings | Measured |

### Commercial KPIs

| KPI | Target |
| --- | ------ |
| Qualified customer interviews | >= 20 |
| Design partners | >= 3 |
| Pilot proposals | >= 5 |
| Pilots started | >= 2 |
| Pilots completed | >= 1 |
| Paid pilots | >= 1 |
| Pilot-to-contract conversion | Measured |
| Annualized contract value | Measured |
| Sales-cycle duration | Measured |
| Customer-defined acceptance rate | Measured |
| Expansion or repeat-use rate | Measured |

### Capital-efficiency KPIs

| KPI | Target |
| --- | ------ |
| Monthly burn | <= $25K |
| Runway remaining | >= 6 months at all times |
| Engineering spend per accepted external reproduction | Measured |
| Infrastructure cost per verified run | Measured |
| Customer-development spend per qualified pilot | Measured |
| Revenue per dollar burned | Measured |
| Milestone variance against plan | Reported |

## The six-object fundraising packet

The strongest fundraising packet contains six controlling objects.

1. **Seed pitch** -- This document: problem, technical insight, verified state, market entry, milestones, team, budget, financing request, and risks.
2. **Technical proof brief** -- A concise description of the protocol, trust boundaries, capsule format, signing process, lineage model, verifier, and exact claim boundary.
3. **Independent evidence packet** -- The Host A → Host B → Verifier C result with hashes, signatures, logs, reports, and verdict.
4. **Demonstration** -- A short recorded or live demonstration showing the handoff and verification without requiring deep code inspection.
5. **Commercial validation file** -- Customer interviews, problem statements, pilot criteria, letters, contracts, pricing tests, and revenue evidence. Interest is not represented as revenue or commitment.
6. **Data-room index** -- Corporate documents, IP assignments, capitalization, financial model, use of funds, security materials, technical repositories, known risks, and document hashes.

Each object has an owner, date, version, status, and integrity hash. The investor can distinguish superseded material from current material immediately.

### Primary artifacts

- `SEED_PITCH.md` -- this document
- `INVESTOR_MEMO.md` -- two-page investment memo
- `hdar-deploy-package.tar.gz` -- sanitized Host A → Host B → Verifier C evidence bundle
- `CLAIM_REGISTRY.json` -- machine-readable claim ledger (12 claims, each with evidence, verification method, and status)
- `build_deploy_package.py` -- reproducible build script that regenerates the entire package from scratch
- `run_on_host_b.py` -- self-contained runner with `--bundle` flag
- `third_party_verifier.py` -- offline verifier with 11 Boolean predicates
- `INSTRUCTIONS.txt` -- step-by-step reproduction guide with runner hash verification

## The five archives must become one product history

Each archive is a layer in the same system, not a separate company.

| Archive | Durable contribution | Current use | Evidence status | Disposition |
| ------- | -------------------- | ----------- | --------------- | ----------- |
| Archive A (HDAR POC) | Core continuity model | Used in capsule protocol | Implemented | Canonical |
| Archive B (HDAR full repo) | Host transport mechanics | Used in runner | Implemented | Canonical |
| Archive C (Evidence/receipts) | Proof and receipt logic | Used in verifier packet | Implemented | Canonical |
| Archive D (Compute-market concepts) | Future resolver layer | Not yet integrated | Conceptual | Roadmap |
| Archive E (Commercial/investment) | Commercial and investment model | Used in seed pitch | Hypothesis | Validation required |

The pitch identifies exactly which components have been incorporated into the present proof of concept and which remain conceptual. Investors should not have to infer whether an archive is production code, abandoned experimentation, research material, or future roadmap.

## Risk register

The seed pitch contains a direct risk register rather than hiding risk in general disclaimers.

| Risk | Description | Severity | Mitigation | Test | Residual |
| ---- | ----------- | -------- | ---------- | ---- | -------- |
| Independent reproduction | Package may fail on clean external environment due to undeclared dependencies, path assumptions, packaging errors, or platform differences | High | Test on Colab and clean VMs before sharing with investors | Blind replication on independent host | Medium after successful reproduction |
| Security | Signed capsules may still contain malicious or unsafe workloads. Integrity is not equivalent to safety | High | Sandbox execution, secret scanning, workload review | Adversarial capsule test suite | High until sandboxing implemented |
| Key management | Losing, exposing, or misbinding keys invalidates authorization and attribution | High | Key rotation, escrow, revocation procedures | Key rotation test | Medium after rotation implemented |
| Replay and rollback | A valid older capsule or signed successor could be reused out of sequence | Medium | Freshness tokens, monotonic epoch enforcement | Replay attack test suite | Low after monotonicity enforced |
| Verifier independence | A verifier derived from the same implementation may reproduce the same defect | Medium | Independent verifier implementation, cross-implementation testing | Differential verification test | Medium until second verifier exists |
| Determinism | Environmental differences may produce divergent state even when logical task is equivalent | Medium | Canonical serialization, environment fingerprinting | Cross-platform determinism test | Low for deterministic tasks; open for real workloads |
| Product scope | Platform may become too generalized before one customer workflow is solved completely | Medium | Focus on one pilot workflow before generalizing | Pilot completion | Medium |
| Market | Prospective customers may accept existing containers, orchestration tools, or workflow systems as sufficient | Medium | Customer interviews, differentiation testing | 20+ qualified interviews | High until customer validation |
| Procurement | Enterprise buyers may require security certifications, insurance, support terms beyond seed budget | Medium | Start with smaller teams, build toward enterprise | Pilot procurement cycle | High for enterprise; lower for SMB |
| Founder concentration | Architecture, implementation, verification knowledge, and fundraising concentrated in one person | High | Document everything, recruit technical advisor, hire engineer with seed funds | Knowledge transfer test | Medium after first hire |
| Financing | 12-month runway may be insufficient if enterprise pilots have long sales cycles | Medium | Start customer development immediately, target SMB first | Runway tracking | Medium |
| Securities compliance | Financing documents and investor outreach must comply with securities law | High | Retain qualified securities counsel before solicitation | Counsel review | Low after counsel sign-off |

## Fundraising compliance boundary

The financing documents and investor outreach should be reviewed by qualified securities counsel before solicitation or acceptance of funds. An offer or sale of startup securities must either be registered or conducted under an applicable exemption, even when the buyer is an angel, friend, family member, or venture fund.

Different private-offering pathways impose different conditions, including rules concerning general solicitation, investor eligibility, disclosures, restricted securities, and filings. Rule 506(b) generally prohibits general solicitation, while broadly solicited offerings implicate different requirements.

The public-facing technical demonstration and the securities offering should not be casually blended. A public website may explain the product and evidence, but statements about the specific security, valuation terms, investor returns, or active fundraising process need to align with the exemption and counsel's instructions. Private-company securities are generally illiquid and subject to resale restrictions, so the pitch should not imply easy liquidity or a guaranteed exit.

## Round structure

| Field | Value |
| ----- | ----- |
| Raise | $300,000 |
| Instrument | Post-money SAFE |
| Runway | ~12 months |
| Purpose | Convert verified prototype into paid cross-host continuity pilots |

The valuation cap should not be invented from archive size or theoretical collateral value. It should be negotiated from team credibility, proof strength, market access, customer evidence, and competing investor interest.

## Current claim boundary

### Verified

- [x] Signed capsule creation
- [x] Deterministic restoration
- [x] Deterministic continuation
- [x] Cryptographic lineage
- [x] Independent verification program
- [x] Regression-tested implementation
- [x] Portable deployment package
- [x] Evidence packet signing
- [x] External bundle hash verification
- [x] Independent execution environment (GitHub Codespaces, Ubuntu 24.04 x86_64)
- [x] Independent reproduction (11/11 verifier checks passed)
- [x] Cross-platform verification (macOS arm64 → Linux x86_64)

### Remaining

- [ ] Multi-host repetition
- [ ] Production operational hardening
- [ ] Commercial workload validation
- [ ] Enterprise security review

Being explicit about boundaries increases credibility. Investors can see exactly what remains to be validated instead of wondering what is being implied.

## Five security boundaries investors will ask about

Without these, "portable agent state" can quickly become "portable remote-code-execution gift basket."

**1. Key custody and recovery.** What happens when the owner key is lost, rotated, compromised, or inherited? The system needs key rotation, escrow, and revocation procedures that do not break existing capsules.

**2. Runner authentication.** The restored capsule and the code performing restoration must both be signed and verified. A capsule that restores correctly under a tampered runner is not trustworthy.

**3. Sandboxing.** Host B must not receive unrestricted filesystem, network, environment-variable, or credential access. Restoration must occur in a constrained execution environment.

**4. Secret handling.** Capsules must detect and control credentials, private keys, tokens, and machine-specific secrets. Secrets must be mapped, redacted, or encrypted before transport.

**5. Policy compatibility.** Host B must prove that its available capabilities satisfy -- or safely reduce -- the capsule's requested authority. Authority attenuation is a major enterprise differentiator.

## Technology Readiness Level

Current state: **TRL 4-5** -- core components integrated and validated in a laboratory-style environment (local simulation with independent cryptographic verification, 11-check third-party verifier). The deploy package is ready for blind replication on an independent machine, which would move evidence toward the "relevant environment" expected at TRL 5-6.

## Current investment classification

**Strong technical pre-seed**

**Seed candidate after external proof and customer traction**

| Dimension | Assessment |
| --------- | ---------: |
| Technical architecture | 8/10 |
| Prototype evidence | 8.5/10 |
| Product reliability | 5/10 |
| Security maturity | 4/10 |
| Customer validation | 2/10 |
| Revenue validation | 1/10 |
| Overall seed readiness | **6.5/10** |

## Seed status trajectory

Today:

```
[ Externally reproduced prototype — 8/10 — 11/11 checks passed on independent Linux host (GitHub Codespaces, Ubuntu 24.04, x86_64) ]
```

Independent Host B run completed:
- Host A: macOS (your Mac, arm64)
- Host B: Ubuntu 24.04 x86_64 (GitHub Codespaces, Azure cloud)
- Verifier C: same Codespaces instance (operationally separate from Host A)
- Result: 11/11 checks passed, including platforms_differ
- Artifacts saved to: `independent-host-b-results/`

After a paid pilot proving recovery time, prevented duplicate effects, or reduced agent-operations risk:

```
[ Seed-investment ready ]
```

The progression is strict:

```text
local consistency
    → independent reproduction
    → cross-environment repeatability
    → customer acceptance
    → paid use
    → scalable infrastructure
```

Do not skip from the first stage to the last in the language of the pitch. The investment case becomes stronger -- not weaker -- when every claim is visibly constrained by the evidence that currently supports it.

## The one-sentence $300K ask

> **We are raising $300,000 on a post-money SAFE to convert our locally verified signed-state transport prototype into an independently reproduced three-party system, complete a customer-shaped pilot, and establish the technical, security, and commercial evidence required for a repeatable verifiable-workload-handoff product.**

That sentence states:

- The amount
- The intended instrument
- The present maturity
- The next validation boundary
- The product category
- The commercial milestone
- The evidence expected from the round

It does not claim that the market is already proven, that the architecture is production ready, or that signatures alone establish a defensible business.

## Investor-facing pitch

> **HDAR is a continuity and verification layer that lets an AI agent stop on one machine, restore on another, continue from authenticated state, and produce independently verifiable evidence of what happened.**

Lead with:

> **The machine can die. The governed agent operation continues -- and the continuity is independently provable.**

Support it with:

- MirrorLease controls what the agent may access
- EvidencePipe controls whether the agent may act
- HDAR preserves and migrates verified state
- ALPHA-GPT optionally supplies private local intelligence

Do not lead with:

- blockchain
- palindromes
- spreadsheet neural weights
- personalized chat imitation
- RentMasseur conversion statistics
- every experimental project created during the chat

Those details create cognitive shrapnel.

## The investor conclusion

The project's strongest asset is not that it contains unusually ambitious language about hardware-detached agents. Its strongest asset is the emerging ability to bind a claim to a signed source state, transport that state, continue it under a different operator, generate a successor, and let another party independently determine whether the declared transition occurred.

The independent Host B reproduction has been completed. The package ran on GitHub Codespaces (Ubuntu 24.04, x86_64) — an environment the founder does not control — and produced 11/11 verifier checks. The project has crossed from locally verified prototype to externally reproduced prototype.

The next gating milestone is cross-environment repeatability (3+ hosts, 2+ OS configurations) and a real customer-shaped workload. After a customer pays for that acceptance boundary, it becomes commercial evidence.

## Immediate security actions

Before any external sharing:

1. **Revoke all exposed credentials.** The ALPHA-GPT corpus and Archive 2 contain live-looking OpenAI, OpenRouter, Google, Hugging Face, and GitHub credentials. Treat all as compromised.
2. **Replace the evidence signing key.** `pipeline_output/evidence/signing_key.pem` is a private Ed25519 key distributed inside the evidence bundle. The signature is therefore untrustworthy. Generate a new key outside the bundle.
3. **Run deterministic secret detection** on all archives before publishing. PII redaction, credential scanning, and path sanitization are mandatory.
4. **Do not publish archives as they stand.** They contain thousands of absolute Mac paths, email addresses, phone-number patterns, and tunnel identifiers.

## The single strongest next artifact

Not another document. Not another deck. A **blind replication**.

The deploy package is ready. Someone who has never spoken to the founder receives only:

```
hdar-deploy-package.tar.gz
RUN_ON_REAL_HOST_B.md
```

They execute the documented steps on their own machine and produce:

- `host_b_report.json`
- `host_b_evidence_packet.json`
- `successor_capsule_epoch_2.tar.gz`
- Host B public key
- Host B signature
- Third-party verification output (11/11 checks)

without needing clarification from the founder.

The package includes:

- `run_on_host_b.py` -- self-contained runner with `--bundle` flag for external tar.gz loading
- `transport_capsule_epoch_1_signed.tar.gz` -- owner-signed E1 capsule
- `host_a_build_report.json` -- Host A build report for cross-verification
- `owner_public_key.txt` -- owner Ed25519 public key (out-of-band channel)
- `third_party_verifier.py` -- offline verifier (run on a THIRD machine)
- `INSTRUCTIONS.txt` -- step-by-step reproduction guide with runner hash verification
- `build_deploy_package.py` -- reproducible build script that regenerates the entire package from scratch
- `CLAIM_REGISTRY.json` -- machine-readable claim ledger

If that succeeds, the core technical claim survives outside the inventor's own environment. For a deep-technology investor, that evidence carries substantially more weight than additional architectural explanation.
