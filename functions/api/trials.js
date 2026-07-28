const corsHeaders = {
  'content-type': 'application/json; charset=utf-8',
  'cache-control': 'no-store',
  'access-control-allow-origin': '*',
  'access-control-allow-headers': 'content-type',
  'access-control-allow-methods': 'GET,POST,OPTIONS'
};

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: corsHeaders
});

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

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
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

export async function onRequestOptions() {
  return json({ ok: true });
}

export async function onRequestGet(context) {
  if (!context.env.LEADS || typeof context.env.LEADS.list !== 'function') {
    return json({
      ok: true,
      trialCount: null,
      stored: false,
      storage: 'not_configured'
    });
  }
  const list = await context.env.LEADS.list({ prefix: 'trial:', limit: 1000 });
  return json({
    ok: true,
    trialCount: list.keys.length,
    stored: true,
    storage: 'cloudflare_kv',
    truncated: !list.list_complete
  });
}

export async function onRequestPost(context) {
  let input;
  try {
    input = await context.request.json();
  } catch {
    return json({ error: 'Invalid JSON body.' }, 400);
  }

  if (containsSecretBearingKey(input)) {
    return json({ error: 'Do not submit passwords, cookies, tokens, session data, or authorization fields.' }, 400);
  }

  const trial = normalize(input);
  const validationError = validate(trial);
  if (validationError) return json({ error: validationError }, 422);

  const acceptedAt = new Date().toISOString();
  const fingerprint = await sha256(JSON.stringify({ trial, acceptedAt }));
  const receiptId = `MB-TRIAL-${acceptedAt.slice(0, 10).replaceAll('-', '')}-${fingerprint.slice(0, 12).toUpperCase()}`;
  const record = {
    type: 'trial_signup',
    receiptId,
    acceptedAt,
    trialDays: 7,
    activation: 'manual_review_required',
    trial,
    platform: 'cloudflare'
  };

  let stored = false;
  if (context.env.LEADS && typeof context.env.LEADS.put === 'function') {
    await context.env.LEADS.put(`trial:${receiptId}`, JSON.stringify(record), {
      metadata: { type: record.type, plan: trial.plan, source: trial.source }
    });
    stored = true;
  }

  let forwarded = false;
  if (context.env.LEAD_WEBHOOK_URL) {
    try {
      const headers = { 'content-type': 'application/json' };
      if (context.env.LEAD_WEBHOOK_TOKEN) headers.authorization = `Bearer ${context.env.LEAD_WEBHOOK_TOKEN}`;
      const response = await fetch(context.env.LEAD_WEBHOOK_URL, {
        method: 'POST',
        headers,
        body: JSON.stringify(record)
      });
      forwarded = response.ok;
      if (!response.ok) console.error('Trial webhook failed', response.status, receiptId);
    } catch (error) {
      console.error('Trial webhook error', receiptId, error?.message || error);
    }
  }

  return json({
    ok: true,
    receiptId,
    acceptedAt,
    trialDays: 7,
    activation: record.activation,
    plan: trial.plan,
    stored,
    forwarded,
    platform: record.platform
  }, 201);
}

export async function onRequest() {
  return json({ error: 'Method not allowed.' }, 405);
}
