# RentMasseur Unified: production deployment

Repository: `overandor/rentmasseur-unified`
Branch: `main`

The same root landing page and `/api/intake` contract run natively on Cloudflare Pages, Vercel, and Netlify.

## Shared behavior

- Landing page: `/`
- Intake endpoint: `POST /api/intake`
- Health endpoint: `GET /api/health`
- Existing optimizer relay: `/api/engine/*`
- Existing OS relay: `/os/*`
- Optional environment variables:
  - `LEAD_WEBHOOK_URL`
  - `LEAD_WEBHOOK_TOKEN`

Never commit tokens or paste them into screenshots. Store them only as encrypted environment variables in the hosting dashboard.

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
- `netlify/functions/health.js`
- `netlify.toml`

## Smoke tests

```bash
curl -s https://YOUR_HOST/api/health

curl -s -X POST https://YOUR_HOST/api/intake \
  -H 'content-type: application/json' \
  -d '{"name":"Test","contact":"test@example.com","service":"Deep tissue","timing":"week","budget":"160-249","location":"Manhattan","notes":"Production pipeline smoke test request."}'
```

A valid intake response includes `receiptId`, `score`, `priority`, and `nextAction`.
