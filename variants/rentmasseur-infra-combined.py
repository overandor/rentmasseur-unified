#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  RENTMASSEUR INFRASTRUCTURE — ALL FILES COMBINED INTO ONE                    ║
║  Generated: 2026-07-14                                                       ║
║                                                                              ║
║  This file consolidates the entire RentMasseur automation infrastructure     ║
║  from 3 project locations into a single reference document.                  ║
║                                                                              ║
║  Source locations:                                                           ║
║    1. /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/         ║
║       rentmasseur-extension/  (MEMBRA extension — most complete)             ║
║    2. /Users/alep/Downloads/windsurf-smoke/rm_traffic/  (Traffic layer)      ║
║    3. /Users/alep/rentmasseur-optimizer/  (Original optimizer)               ║
║                                                                              ║
║  Architecture overview:                                                      ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │                    macOS launchd schedulers                         │     ║
║  │  com.rentmasseur.availability-15min  (every 15 min)               │     ║
║  │  com.rentmasseur.engagement-daemon   (daily at 10:00)             │     ║
║  └────────────────────────────┬────────────────────────────────────────┘     ║
║                               ▼                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │                    LAYER 1: API Client + Auth                      │     ║
║  │  api_client.py    — RentMasseurAPI (HTTP, confirmed endpoints)     │     ║
║  │  auth.py          — AuthSession (login, JWT, keychain, cookies)    │     ║
║  └────────────────────────────┬────────────────────────────────────────┘     ║
║                               ▼                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │              LAYER 2: Guards & Availability                        │     ║
║  │  visibility_guard.py   — ensure profile not hidden                 │     ║
║  │  availability_guard.py — refresh before expiry (45min threshold)   │     ║
║  │  availability_keeper.py— standalone 24/7 daemon (5min checks)      │     ║
║  │  availability_algos.py — 9 traffic-maximizing availability algos   │     ║
║  └────────────────────────────┬────────────────────────────────────────┘     ║
║                               ▼                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │              LAYER 3: Content & Bio Optimization                   │     ║
║  │  rentmasseur_core.py     — shared login/driver/bio utilities       │     ║
║  │  rentmasseur_optimizer.py— 30 bio strategies + Groq LLM generation │     ║
║  │  rentmasseur_coordinator— intent router picks top strategies       │     ║
║  │  intent_router.py        — LLM ranks strategies by time/season     │     ║
║  │  bio_ab_tester.py        — A/B test bios vs competitors            │     ║
║  │  rl_feedback.py          — RL reward loop (views→clicks→bookings)  │     ║
║  └────────────────────────────┬────────────────────────────────────────┘     ║
║                               ▼                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │              LAYER 4: Traffic & Engagement                         │     ║
║  │  traffic_loop.py       — 30 client-magnet functions w/ LLM CI/CD   │     ║
║  │  engagement_engine.py  — reciprocal visits + LLM messaging         │     ║
║  │  money_loop.py         — closed-loop revenue optimization          │     ║
║  │  fortress.py           — anti-fragile self-healing automation      │     ║
║  │  hypothesis_lab.py     — 300 growth hypotheses w/ bandit + FDR     │     ║
║  └────────────────────────────┬────────────────────────────────────────┘     ║
║                               ▼                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │              LAYER 5: Orchestration & Daemon                       │     ║
║  │  orchestrator.py       — master orchestrator (all rotations)       │     ║
║  │  daemon.py             — ProfileOpsDaemon (audit/guard/draft/dmn)  │     ║
║  │  production_pipeline.py— full pipeline: scrape→AGI→Groq→Selenium   │     ║
║  └────────────────────────────┬────────────────────────────────────────┘     ║
║                               ▼                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │              LAYER 6: Selenium Availability Keeper                 │     ║
║  │  rentmasseur_availability.py — Selenium-based 24/7 availability    │     ║
║  │  _set_availability.py         — quick UC-based availability setter │     ║
║  └────────────────────────────┬────────────────────────────────────────┘     ║
║                               ▼                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │              LAYER 7: Persistence                                   │     ║
║  │  db.py                 — SQLite: receipts, traffic, variants, exps │     ║
║  │  profileops.db         — main operations database                  │     ║
║  │  engagement.db         — engagement tracking                       │     ║
║  │  traffic.db / traffic_loop.db — traffic metrics                    │     ║
║  │  fortress.db           — fortress state                            │     ║
║  │  hypothesis_lab.db     — 300 experiment results                    │     ║
║  │  availability_keeper.db — availability log                        │     ║
║  └─────────────────────────────────────────────────────────────────────┘     ║
╚══════════════════════════════════════════════════════════════════════════════╝

FILE INVENTORY (all source files):

LAYER 1 — API & Auth:
  1. rm_traffic/api_client.py       (348 lines)  — RentMasseurAPI HTTP client
  2. rm_traffic/auth.py             (100 lines)  — AuthSession + keychain

