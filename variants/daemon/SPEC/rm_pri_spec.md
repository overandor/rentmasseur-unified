# RM-PRI — RentMasseur Profile Revenue Intelligence

## Definition

RM-PRI is a C++/Python closed-loop profile optimization engine that uses
real competitor bios, public visit velocity, authenticated dashboard stats,
validated prediction, approval-gated profile mutation, and receipt-backed
experiments to improve legitimate inbound demand.

## Versioning

- v0.1: Real Bio Corpus Analyzer
- v0.2: Public Views/Day Enricher
- v0.3: Views/Day Predictor
- v0.4: Candidate Bio Generator + Risk Filter
- v0.5: Approval Queue + Profile Snapshotter
- v0.6: Live Experiment Runner
- v0.7: Dashboard Feedback Learner
- v1.0: Closed-Loop Profile Revenue Intelligence

Only v1.0 deserves the "AGI-like" label.

## 3-Layer Architecture

### Layer A — Python API Control Plane
- Authentication, requests, snapshots, safe account mutation
- Does NOT do heavy ML or generate bios
- Talks to RentMasseur via direct API (not Selenium)

### Layer B — C++ Intelligence Engine
- Feature extraction, MLP predictor, GA optimizer, candidate scorer
- Tokenization, n-gram indexing, readability, speech scoring
- Walk-forward validation, baseline comparison
- Commands: validate, atomize, features, train, generate, score, evolve, select, report

### Layer C — Experiment / Receipt Ledger
- No mutation without receipt
- No experiment without before/after stats
- No "winner" without measurement
- Rollback required

## Data Contracts

### Contract 1 — Raw Profile Record
username, city, headline, description, isAvailable, isGold, ratingAverage, reviewsCount, isCertified, services, distance, travels

### Contract 2 — Enriched Public Profile Record
Adds: public_visits, member_since, days_online, views_per_day

### Contract 3 — Feature Vector
headline_len, description_len, word_count, sentence_count, paragraph_count, services_count, has_cta, cta_score, trust_score, proof_score, location_score, urgency_score, service_specificity, body_area_specificity, humor_score, speech_score, risk_score, novelty_score, gold, available, certified, rating, reviews

### Contract 4 — Candidate Bio
variant_id, headline, description, source, parent_ids, features, prediction, status

### Contract 5 — Experiment Label
experiment_id, variant_id, window_hours, before{}, after{}, labels{}

## Scoring Stages

### Stage 1: ReviewStrengthScore (available now)
log(1 + reviewsCount) + 0.20 * ratingAverage + 0.40 * isGold + 0.25 * isAvailable + 0.50 * isCertified + 0.20 * trust_score + 0.15 * cta_score - 0.30 * risk_score

### Stage 2: MarketDemandScore (after visit enrichment)
0.50 * normalized_views_per_day + 0.20 * normalized_reviews_per_day + 0.10 * rating_score + 0.05 * isGold + 0.05 * isAvailable + 0.05 * trust_score + 0.05 * cta_score - 0.20 * risk_score

### Stage 3: ProfileConversionScore (after dashboard stats)
0.45 * contact_click_rate + 0.25 * email_rate + 0.20 * contacts_per_available_hour + 0.10 * rank_lift - 0.30 * risk_score

### Stage 4: ProfitBioScore (after bookings/revenue)
0.30 * profile_view_lift + 0.25 * contact_click_lift + 0.20 * email_lift + 0.15 * phone_or_text_lift + 0.05 * novelty_score + 0.05 * speech_readability - 0.30 * risk_score - 0.15 * fake_claim_penalty - 0.10 * explicitness_penalty

## Model Validation

Must beat baselines:
- Baseline 1: global median views/day
- Baseline 2: city median views/day
- Baseline 3: Gold-profile median views/day
- Baseline 4: reviewsCount only
- Baseline 5: description length only

Hard gate: No out-of-sample improvement = no deployment.

## Control Modes

- Mode 0: Read-only (validate, read dashboard, scrape market)
- Mode 1: Draft-only (generate, score, risk-filter, save drafts)
- Mode 2: Approval-required (apply approved variant, snapshot, experiment, receipt)
- Mode 3: Autonomous monitoring (collect stats, detect anomalies, alert)
- Mode 4: Fully automatic (DISABLED until 20+ experiments + stable model + rollback tested)

## Experiment Design

Minimum fields: variant_id, started_at, ended_at, weekday, time_window, availability_minutes, profile_views_before/after, contact_clicks_before/after, new_emails_before/after, rank_before/after, profile_hidden_state, visibility_state, rollback_snapshot

## Receipt Schema

receipt_id, variant_id, action, status, started_at, ended_at, before{}, after{}, computed{}, prediction{}, decision{}, rollback{}

## Key Metric

contacts_per_available_hour = contact_clicks / available_hours

A profile that gets 20 clicks in 2 available hours is stronger than one that gets 30 clicks across 24 hours.

## What Not To Build

- Fake AGI dashboard
- Infinite bios with no labels
- Selenium-only control
- Auto-message system
- Fake traffic generator
- Fake review harvester
- Hardcoded credentials
- Unvalidated predictor
- Profile mutation without rollback
- Candidate generator without risk filter
