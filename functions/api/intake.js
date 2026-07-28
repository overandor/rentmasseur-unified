const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
    'access-control-allow-headers': 'content-type',
    'access-control-allow-methods': 'POST,OPTIONS'
  }
});

const clean = (value, max = 200) => String(value ?? '').trim().slice(0, max);

function scoreLead(lead) {
  let score = 20;
  const reasons = [];

  if (lead.name) { score += 8; reasons.push('name supplied'); }
  if (lead.contact.includes('@') || /\d{7,}/.test(lead.contact.replace(/\D/g, ''))) {
    score += 14; reasons.push('reachable contact');
  }
  if (lead.location) { score += 10; reasons.push('location supplied'); }
  if (lead.notes.length >= 25) { score += 8; reasons.push('clear request detail'); }

  const timingPoints = { today: 22, tomorrow: 18, week: 12, flexible: 6 };
  score += timingPoints[lead.timing] || 0;
  if (lead.timing === 'today' || lead.timing === 'tomorrow') reasons.push('high scheduling intent');

  const budgetPoints = { under100: 2, '100-159': 10, '160-249': 18, '250plus': 22 };
  score += budgetPoints[lead.budget] || 0;
  if (lead.budget === '160-249' || lead.budget === '250plus') reasons.push('strong budget fit');

  return { score: Math.min(100, score), reasons };
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function onRequestOptions() {
  return json({ ok: true });
}

export async function onRequestPost(context) {
  let input;
  try {
    input = await context.request.json();
  } catch {
    return json({ error: 'Invalid JSON body.' }, 400);
  }

  const lead = {
    name: clean(input.name, 80),
    contact: clean(input.contact, 120),
    service: clean(input.service, 80),
    timing: clean(input.timing, 20),
    budget: clean(input.budget, 20),
    location: clean(input.location, 120),
    notes: clean(input.notes, 1000),
    source: clean(input.source || 'unknown', 60),
    submittedAt: clean(input.submittedAt || new Date().toISOString(), 40)
  };

  if (!lead.name || !lead.contact || !lead.location) {
    return json({ error: 'Name, contact, and location are required.' }, 422);
  }

  const { score, reasons } = scoreLead(lead);
  const acceptedAt = new Date().toISOString();
  const fingerprint = await sha256(JSON.stringify({ lead, acceptedAt }));
  const receiptId = `RM-${acceptedAt.slice(0, 10).replaceAll('-', '')}-${fingerprint.slice(0, 12).toUpperCase()}`;
  const priority = score >= 80 ? 'hot' : score >= 60 ? 'warm' : 'standard';
  const nextAction = score >= 80
    ? 'Immediate booking follow-up'
    : score >= 60
      ? 'Confirm availability and session details'
      : 'Nurture and clarify requirements';

  const record = {
    receiptId,
    acceptedAt,
    priority,
    score,
    reasons,
    nextAction,
    lead
  };

  if (context.env.LEADS && typeof context.env.LEADS.put === 'function') {
    await context.env.LEADS.put(`lead:${receiptId}`, JSON.stringify(record), {
      metadata: { priority, score, source: lead.source }
    });
  }

  if (context.env.LEAD_WEBHOOK_URL) {
    const headers = { 'content-type': 'application/json' };
    if (context.env.LEAD_WEBHOOK_TOKEN) headers.authorization = `Bearer ${context.env.LEAD_WEBHOOK_TOKEN}`;
    const webhookResponse = await fetch(context.env.LEAD_WEBHOOK_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify(record)
    });
    if (!webhookResponse.ok) {
      console.error('Lead webhook failed', webhookResponse.status, receiptId);
    }
  }

  return json({
    ok: true,
    receiptId,
    acceptedAt,
    priority,
    score,
    reasons,
    nextAction,
    stored: Boolean(context.env.LEADS),
    forwarded: Boolean(context.env.LEAD_WEBHOOK_URL)
  }, 201);
}

export async function onRequest() {
  return json({ error: 'Method not allowed.' }, 405);
}
