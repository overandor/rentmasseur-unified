# The Thirteen Primitives — Agent Continuity Protocol

*Canonical competitive landscape and primitive analysis. Informs all funding and technical roadmap decisions. Referenced by CARTMAN_AUTOPSY.md and FOUNDER_PROOF_BRIEF.md.*

## Market Context

A $30 million seed round cannot be guaranteed by building thirteen clever components. That size of seed would require a credible new category, strong technical evidence, outside adoption, and a believable path to becoming infrastructure rather than a feature.

The category is financially real. E2B announced a $21 million Series A for agent-cloud infrastructure, Daytona announced a $24 million Series A for agent computers, and Browserbase announced a $40 million Series B for browser infrastructure. Those are later-stage rounds rather than comparable seeds, but they show that investors will fund foundational execution layers for agents.

The novelty boundary has also moved. E2B now preserves filesystem and memory state across pause and resume, supports automatic wake-up on activity, and creates snapshots that survive deletion. Daytona preserves VM memory and files without CPU consumption while paused, supports hot snapshots, and can fork independent descendants with recorded ancestry. Therefore, "persistent sandbox," "pause and resume," "memory snapshot," and "serverless wake-up" are no longer sufficient inventions by themselves.

CRIU already freezes and restores Linux processes, Firecracker persists microVM memory and virtual-machine state, OCI standardizes portable software images, SPIFFE provides workload identities across heterogeneous infrastructure, and in-toto records who performed software-supply-chain steps and in which order. However, these systems do not jointly define the authoritative continuity of a stateful AI agent across unrelated execution providers.

## The Thirteen Primitives

### 1. Agent-native suspension capsule standard

An open, canonical format representing an agent as a durable computational entity rather than merely a filesystem or frozen VM.

It binds together identity, parent lineage, working state, unfinished obligations, memory references, model configuration, tools, content-addressed files, capabilities, secret references, external-effect status, restoration requirements, and signed evidence.

OCI images contain enough information to distribute and launch software, but they do not describe an agent's unfinished obligations, authority lineage, semantic checkpoint, or continuity status. VM snapshots preserve machine state but remain coupled to specific virtualization and hardware assumptions. Firecracker explicitly states that snapshots are not compatible across CPU architectures and may even be unstable across different host kernels.

A solo founder could define the specification, reference implementation, validators, conformance fixtures, migration adapters, and registry integration on an M5 Pro.

The moat would be the standard, compatibility suite, adoption surface, and accumulated provider adapters — not the archive format itself.

**Fundable positioning: OCI for persistent agents.**

### 2. Semantic quiescence protocol

A conventional snapshot freezes instructions. A semantic quiescence protocol determines whether an agent is at a safe operational boundary.

It must establish that no model stream, child agent, database transaction, deployment, message, payment-like action, or external tool call is left in an indeterminate state. It must understand the difference between "the process stopped" and "the operation can safely be resumed."

This is absent from infrastructure that only captures RAM, processes, or disk. E2B notes that snapshot creation drops active connections such as WebSockets, PTYs, and command streams. CRIU can preserve substantial process state, but application-level side-effect meaning remains the responsibility of higher layers.

A three-year solo implementation could support a bounded adapter set: filesystem, SQLite or PostgreSQL, HTTP mutations, message delivery, Git operations, deployment jobs, and agent tool calls.

The hard-to-copy asset becomes the adapter library and the formal suspension contract.

**Fundable positioning: The consistency barrier for long-running agents.**

### 3. Durable external-effect transaction registry

Every externally visible action receives a stable operation identity, an intent digest, authorization evidence, submission status, provider receipt, reconciliation mechanism, and final disposition. After a crash or migration, the runtime must determine whether the operation committed before retrying it.

This is how an agent avoids paying twice, sending twice, deploying twice, or repeating an irreversible API mutation because its response packet disappeared.

The primitive provides exactly-once-or-explicitly-reconciled semantics above APIs that may offer only at-least-once delivery or provider-specific idempotency.

A solo developer could build the protocol and a carefully selected integration set. Production breadth would later require a team, but a compelling demonstration needs only several high-value adapters and aggressive failure injection.

**Fundable positioning: Transactional effects for probabilistic software.**

### 4. Fenced authoritative-continuity protocol

This may be the single most valuable missing primitive.

