import {test, before, after} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {build} from 'esbuild';
import {Miniflare} from 'miniflare';
import {randomUUID} from 'node:crypto';
let mf, db;
function fixture() {
  return {id:randomUUID(),policyVersion:'2026-09-20',rating:'up',pseudonym:'TestOtter',comment:'Synthetic integration test',
    consent:{improvement:true,publication:true,license:'CC-BY-4.0'},chat:{messages:[{role:'user',content:'Hej'},{role:'assistant',content:'Hej!'}],summary:null},
    metadata:{appVersion:'test',platform:'test',modelId:'synthetic',contextTokens:4096,replyTokens:512,mixedLM:false}};
}
before(async () => {
  await build({entryPoints:['src/index.ts'],outfile:'.test-build/worker.js',bundle:true,format:'esm',platform:'browser'});
  mf = new Miniflare({telemetry:{enabled:false},workers:[{
    config:{name:'feedback',type:'worker',compatibilityDate:'2026-09-20',
      manifest:{mainModule:'worker.js',modules:{'worker.js':{type:'esm',contents:readFileSync('.test-build/worker.js','utf8')}}},
      env:{DB:{type:'d1',id:'DB'},SUBMISSION_LIMIT:{type:'rate-limit',namespace:'1001',simple:{limit:20,period:60}}}},
    dev:{stripCfConnectingIp:false}}]});
  db = await mf.getD1Database('DB');
  await db.exec(readFileSync('migrations/0001_feedback.sql','utf8').replace(/^--.*$/gm,'').replace(/\n/g,' '));
});
after(async () => { await mf?.dispose(); });
function post(payload, headers = {}) {
  return mf.dispatchFetch('https://feedback.test/v1/feedback',{method:'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':randomUUID(),...headers},body:typeof payload === 'string' ? payload : JSON.stringify(payload)});
}
test('private intake, concurrent idempotency, changed payload conflict',async () => {
  const p = fixture(); const responses = await Promise.all([post(p),post(p)]);
  assert.deepEqual(responses.map(r=>r.status).sort(),[200,201]);
  assert.equal((await responses[0].json()).id,p.id);
  assert.equal((await post({...p,comment:'changed'})).status,409);
  const row = await db.prepare('SELECT * FROM feedback WHERE id=?').bind(p.id).first();
  assert.equal(row.review,'pending');assert.equal(row.publication,1);
  assert.equal((await mf.dispatchFetch('https://feedback.test/v1/feedback')).status,405);
  assert.equal((await mf.dispatchFetch(`https://feedback.test/v1/feedback/${p.id}`)).status,404);
});
test('explicit consent, current policy, correct license, strict allowlist',async () => {
  for (const mutate of [p=>p.consent.improvement=false,p=>p.policyVersion='old',p=>p.consent.license=null,
    p=>p.chat.messages[0].role='tool',p=>p.metadata.path='/private/model.gguf',p=>p.pseudonym='',p=>p.rating='maybe',
    p=>p.chat.summary={content:'summary',coveredMessages:99}]) {
    const p=fixture();mutate(p);assert.equal((await post(p)).status,400);
  }
  const p=fixture();p.consent={improvement:true,publication:false,license:null};
  assert.equal((await post(p)).status,201);
  await assert.rejects(db.prepare("UPDATE feedback SET review='approved' WHERE id=?").bind(p.id).run());
});
test('Unicode summary; reject malformed, oversized, cross-origin and wrong media type', async () => {
  const p=fixture();p.chat.summary={content:'Dansk æøå 🦉',coveredMessages:2};
  assert.equal((await post(p)).status,201);
  assert.equal((await post('{')).status,400);
  assert.equal((await post(' '.repeat(1048577))).status,413);
  assert.equal((await post(fixture(),{Origin:'https://example.org'})).status,403);
  assert.equal((await post(fixture(),{'Content-Type':'text/plain'})).status,415);
});
test('native rate limiter rejects bursts',async () => {
  const key=randomUUID();let blocked=false;
  for(let n=0;n<25;n++) if((await post('{}',{'CF-Connecting-IP':key})).status===429) blocked=true;
  assert.equal(blocked,true);
});
test('atomic daily cap; retries still retrieve receipts at capacity',async () => {
  const p=fixture();assert.equal((await post(p)).status,201);
  await db.prepare("UPDATE daily_admission SET submissions=500 WHERE day=date('now')").run();
  assert.equal((await post(fixture())).status,503);assert.equal((await post(p)).status,200);
  assert.equal((await db.prepare("SELECT submissions FROM daily_admission WHERE day=date('now')").first()).submissions,500);
});
