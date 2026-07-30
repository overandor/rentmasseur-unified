# HDAR Seed-Investment Summary

## Company

**Alep Research** — Hardware-Detached Agent Runtime (HDAR)

## One-liner

Agent continuity infrastructure that lets autonomous workloads resume on any host, with cryptographic proof of lineage, workspace integrity, and authorized side effects.

## Problem

Agents die when their hosts die. Cloud instances are ephemeral, laptops crash, and provider accounts get suspended. When an agent loses its host, it loses its workspace, its execution context, and its progress. There is no standard way to:

1. Package an agent's full state into a portable, verifiable capsule
2. Restore it on a completely different host with content-addressed integrity
3. Prove that the restored agent continued the same task with the same workspace
4. Verify that every side effect (file write, API call, network action) was authorized

Current solutions (checkpoint/restore, container migration, VM snapshots) are host-coupled, opaque, and don't provide cryptographic proof of continuation. They also require the same infrastructure stack on both ends.

## Solution

HDAR (Hardware-Detached Agent Runtime) provides:

- **Transport capsules**: Content-addressed, self-describing packages containing the agent workspace, state, manifest, and receipt chain
- **Portable resurrection**: A single Python script (`run_on_host_b.py`) that verifies, restores, continues, and re-seals — runs on any host with stock Python 3
- **Epoch-based lineage**: Each continuation advances the epoch and links to the parent manifest hash, creating a verifiable chain of custody
- **Receipt verification**: Every capsule includes a cryptographically verified receipt proving the sealing event
- **Deterministic task continuation**: The restored workspace contains an unfinished computation; Host B completes it and the result is independently verifiable
- **Host B evidence packet**: Signed v1-schema evidence packet with host fingerprint, nonce, UTC timestamps, keypair, exit codes, and verification commands

## Technology stack

- **Language**: Python 3.8+ (portable, zero-dependency core)
- **Cryptographic primitives**: SHA-256 content addressing, Ed25519 signing (via `cryptography` package)
- **Transport**: Tar.gz capsules, base64-embedded bundles, any HTTPS endpoint
- **Verification**: Receipt oracles, manifest hash chains, workspace root hashes
- **Future**: MirrorLease (temporary file access leases), EvidencePipe (blocking actions without authorization)

## Traction / proof status

### Current (portable resurrection proof)

- 7 audit fixes implemented and verified
- Enhanced Host B evidence packet (v1 schema) with Ed25519 signing
- Deterministic task continuation (sum of primes below 100 = 1060)
- Runner self-authentication via external SHA-256
- Safe tar extraction with path validation
- Receipt verification (hash, schema, epoch, manifest reference)
- Content-addressed workspace restoration with exact match verification
- Epoch advancement and successor capsule sealing

### Next milestones

1. **Independent Host B execution** — Run on a genuinely remote host with different filesystem and network
2. **Cryptographic owner authorization** — Ed25519 owner signature on capsule, verified by runner
3. **Host B attestation signing** — Verified against a known key, not self-generated
4. **Production receipt oracle** — External service for receipt verification
5. **MirrorLease integration** — Narrow, temporary file access leases
6. **EvidencePipe integration** — Blocking actions without fresh authorization or evidence

## Market

Autonomous agent infrastructure is an emerging category with no established standard for continuity and portability. Adjacent markets:

- **Agent orchestration platforms** (LangChain, AutoGen, CrewAI): Need continuity for long-running agents
- **CI/CD and batch compute** (GitHub Actions, Render, Fly.io): Need portable workload migration
- **Edge and IoT** (distributed compute): Need lightweight, verifiable agent deployment
- **AI safety and auditability**: Need cryptographic proof of what an agent did and where

## Business model

- **Open-source core** (HDAR runner, capsule format, verification): Adoption flywheel
- **Hosted receipt oracle** (SaaS): Verification as a service for organizations running agents at scale
- **Enterprise license**: On-premise receipt oracle, MirrorLease policy engine, EvidencePipe integration
- **Marketplace**: Pre-built capsule templates for common agent frameworks

## Team

- **Alep** — Solo builder, systems engineer with background in distributed systems, cryptographic verification, and agent infrastructure

## Use of funds ($300K)

| Allocation | Amount | Purpose |
|---|---|---|
| Independent Host B proof | $30K | Remote execution, cryptographic owner authorization, attestation signing |
| MirrorLease MVP | $60K | Temporary file access leases with scope-limited permissions |
| EvidencePipe MVP | $60K | Blocking unauthorized actions, fresh evidence requirements |
| Production receipt oracle | $50K | Hosted verification service, API, SDK |
| Open-source community | $40K | Documentation, examples, integration guides, conference talks |
| Legal and incorporation | $20K | Entity formation, IP protection, contracts |
| Operating runway | $40K | 6 months solo builder runway |

## Competitive advantages

1. **Hardware-detached by design** — Not tied to any provider, hypervisor, or container runtime
2. **Cryptographic proof chain** — Every continuation is verifiable from capsule to capsule
3. **Zero-dependency core** — Runs on any host with stock Python 3
4. **Receipt-based side effect verification** — Not just state transfer, but proof of authorized actions
5. **Open and extensible** — Capsule format is documented, verification is transparent

## Risks

- **Adoption risk**: No existing standard for agent continuity; market may not materialize
- **Competition**: Large cloud providers could build similar functionality
- **Cryptographic complexity**: Production-grade signing and verification is hard to get right
- **Solo founder**: Bus factor of 1; need to build team or community

## Ask

$300K seed for 6 months to achieve independent-host proof with cryptographic owner authorization, production receipt oracle MVP, and MirrorLease + EvidencePipe prototypes.
