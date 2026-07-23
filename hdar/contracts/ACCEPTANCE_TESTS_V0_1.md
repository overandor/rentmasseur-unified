# HDAR Benchmarks and Acceptance Tests v0.1

## Evidence levels

- **unit:** deterministic protocol or component test;
- **same-host-isolated:** two replaceable VM-backed runtimes on one physical host;
- **independent-host:** source and destination have separate failure and
  administrative domains;
- **external:** reproduced by a person outside the founding team.

Passing a lower level never implies a higher level.

## Stage 0 and capsule-core acceptance catalog

| ID | Requirement | Minimum evidence | Automated coverage |
|---|---|---|---|
| S0-CONTRACT-001 | Machine-readable contract and human documents agree on version, promise, restoration classes, attenuation, tests, and unsupported features | unit | `tests/test_stage0_contract.py` |
| CAP-ROUNDTRIP-001 | Seal workspace, delete the original, restore all files and metadata, and match the pre-seal workspace root | unit | `tests/test_phase1.py::test_phase1_seal_restore` |
| CAP-TAMPER-001 | Modified manifest, receipt, or block is rejected | unit | `tests/test_phase1.py::test_tamper_detection`; `tests/test_transport_evidence.py::test_transport_hash_mismatch_rejected` |
| CAP-INCOMPLETE-001 | Missing required artifact or referenced block is rejected before materialization | unit | required; no dedicated test yet |
| CAP-ROLLBACK-001 | Unauthorized epoch rollback is rejected | unit | `tests/test_capabilities_verifier.py::test_offline_verifier_detects_rollback` |
| CAP-DEDUP-001 | A second capsule transfers only missing blocks and reports reused bytes/blocks | unit | `tests/test_transport_evidence.py::test_transport_deduplication` |
| RESTORE-CLASS-001 | Exact, semantic, and degraded classifications follow the frozen contract | unit | `tests/test_restoration_contract.py` |
| AUTH-ATTENUATE-001 | Equal/narrower grants pass; broader, unknown, or ungranted capabilities fail | unit | `tests/test_capabilities_verifier.py` |
| EFFECT-ONCE-001 | Duplicate operation IDs and uncertain outcomes cannot cause duplicate external effects | unit | `tests/test_p0_lifecycle.py::test_effect_registry_duplicate_prevention`; `tests/test_p0_provider.py::test_controller_duplicate_payment_prevented` |
| LEASE-SPLIT-001 | Two concurrent wake attempts yield one active authority | unit | `tests/test_p0_provider.py::test_controller_concurrent_wake_refused` |
| DESTROY-RUNTIME-001 | Runtime destroy is followed by provider absence evidence and stale-token rejection | same-host-isolated | `tests/test_p0_provider.py::test_provider_destruction_verified`; `tests/test_fencing_integration.py` |
| MIGRATE-SAMEHOST-001 | Runtime A is destroyed; a fresh VM-backed Runtime B restores durable state and continues under attenuated authority | same-host-isolated | `demo_continuity.py`; evidence must name the physical host boundary |
| SSH-STABLE-001 | One stable SSH identity resolves, wakes, verifies, attaches, reseals, and destroys across reconnects | same-host-isolated | required; not yet accepted |
| MIGRATE-SECONDHOST-001 | Runtime A is destroyed and continuation succeeds on an operationally independent host | independent-host | required; not yet accepted |

## Benchmark protocol

Each lifecycle benchmark must record at minimum:

- run ID, contract/spec version, commit, provider, OS, architecture, and image digest;
- source and destination physical-host identifiers or an explicit same-host label;
- restoration class and compatibility report;
- source/destination workspace roots and capsule hashes;
- capsule bytes, transferred delta bytes, reused block count, and dedup ratio;
- seal, verify, transfer, materialize, restore, destroy, and end-to-end latency;
- dormant compute consumption;
- capability mappings and rejected mappings;
- external operation IDs, reconciliations, and duplicate-effect count;
- source destruction and destination execution receipts;
- pass/fail plus precise failure class.

Latency summaries must publish sample count, median, p95, maximum, failures, and
environment. Restore-success rate must count all initiated restores, not only
completed ones. A same-host directory copy cannot be reported as migration.

## Stage exit rules

- Every required acceptance ID has an artifact or an explicit `not yet accepted`
  status.
- No acceptance result may rely only on a prose summary or green banner.
- Provider and physical-host boundaries must be named.
- Unsupported features cannot be promoted by implication.
- A failed integrity invariant is never converted into a degraded success.
