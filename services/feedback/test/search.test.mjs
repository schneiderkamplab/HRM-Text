import {test, before, after} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {build} from 'esbuild';
import {Miniflare} from 'miniflare';
import {randomBytes, createHash, randomUUID} from 'node:crypto';
let mf, db, calls = 0, mode = 'ok';
const key = () => `mimir_${randomBytes(24).toString('hex')}`;
const hash = k => createHash('sha256').update(k).digest('hex');
async function seed(k, limit=100) {
  await db.prepare('INSERT INTO search_keys (key_hash,jina_key,daily_limit) VALUES (?,?,?)')
    .bind(hash(k),'jina_synthetic_test_secret',limit).run();
}
before(async () => {
  await build({entryPoints:['src/index.ts'],outfile:'.test-build/search.js',bundle:true,format:'esm',platform:'browser'});
  mf = new Miniflare({telemetry:{enabled:false},workers:[{
    config:{name:'search',type:'worker',compatibilityDate:'2026-09-20',
      manifest:{mainModule:'search.js',modules:{'search.js':{type:'esm',contents:readFileSync('.test-build/search.js','utf8')}}},
      env:{DB:{type:'d1',id:'DB'},SEARCH_LIMIT:{type:'rate-limit',namespace:'1002',simple:{limit:10,period:60}}}},
    dev:{stripCfConnectingIp:false,outboundService:{type:'fetcher',handler:async request => {
      calls++;
      assert.equal(request.url,'https://s.jina.ai/');
      assert.equal(request.method,'POST');
      assert.equal(request.headers.get('authorization'),'Bearer jina_synthetic_test_secret');
      assert.deepEqual(Object.keys(await request.json()),['q']);
      if(mode==='fail') return new Response('sensitive upstream error',{status:401});
      if(mode==='huge') return new Response('x'.repeat(262145));
      return Response.json({data:[{title:'DFM',url:'https://foundationmodels.dk/',description:'Dansk forskning',secret:'never forwarded'},
        {title:'unsafe',url:'file:///etc/passwd'}, {title:'invalid',url:'javascript:alert(1)'}]});
    }}}}]});
  db=await mf.getD1Database('DB');
  await db.exec(readFileSync('migrations/0002_search.sql','utf8').replace(/^--.*$/gm,'').replace(/\n/g,' '));
});
after(async()=>{await mf?.dispose();});
function post(k,body={query:'Danske modeller'},headers={}) {
  return mf.dispatchFetch('https://search.test/v1/search',{method:'POST',headers:{'Content-Type':'application/json',
    'CF-Connecting-IP':randomUUID(),'Authorization':`Bearer ${k}`,...headers},body:JSON.stringify(body)});
}
test('authentication, disabled keys, and private routes do not contact provider',async()=>{
  const before=calls,k=key();await seed(k);
  assert.equal((await post('invalid')).status,401);
  assert.equal((await post(key())).status,401);
  await db.prepare('UPDATE search_keys SET enabled=0 WHERE key_hash=?').bind(hash(k)).run();
  assert.equal((await post(k)).status,401);
  assert.equal((await mf.dispatchFetch('https://search.test/v1/search')).status,405);
  assert.equal((await mf.dispatchFetch('https://search.test/v1/search/keys')).status,404);
  assert.equal(calls,before);
});
test('strict request validation, result allowlist, and no credentials in response',async()=>{
  const k=key();await seed(k);
  for(const body of [{query:''},{query:'x'.repeat(2001)},{query:'ok',chat:[]},null])
    assert.equal((await post(k,body)).status,400);
  assert.equal((await post(k,undefined,{Origin:'https://evil.test'})).status,403);
  const r=await post(k);assert.equal(r.status,200);
  assert.deepEqual(await r.json(),{results:[{title:'DFM',url:'https://foundationmodels.dk/',description:'Dansk forskning'}]});
});
test('daily admission atomic at limit, UTC reset, revocation and rate limit',async()=>{
  const k=key();await seed(k,2);
  const responses=await Promise.all([post(k),post(k),post(k)]);
  assert.deepEqual(responses.map(r=>r.status).sort(),[200,200,429]);
  await db.prepare("UPDATE search_keys SET usage_day='2000-01-01' WHERE key_hash=?").bind(hash(k)).run();
  assert.equal((await post(k)).status,200);
  const burst=key();await seed(burst);
  let limited=false;
  for(let i=0;i<12;i++) if((await post(burst)).status===429) limited=true;
  assert.ok(limited);
});
test('provider errors and oversized responses are sanitized',async()=>{
  const k=key();await seed(k);
  mode='fail';let r=await post(k);assert.equal(r.status,502);
  assert.deepEqual(await r.json(),{error:'search_provider_unavailable'});
  mode='huge';r=await post(k);assert.equal(r.status,503);
  assert.deepEqual(await r.json(),{error:'search_unavailable'});mode='ok';
});
