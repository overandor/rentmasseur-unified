# HDAR — $300K Pre-Seed Investment Memo

## One-Sentence Ask

We are raising $300,000 to turn our independently verified cross-host AI-agent continuation prototype into a production API, complete 100 signed migration runs across multiple providers, and secure the first paid deployments with teams operating autonomous coding agents.

## Problem

Autonomous coding agents lose continuity when their session, provider, VM, or machine disappears. There is no standard way to package an agent's full state, restore it on a different host, prove the restoration was exact, and verify that the agent continued the same task — not a screenshot, not self-reported success, but cryptographic proof.

## Solution

HDAR (Hardware-Detached Agent Runtime) is a continuity and verification layer that lets an AI agent stop on one machine, restore on another, continue from authenticated state, and produce independently verifiable evidence of what happened.

**The loop:**

```
Suspend → Package → Sign → Transfer → Verify → Restore → Continue → Reseal → Audit
```

Each continuation produces a proof packet containing:
- Original owner Ed25519 signature
- Source capsule content hash
- Independent Host B identity and platform
- Restored state root hash (exact match verification)
- Deterministic task continuation result
- Successor capsule hash with epoch advancement
- Lineage transition (E1 → E2 parent chain)
- Host B Ed25519 signature
- Independent third-party verifier result (11/11 checks)

## What We Can Honestly Claim Today

**Verified:**
- Portable agent-state capsule that restores exactly on an independent host
- Epoch 1 → Epoch 2 lineage advancement with cryptographic proof
- Owner Ed25519 signing and verification (not HMAC placeholders)
- Host B Ed25519 report signing with independent evidence packet
- Third-party verifier: 11/11 checks pass (owner sig, capsule integrity, lineage, state advancement, task continuation, Host B sig, platform independence, cross-checks, evidence packet sig)
- Deterministic task: sum of primes below 100 = 1060 (independently verifiable)
- Safe tar extraction, path validation, receipt verification (7 audit fixes implemented)

**Not yet claimed:**
- Autonomous agents running continuously across arbitrary providers
- External operator reproduction (we need you to run Host B)
- Production SSH gateway routing
- 24/7 reliability
- Paying customers

## Use of Funds ($300K / ~12 months)

| Allocation | Amount | Outcome |
|---|---|---|
| Founder/engineering runway | $120,000 | Production API, 100+ continuation runs |
| Infrastructure (workers, GPUs, storage, observability) | $55,000 | Hosted verification service |
| Security review, key management, signing | $40,000 | Production-grade crypto |
| Product engineering and customer integration | $35,000 | Design partner deployments |
| Legal, incorporation, IP hygiene | $25,000 | Clean entity and contracts |
| Independent reproductions and paid design partners | $15,000 | External evidence |
| Contingency | $10,000 | — |
| **Total** | **$300,000** | |

## Milestones

**Days 1–30:** Rotate credentials, sanitize repos, run proof on independent VM, recruit design partners.

**Days 31–60:** Route through real provider/SSH gateway, record failure-mode tests, publish reproducible demo, recruit 3 design partners.

**Days 61–120:** Convert proof to API + dashboard, execute 100 cross-host runs, complete 2 external reproductions, secure 1 paid pilot.

**Days 121–180:** Turn pilot into repeatable deployment, demonstrate multi-provider, add policy-bound approvals, produce customer-visible evidence ledger, prepare seed round.

## Investor-Facing KPIs

| Metric | Target |
|---|---|
| Independent host reproductions | ≥ 3 |
| Signed cross-host continuations | ≥ 100 |
| Exact restoration rate | ≥ 99% |
| Invalid/corrupt capsule rejection | 100% |
| External design partners | ≥ 3 |
| Paid pilots | ≥ 1 |
| Verified continuation revenue | First dollars collected |

**Decisive KPI:** Verified successful cross-host continuations performed for external users.

## Commercial Model

- **Developer pilot:** $1,500–$5,000 setup + $250–$1,000/month
- **Team continuity service:** $2,000–$10,000/month (based on agents, executions, volume)
- **Enterprise deployment:** $25,000–$100,000/year (private infra, policies, audit retention)

First sale: "We make one critical agent workflow resumable and independently auditable."

## Round Structure

- **Raise:** $300,000
- **Instrument:** Post-money SAFE
- **Runway:** ~12 months
- **Purpose:** Convert verified prototype into paid cross-host continuity pilots

## Evidence Bundle

The accompanying `deploy-package/` directory contains the full cryptographic proof:

1. `run_on_host_b.py` — Self-contained Host B runner with embedded signed capsule
2. `transport_capsule_epoch_1_signed.tar.gz` — Owner-signed E1 capsule
3. `host_a_build_report.json` — Host A build report for cross-verification
4. `owner_public_key.txt` — Owner Ed25519 public key (out-of-band channel)
5. `third_party_verifier.py` — Offline verifier (run on a THIRD machine)
6. `INSTRUCTIONS.txt` — Step-by-step reproduction guide

Run the verifier yourself. 11/11 checks should pass on an independent host.
