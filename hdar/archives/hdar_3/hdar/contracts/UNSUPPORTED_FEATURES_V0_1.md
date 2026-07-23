# HDAR Unsupported and Deferred Features v0.1

The following features are outside the v0.1 product contract unless a later
version adds a requirement and corresponding acceptance evidence.

| ID | Feature | Current status |
|---|---|---|
| UNSUP-001 | Metal-to-CUDA live migration | Deferred |
| UNSUP-002 | Cross-ISA live process restoration | Deferred |
| UNSUP-003 | Portable GPU kernel, command-buffer, or accelerator-memory state | Deferred |
| UNSUP-004 | Arbitrary TCP, TLS, WebSocket, or QUIC session migration | Deferred |
| UNSUP-005 | Deterministic LLM token-for-token replay | Deferred |
| UNSUP-006 | Portable model KV-cache restoration across engines | Deferred |
| UNSUP-007 | Compute-marketplace scheduling | Deferred |
| UNSUP-008 | Consensus between autonomous capsule forks | Deferred |
| UNSUP-009 | Hosted multi-tenant control plane and enterprise isolation | Deferred |
| UNSUP-010 | Stable public SSH identity across providers | Designed/partial; not accepted |
| UNSUP-011 | Genuine physical second-host restoration | Adapter/harness work exists; not accepted by current same-host proof |
| UNSUP-012 | Exact live process restoration | Contract defined; not proven |
| UNSUP-013 | Automatic continuation after degraded restoration | Prohibited without explicit approval |
| UNSUP-014 | Security against owner-key compromise | Out of scope |
| UNSUP-015 | Confidentiality for unencrypted capsule artifacts | Out of scope |

An adapter, mock, same-host directory, logical VM, or design document does not
change these statuses. Promotion requires the matching acceptance test and
evidence level in `ACCEPTANCE_TESTS_V0_1.md`.

