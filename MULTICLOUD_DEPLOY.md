# RentMasseur Unified: production deployment

Repository: `overandor/rentmasseur-unified`
Branch: `main`

The same landing pages, booking intake, and MasseurBoost trial contract run natively on Cloudflare Pages, Vercel, and Netlify.

## Shared behavior

- Landing page: `/`
- MasseurBoost entry: `/masseurboost/`
- Booking intake: `POST /api/intake`
- Trial intake: `POST /api/trials`
- Trial status: `GET /api/trials`
- Health endpoint: `GET /api/health`
- Existing optimizer relay: `/api/engine/*`
- Existing OS relay: `/os/*`
- Optional environment variables:
  - `LEAD_WEBHOOK_URL`
  - `LEAD_WEBHOOK_TOKEN`

Never commit tokens or paste them into screenshots. Store them only as encrypted environment variables in the hosting dashboard.

## Trial contract

`POST /api/trials` accepts:

- `name`
- `contact`
- `plan`: `Starter`, `Growth`, or `Dominator`
- `profile_url`
- optional `city`
- optional `goals`
- `consent: true`

The endpoint rejects password, cookie, token, session, bearer, and authorization fields. A successful response includes:

- `receiptId`
- `trialDays: 7`
- `activation: manual_review_required`
- `stored`
- `forwarded`
- `platform`

Cloudflare can persist records to the optional `LEADS` KV binding. Vercel and Netlify report local persistence as false unless the record is forwarded to `LEAD_WEBHOOK_URL`.

## Cloudflare Pages

- Git repository: `overandor/rentmasseur-unified`
- Production branch: `main`
- Root directory: repository root
- Build command: empty
- Build output directory: `.`
- Functions directory is detected from `functions/`
- Optional KV binding name: `LEADS`

Cloudflare implementation:

- `functions/api/intake.js`
- `functions/api/trials.js`
- `functions/api/health.js`
- `wrangler.toml`

## Vercel

Import the GitHub repository as a new project.

- Framework preset: Other
- Root directory: repository root
- Build command: empty
- Output directory: `.`
- Production branch: `main`

Vercel implementation:

- `api/intake.js`
- `api/trials.js`
- `api/health.js`
- `vercel.json`

## Netlify

Import the GitHub repository as a new site.

- Base directory: empty
- Build command: empty
- Publish directory: `.`
- Functions directory: `netlify/functions`
- Production branch: `main`

Netlify implementation:

- `netlify/functions/intake.js`
- `netlify/functions/trials.js`
- `netlify/functions/health.js`
- `netlify.toml`

## Smoke tests

```bash
curl -s https://YOUR_HOST/api/health

curl -s -X POST https://YOUR_HOST/api/intake \
  -H 'content-type: application/json' \
  -d '{"name":"Test","contact":"test@example.com","service":"Deep tissue","timing":"week","budget":"160-249","location":"Manhattan","notes":"Production pipeline smoke test request."}'

curl -s -X POST https://YOUR_HOST/api/trials \
  -H 'content-type: application/json' \
  -d '{"name":"CI Trial","contact":"ci-trial@example.invalid","plan":"Growth","profile_url":"https://www.rentmasseur.com/example-profile","city":"New York","goals":"Verify the receipt-backed trial contract.","consent":true}'
```

A valid booking response includes `receiptId`, `score`, `priority`, and `nextAction`. A valid trial response includes `receiptId`, `trialDays`, `activation`, `stored`, and `forwarded`.