LAYER 2 — Guards & Availability:
  3. rm_traffic/visibility_guard.py  (55 lines)   — ensure_visible()
  4. rm_traffic/availability_guard.py(91 lines)   — check + refresh availability
  5. rm_traffic/availability_keeper.py(341 lines) — 24/7 daemon
  6. rm_traffic/availability_algos.py(597 lines)  — 9 availability algorithms

LAYER 3 — Content & Bio:
  7. rentmasseur_core.py            (462 lines)  — shared login/driver/bio
  8. rentmasseur_optimizer.py       (637 lines)  — 30 strategies + Groq
  9. rentmasseur_coordinator.py     (135 lines)  — intent router coordinator
  10. intent_router.py              (143 lines)  — LLM strategy ranking
  11. bio_ab_tester.py              (497 lines)  — A/B testing engine
  12. rl_feedback.py                (463 lines)  — RL reward loop

LAYER 4 — Traffic & Engagement:
  13. rm_traffic/traffic_loop.py    (1178 lines) — 30 client-magnet functions
  14. rm_traffic/engagement_engine.py(1684 lines)— reciprocal visits + messages
  15. rm_traffic/money_loop.py      (788 lines)  — revenue optimization
  16. rm_traffic/fortress.py        (830 lines)  — anti-fragile automation
  17. rm_traffic/hypothesis_lab.py  (969 lines)  — 300 growth hypotheses

LAYER 5 — Orchestration:
  18. orchestrator.py               (345 lines)  — master orchestrator
  19. rm_traffic/daemon.py          (211 lines)  — ProfileOpsDaemon
  20. production_pipeline.py        (575 lines)  — full production pipeline

LAYER 6 — Selenium:
  21. rentmasseur_availability.py   (731 lines)  — Selenium availability keeper
  22. _set_availability.py          (144 lines)  — quick UC setter

LAYER 7 — Persistence:
  23. rm_traffic/db.py              (268 lines)  — SQLite schema + receipts

SCHEDULING:
  24. com.rentmasseur.availability-15min.plist  — launchd every 15min
  25. com.rentmasseur.engagement-daemon.plist   — launchd daily 10:00

CONFIG:
  26. availability.json             (17 lines)   — availability config
  27. .env                          — credentials (RM_USER, RM_PASS, GROQ_API_KEY)

TOTAL: ~9,000+ lines across 27 files
"""


# ═══════════════════════════════════════════════════════════════════════════
# FILE 1: rm_traffic/api_client.py (348 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/api_client.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RentMasseur API Client — bounded, production-ready HTTP client.

Confirmed endpoints only. No guesswork. No spam.

Endpoints:
  GET  /api/v1/account/dashboard              — dashboard data
  GET  /api/v1/account/dashboard/availability — availability status
  PUT  /api/v1/account/dashboard/availability — set availability (option + duration)
  GET  /api/v1/account/dashboard/ad-statistics— ad stats
  GET  /api/v1/account/keeponline             — keep-online status (hidden, visits, emails)
  GET  /api/v1/settings/about                 — profile about (headline, description)
  PUT  /api/v1/settings/about                 — update bio
  PUT  /api/v1/settings/visibility            — show/hide profile
  PUT  /api/v1/settings/sms                   — SMS alerts toggle
  PUT  /api/v1/settings/track-actions         — tracking toggle
  GET  /api/v1/mailbox                        — mailbox (paginated)
  POST /api/v1/mailbox/send                   — send message
  GET  /api/v1/mailbox/conversation/{username}— conversation thread
  GET  /api/v1/blogs                          — blog list
  POST /api/v1/blogs                          — create blog
  PUT  /api/v1/blogs/{id}                     — update blog
  DELETE /api/v1/blogs/{id}                   — delete blog
  POST /api/v1/search                         — search masseurs by city
  GET  /api/v1/profile/{username}             — profile data
  POST /api/v1/login                          — login (email, password, csrf, remember)

Key class: RentMasseurAPI
  - Rate-limited (min_request_interval=2.0s)
  - In-memory TTL cache (15s) for read endpoints
  - CSRF token extraction
  - Bearer token auth
  - Cookie session replay
  - Proxy support (PROXY_URL, PROXY_SECRET env vars)
  - audit_endpoints() — test all confirmed endpoints
  - full_status() — dashboard + availability + stats + keeponline + about + interview
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 2: rm_traffic/auth.py (100 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/auth.py
# ═══════════════════════════════════════════════════════════════════════════
"""
AuthSession — login, JWT, session health.