Capsules are copyable. A copy alone cannot establish migration because two restored copies may both claim to be the agent. The continuity protocol guarantees that only the holder of the newest lease generation may advance lineage, commit protected effects, use sensitive capabilities, or publish an authoritative state.

Older runtimes could remain physically alive during a network partition, but their fencing tokens would be rejected. This turns a stale runtime from "dangerous clone" into "unauthorized historical process."

Kubernetes Lease objects and distributed leader-election techniques provide useful lower-level mechanisms, but they do not define authority transfer for a forkable agent with signed lineage, budgets, external obligations, and provider migration. SPIFFE identifies workloads wherever they run, but identity alone does not decide which copy owns the next authoritative epoch.

A solo founder can implement this using a transactional database first, followed by replicated back ends and formal concurrency tests.

**Fundable positioning: Consensus for agent identity without requiring a blockchain-shaped carnival.**

### 5. Dual exact-versus-semantic restoration contract

The industry uses "resume" for several completely different operations.

Exact restoration may preserve process memory, registers, threads, open descriptors, inference-engine state, and accelerator state on sufficiently compatible infrastructure.

Semantic restoration preserves the agent's identity, files, goals, evidence, authority, unresolved work, and safe continuation boundary while reconstructing execution on incompatible infrastructure.

The protocol forces every restoration receipt to declare what was preserved exactly, what was reconstructed, what was replayed, what was discarded, and where divergence is possible.

Firecracker snapshots are tied to CPU and host compatibility. A current vLLM RFC combines CUDA checkpointing with CRIU for CPU-plus-GPU persistence, but its stated requirements remain Linux, x86-64, recent NVIDIA drivers, substantial host memory, and compatible runtime conditions. It is not a Darwin/Metal-to-Linux/CUDA universal continuation format.

A solo developer should not attempt universal cross-architecture process translation. The feasible invention is the honest contract, restoration planner, classifiers, receipts, and adapters.

**Fundable positioning: The portability semantics for stateful AI.**

### 6. Capability-continuity compiler

Translates an agent's authorized capabilities from one provider's policy model into equivalent or narrower capabilities at another provider.

It reasons about filesystem scope, network destinations, spending limits, secret operations, deployment environments, geographic restrictions, tool access, time limits, and required human approvals.

Central invariant:

> Migration may preserve or reduce authority, but it may never silently increase authority.

SPIFFE provides portable authentication for workloads across heterogeneous environments. That is valuable infrastructure, but authentication answers "who is this workload?" The proposed compiler additionally answers "which exact authority may this continuing agent retain here, and what must be degraded or refused?"

The solo-build strategy is to create a small capability language and adapters for several execution environments rather than attempt every cloud IAM system immediately.

The moat becomes the translation graph, policy proofs, enterprise integrations, and degradation semantics.

**Fundable positioning: IAM for migratory agents.**

### 7. Secretless capability-rebinding broker

A capsule must never carry portable production secrets.

Instead, it carries signed references to permitted operations. At restoration time, the destination proves agent identity, capsule lineage, current lease generation, destination properties, and requested action. A trusted broker then executes or signs that narrowly scoped operation without exposing the underlying credential to the model or temporary runtime.

SPIFFE already issues short-lived identity documents to workloads, including across heterogeneous infrastructure and organizational boundaries. The missing layer is continuity-aware authorization tied to capsule lineage, fenced ownership, migration history, and operation-specific grants.

A solo founder could build integrations with SSH certificates, GitHub installation tokens, cloud signing services, one deployment provider, and a generic HTTP-signing proxy.

**Fundable positioning: Agents can exercise authority without possessing credentials.**

### 8. Proof-carrying migration receipt chain

Every transition creates a portable evidence object binding:

the source capsule, source termination, lease transfer, destination manifest, signature verification, capability attenuation, restoration class, executed operations, test results, returned state, and next authoritative capsule.

in-toto already secures software-supply-chain integrity by recording what steps were performed, by whom, and in what order. The missing primitive applies that evidentiary model to a living agent's state transitions, authority transfer, restore classification, and external effects.

The verifier must work offline and fail when any state block, signature, parent hash, capability, lease generation, test result, or execution receipt changes.

A solo developer can realistically build this. The current cryptographic capsule work is already the beginning of it.

