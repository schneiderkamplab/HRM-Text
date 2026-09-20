import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root = fileURLToPath(new URL('..', import.meta.url));
export function query(sql, remote = true) {
  const result = spawnSync(process.execPath, [fileURLToPath(new URL('../node_modules/wrangler/bin/wrangler.js', import.meta.url)),
    'd1','execute','dfm-mimir-feedback',remote ? '--remote' : '--local','--json','--command',sql],
    {cwd:root,encoding:'utf8',maxBuffer:64*1024*1024});
  if (result.status !== 0) throw Error('Database operation failed. Check Wrangler authentication and database availability.');
  return JSON.parse(result.stdout).flatMap(r => r.results ?? []);
}
