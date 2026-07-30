---
title: RentMasseur Optimizer
emoji: 🐺
colorFrom: red
colorTo: red
sdk: docker
app_port: 7860
pinned: true
license: mit
---

# RentMasseur RevenueOps Control Plane

No mock. No fake numbers. No AGI labels. Every action returns evidence or blocks.

## Status Labels
- **GREEN_REAL**: proven by completed job receipt
- **YELLOW_RUNNING**: command queued or running
- **RED_FAILED**: command failed with exit code and logs
- **GRAY_NO_DATA**: endpoint works but no real input exists
- **BLACK_DISABLED**: unsafe or platform-blocked action

## Endpoints
- `GET /api/health` — service status
- `GET /api/report` — verified/missing/blocked state
- `GET /api/bios` — real bio files only (no hardcoded empty)
- `GET /api/jobs` — job list
- `GET /api/jobs/{id}` — job detail with exit_code, stdout, stderr
- `GET /api/jobs/{id}/receipt` — job receipt
- `GET /api/audit/files` — file audit (compiled/called/dead/mock)
- `GET /api/funnel/daily` — real leads funnel, no fake revenue
- `POST /api/run/ga-rl` — run AGI pipeline (admin)
- `POST /api/run/orchestrator` — full pipeline (admin)
- `POST /api/rotate/bio` — rotate bio (admin)
- `POST /api/rotate/strategy` — rotate strategy (admin)
- `POST /api/metrics/ingest` — ingest real metrics (admin)
- `POST /api/manual/apply-plan` — record manual plan (admin)
- `POST /api/ci/trigger` — trigger GitHub Actions (admin)
- `GET /api/receipts` — receipt ledger
- `POST /api/run/availability` — BLOCKED (captcha)

## Environment Variables
- `ADMIN_TOKEN` — required for all mutation endpoints
- `GITHUB_TOKEN` — required for CI/CD trigger
- `GITHUB_REPO` — repo for workflow dispatch
