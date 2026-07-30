# HDAR Product Requirements Document (PRD)

## $300K Seed Feature Set

**Version**: 1.0
**Date**: 2026-07-20
**Author**: Alep Research

---

## 1. Vision

Build the first production-grade hardware-detached agent runtime that provides
cryptographic proof of agent continuity across heterogeneous hosts, with
authorized side effects and verifiable lineage.

## 2. Goals

1. Achieve independent-host proof with cryptographic owner authorization
2. Ship MirrorLease MVP for scoped file access
3. Ship EvidencePipe MVP for authorized action enforcement
4. Deploy production receipt oracle as a hosted service
5. Build open-source community and integration ecosystem

## 3. Non-goals

- Building a general-purpose agent framework (LangChain, AutoGen already do this)
- Replacing container runtimes (Docker, Kubernetes)
- Building a cloud provider or hosting platform
- Supporting non-Python agent runtimes in the first release

---

## 4. Feature set and acceptance criteria

### 4.1 Independent Host B proof ($30K)

**Objective**: Prove that an agent capsule can be transported to and executed on
a genuinely independent host with cryptographic owner authorization.

**Acceptance criteria**:

| ID | Criterion | Verification |
|----|-----------|--------------|
| B-1 | Runner executes on a host with different OS, filesystem, and network than Host A | `host_b_report.json` shows `platforms_differ: true` |
| B-2 | Owner signs capsule with Ed25519 private key; runner verifies with owner public key | `host_b_report.json` shows `owner_signature_verified: true` |
| B-3 | Host B generates its own Ed25519 keypair and signs the report | `host_b_report.json` shows `host_b_signature` present and `host_b_keypair.algorithm = "ed25519"` |
| B-4 | Host B attestation is verified against a pre-registered public key | `host_b_report.json` shows `host_b_attestation_verified: true` |
| B-5 | Evidence packet (v1) is generated with all required fields | `host_b_evidence_packet.json` passes schema validation |
| B-6 | Transport channel is replaceable (not Localtunnel-dependent) | Runner works with any HTTPS URL; no hardcoded transport |
| B-7 | Deterministic task continuation succeeds on independent host | `task_continuation.passed = true`, result = 1060 |

### 4.2 MirrorLease MVP ($60K)

**Objective**: Provide narrow, temporary file access leases that scope what
files an agent can read/write on a host.

**Acceptance criteria**:

| ID | Criterion | Verification |
|----|-----------|--------------|
| M-1 | Lease definition format with scope (path patterns), duration, and permissions (read/write) | JSON schema validated |
| M-2 | Lease enforcement in runner — agent cannot access files outside lease scope | Access attempt returns `AccessDenied` |
| M-3 | Lease expiration — after TTL, all file handles are revoked | Post-expiration access returns `LeaseExpired` |
| M-4 | Lease audit log — all file accesses recorded with timestamp, path, and permission | Audit log JSON present and complete |
| M-5 | Lease revocation — owner can revoke a lease before expiration | Revoked lease immediately denies access |
| M-6 | Integration with capsule format — lease state included in workspace manifest | `manifest.json` contains `mirror_leases` field |

### 4.3 EvidencePipe MVP ($60K)

**Objective**: Block agent actions that lack fresh authorization or verifiable evidence.

**Acceptance criteria**:

| ID | Criterion | Verification |
|----|-----------|--------------|
| E-1 | Action policy format defining required evidence per action type | JSON schema validated |
| E-2 | Evidence collection — agent must provide evidence (receipt, signature, timestamp) before executing action | Missing evidence blocks action |
| E-3 | Evidence verification — evidence is cryptographically verified before action proceeds | Invalid evidence blocks action |
| E-4 | Evidence freshness — evidence must be within configurable TTL | Stale evidence blocks action |
| E-5 | Evidence log — all evidence and action outcomes recorded | Evidence log JSON present and complete |
| E-6 | Integration with receipt oracle — receipts serve as evidence for side effects | Receipt verified before side effect proceeds |

### 4.4 Production receipt oracle ($50K)

**Objective**: Deploy a hosted service that verifies capsule receipts and provides
an API for third-party verification.

**Acceptance criteria**:

