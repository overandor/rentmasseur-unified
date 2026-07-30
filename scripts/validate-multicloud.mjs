import { access, readFile } from 'node:fs/promises';
import { constants } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';

const require = createRequire(import.meta.url);

const required = [
  'index.html',
  'wrangler.toml',
  'vercel.json',
  'netlify.toml',
  'functions/api/intake.js',
  'functions/api/trials.js',
  'functions/api/health.js',
  'api/intake.js',
  'api/trials.js',
  'api/health.js',
  'netlify/functions/intake.js',
  'netlify/functions/trials.js',
  'netlify/functions/health.js',
  'integrations/hf-source/dashboard/index.html',
  'masseurboost/index.html'
];

for (const file of required) await access(file, constants.R_OK);

const html = await readFile('index.html', 'utf8');
for (const token of ['RentMasseur Unified', '/api/intake', 'leadForm', 'Request a session']) {
  if (!html.includes(token)) throw new Error(`index.html missing required interface contract: ${token}`);
}

const dashboard = await readFile('integrations/hf-source/dashboard/index.html', 'utf8');
for (const token of ['/api/health', '/api/funnel/daily', '/api/kpis', '/api/candidates', '/api/receipts', '/api/trials', 'createTrial(payload)']) {
  if (!dashboard.includes(token)) throw new Error(`MasseurBoost dashboard missing live contract: ${token}`);
}
for (const forbidden of ['using demo values', '1,334', 'ZK-proof', 'href="#"']) {
  if (dashboard.includes(forbidden)) throw new Error(`MasseurBoost dashboard still contains mock content: ${forbidden}`);
}

const entry = await readFile('masseurboost/index.html', 'utf8');
if (!entry.includes('/integrations/hf-source/dashboard/')) throw new Error('MasseurBoost entry path does not target the live dashboard');

const vercel = JSON.parse(await readFile('vercel.json', 'utf8'));
if (!Array.isArray(vercel.rewrites)) throw new Error('vercel.json must define rewrites');

const netlify = await readFile('netlify.toml', 'utf8');
for (const route of ['/api/intake', '/api/trials', '/api/health']) {
  if (!netlify.includes(route)) throw new Error(`netlify.toml missing route: ${route}`);
}

const cloudflareIntake = await readFile('functions/api/intake.js', 'utf8');
const vercelIntake = await readFile('api/intake.js', 'utf8');
const netlifyIntake = await readFile('netlify/functions/intake.js', 'utf8');
for (const [name, source] of [['cloudflare', cloudflareIntake], ['vercel', vercelIntake], ['netlify', netlifyIntake]]) {
  for (const contract of ['receiptId', 'score', 'priority', 'nextAction']) {
    if (!source.includes(contract)) throw new Error(`${name} intake missing contract field: ${contract}`);
  }
}

const trialPayload = {
  name: 'CI Trial',
  contact: 'ci-trial@example.invalid',
  plan: 'Growth',
  profile_url: 'https://www.rentmasseur.com/example-profile',
  city: 'New York',
  goals: 'Verify the receipt-backed trial contract in CI.',
  consent: true,
  source: 'ci_contract_test'
};

function assertTrial(body, provider) {
  if (!body?.ok) throw new Error(`${provider} trial was not accepted`);
  if (!String(body.receiptId || '').startsWith('MB-TRIAL-')) throw new Error(`${provider} trial receipt format is invalid`);
  if (body.receipt !== body.receiptId || body.trial_id !== body.receiptId) throw new Error(`${provider} trial receipt aliases are inconsistent`);
  if (body.trialDays !== 7) throw new Error(`${provider} trial duration is invalid`);
  if (body.activation !== 'manual_review_required') throw new Error(`${provider} activation boundary is missing`);
}

const cloudflare = await import('../functions/api/trials.js');
const kvWrites = [];
const cloudflareResponse = await cloudflare.onRequestPost({
  request: new Request('https://example.pages.dev/api/trials', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(trialPayload)
  }),
  env: {
    LEADS: {
      async put(key, value, options) { kvWrites.push({ key, value, options }); },
      async list() { return { keys: kvWrites.map(({ key }) => ({ name: key })), list_complete: true }; }
    }
  }
});
const cloudflareBody = await cloudflareResponse.json();
assertTrial(cloudflareBody, 'cloudflare');
if (!cloudflareBody.stored || kvWrites.length !== 1) throw new Error('cloudflare trial did not persist to KV');
if (cloudflareResponse.headers.get('access-control-allow-origin') !== '*') throw new Error('cloudflare trial CORS is missing');

const cloudflareRejected = await cloudflare.onRequestPost({
  request: new Request('https://example.pages.dev/api/trials', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ ...trialPayload, password: 'forbidden' })
  }),
  env: {}
});
if (cloudflareRejected.status !== 400) throw new Error('cloudflare trial accepted a password field');

const { default: vercelTrials } = await import('../api/trials.js');
const vercelReq = { method: 'POST', body: trialPayload };
const vercelRes = {
  headers: {}, statusCode: 200, body: null,
  setHeader(name, value) { this.headers[name.toLowerCase()] = value; },
  status(code) { this.statusCode = code; return this; },
  json(body) { this.body = body; return this; },
  end() { return this; }
};
await vercelTrials(vercelReq, vercelRes);
if (vercelRes.statusCode !== 201) throw new Error(`vercel trial returned ${vercelRes.statusCode}`);
assertTrial(vercelRes.body, 'vercel');
if (vercelRes.headers['access-control-allow-origin'] !== '*') throw new Error('vercel trial CORS is missing');
if (vercelRes.body.stored !== false) throw new Error('vercel trial falsely claims local persistence');

const netlifySource = await readFile('netlify/functions/trials.js', 'utf8');
const netlifyModule = { exports: {} };
vm.runInNewContext(netlifySource, {
  module: netlifyModule,
  exports: netlifyModule.exports,
  require,
  process,
  fetch,
  console,
  URL,
  setTimeout,
  clearTimeout
}, { filename: 'netlify/functions/trials.js' });
const netlifyResponse = await netlifyModule.exports.handler({
  httpMethod: 'POST',
  body: JSON.stringify(trialPayload)
});
if (netlifyResponse.statusCode !== 201) throw new Error(`netlify trial returned ${netlifyResponse.statusCode}`);
const netlifyBody = JSON.parse(netlifyResponse.body);
assertTrial(netlifyBody, 'netlify');
if (netlifyResponse.headers['access-control-allow-origin'] !== '*') throw new Error('netlify trial CORS is missing');
if (netlifyBody.stored !== false) throw new Error('netlify trial falsely claims local persistence');

console.log(JSON.stringify({
  ok: true,
  service: 'rentmasseur-unified',
  providers: ['cloudflare', 'vercel', 'netlify'],
  checkedFiles: required.length,
  intakeContract: ['receiptId', 'score', 'priority', 'nextAction'],
  trialContract: ['receiptId', 'receipt', 'trial_id', 'trialDays', 'activation', 'stored', 'forwarded'],
  liveDashboard: true
}, null, 2));
