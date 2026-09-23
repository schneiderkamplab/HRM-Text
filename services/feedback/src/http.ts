import { MAX_BYTES } from './payload';
export function response(status: number, value: unknown) {
  return Response.json(value, {status, headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
}
export async function readBody(request: Request, maxBytes = MAX_BYTES): Promise<string> {
  if (Number(request.headers.get('content-length')) > maxBytes) throw Error('too_large');
  if (!request.body) throw Error('invalid');
  const reader = request.body.getReader();
  const bytes = new Uint8Array(maxBytes);
  let length = 0;
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; void reader.cancel(); }, 10000);
  try {
    for (;;) {
      const {value,done} = await reader.read();
      if (done) break;
      if (length + value.length > maxBytes) { void reader.cancel(); throw Error('too_large'); }
      bytes.set(value,length);
      length += value.length;
    }
  } finally { clearTimeout(timer); reader.releaseLock(); }
  if (timedOut) throw Error('invalid');
  return new TextDecoder('utf-8', {fatal:true,ignoreBOM:false}).decode(bytes.subarray(0,length));
}
