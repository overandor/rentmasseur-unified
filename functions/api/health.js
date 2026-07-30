export function onRequest() {
  return Response.json({
    ok: true,
    service: 'rentmasseur-unified',
    runtime: 'cloudflare-pages-functions',
    pipeline: ['capture', 'validate', 'score', 'route', 'receipt'],
    timestamp: new Date().toISOString()
  }, {
    headers: { 'cache-control': 'no-store' }
  });
}
