exports.handler = async () => ({
  statusCode: 200,
  headers: {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store'
  },
  body: JSON.stringify({
    ok: true,
    service: 'rentmasseur-unified',
    provider: 'netlify',
    pipeline: ['capture', 'validate', 'score', 'route', 'receipt'],
    timestamp: new Date().toISOString()
  })
});
