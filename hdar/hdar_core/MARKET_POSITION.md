# Agent Continuity Protocol — Market Position & Build Plan

## Product name: Agent Continuity Protocol

> The open suspension, identity, capability, and verification layer that lets
> persistent agents move between sandbox providers without losing their
> operational continuity.

## Market signal

- E2B: $21M Series A for agent cloud infrastructure
- Browserbase: $40M Series B for browser infrastructure for agents
- OpenAI Agents SDK: multiple sandbox providers behind common workspace abstraction
- Daytona: stateful agent sandboxes
- vLLM: CPU+CUDA persistence still RFC (Feb 2026)

Investors recognize the runtime category. A generic sandbox is no longer novel.
The novelty must be a **provider-neutral continuity layer** connecting fragments.

## Five highest-leverage primitives (72-hour build)

1. **Agent Suspension Capsule** — canonical artifact representing agent independent of machine
2. **Semantic Quiescence Barrier** — protocol determining whether agent is safe to suspend
3. **Agent-Addressed SSH Resolver** — SSH addresses the agent, not the machine
4. **Capability Continuity Compiler** — maps authority safely between providers
5. **Proof-Carrying Migration Receipt** — signed portable receipt for every transition

## The demonstration sequence

```
ssh demo@agent.local

Agent begins a multi-step task
→ creates files and unresolved work
→ reaches semantic quiescence
→ seals signed capsule
→ original container is destroyed
→ backing runtime changes
→ same SSH address reconnects
→ agent restores its identity and workspace
→ remaining work completes
→ verifier proves the full transition chain
```

## Fundable artifact

```
running demonstration
+ public protocol specification
+ independent verifier
+ measurable restoration benchmark
+ explicit security invariants
+ three design-partner letters
```

## 13 defensible primitives (full vision)

1. Agent Suspension Capsule Format — "OCI for persistent agents"
2. Semantic Quiescence Barrier — "The consistency layer for long-running agents"
3. Dual Exact/Semantic Restore Contract — "A portability contract for stateful AI"
4. Agent-Addressed SSH Resolver — "DNS plus SSH for mobile computational identities"
5. Proof-Carrying Migration Receipt — "A cryptographic chain of custody for autonomous computation"
6. Capability Continuity Compiler — "IAM for migratory agents"
7. Secretless Capability Rebinding — "Agents can use authority without possessing credentials"
8. Fork-Safe Computational Identity — "Git semantics for living agents, with authority-aware branches"
9. Transactional Tool-Call Continuation — "Exactly-once effects for probabilistic agents"
10. Content-Addressed Agent State Delta — "Git and content-addressed storage for operational AI state"
11. Restore Compatibility Planner — "A scheduling control plane for portable agents"
12. Dormant-Agent Wake Registry — "Serverless agents that truly disappear between jobs"
13. Self-Verifying Materialize–Run–Collapse Engine — "The provider-neutral runtime layer for persistent AI workers"

## Honest positioning

Calling a three-day prototype "exact heterogeneous process migration" destroys credibility.
Demonstrating **exact same-runtime restoration plus honestly labeled cross-runtime semantic
continuation** strengthens it.

## Current build status (as of Jul 17 2026)

| Primitive | Status | Tests |
|---|---|---|
| #1 Suspension Capsule | ✅ Built | 4 tests + demo |
| #2 Semantic Quiescence | ✅ Built | 5 tests + demo |
| #3 SSH Resolver | ✅ Built (gateway) | 3 tests + demo |
| #4 Capability Continuity | ⚠️ Partial | Non-expansion enforced, no compiler |
| #5 Migration Receipt | ⚠️ Partial | Receipts exist, no full A→B→A offline verifier |
| #6-13 | Not started | — |
