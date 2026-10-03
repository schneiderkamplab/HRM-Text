// Admin-only. Read credentials through stdin; never place them in CLI arguments.
import {createHash} from 'node:crypto';
import {mkdtempSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
let input='';
for await (const chunk of process.stdin) {
  input+=chunk;
  if(input.length>8192) throw Error('Input too large');
}
let value;
try { value=JSON.parse(input); } catch { throw Error('Expected JSON input'); }
if (!/^mimir_[a-f0-9]{6,128}$/.test(value.mimirKey ?? '')) throw Error('Invalid Mimir key format');
const hash=createHash('sha256').update(value.mimirKey).digest('hex');
let sql;
if (value.enabled === false) {
  sql=`UPDATE search_keys SET enabled=0 WHERE key_hash='${hash}';`;
} else {
  if(!/^jina_[A-Za-z0-9_-]+$/.test(value.jinaKey ?? '')) throw Error('Invalid Jina key format');
  const limit=value.dailyLimit ?? 100;
  if(!Number.isInteger(limit) || limit<1 || limit>10000) throw Error('Invalid daily limit');
  // Validated alphabet excludes SQL quotes. Preserve usage on rotation/re-enabling.
  sql=`INSERT INTO search_keys (key_hash,jina_key,daily_limit) VALUES ('${hash}','${value.jinaKey}',${limit})
    ON CONFLICT(key_hash) DO UPDATE SET jina_key=excluded.jina_key,daily_limit=excluded.daily_limit,enabled=1;`;
}
const directory=mkdtempSync(join(tmpdir(),'mimir-search-admin-'));
try {
  const file=join(directory,'mapping.sql');
  writeFileSync(file,sql,{mode:0o600});
  const result=spawnSync(process.execPath,[fileURLToPath(new URL('../node_modules/wrangler/bin/wrangler.js',import.meta.url)),
    'd1','execute','dfm-mimir-feedback',process.argv.includes('--local') ? '--local' : '--remote','--file',file],
    {cwd:fileURLToPath(new URL('..',import.meta.url)),encoding:'utf8',env:{...process.env,WRANGLER_LOG:'error'}});
  // SQL errors/output may include credentials. Never echo them.
  if(result.status!==0) throw Error('Mapping update failed; check database migrations and account access.');
  console.log('Search mapping updated.');
} finally { rmSync(directory,{recursive:true,force:true}); }