The replication moat comes from schema stability, independent verifiers, compliance integrations, incident-reconstruction tooling, and accumulated migration evidence.

**Fundable positioning: A chain of custody for autonomous computation.**

### 9. Fork-, rollback-, and merge-safe computational identity

Snapshots and sandboxes can already fork. Daytona explicitly supports independent VM descendants and records their parent-child relationship. What remains unresolved is what forked identity means when authority, money, external obligations, and revocation are involved.

The primitive must answer:

- Which fork is authoritative?
- Can both branches reason but only one deploy?
- How are budgets divided?
- Can a rolled-back state regain revoked permission?
- How are obligations transferred?
- Can branches merge memories without merging authority?
- What happens to secret grants after a fork?

This combines cryptographic lineage, monotonic generations, branch identities, capability partitioning, anti-rollback controls, merge receipts, and explicit succession rules.

It is feasible on one M5 Pro because it is fundamentally a protocol, database, verifier, and test problem — not a datacenter problem.

**Fundable positioning: Git semantics for stateful agents, with authority-aware branching.**

### 10. Agent-addressed SSH resolver

The SSH identity names the persistent agent, not its current server.

A connection to one stable agent address locates the newest authoritative capsule, acquires its fenced lease, chooses suitable compute, materializes the runtime, verifies continuity, and attaches the terminal. Later, the runtime quiesces, seals, and disappears while the SSH identity remains stable.

OpenSSH already provides the correct gateway substrate. `ForceCommand` can replace the client-requested command and expose the original request through `SSH_ORIGINAL_COMMAND`; `DisableForwarding` can close forwarding channels in restricted configurations. The missing invention is the continuity-aware resolver and host-independent trust model behind that gateway.

The difficult problems are split-brain prevention, host-key continuity, session reconnection, restoration latency, provider failure, and authenticated handoff to temporary runtimes.

A solo developer can build a serious implementation using OpenSSH, certificates, a resolver service, two or three provider adapters, and a session proxy.

**Fundable positioning: A permanent SSH door for machines that do not permanently exist.**

### 11. Restore-compatibility and degradation planner

A dormant capsule describes what it needs without knowing where it will run.

The planner evaluates CPU architecture, operating system, memory, accelerator, model availability, storage, network policy, jurisdiction, cost, latency, provider trust, and capability support. It returns ranked exact-restoration and semantic-restoration plans with explicit missing features and required approvals.

Firecracker warns about host-kernel, CPU-model, device, and external-resource compatibility. vLLM's proposed CUDA checkpoint path has explicit operating-system, architecture, driver, memory, and storage requirements.

One person can build the planner and provider manifest system. The long-term moat is real restore telemetry: which combinations actually worked, how long they took, what degraded, and what failed.

**Fundable positioning: The scheduling intelligence for portable agents.**

### 12. Destination execution witness

A destination saying "I ran the agent correctly" is not proof.

This primitive creates an ephemeral destination identity, binds it to the runtime environment, signs the received capsule hash, records the verification result, attests the host and sandbox properties, signs executed operations and outputs, and returns a content-addressed result.

Where trusted hardware is available, it could incorporate hardware-backed attestation. NIST defines attestation as digitally signing securely stored measurements and allowing the requester to validate both the signature and measurements. SPIFFE also supports attestation-based issuance of workload identity.

The initial solo implementation can support software witnesses and provider-signed metadata, then add hardware-backed integrations later.

The key distinction is that the destination may attest execution but may not mint the owner's next authoritative epoch.

**Fundable positioning: Remote execution evidence that does not require trusting the remote agent.**

### 13. Self-verifying materialize–run–collapse engine

The synthesis that turns the twelve preceding primitives into a company.

The engine accepts a dormant capsule, verifies it, acquires exclusive authority, selects compute, transfers missing state, rebinds attenuated capabilities, restores the runtime, exposes the stable SSH session, executes work, reconciles effects, reaches semantic quiescence, seals a proposed transition, verifies destination evidence, advances authoritative lineage, destroys the runtime, and releases compute.

E2B and Daytona already demonstrate that memory-preserving pause, automatic wake-up, snapshots, and agent computers are commercially important. CRIU, Firecracker, OCI, SPIFFE, in-toto, and OpenSSH provide powerful lower-level parts. The open territory is the provider-neutral continuity and authority protocol that sits above all of them.