| ID | Criterion | Verification |
|----|-----------|--------------|
| R-1 | REST API: `POST /verify` accepts a receipt JSON and returns verification result | API returns `{ "verified": true, "checks": [...] }` |
| R-2 | REST API: `GET /receipt/{hash}` returns receipt by hash | Returns receipt JSON or 404 |
| R-3 | REST API: `POST /register` accepts a new receipt and stores it | Returns `{ "registered": true, "receipt_hash": "..." }` |
| R-4 | Receipt verification checks: hash integrity, schema, epoch, manifest reference, timestamp freshness | All checks returned in verification result |
| R-5 | API authentication via Ed25519-signed requests | Unauthenticated requests return 401 |
| R-6 | Rate limiting and abuse prevention | Documented limits enforced |
| R-7 | SDK: Python client library for receipt oracle | `pip install hdar-receipt-oracle` works |
| R-8 | Uptime SLA: 99.5% for first 6 months | Monitoring dashboard shows uptime |

### 4.5 Open-source community ($40K)

**Acceptance criteria**:

| ID | Criterion | Verification |
|----|-----------|--------------|
| O-1 | Documentation site with quickstart, API reference, and guides | Site live at hdar.dev (or equivalent) |
| O-2 | Example integrations with 2 agent frameworks (LangChain, AutoGen) | Working examples in repo |
| O-3 | Conference talk proposal submitted to 2 venues | Proposal receipts |
| O-4 | GitHub repo with 100+ stars | GitHub star count |
| O-5 | Contributing guide and code of conduct | Files present in repo |

### 4.6 Legal and incorporation ($20K)

**Acceptance criteria**:

| ID | Criterion | Verification |
|----|-----------|--------------|
| L-1 | Legal entity formed (LLC or C-corp) | Filed articles |
| L-2 | Open-source license selected and applied (Apache 2.0 or MIT) | LICENSE file in repo |
| L-3 | IP assignment agreement template | Document prepared |
| L-4 | Privacy policy and terms of service for receipt oracle | Documents published |

### 4.7 Operating runway ($40K)

**Acceptance criteria**:

| ID | Criterion | Verification |
|----|-----------|--------------|
| F-1 | 6 months of solo builder runway | Budget shows $40K / 6 months |
| F-2 | Monthly burn rate documented | Spreadsheet or ledger |

---

## 5. Technical architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Host A     │     │   Transport  │     │   Host B     │
│              │     │   (HTTPS)    │     │              │
│  Agent ────► │────►│  Capsule ──► │────►│  Runner      │
│  Workspace   │     │  tar.gz      │     │  Verify      │
│  State       │     │  + manifest  │     │  Restore     │
│  Receipt     │     │  + receipt   │     │  Continue    │
│              │     │              │     │  Reseal      │
│  Seal ──────►│     │              │     │  Sign ──────►│
│  Epoch N     │     │              │     │  Epoch N+1   │
└──────────────┘     └──────────────┘     └──────────────┘
                                                │
                                    ┌───────────┘
                                    ▼
                          ┌──────────────┐
                          │  Receipt     │
                          │  Oracle      │
                          │  (SaaS)      │
                          │              │
                          │  Verify      │
                          │  Register    │
                          │  Retrieve    │
                          └──────────────┘
```

## 6. Timeline

| Month | Milestone |
|-------|-----------|
| 1 | Independent Host B proof with owner authorization |
| 2 | Host B attestation signing verified |
| 3 | MirrorLease MVP (scope, duration, enforcement) |
| 4 | EvidencePipe MVP (action policy, evidence collection) |
| 5 | Production receipt oracle deployed |
| 6 | Open-source launch, documentation, examples |

## 7. Success metrics

| Metric | Target (6 months) |
|--------|-------------------|
| Independent Host B proofs completed | 10+ |
| GitHub stars | 100+ |
| Receipt oracle API calls/month | 1,000+ |
| Agent framework integrations | 2+ |
| Conference talks accepted | 1+ |
| Paying receipt oracle customers | 1+ |

## 8. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Adoption risk | Open-source core, examples, conference talks |
| Competition | First-mover in agent continuity; patent-defensible receipt chain |
| Crypto complexity | Use established libraries (cryptography, Ed25519); external audit |
| Solo founder | Build community; hire with seed+ round |
| Market timing | Adjacent markets (CI/CD, edge compute) provide bridge use cases |
