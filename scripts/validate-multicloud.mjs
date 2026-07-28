import { access, readFile } from 'node:fs/promises';
import { constants } from 'node:fs';

const required = [
  'index.html',
  'wrangler.toml',
  'vercel.json',
  'netlify.toml',
  'functions/api/intake.js',
  'functions/api/health.js',
  'api/intake.js',
  'api/health.js',
  'netlify/functions/intake.js',
  'netlify/functions/health.js'
];

for (const file of required) await access(file, constants.R_OK);

const html = await readFile('index.html', 'utf8');
for (const token of ['RentMasseur Unified', '/api/intake', 'Cloudflare', 'Vercel', 'Netlify']) {
  if (!html.includes(token)) throw new Error(`index.html missing required token: ${token}`);
}

const vercel = JSON.parse(await readFile('vercel.json', 'utf8'));
if (!Array.isArray(vercel.rewrites)) throw new Error('vercel.json must define rewrites');

const netlify = await readFile('netlify.toml', 'utf8');
for (const route of ['/api/intake', '/api/health']) {
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

console.log(JSON.stringify({
  ok: true,
  service: 'rentmasseur-unified',
  providers: ['cloudflare', 'vercel', 'netlify'],
  checkedFiles: required.length,
  contract: ['receiptId', 'score', 'priority', 'nextAction']
}, null, 2));
