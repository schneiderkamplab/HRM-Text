import { readBody, response } from './http';

export async function search(request: Request, env: Env): Promise<Response> {
  if (request.method !== 'POST') return response(405, {error: 'method_not_allowed'});
  if (request.headers.has('origin')) return response(403, {error: 'native_clients_only'});
  if (request.headers.get('content-type')?.split(';')[0].trim() !== 'application/json') {
    return response(415, {error: 'json_required'});
  }
  const ip = request.headers.get('CF-Connecting-IP') ?? 'unknown';
  if (!(await env.SEARCH_LIMIT.limit({key: `ip:${ip}`})).success) {
    return response(429, {error: 'rate_limited'});
  }
  const key = request.headers.get('authorization')?.match(/^Bearer (mimir_[a-f0-9]{6,128})$/)?.[1];
  if (!key) return response(401, {error: 'invalid_search_key'});
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',
    new TextEncoder().encode(key))), b => b.toString(16).padStart(2, '0')).join('');
  if (!(await env.SEARCH_LIMIT.limit({key: `key:${hash}`})).success) {
    return response(429, {error: 'rate_limited'});
  }
  let query: string;
  try {
    const body = JSON.parse(await readBody(request, 16384));
    if (!body || Object.keys(body).length !== 1 || typeof body.query !== 'string' ||
        !body.query.trim() || body.query.length > 2000) throw Error('invalid');
    query = body.query.trim();
  } catch { return response(400, {error: 'invalid_query'}); }
  try {
    // Atomic per-key daily admission: parallel requests cannot overspend the cap.
    // Count admitted attempts even when Jina fails; never log queries or secrets.
    const row = await env.DB.prepare(`UPDATE search_keys SET
      used=CASE WHEN usage_day=date('now') THEN used+1 ELSE 1 END,
      usage_day=date('now') WHERE key_hash=? AND enabled=1
      AND (usage_day<>date('now') OR used<daily_limit) RETURNING jina_key`).bind(hash)
      .first<{jina_key: string}>();
    if (!row) {
      const known = await env.DB.prepare('SELECT enabled FROM search_keys WHERE key_hash=?')
        .bind(hash).first<{enabled: number}>();
      return known?.enabled === 1 ? response(429, {error: 'daily_limit'}) :
        response(401, {error: 'invalid_search_key'});
    }
    const upstream = await fetch('https://s.jina.ai/', {
      method: 'POST', redirect: 'manual', signal: AbortSignal.timeout(30000),
      headers: {'Authorization': `Bearer ${row.jina_key}`, 'Content-Type': 'application/json',
        'Accept': 'application/json', 'X-Respond-With': 'no-content'},
      body: JSON.stringify({q: query}),
    });
    if (!upstream.ok) {
      await upstream.body?.cancel();
      return response(502, {error: 'search_provider_unavailable'});
    }
    // Reuse bounded streaming reader; provider response bodies are untrusted.
    const body = JSON.parse(await readBody(new Request('https://local/', {
      method: 'POST', body: upstream.body,
    }), 262144));
    if (!Array.isArray(body.data)) throw Error('invalid_provider_response');
    const results = body.data.slice(0, 5).flatMap((item: Record<string, unknown>) => {
      if (!item || typeof item.url !== 'string') return [];
      let url: URL;
      try { url = new URL(item.url); } catch { return []; }
      if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || item.url.length > 2048) return [];
      return [{title: typeof item.title === 'string' ? item.title.slice(0, 300) : item.url,
        url: item.url, description: typeof item.description === 'string' ? item.description.slice(0, 1500) : ''}];
    });
    return response(200, {results});
  } catch { return response(503, {error: 'search_unavailable'}); }
}