- get_credential(name): reads from env vars or macOS Keychain
- save_token_to_keychain(token): stores access token in Keychain
- load_session_from_file(path): loads cookies from saved session JSON
- AuthSession.login(): tries saved session first, falls back to API login
- AuthSession.is_authenticated(): lightweight check via get_keeponline()
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 3: rm_traffic/visibility_guard.py (55 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/visibility_guard.py
# ═══════════════════════════════════════════════════════════════════════════
"""
Visibility Guard — ensure profile is shown in search.

ensure_visible(api):
  1. GET /account/keeponline → check isAdHidden
  2. If hidden → PUT /settings/visibility {isAdHidden: false}
  3. Verify → GET /account/keeponline again
  4. Write receipt (before/after, verified flag)
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 4: rm_traffic/availability_guard.py (91 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/availability_guard.py
# ═══════════════════════════════════════════════════════════════════════════
"""
Availability Guard — refresh availability only when near expiry.

REFRESH_THRESHOLD_SECONDS = 45 * 60  (45 minutes)

check_availability(api):
  - GET /account/dashboard/availability
  - Compute seconds remaining from countdown
  - Alert if remaining < 45min
  - Write receipt

refresh_availability(api, hours=6):
  - hours 1-6 maps to duration index 0-5
  - PUT /account/dashboard/availability {option: 1, duration: 5}
  - Verify: GET again, check selected == "Available" and countdown increased
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 5: rm_traffic/availability_keeper.py (341 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/availability_keeper.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RM Availability Keeper — standalone 24/7 daemon.

Keeps profile "Available" at all times. Re-authenticates automatically.
Refreshes availability before expiry. Handles session drops.

Config:
  REFRESH_THRESHOLD_SEC = 30 * 60  (refresh when < 30min remaining)
  CHECK_INTERVAL_SEC = 5 * 60      (check every 5 min)
  MAX_DURATION = 5                  (6 hours, longest available option)

AvailabilityKeeper class:
  - login(): auth via AuthSession, track consecutive_failures
  - ensure_session(): re-login if > 50min since last login
  - check_and_refresh(): check availability, refresh if needed
    - If not "Available" → refresh
    - If remaining < 30min → refresh
    - On failure: re-login + retry (max 3 consecutive)
  - run_forever(): SIGINT/SIGTERM aware, 5min cycles, backoff after 5 failures
  - run_once(): single check + refresh
  - show_status(): print availability, visits, emails, recent log

SQLite: availability_keeper.db
  Table: availability_log (ts, action, option, duration, remaining_sec, success, detail)
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 6: rm_traffic/availability_algos.py (597 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/availability_algos.py
# ═══════════════════════════════════════════════════════════════════════════
"""
9 Availability Algorithms for Maximum Traffic.

Each algo controls when/how the profile goes available/offline to maximize
visibility, search rank, and traffic attraction.

Algorithms:
  1. JitterBurst       — brief offline pulses → "recently available" signal
  2. PeakHourSync      — match availability to historical peak traffic hours
  3. CompetitorGap     — go available when competitors drop off
  4. RefreshCascade    — staggered refresh before expiry, never gap
  5. SearchRankBoost   — toggle to appear in "available now" filters more
  6. DemandPulse       — short availability windows during low-traffic
  7. GeoRotation       — rotate timing to catch multiple timezone waves
  8. EngagementTrigger — refresh immediately after receiving a visit/message
  9. BackoffRecovery   — exponential backoff on API failure, never lose presence

AlgoState dataclass tracks:
  - available, last_refresh, last_visit, last_message
  - competitor_count, competitor_available
  - profile_views_1h/24h, current_hour, day_of_week
  - api_failures, availability_option, availability_expires
  - bursts_executed, refreshes_executed, toggles_executed
  - algo_history (last 200), attribution data, view_samples, algo_fire_log
  - baseline_rate (views/min when no algo recently fired)

Includes traffic attribution: computes baseline view rate vs post-algo lift.
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 7: rentmasseur_core.py (462 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/rentmasseur_core.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RentMasseur Core — shared login, driver, availability, and bio update utilities.
Used by all 30 strategy scripts and the coordinator.

Key functions:
  setup_driver(headless=True) — Chrome/UC driver with stealth options
  login(driver) — JS-based brute-force login discovery (5 attempts)
  set_availability_24_7(driver) — JS automation of availability selects
  update_bio(driver, new_bio) — discovers bio field across multiple URLs
  save_bio_field(driver, result, new_bio) — fills + saves bio via JS
  groq_generate_bio(strategy_name, strategy_prompt, current_bio) — Groq LLM bio gen

Bio history: bio_history.json (last 50 entries with hash dedup)
Bio files saved to: bios/ directory
Groq model: llama-3.3-70b-versatile
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 8: rentmasseur_optimizer.py (637 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/rentmasseur_optimizer.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RentMasseur Optimizer — CI/CD ready.

30 BIO STRATEGIES:
  sensory_luxury, therapeutic_expert, mystery_desire, local_hustle,
  transformation_story, night_owl, athlete_recovery, ceo_executive,
  spiritual_healer, traveler_companion, medical_referral, artist_soul,
  discrete_confidential, first_timer, seasonal_special, couples_duo,
  bodybuilder_therapy, yoga_fusion, luxury_concierge, recovery_addiction,
  military_veteran, lgbtq_pride, senior_gentle, office_relief,
  dancer_flexibility, meditation_guide, hot_stone_specialist, quick_lunch,
  birthday_gift, weekly_ritual

Functions:
  groq_generate_bio_variants(current_bio, location_hint) — generate all 30 variants
  groq_generate_bio(current_bio) — pick longest variant as best
  update_bio(driver, new_bio) — find bio field, generate, fill, save
  run_once(headless, skip_bio) — login → availability → bio update

Bio dedup: MD5 hash of bio text, skip if hash in history (last 50)
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 9: rentmasseur_coordinator.py (135 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/rentmasseur_coordinator.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RentMasseur Coordinator — uses intent router to pick top strategies,
generates bios, auto-saves to files, and updates the best one to the site.

Flow:
  1. Login
  2. Set availability 24/7
  3. Find bio field (update_bio discovery)
  4. If --pick-best: route_intents(top_n) via LLM
     Else: run all 30 strategies
  5. Generate bio for each strategy via groq_generate_bio()
  6. Pick longest bio as best
  7. save_bio_field() to upload to live profile

CLI: --headless, --skip-availability, --skip-bio, --pick-best, --top-n
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 10: intent_router.py (143 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/intent_router.py
# ═══════════════════════════════════════════════════════════════════════════
"""
Intent Router — uses Groq LLM to analyze context and rank top bio strategies.

route_intents(top_n=5):
  1. Build context: time of day, season, location, target
  2. Send all 30 strategy names + descriptions to Groq
  3. LLM picks top N most likely to convert RIGHT NOW
  4. Returns JSON array of strategy names
  5. Fallback: first N strategies if LLM fails

Context factors:
  - Time of day: morning/afternoon/evening/late night
  - Season: winter/spring/summer/fall
  - Location: Manhattan, NYC
  - Target: maximum bookings and traffic
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 11: bio_ab_tester.py (497 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/bio_ab_tester.py
# ═══════════════════════════════════════════════════════════════════════════
"""
Bio A/B testing engine — generates multiple bio variants, scores them
against competitors, and only uploads the verified winner.

Process:
  1. Scrape top 10 competitor bios from RentMasseur
  2. Generate 30 bio variants via Groq
  3. Score each bio: CTA strength, urgency, SEO keywords, emotional hook,
     uniqueness, length, phone-call conversion potential
  4. A/B test: split into pairs, Groq picks winner of each pair
  5. Final winner must beat ALL competitor bios
  6. Only upload if winner scores higher than current bio

Competitor URLs: 10 hardcoded RentMasseur profiles
CLI: --dry-run, --competitors-only
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 12: rl_feedback.py (463 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/rl_feedback.py
# ═══════════════════════════════════════════════════════════════════════════
"""
Reinforcement Learning feedback loop for RentMasseur profile optimization.

Reward function:
  reward = (views * 1) + (email_clicks * 5) + (phone_clicks * 10) + (bookings * 50)
  penalty = (bio_age_days * -0.5)  # stale bios decay

Tracks profile views, email clicks, phone calls, and booking inquiries per bio variant.
Scrapes profile stats from RentMasseur, correlates to active bio, updates RL state.
Bios that underperform are retired. Top performers are reused and mutated by LLM.

State files:
  content/rl_state.json   — current bio, best bio, total rotations, rotate flag
  content/rl_history.json — reward history per bio variant

CLI: --report, --reset
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 13: rm_traffic/traffic_loop.py (1178 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/traffic_loop.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RentMasseur Traffic Loop — 30 client-magnet functions with LLM continuous improvement.

Every function:
  1. Reads current state from RM API / Selenium / SQLite
  2. Calls LLM to analyze, prioritize, or generate improvements
  3. Executes the action (API call, Selenium, or DB write)
  4. Verifies the result
  5. Writes a receipt
  6. Feeds the result back into the LLM for next-cycle improvement

Each cycle produces:
  - Traffic snapshot (views, contacts, rank)
  - LLM-generated improvement decisions
  - Executed actions with receipts
  - Before/after metrics for A/B validation
  - Training rows for GPT-of-Money

NY cities targeted: manhattan-ny, brooklyn-ny, queens-ny, bronx-ny,
  staten-island-ny, long-island-ny, westchester-ny

CLI: --once, --daemon, --stats, --function <id>
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 14: rm_traffic/engagement_engine.py (1684 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/engagement_engine.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RentMasseur Engagement Engine — automated reciprocal visits + messaging + LLM CI/CD.

What it does:
  1. Scrapes "Who Saw Me" page via Selenium to get usernames of visitors
  2. Visits every NY profile found in search (reciprocal visibility)
  3. Visits back every client who visited your profile (reciprocal engagement)
  4. Sends LLM-generated personalized messages to clients who visited you
  5. Runs on CI/CD schedule with receipts, metrics, screenshot proof
  6. Verify/reconfirm protocol after each visit and message
  7. Respects rate limits, deduplicates, tracks state in SQLite

Safety rails:
  - Max 1 message per user per 24h (configurable)
  - No fake reviews or testimonials
  - No CAPTCHA bypass
  - No messages without LLM-generated personalized content
  - Rate limit enforcement

CLI: --once, --daemon, --visit-only, --message-only, --stats
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 15: rm_traffic/money_loop.py (788 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/money_loop.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RentMasseur Money Loop — closed-loop revenue optimization algorithm.

Pipeline:
  1. REVENUE SIGNAL COLLECTION
     - Scan mailbox for booking inquiries
     - Classify: booking / inquiry / spam / reply
     - Track premium/gold senders = higher conversion value
     - Pull ad stats: views → contact_clicks → emails funnel

  2. CONVERSION FUNNEL
     - CTR = contact_clicks / views
     - Email rate = emails / contact_clicks
     - Booking rate = bookings / emails
     - Revenue = bookings × avg_rate

  3. ATTRIBUTION
     - Bio headline → attributed views/contacts
     - Last message → attributed reply/booking
     - Last visit batch → attributed new visitors
     - Search rank → attributed organic discovery
     - Availability → attributed "available now" filter

  4. LLM REVENUE OPTIMIZER
     - Decides: bio change? rate change? who to message? extend availability?
     - Output: ranked action list with priority scores

  5. EXECUTE + MEASURE
     - Execute top-ranked actions
     - Take after-snapshot, calculate real deltas
     - Store attribution: action → real impact metrics

  6. CONTINUOUS IMPROVEMENT
     - Compare funnel metrics to last cycle
     - Update action weightings based on real metric improvements
     - Train MLP on (bio_features → funnel_metrics)

CLI: --once, --daemon, --stats
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 16: rm_traffic/fortress.py (830 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/fortress.py
# ═══════════════════════════════════════════════════════════════════════════
"""
FORTRESS — RentMasseur Automation Fortress.

Anti-fragile, self-healing profile automation with layered defenses.

10 Layers:
  1. Credential Vault       — env vars / macOS Keychain, never hardcoded
  2. Identity Rotation      — browser fingerprint rotation, proxy support
  3. Multi-Modal Login      — API token, cookie replay, Selenium, manual captcha
  4. Adaptive Rate Limiting — slow down when site shows signs of stress
  5. Self-Healing Session   — detect expiry, re-login, retry with backoff
  6. Health Monitor         — track every metric, alert on anomalies
  7. Multi-LLM Engine       — Ollama / Groq / OpenRouter with fallback
  8. Safety Governor        — kill switch, human approval for risky actions
  9. Receipt Fortress       — Merkle-style chained receipt log
  10. Local Dashboard       — web UI showing real-time status

Intervals:
  AVAIL_CHECK_INTERVAL = 1h    AVAIL_REFRESH_THRESHOLD = 10min
  VISIBILITY_CHECK_INTERVAL = 5min   STATS_INTERVAL = 15min
  BIO_EXPERIMENT_INTERVAL = 24h      DASHBOARD_INTERVAL = 1h
  HEALTH_CHECK_INTERVAL = 5min

User agents: 4 rotating (Chrome Mac, Chrome Win, Chrome Linux, Safari Mac)

CLI: --daemon, --dashboard, --status, --suggest-bio, --apply-bio
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 17: rm_traffic/hypothesis_lab.py (969 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/hypothesis_lab.py
# ═══════════════════════════════════════════════════════════════════════════
"""
300-Hypothesis Growth Lab — controlled experiment engine.

Generates, tests, scores, and retires 300 growth hypotheses using live
RM endpoint data only. No synthetic data. No fake visits. No fake clicks.

Features:
  - Contextual bandit for exploration/exploitation
  - Benjamini-Hochberg FDR control every 25 completed tests
  - Promotes only hypotheses that prove real lift

10 buckets of 30 hypotheses:
  001-030: Availability uptime
  031-060: Visibility and search presence
  061-090: Bio/headline optimization
  091-120: Pricing and rate optimization
  121-150: Engagement (visits, messages)
  151-180: Competitor positioning
  181-210: Seasonal/temporal patterns
  211-240: Mailbox/conversion optimization
  241-270: Content (blog, interview)
  271-300: Cross-platform attribution

Allowed actions: refresh_availability, ensure_visible, detect_account_issues,
  classify_mailbox_intent, draft_reply_queue, headline_variant_test,
  about_variant_test, search_rank_scan, competitor_position_scan,
  pricing_copy_test, traffic_delta_report, roi_report

CLI: --seed-300, --list, --run-next, --daemon, --report, --winners
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 18: orchestrator.py (345 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/orchestrator.py
# ═══════════════════════════════════════════════════════════════════════════
"""
Master orchestrator for RentMasseur dynamic optimization.

Runs the full autonomous loop:
  1. RL feedback collection (views, clicks, calls)
  2. Bio rotation (A/B tested, phone-call optimized)
  3. Photo rotation
  4. Price rotation
  5. Interview rotation
  6. Blog rotation
  7. Data collection and correlation
  8. Performance optimization

Reward weights: views=1, email_clicks=5, phone_clicks=10, booking_inquiries=50,
  favorites=3, messages=8

Rotation rules (max_age_hours, min_reward_threshold):
  bio: 24h/5, photo: 48h/3, price: 12h/8, interview: 72h/2, blog: 48h/4

CLI: --all, --bio, --photo, --price, --interview, --blog, --stats,
     --content, --report, --dry-run
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 19: rm_traffic/daemon.py (211 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/daemon.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RM ProfileOps Daemon — safe, bounded, receipt-bearing account ops engine.

Modes:
  audit  — read only, change nothing
  guard  — fix visibility + availability only
  draft  — generate content drafts, do not publish
  daemon — run safe loop continuously

The daemon never:
  - fakes reviews
  - fakes visits
  - auto-sends messages
  - auto-publishes blogs
  - auto-changes interview
  - makes destructive changes without backup

Intervals:
  CHECK_INTERVAL = 5min
  AVAILABILITY_CHECK_INTERVAL = 30min
  DAILY_DRAFT_INTERVAL = 24h

ProfileOpsDaemon.run_cycle():
  1. Check auth, re-login if needed
  2. guard() — ensure_visible + check_availability + refresh if needed
  3. Daily: generate bio/blog/interview drafts (if not guard mode)
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 20: production_pipeline.py (575 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/production_pipeline.py
# ═══════════════════════════════════════════════════════════════════════════
"""
RentMasseur Production Pipeline — combines all real systems into one command.

10-step pipeline:
  1. Live scrape: real competitor availability from rentmasseur.com
  2. AGI train: C++ MLP trained on 2,723 real bios
  3. AGI generate: 100K candidates via C++ engine
  4. AGI score + evolve + select: GA optimization
  5. Groq intent router: pick top strategies based on time/season
  6. Groq LLM: generate bios for top strategies
  7. Merge pools: combine AGI + Groq candidates
  8. Selenium: login → set 24/7 availability → apply best bio
  9. Receipt ledger: SHA-256 chained proof for every action
  10. Save: all results, bios, stats, receipts

ReceiptLedger: Merkle-style SHA-256 chained receipts
  - Each entry: index, timestamp, action, description, data, prev_hash, hash
  - Stored as JSONL

CLI: --skip-scrape, --skip-selenium, --agi-only, --groq-only
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 21: rentmasseur_availability.py (731 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/rentmasseur_availability.py
# ═══════════════════════════════════════════════════════════════════════════
"""
Selenium automation script to keep rentmasseur.com availability set to 24/7.

Two login methods:
  brute_force_login(driver, max_retries=5) — JS DOM discovery, captcha detection
  login(driver) — native input setter + Enter key (React/Next.js compatible)

Key features:
  - undetected-chromedriver support (stealth mode)
  - Popup/cookie banner dismissal (36 CSS + XPath selectors)
  - Captcha/anti-bot detection (crowdsec, cloudflare, etc.)
  - DOM scan utility (dump all interactive elements)
  - Debug screenshots + page source on failure
  - set_availability_24_7() — JS automation of select elements

CLI: --once, --headless, --interval (minutes)
  Default: runs in loop with 5-minute interval
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 22: _set_availability.py (144 lines)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/_set_availability.py
# ═══════════════════════════════════════════════════════════════════════════
"""
Quick availability setter using undetected-chromedriver.

Flow:
  1. Login via UC + native input setter
  2. Navigate to /settings/travels
  3. Dump all selects, buttons, inputs, textareas
  4. Try: select → radio → checkbox for availability control
  5. Save via button click
  6. Write JSON receipt to receipts/ directory
  7. Fallback: try /settings page, dump toggles
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 23: rm_traffic/db.py (268 lines)
# Path: /Users/alep/Downloads/windsurf-smoke/rm_traffic/db.py
# ═══════════════════════════════════════════════════════════════════════════
"""
ProfileOps database — SQLite persistence for receipts, traffic snapshots,
content variants, experiments, and endpoint map.

Tables:
  receipts (receipt_hash PK, receipt_type, action, input_hash, output_hash,
            verified, created_at, raw_json)
  traffic_snapshots (id, created_at, profile_views, contact_clicks,
            new_visits, new_emails, is_hidden, is_available,
            availability_valid_to, headline, description_len, raw_json)
  content_variants (variant_id PK, kind, headline, description, title, body,
            status, hypothesis, created_at, applied_at, removed_at)
  experiments (experiment_id PK, variant_id, started_at, ended_at,
            baseline_views, baseline_clicks, final_views, final_clicks,
            result_json)
  endpoint_map (endpoint_id PK, method, ...)

WAL mode enabled. write_receipt() for audit trail.
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 24: com.rentmasseur.availability-15min.plist
# Path: /Users/alep/Downloads/windsurf-smoke/com.rentmasseur.availability-15min.plist
# ═══════════════════════════════════════════════════════════════════════════
"""
launchd plist — runs rm_cicd.sh every 15 minutes (900 seconds).

Program: /bin/bash /Users/alep/Downloads/windsurf-smoke/rm_cicd.sh 15min
RunAtLoad: true
KeepAlive: on successful exit
Environment: RM_USER, RM_PASS, RENTMASSEUR_USER, RENTMASSEUR_PASS,
             RM_PHONE, GROQ_API_KEY, OPENROUTER_API_KEY
Logs: data/engagement_daemon/logs/launchd_15min.{out,err}.log
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 25: com.rentmasseur.engagement-daemon.plist
# Path: /Users/alep/Library/LaunchAgents/com.rentmasseur.engagement-daemon.plist
# ═══════════════════════════════════════════════════════════════════════════
"""
launchd plist — runs /Users/alep/rm_cicd daily at 10:00 AM.

Program: /Users/alep/rm_cicd
StartCalendarInterval: Hour=10, Minute=0
KeepAlive: false
RunAtLoad: false
WorkingDirectory: /Users/alep/Downloads/windsurf-smoke
Logs: data/engagement_daemon/logs/launchd_{stdout,stderr}.log
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 26: availability.json
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/availability.json
# ═══════════════════════════════════════════════════════════════════════════
"""
{
  "status": "active_keeper",
  "availability": {
    "available": true,
    "label": "Available 24/7",
    "source": "selenium_availability_keeper",
    "schedule": "every 30 minutes"
  },
  "live_profile_update_allowed": true,
  "automation": {
    "login_automation": "enabled",
    "captcha_path": "retry_on_failure",
    "manual_approval_required": false,
    "fallback": "manual_if_captcha_blocks"
  },
  "timestamp": "2026-06-26T09:31:00Z"
}
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE 27: .env (credentials — NOT included for security)
# Path: /Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/.env
# ═══════════════════════════════════════════════════════════════════════════
"""
Environment variables (from .env and launchd plists):
  RENTMASSEUR_USERNAME / RM_USER     — rentmasseur.com login email
  RENTMASSEUR_PASSWORD / RM_PASS     — rentmasseur.com login password
  RM_PHONE                           — phone number for profile
  GROQ_API_KEY                       — Groq API key (llama-3.3-70b-versatile)
  OPENROUTER_API_KEY                 — OpenRouter API key (fallback LLM)
  GROQ_MODEL                         — default: llama-3.3-70b-versatile
  PROXY_URL                          — optional reverse proxy URL
  PROXY_SECRET                       — optional proxy auth header
"""


# ═══════════════════════════════════════════════════════════════════════════
# COMPLETE FILE LISTING (all files in rentmasseur-extension/)
# ═══════════════════════════════════════════════════════════════════════════
"""
/Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/
├── .env                          (credentials)
├── .env.example                  (template)
├── .gitignore
├── .rm_storage_state.json        (196KB — Selenium session state)
├── DEMO_STATUS.txt
├── Dockerfile
├── README.md
├── _deploy_bio_audio_captcha.py  (14KB)
├── _deploy_bio_captcha.py        (12KB)
├── _deploy_bio_uc.py             (6.9KB)
├── _deploy_fast.py               (6.6KB)
├── _deploy_find_bio.py           (6.5KB)
├── _deploy_settings.py           (7.9KB)
├── _dump_profile.py              (4.8KB)
├── _dump_whosawme.py             (3.7KB)
├── _find_edit_page.py            (3.9KB)
├── _set_availability.py          (6.6KB)  ← FILE 22
├── availability.json             (449B)   ← FILE 26
├── auto_bio_updater.py           (4.9KB)
├── bio_ab_tester.py              (20KB)   ← FILE 11
├── bio_history.json              (281B)
├── blog_rotator.py               (4.8KB)
├── checker.py                    (5.1KB)
├── competitor_scraper.py         (8KB)
├── content.css                   (1.9KB)
├── content.js                    (5.7KB)
├── cpp_os_server.cpp             (51KB)
├── daily_evidence.py             (12KB)
├── dashboard.py                  (6.4KB)
├── demo.html                     (2.2KB)
├── deploy_bio_experiment.py      (4.9KB)
├── email_templates.py            (4.2KB)
├── ga_rl_optimizer.cpp           (11KB)
├── ga_rl_optimizer.py            (20KB)
├── hf_app.py                     (15KB)
├── intent_router.py              (6.9KB)  ← FILE 10
├── interview_rotator.py          (4.9KB)
├── kpis.py                       (11KB)
├── manifest.json                 (741B — Chrome extension manifest)
├── metrics_collector.py          (4KB)
├── orchestrator.py               (11KB)  ← FILE 18
├── photo_rotator.py              (8.5KB)
├── post_bio.py                   (5.8KB)
├── post_blog.py                  (7KB)
├── post_interview.py             (7.5KB)
├── price_rotator.py              (7KB)
├── production_control_loop.cpp   (15KB)
├── production_pipeline.py        (22KB)  ← FILE 20
├── providers.json                (523B)
├── push_bio.py                   (8.5KB)
├── rentmasseur_availability.py   (31KB)  ← FILE 21
├── rentmasseur_coordinator.py    (8.2KB) ← FILE 9
├── rentmasseur_core.py           (21KB)  ← FILE 7
├── rentmasseur_optimizer.py      (27KB)  ← FILE 8
├── requirements.txt
├── rl_feedback.py                (16KB)  ← FILE 12
├── rm_selenium_cicd.py           (25KB)
├── rotator_engine.cpp            (14KB)
├── rotator_engine.js             (8.9KB)
├── run_bio_pipeline.py           (8.8KB)
├── seo_keywords.py               (4.4KB)
├── server.py                     (5.8KB)
├── social_media_generator.py     (5.2KB)
├── start.sh
├── visit_back.py                 (6.4KB)
├── weekly_report.py              (5.5KB)
├── bios/                         (generated bio files)
├── content/                      (generated content)
├── debug/                        (debug screenshots + HTML)
├── pipeline_output/              (pipeline results)
├── quarantine/                   (quarantined content)
└── receipts/                     (JSON receipts)
"""

# ═══════════════════════════════════════════════════════════════════════════
# COMPLETE FILE LISTING (all files in rm_traffic/)
# ═══════════════════════════════════════════════════════════════════════════
"""
/Users/alep/Downloads/windsurf-smoke/rm_traffic/
├── __init__.py
├── action_api_map.json           (265KB — API action mapping)
├── action_bandit.py              (8.7KB — contextual bandit)
├── action_to_api.py              (19KB — action → API translation)
├── analyze_bios.py
├── api_client.py                 (12KB)  ← FILE 1
├── api_extractor.py              (24KB — endpoint discovery)
├── approval_queue.py             (1.9KB)
├── auth.py                       (3KB)   ← FILE 2
├── availability_algos.py         (26KB)  ← FILE 6
├── availability_guard.py         (2.9KB) ← FILE 4
├── availability_keeper.py        (12KB)  ← FILE 5
├── bio_appraiser.py
├── bio_evolver.py
├── bio_fast_scraper.py
├── bio_features.py
├── bio_generator.cpp             (8.5KB)
├── bio_generator.py              (9.9KB)
├── bio_generator_v2.cpp          (21KB)
├── bio_ml.cpp                    (20KB)
├── bio_ml_trainer.py
├── bio_predictor.py
├── bio_scraper.py
├── bio_token_backend.py
├── bio_tokenizer.py
├── bio_variants.py
├── bio_variants_library.py       (12KB)
├── bio_view_scraper.py
├── blog_agent.py
├── blog_interview_endpoints.json
├── blog_optimizer.py
├── booking_ir.py                 (10KB — booking intent recognition)
├── cdp_capture.py                (18KB — Chrome DevTools Protocol)
├── cdp_discovery.py              (8.4KB)
├── cicd_gag.py                   (39KB)
├── cli.py                        (24KB)
├── config.json / config.yaml
├── content_optimizer.py
├── content_policy.py
├── cookie_login.py
├── daemon.py                     (7.5KB)  ← FILE 19
├── db.py                         (8.9KB)  ← FILE 23
├── discover_blog_interview.py
├── endpoint_registry.py
├── engagement.db                 (49KB)
├── engagement_engine.py          (71KB)   ← FILE 14
├── engine.py                     (29KB)
├── execution_engine.py
├── feature_store.py              (9.8KB)
├── fetch_all_views.py
├── fortress.db / fortress.py     (33KB)   ← FILE 16
├── hypothesis_lab.db / .py       (59KB)   ← FILE 17
├── intent_engine.py
├── interview_agent.py
├── llm_bio_writer.py
├── llm_client.py                 (8.3KB — multi-LLM fallback)
├── money_daemon.py               (17KB)
├── money_loop.db / .py           (36KB)   ← FILE 15
├── money_training_selenium.py    (22KB)
├── overclock_bandit.db
├── overclock_ir.py               (11KB)
├── overclock_receipts.db
├── probe.py - probe6.py          (CDP probes)
├── profileops.db                 (778KB)
├── profileops.py                 (40KB)
├── receipts.py
├── recover_scrape.py
├── reply_drafter.py              (16KB)
├── reports.py
├── revenue_ir.py
├── revenue_overclock_ai.py       (16KB)
├── reward_engine.py
├── roi.db / roi_algorithm.py     (20KB)
├── score_bios.py
├── search_rank.py
├── service.db / service.py       (37KB)
├── session.json
├── social_traffic_tunnel.py      (22KB)
├── state.py / state_engine.py
├── stats_collector.py
├── stats_dashboard.py
├── traffic.db / traffic_loop.db
├── traffic_loop.py               (60KB)   ← FILE 13
├── transformers_llm.js
├── visibility_guard.py           (1.4KB)  ← FILE 3
├── visitor_revisit_engine.py     (15KB)
└── data/                         (127MB — scraped data)
"""


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY METRICS
# ═══════════════════════════════════════════════════════════════════════════
"""
Total source files:     27 core + 60+ supporting
Total lines of code:    ~9,000+ (core) / ~15,000+ (all)
Languages:              Python, C++, JavaScript, HTML/CSS, Shell
Databases:              7 SQLite DBs (profileops, engagement, traffic,
                        traffic_loop, fortress, hypothesis_lab, availability_keeper)
Scheduling:             2 launchd plists (15min + daily)
LLM providers:          Groq (primary), OpenRouter (fallback), Ollama (local)
Browser automation:     Selenium + undetected-chromedriver + CDP
Chrome extension:       manifest.json + content.js + popup.html
C++ components:         bio_generator, bio_ml, ga_rl_optimizer, rotator_engine,
                        cpp_os_server, production_control_loop
Key APIs:               20+ confirmed RentMasseur REST endpoints
Hypotheses:             300 growth experiments
Bio strategies:         30 marketing angles
Availability algos:     9 traffic-maximizing algorithms
"""
