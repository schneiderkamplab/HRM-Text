import { MAX_BYTES, POLICY_VERSION, validatePayload } from './payload';
function response(status: number, value: unknown) {
  return Response.json(value, {status, headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
}
async function readBody(request: Request): Promise<string> {
  if (Number(request.headers.get('content-length')) > MAX_BYTES) throw Error('too_large');
  if (!request.body) throw Error('invalid');
  const reader = request.body.getReader();
  const bytes = new Uint8Array(MAX_BYTES);
  let length = 0;
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; void reader.cancel(); }, 10000);
  try {
    for (;;) {
      const {value,done} = await reader.read();
      if (done) break;
      if (length + value.length > MAX_BYTES) { void reader.cancel(); throw Error('too_large'); }
      bytes.set(value,length);
      length += value.length;
    }
  } finally { clearTimeout(timer); reader.releaseLock(); }
  if (timedOut) throw Error('invalid');
  return new TextDecoder('utf-8', {fatal:true,ignoreBOM:false}).decode(bytes.subarray(0,length));
}
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const path = new URL(request.url).pathname;
    if (path === '/health' && request.method === 'GET') return response(200,{status:'ok',policyVersion:POLICY_VERSION});
    if (path !== '/v1/feedback') return response(404,{error:'not_found'});
    if (request.method !== 'POST') return response(405,{error:'method_not_allowed'});
    // Native clients don't send Origin. No cross-origin browser intake in this MVP.
    if (request.headers.has('origin')) return response(403,{error:'native_clients_only'});
    if (request.headers.get('content-type')?.split(';')[0].trim() !== 'application/json') return response(415,{error:'json_required'});
    const {success} = await env.SUBMISSION_LIMIT.limit({key:request.headers.get('CF-Connecting-IP') ?? 'unknown'});
    if (!success) return response(429,{error:'rate_limited'});
    let payload;
    try { payload = validatePayload(JSON.parse(await readBody(request))); }
    catch (e) { return response(e instanceof Error && e.message === 'too_large' ? 413 : 400,{error:'invalid_payload'}); }
    const json = JSON.stringify(payload);
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(json))), b => b.toString(16).padStart(2,'0')).join('');
    try {
      const inserted = await env.DB.prepare(`INSERT INTO feedback (id,rating,pseudonym,publication,payload,payload_hash)
        VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING`).bind(payload.id,payload.rating,payload.pseudonym,+payload.consent.publication,json,hash).run();
      const row = await env.DB.prepare('SELECT received_at,payload_hash FROM feedback WHERE id=?').bind(payload.id).first<{received_at:string,payload_hash:string}>();
      if (!row) return response(503,{error:'temporarily_unavailable'});
      if (row.payload_hash !== hash) return response(409,{error:'submission_id_conflict'});
      return response(inserted.meta.changes > 0 ? 201 : 200,{id:payload.id,receivedAt:row.received_at});
    } catch (e) {
      // Never log SQL exceptions: they can include bound conversation data.
      return response(503,{error:'temporarily_unavailable'});
    }
  }
} satisfies ExportedHandler<Env>;
