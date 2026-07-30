---
title: RentMasseur RevenueOps
emoji: 🚀
colorFrom: purple
colorTo: blue
sdk: docker
pinned: false
---

# RentMasseur RevenueOps Control Plane

Unified, approval-gated RevenueOps control plane for RentMasseur profile optimization.

This repo consolidates three former repos into one canonical source:
- `rentmasseur-extension` (Chrome extension + 24/7 CI/CD pipeline)
- `hf-rentmasseur-optimizer` (HuggingFace Space deployment)
- `rentmasseur-unified` (C++ control plane, API endpoints, docs)

## What This Repo Does

- **24/7 pipeline** — GitHub Actions hourly cycle: availability keeper, metrics, KPIs, GA+RL optimizer
- **Demo agent** — Playwright/Selenium browser automation with anti-bot stealth, visitor tracking, auto-messaging
- **Engagement engine** — Scrapes visitors, tracks repeat visits in SQLite, auto-messages threshold visitors
- **Bio A/B testing** — Controlled bio experiments with frozen variables and lift measurement
- **Content rotation** — Daily blog posts, interview questions, photo rotation
- **C++ control plane** (`cpp_os_server.cpp`) — native HTTP server on port 7860
- **Chrome extension** — first-party capture tool for profile metrics
- **Receipt-backed decisions** — every action writes a tamper-evident receipt with SHA-256 chain
- **Cloudflare Functions** — `api/` and `functions/` for edge deployment
- **HuggingFace Space** — Docker deployment with live dashboard

## What This Repo Does NOT Do

- No CAPTCHA fighting or anti-bot bypass
- No unattended profile mutation without receipt
- No mass content generation to the live profile without approval

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RENTMASSEUR_USERNAME` | Yes | Platform login username |
| `RENTMASSEUR_PASSWORD` | Yes | Platform login password |
| `GROQ_API_KEY` | Yes | Groq API key for bio generation and intent routing |
| `GROQ_MODEL` | No | Groq model (default: `llama-3.3-70b-versatile`) |
| `ADMIN_TOKEN` | Yes | Bearer token for mutation endpoints |
| `HF_TOKEN` | For HF deploy | HuggingFace access token |
| `HF_SPACE_NAME` | For HF deploy | HF Space name (e.g. `user/rentmasseur-optimizer`) |
| `HF_URL` | No | HF Space URL for metrics fetch |
| `PROXY_URL` | No | HTTP/SOCKS5 proxy for Chrome automation |
| `REBRANDLY_LINK` | No | Clickable booking link for bios/CTAs |

## Deployment

### Docker (local or HF Space)

```bash
docker build -t rm-revenueops .
docker run -p 7860:7860 \
  -e ADMIN_TOKEN="your-secret-token" \
  -e GROQ_API_KEY="gsk_..." \
  rm-revenueops
```

### HuggingFace Space

The `deploy-hf-space.yml` workflow syncs to HF Space every 6 hours. Set `HF_TOKEN` and `HF_SPACE_NAME` as GitHub secrets.

### Cloudflare Functions

`functions/` directory contains edge API endpoints. Deploy with `wrangler deploy` using `wrangler.toml`.

## GitHub Actions Workflows

| Workflow | Schedule | Description |
|----------|----------|-------------|
| `pipeline-24-7.yml` | Hourly | Availability keeper + metrics + KPIs + hourly optimizer |
| `rm-demo-agent.yml` | Manual | Full demo agent run with login, visit-back, auto-messaging |
| `rm-engagement.yml` | Manual | Visitor scraping and engagement |
| `auto-bio-update.yml` | Daily | Pick and deploy best bio |
| `daily-content.yml` | Daily | Generate blog posts and interview questions |
| `master-rotator.yml` | Daily | Rotate content across channels |
| `photo-rotation.yml` | Daily | Rotate profile photos |
| `rm-bio-loop.yml` | Daily | Bio A/B test loop |
| `weekly-report.yml` | Weekly | Generate weekly performance report |
| `deploy-hf-space.yml` | 6h | Sync to HuggingFace Space |
| `ci.yml` | Push | CI validation |
| `multicloud-validate.yml` | Push | Multicloud deployment validation |

## File Structure

```
/
  Dockerfile                    — Docker image for HF Space / local
  README.md                     — This file
  requirements.txt              — Python dependencies

  # Python automation
  rm_demo_agent.py              — Playwright/Selenium demo agent
  rm_engagement_engine.py       — Visitor engagement automation
  rentmasseur_availability.py   — 24/7 availability keeper
  auto_bio_updater.py           — Bio selection and deployment
  bio_ab_tester.py              — Bio A/B testing
  blog_rotator.py               — Blog content rotation
  competitor_scraper.py         — Competitor profile scraping
  ga_rl_optimizer.py            — GA+RL profile optimizer
  metrics_collector.py          — Metrics ingestion
  kpis.py                       — KPI computation
  fingerprint.py                — Tamper-evident receipt chain
  rm_proof.py                   — ZK proof system
  rm_telemetry_poller.py        — Telemetry polling
  cartman_engine.py             — Cartman engine
  cartman_watcher.py            — Cartman watcher
  server.py                     — Flask API server
  hf_app.py                     — HuggingFace Space app

  # C++ control plane
  cpp_os_server.cpp             — Native HTTP server (port 7860)
  rotator_engine.cpp            — Rotation engine
  ga_rl_optimizer.cpp           — GA+RL optimizer (C++)
  production_control_loop.cpp   — Production control loop

  # Chrome extension
  manifest.json                 — Extension manifest
  content.js                    — Content script
  popup.html / popup.js         — Extension popup

  # Edge / API
  api/                          — API endpoints (Netlify-style)
  functions/                    — Cloudflare Functions
  wrangler.toml                 — Cloudflare Workers config

  # Content (managed by CI/CD)
  content/
    bios/                       — Generated bio candidates
    blog_posts/                 — Daily blog posts
    interview_questions/        — Interview Q&A content
    metrics/                    — Ingested metrics
    decisions/                  — Decision ledger
    experiments/                — Experiment records

  # Deployment
  deploy/launchagents/          — macOS LaunchAgents
  integrations/                 — Third-party integrations
  docs/                         — Documentation
  guides/                       — SEO guide pages

  # Artifacts (generated by CI/CD, not local)
  artifacts/                    — Receipts, logs, engagement DB
  receipts/                     — Tamper-evident receipt chain
```

## Experiment Workflow

1. Capture dashboard metrics manually or via extension
2. Ingest metrics via `POST /api/metrics/ingest`
3. Review candidates at `GET /api/candidates`
4. Start experiment via `POST /api/experiments/start` (requires ADMIN_TOKEN)
5. Wait 100+ new profile views or 24-48 hours
6. Close experiment and compute lift
7. Decision: `KEEP_CURRENT`, `WINNER_FOUND`, `REVERT_TO_BASELINE`, or `NO_SIGNAL`
