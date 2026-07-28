export default function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  return res.status(200).json({
    ok: true,
    service: 'rentmasseur-unified',
    provider: 'vercel',
    pipeline: ['capture', 'validate', 'score', 'route', 'receipt'],
    timestamp: new Date().toISOString()
  });
}
