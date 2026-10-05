"""Read-only short-batch failure census; no live DB writes or full payload loads."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from dfm12.io import file_hash, load, write_json

ROOT=Path('data/dfm13/wave4')
OUT=Path(__file__).resolve().parent


def connect(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=10)
    db.execute('PRAGMA query_only=ON')
    db.execute('PRAGMA busy_timeout=1000')
    return db


def category(error):
    text=(error or '').lower()
    if not text: return 'missing_error_lease_or_unknown'
    if 'incomplete output: length' in text or 'incomplete generation: length' in text: return 'model_length'
    if text.startswith('jsondecodeerror:'): return 'json_parse'
    if any(t in text for t in ('readtimeout','connecttimeout','connecterror','remoteprotocolerror','serverdisconnected','connectionreset','brokenpipe','readerror','networkerror','timed out','timeout','connection refused','server error \'500','server error \'502','server error \'503','server error \'504','429 too many','408 request')): return 'transport_or_transient_http'
    if text.startswith('http') or 'status code' in text: return 'http_other_needs_inspection'
    if any(t in text for t in ('invalid audit','keep contradicts scores','response must be a json object','invalid_role_order','missing_assistant_target')): return 'model_schema'
    return 'other_needs_inspection'


def main():
    assert not (OUT/'jobs.jsonl').exists(), 'Preserve diagnostic snapshot'
    start=datetime.now(timezone.utc).isoformat()
    audit=connect(ROOT/'audit/jobs.sqlite')
    ceiling=audit.execute('SELECT max(rowid) FROM jobs').fetchone()[0]
    initial=audit.execute("SELECT count(*) FROM jobs WHERE stage='audit' AND status='failed'").fetchone()[0]
    found=[];last=0
    fields=('rowid','job_id','candidate_id','component','task','language','source_repo','attempts','error','owner')
    while True:
        batch=audit.execute("SELECT rowid,id,json_extract(payload,'$.record.id'),json_extract(payload,'$.record.component'),json_extract(payload,'$.record.task'),json_extract(payload,'$.record.language'),json_extract(payload,'$.record.provenance.repo'),attempts,error,owner FROM jobs WHERE stage='audit' AND status='failed' AND rowid>? AND rowid<=? ORDER BY rowid LIMIT 256",(last,ceiling)).fetchall()
        if not batch: break
        last=batch[-1][0]
        for values in batch:
            row=dict(zip(fields,values));row['error_category']=category(row['error']);found.append(row)
        print('failed metadata',len(found),flush=True)
    audit.close()
    write_json(OUT/'failed-metadata-snapshot.json',dict(start_utc=start,initial_failed=initial,rowid_ceiling=ceiling,jobs=found))
    groups=defaultdict(list)
    for row in found: groups[row['component']].append(row)
    repair=connect(ROOT/'repair/jobs.sqlite')
    component_states={}
    for component, rows in sorted(groups.items(),key=lambda x:str(x[0])):
        if not component or Path(component).name!=component:
            for row in rows:row['ledger_status']='missing_component'
            continue
        folder=ROOT/'release'/component
        status=folder/'status.json'
        component_states[component]=load(status) if status.exists() else None
        if not (folder/'ledger.sqlite').exists():
            for row in rows:row['ledger_status']='no_release_ledger'
            continue
        ledger=connect(folder/'ledger.sqlite')
        try:
            schema={r[1] for r in ledger.execute('PRAGMA table_info(rows)')}
        except sqlite3.OperationalError as exc:
            if 'locked' not in str(exc): raise
            for row in rows: row['ledger_status']='ledger_read_busy'
            ledger.close();continue
        if not {'id','status','repair_job','reaudit_job'}<=schema:
            for row in rows:row['ledger_status']='unexpected_schema'
            ledger.close();continue
        for offset in range(0,len(rows),128):
            group=rows[offset:offset+128]
            ids=list({r['candidate_id'] for r in group})
            try:
                matches={r[0]:r[1:] for r in ledger.execute('SELECT id,status,repair_job,reaudit_job FROM rows WHERE id IN ('+','.join('?' for _ in ids)+')',ids)}
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc): raise
                for row in group: row['ledger_status']='ledger_read_busy'
                continue
            for row in group:
                state=matches.get(row['candidate_id'])
                if state is None:row['ledger_status']='not_in_release_ledger';continue
                row['ledger_status'],row['repair_job'],row['reaudit_job']=state
                for field in ('repair_job','reaudit_job'):
                    if not row[field]:continue
                    job=repair.execute('SELECT stage,status,attempts,error FROM jobs WHERE id=?',(row[field],)).fetchone()
                    row[field+'_state']=dict(zip(('stage','status','attempts','error'),job)) if job else None
        ledger.close()
    repair.close()
    counts=Counter(); cross=Counter(); sources=Counter(); attempts=Counter(); examples=defaultdict(list)
    with (OUT/'jobs.jsonl').open('w') as handle:
        for row in found:
            counts[row['error_category']]+=1
            cross[(row['error_category'],row['ledger_status'])]+=1
            sources[(row['component'],row['error_category'])]+=1
            attempts[row['attempts']]+=1
            key=(row['component'],row['error_category'],row['ledger_status'])
            if len(examples[key])<2: examples[key].append(row)
            handle.write(json.dumps(row,ensure_ascii=False)+'\n')
    report=dict(start_utc=start,end_utc=datetime.now(timezone.utc).isoformat(),
        consistency='Rolling read-only short statements, not one long cross-database transaction. Job rowid ceiling fixed; failed status may progress during reads.',
        initial_failed=initial,rowid_ceiling=ceiling,observed_failed=len(found),error_categories=dict(counts),attempts=dict(attempts),
        disposition_counts=dict(Counter(r['ledger_status'] for r in found)),
        category_disposition=[dict(category=k[0],disposition=k[1],count=v) for k,v in sorted(cross.items())],
        source_categories=[dict(component=k[0],category=k[1],count=v) for k,v in sorted(sources.items(),key=lambda x:(str(x[0][0]),x[0][1]))],
        components=component_states,examples=[r for group in examples.values() for r in group])
    write_json(OUT/'report.json',report)
    write_json(OUT/'receipt.json',dict(jobs_sha256=file_hash(OUT/'jobs.jsonl'),report_sha256=file_hash(OUT/'report.json'),
        inspection_script_sha256=file_hash(__file__),read_only=True,live_database_writes=0,full_payloads_loaded=0))
    print(json.dumps({k:report[k] for k in ('initial_failed','observed_failed','error_categories','disposition_counts','attempts')},indent=2))


if __name__=='__main__':main()
