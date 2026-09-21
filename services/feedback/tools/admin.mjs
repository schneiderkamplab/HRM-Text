// Account-authenticated operations; never ship this tool or credentials in the app.
import {query} from './database.mjs';
import {writeFileSync} from 'node:fs';
const [command, value, decision] = process.argv.slice(2);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
if (command === 'list') {
  console.log(JSON.stringify(query('SELECT id,received_at,rating,pseudonym,publication,review FROM feedback ORDER BY received_at DESC LIMIT 100'),null,2));
} else if (command === 'export' && value) {
  const rows = query("SELECT id,received_at,pseudonym,payload FROM feedback WHERE publication=1 AND review='approved' ORDER BY received_at");
  const data = rows.map(r => ({id:r.id,receivedAt:r.received_at,attribution:r.pseudonym,license:'https://creativecommons.org/licenses/by/4.0/',feedback:JSON.parse(r.payload)}));
  writeFileSync(value,data.map(r => JSON.stringify(r)).join('\n') + (data.length ? '\n' : ''),{flag:'wx',mode:0o600});
  console.log(`Exported ${data.length} reviewed submissions to ${value}`);
} else if (uuid.test(value ?? '')) {
  if (command === 'show') console.log(JSON.stringify(query(`SELECT * FROM feedback WHERE id='${value}'`),null,2));
  else if (command === 'review' && ['approved','rejected','pending'].includes(decision)) {
    const rows = query(`UPDATE feedback SET review='${decision}' WHERE id='${value}'${decision === 'approved' ? ' AND publication=1' : ''} RETURNING id,review`);
    if (!rows.length) throw Error('Not found or publication was not permitted.');
    console.log(JSON.stringify(rows));
  } else if (command === 'delete') console.log(JSON.stringify(query(`DELETE FROM feedback WHERE id='${value}' RETURNING id`)));
  else throw Error('Invalid command');
} else {
  console.log('Usage: npm run admin -- list | show UUID | review UUID approved|rejected|pending | export NEW-FILE.jsonl | delete UUID');
  process.exitCode = 1;
}
