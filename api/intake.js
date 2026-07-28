import crypto from 'node:crypto';

const clean = (value, max = 200) => String(value ?? '').trim().slice(0, max);

function scoreLead(lead) {
  let score = 20;
  const reasons = [];
  if (lead.name) { score += 8; reasons.push('name supplied'); }
  if (lead.contact.includes('@') || /\d{7,}/.test(lead.contact.replace(/\D/g, ''))) { score += 14; reasons.push('reachable contact'); }
  if (lead.location) { score += 10; reasons.push('location supplied'); }
  if (lead.notes.length >= 25) { score += 8; reasons.push('clear request detail'); }
  score += ({ today: 22, tomorrow: 18, week: 12, flexible: 6 })[lead.timing] || 0;
  score += ({ under100: 2, '100-159': 10, '160-249': 18, '250plus': 22 })[lead.budget] || 0;
  return { score: Math.min(100, score), reasons };
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed.' });
  let input;
  try { input = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {}); }
  catch { return res.status(400).json({ error: 'Invalid JSON body.' }); }
  const lead = {
    name: clean(input.name, 80), contact: clean(input.contact, 120), service: clean(input.service, 80),
    timing: clean(input.timing, 20), budget: clean(input.budget, 20), location: clean(input.location, 120),
    notes: clean(input.notes, 1000), source: clean(input.source || 'vercel', 100),
    landingPath: clean(input.landingPath, 240), referrer: clean(input.referrer, 500),
    utmSource: clean(input.utmSource, 100), utmMedium: clean(input.utmMedium, 100), utmCampaign: clean(input.utmCampaign, 140),
    submittedAt: clean(input.submittedAt || new Date().toISOString(), 40)
  };
  if (!lead.name || !lead.contact || !lead.location) return res.status(422).json({ error: 'Name, contact, and location are required.' });
  const { score, reasons } = scoreLead(lead);
  const acceptedAt = new Date().toISOString();
  const hash = crypto.createHash('sha256').update(JSON.stringify({ lead, acceptedAt })).digest('hex');
  const receiptId = `RM-${acceptedAt.slice(0,10).replaceAll('-','')}-${hash.slice(0,12).toUpperCase()}`;
  const priority = score >= 80 ? 'hot' : score >= 60 ? 'warm' : 'standard';
  const nextAction = score >= 80 ? 'Immediate booking follow-up' : score >= 60 ? 'Confirm availability and session details' : 'Nurture and clarify requirements';
  const attribution = { source: lead.source, landingPath: lead.landingPath, referrer: lead.referrer, utmSource: lead.utmSource, utmMedium: lead.utmMedium, utmCampaign: lead.utmCampaign };
  const record = { receiptId, acceptedAt, priority, score, reasons, nextAction, attribution, lead, platform: 'vercel' };
  if (process.env.LEAD_WEBHOOK_URL) {
    const headers = { 'content-type': 'application/json' };
    if (process.env.LEAD_WEBHOOK_TOKEN) headers.authorization = `Bearer ${process.env.LEAD_WEBHOOK_TOKEN}`;
    await fetch(process.env.LEAD_WEBHOOK_URL, { method: 'POST', headers, body: JSON.stringify(record) });
  }
  return res.status(201).json({ ok: true, ...record, forwarded: Boolean(process.env.LEAD_WEBHOOK_URL) });
}
