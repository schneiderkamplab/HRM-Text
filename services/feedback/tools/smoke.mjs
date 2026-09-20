// Explicit synthetic live test. Requires team Wrangler login for verification/cleanup.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {query} from './database.mjs';
const base = 'https://dfm-mimir-feedback.dfm-mimir-feedback.workers.dev';
const ids=[];
try {
  assert.equal((await fetch(`${base}/health`)).status,200);
  for (const publication of [true,false]) {
    const p={id:randomUUID(),policyVersion:'2026-09-20',rating:'up',pseudonym:'SyntheticTestOtter',comment:'Synthetic service smoke test; deleted immediately',
      consent:{improvement:true,publication,license:publication?'CC-BY-4.0':null},chat:{messages:[{role:'user',content:'Synthetic Hej'},{role:'assistant',content:'Synthetic hej!'}],summary:null},
      metadata:{appVersion:'smoke-test',platform:'test',modelId:'synthetic',contextTokens:4096,replyTokens:512,mixedLM:false}};
    ids.push(p.id);
    const post = () => fetch(`${base}/v1/feedback`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
    assert.equal((await post()).status,201);
    const retry=await post();assert.equal(retry.status,200);assert.equal((await retry.json()).id,p.id);
    const row=query(`SELECT publication,review FROM feedback WHERE id='${p.id}'`)[0];
    assert.equal(row.publication,+publication);assert.equal(row.review,'pending');
    assert.equal(query(`UPDATE feedback SET review='approved' WHERE id='${p.id}' AND publication=1 RETURNING id`).length,+publication);
    assert.equal(query(`SELECT id FROM feedback WHERE id='${p.id}' AND publication=1 AND review='approved'`).length,+publication);
    assert.equal((await fetch(`${base}/v1/feedback/${p.id}`)).status,404);
  }
  assert.equal((await fetch(`${base}/v1/feedback`)).status,405);
  assert.equal((await fetch(`${base}/admin`)).status,404);
  console.log('Live smoke passed: receipts, duplicate retry, private/public permissions, reviewed export eligibility, no public read/admin endpoints.');
} finally {
  for(const id of ids) query(`DELETE FROM feedback WHERE id='${id}'`);
  console.log(`Removed ${ids.length} synthetic test submissions.`);
}
