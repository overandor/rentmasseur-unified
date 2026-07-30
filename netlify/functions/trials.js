const crypto = require('node:crypto');

const clean = (value, max = 300) => String(value ?? '').trim().slice(0, max);
const forbiddenKeys = new Set([
  'password', 'cookie', 'cookies', 'token', 'access_token', 'refreshtoken',
  'refresh_token', 'authorization', 'bearer', 'session', 'sessionid'
]);

function containsSecretBearingKey(value) {
  if (!value || typeof value !== 'object') return false;
  for (const [key, child] of Object.entries(value)) {
    if (forbiddenKeys.has(key.toLowerCase())) return true;
    if (containsSecretBearingKey(child)) return true;
  }
  return false;
}

function normalize(input) {
  return {
    name: clean(input.name, 80),
    contact: clean(input.contact, 120),
    plan: clean(input.plan, 30),
    profileUrl: clean(input.profile_url || input.profileUrl, 300),
    city: clean(input.city, 100),
    goals: clean(input.goals, 1000),
    consent: input.consent === true,
    source: clean(input.source || 'masseurboost', 80),
    landingUrl: clean(input.landing_url || input.landingUrl, 500),
    referrer: clean(input.referrer, 500),
    submittedAt: clean(input.submitted_at || input.submittedAt || new Date().toISOString(), 40)
  };
}

function validate(trial) {
  if (!trial.name || !trial.contact || !trial.profileUrl || !trial.plan || !trial.consent) {
    return 'Name, contact, profile URL, plan, and consent are required.';
  }
  if (!/^https?:\/\//i.test(trial.profileUrl)) return 'Profile URL must start with http:// or https://.';
  if (!['Starter', 'Growth', 'Dominator'].includes(trial.plan)) return 'Unknown plan.';
  return null;
}

const response = (statusCode, body) => ({
  statusCode,
  headers: {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
    'access-control-allow-headers': 'content-type',
    'access-control-allow-methods': 'GET,POST,OPTIONS'
  },
  body: body === null ? '' : JSON.stringify(body)
});

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') return response(204, null);
  if (event.httpMethod === 'GET') {
    return response(200, {
      ok: true,
      trialCount: null,
      stored: false,
      storage: process.env.LEAD_WEBHOOK_URL ? 'external_webhook' : 'not_configured'
    });
  }
  if (event.httpMethod !== 'POST') return response(405, { error: 'Method not allowed.' });

  let input;
  try {
    input = JSON.parse(event.body || '{}');
  } catch {
    return response(400, { error: 'Invalid JSON body.' });
  }

  if (containsSecretBearingKey(input)) {
    return response(400, { error: 'Do not submit passwords, cookies, tokens, session data, or authorization fields.' });
  }

  const trial = normalize(input);
  const validationError = validate(trial);
  if (validationError) return response(422, { error: validationError });

  const acceptedAt = new Date().toISOString();
  const hash = crypto.createHash('sha256').update(JSON.stringify({ trial, acceptedAt })).digest('hex');
  const receiptId = `MB-TRIAL-${acceptedAt.slice(0, 10).replaceAll('-', '')}-${hash.slice(0, 12).toUpperCase()}`;
  const record = {
    type: 'trial_signup',
    receiptId,
    acceptedAt,
    trialDays: 7,
    activation: 'manual_review_required',
    trial,
    platform: 'netlify'
  };

  let forwarded = false;
  if (process.env.LEAD_WEBHOOK_URL) {
    try {
      const headers = { 'content-type': 'application/json' };
      if (process.env.LEAD_WEBHOOK_TOKEN) headers.authorization = `Bearer ${process.env.LEAD_WEBHOOK_TOKEN}`;
      const webhookResponse = await fetch(process.env.LEAD_WEBHOOK_URL, {
        method: 'POST',
        headers,
        body: JSON.stringify(record)
      });
      forwarded = webhookResponse.ok;
      if (!webhookResponse.ok) console.error('Trial webhook failed', webhookResponse.status, receiptId);
    } catch (error) {
      console.error('Trial webhook error', receiptId, error?.message || error);
    }
  }

  return response(201, {
    ok: true,
    receiptId,
    receipt: receiptId,
    trial_id: receiptId,
    acceptedAt,
    trialDays: 7,
    activation: record.activation,
    plan: trial.plan,
    stored: false,
    forwarded,
    platform: record.platform,
    persistence: forwarded ? 'external_webhook' : 'receipt_only'
  });
};
