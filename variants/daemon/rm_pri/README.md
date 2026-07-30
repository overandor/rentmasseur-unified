# RM-PRI — RentMasseur Profile Revenue Intelligence

Non-toy, closed-loop profile optimization engine.

## Honest version ladder

- v0.1: Real Bio Corpus Analyzer ✅
- v0.2: Public Views/Day Enricher — in progress
- v0.3: Views/Day Predictor
- v0.4: Candidate Bio Generator + Risk Filter
- v0.5: Approval Queue + Profile Snapshotter
- v0.6: Live Experiment Runner
- v0.7: Dashboard Feedback Learner
- v1.0: Closed-Loop Profile Revenue Intelligence

Only v1.0 earns the "AGI-like" label.

## Directory layout

```text
rm_pri/
  cpp/          C++ intelligence engine
  py/           Python API control plane
  data/         Datasets, models, candidates, receipts, experiments
  README.md     this file
```

## Build

```bash
cd rm_pri/cpp
make
```

## Commands

```bash
python3 rm_pri/py/cli.py status
python3 rm_pri/py/cli.py validate
python3 rm_pri/py/cli.py api-check
python3 rm_pri/py/enrich.py --delay 1.0
python3 rm_pri/py/cli.py train --label reviews --cv 5
```

## Current blocker

Public visit enrichment requires reaching `rentmasseur.com` without CrowdSec captcha.
When the site is clear, run the enricher. If captcha returns, rotate IP or wait.

## Data contracts

- `real_bios_raw.jsonl` — raw corpus from RentMasseur
- `real_bios_with_views.jsonl` — enriched with public_visits, member_since, days_online, views_per_day
- `candidates.jsonl` — generated candidate bios
- `scored_candidates.jsonl` — scored by trained model
- `experiments.jsonl` — before/after experiment labels
- `receipts/ledger.jsonl` — chained SHA-256 receipts

## Safety rules

- No fake reviews
- No fake visits
- No fake availability
- No spam messaging
- No scraping private user data
- No bypassing controls
- No publishing risky content without approval
- No hardcoded credentials
