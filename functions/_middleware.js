const CANONICAL_ORIGIN = 'https://rentmasseur-unified-prod-happo.vercel.app';

export async function onRequest(context) {
  const url = new URL(context.request.url);

  if (url.pathname.startsWith('/api/')) {
    return context.next();
  }

  const canonicalHost = new URL(CANONICAL_ORIGIN).hostname;
  if (url.hostname === canonicalHost) {
    return context.next();
  }

  const target = new URL(url.pathname + url.search, CANONICAL_ORIGIN);
  return Response.redirect(target.toString(), 301);
}