**Fundable positioning: The authoritative continuity layer for persistent AI workers.**

## What one person can realistically accomplish in three years

The entire development control plane can be built from an M5 Pro. Local testing uses Apple's container runtime, which runs each container inside a lightweight Linux VM. Remote Linux, GPU, and cloud environments are still required for genuine heterogeneous-provider tests, but the M5 Pro remains the primary development, signing, orchestration, and verification machine.

The realistic sequence is:

**Year one:** freeze the capsule specification, complete quiescence, external-effect reconciliation, fenced leases, offline verification, and real local runtime creation and destruction.

**Year two:** add cross-host transport, destination receipts, capability translation, secretless rebinding, the SSH resolver, and sustained fault-injection testing across several providers.

**Year three:** publish the conformance suite, add restore planning and attestation, run thousands of migrations, recruit design partners, produce enterprise integrations, and establish the protocol as an open standard with a commercial control plane.

Do not try to build a universal accelerator-state translator, cross-ISA register converter, custom hypervisor, cloud marketplace, and new LLM simultaneously. Those are not realistic solo goals.

Build the continuity layer above existing compute.

## The five that matter most

The highest-leverage core is:

1. Agent-native suspension capsule
2. Fenced authoritative continuity
3. Dual exact-versus-semantic restoration
4. Capability-continuity compiler
5. Proof-carrying migration chain

Together, these form an **Agent Continuity Protocol**.

The other eight turn the protocol into a usable, defensible platform.

## What would make a $30 million seed credible

Three years of code by itself would probably not do it. The investor-grade package would need:

- A published protocol and independent verifier
- At least three genuinely different execution providers
- Thousands of successful migrations under fault injection
- Demonstrated split-brain prevention
- Evidence that no destination receives owner signing authority
- Benchmarked restore latency and transferred-state efficiency
- Several serious design partners
- One or more paid enterprise deployments
- A visible developer ecosystem using the capsule format

The honest claim is not that these thirteen items automatically produce a $30 million check.

The credible claim is:

> Building them as one coherent protocol could create a new infrastructure category large enough to justify that scale of financing — because it would govern identity, authority, continuity, and evidence above every sandbox and compute provider rather than competing as one more sandbox.

## Competitive Landscape Summary

| System | What it does | What it does not do |
|---|---|---|
| E2B | Agent cloud, pause/resume, snapshots, auto-wake | No authority lineage, no fenced continuity, no capsule standard |
| Daytona | VM sandboxes, memory pause, hot snapshots, fork | No authority-aware fork, no continuity protocol, no quiescence |
| Browserbase | Browser infrastructure | Not agent continuity, not compute migration |
| CRIU | Process freeze/restore | No semantic quiescence, no authority, no cross-provider |
| Firecracker | microVM snapshots | Architecture-locked, no agent identity, no continuity |
| OCI | Portable software images | No agent state, no obligations, no authority |
| SPIFFE | Workload identity | No continuity, no authority transfer, no fenced ownership |
| in-toto | Supply-chain integrity | No agent state transitions, no migration, no quiescence |
| OpenSSH | Secure shell gateway | No agent resolution, no continuity, no lease-aware wake |

## Current Implementation Status (July 2026)

| Primitive | Python prototype | C++ rewrite | Proven |
|---|---|---|---|
| 1. Suspension capsule | Implemented | In progress | Reproduced (55/55) |
| 2. Semantic quiescence | Implemented | Pending | Reproduced |
| 3. Effect registry | Implemented | Pending | Reproduced |
| 4. Fenced continuity | Implemented (SQLite) | Pending | Reproduced (same-host) |
| 5. Restoration contract | Implemented | Pending | Reproduced |
| 6. Capability compiler | Implemented | In progress | Reproduced |
| 7. Secretless rebinding | Proposed | Not started | Proposed |
| 8. Migration receipt chain | Implemented | Pending | Reproduced |
| 9. Fork-safe identity | Partial | Not started | Partial |
| 10. SSH resolver | Logical gateway only | Not started | Not yet evidenced |
| 11. Restore planner | Proposed | Not started | Proposed |
| 12. Destination witness | Implemented (Ed25519) | Pending | Reproduced (same-host) |
| 13. Materialize-run-collapse | Implemented (demo_continuity.py) | Not started | Reproduced (55/55, same-host) |
