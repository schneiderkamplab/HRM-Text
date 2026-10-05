"""CPU-only SR terminal refresh and existing-convention publication."""
import json
from pathlib import Path
import sqlite3

from dfm12.io import file_hash, load, write_json
from dfm12.wave_repair import process
from dfm12.wave_release import release


def main():
    root=Path('data/dfm13/wave4')
    output=Path(__file__).resolve().parent/'finalization'
    ledger=root/'release/wikipedia-sr'
    snapshot=output/'retry-jobs-before.json'
    if not snapshot.exists():
        db=sqlite3.connect((ledger/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
        queue=sqlite3.connect((root/'repair/jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
        retries=[]
        for key,job in db.execute("SELECT id,reaudit_job FROM rows WHERE status='audit_retry_pending'"):
            fields=('status','attempts','owner','result','error')
            state=queue.execute('SELECT '+','.join(fields)+' FROM jobs WHERE id=?',(job,)).fetchone()
            retries.append(dict(candidate_id=key,job_id=job,job=dict(zip(fields,state)) if state else None))
        write_json(snapshot,dict(jobs=retries,source_status=load(ledger/'status.json'),
            observed_processes={'finalizer':2355940,'tokenizer':2134027,'primary_audit':2032197,'audit_booster':2111441},
            retry_client_note='No active repair/jobs.sqlite client found; all 22 referenced retries already terminal. repair-audit-client.log records 21 completions and four request errors. No restart/reset needed.'))
        db.close();queue.close()
    process(root,'wikipedia-sr')
    status=load(ledger/'status.json')
    if not status['terminal'] or not status['export_ready']:
        raise ValueError('SR not ready; preserve unresolved statuses')
    if status['counts'].get('excluded_manual_review')!=4:
        raise ValueError('Manual exclusion count changed')
    write_json(output/'terminal-status.json',status)
    for task in ('denoising','paragraph-reordering','prefix-continuation','span-filling'):
        publication=ledger/task/'publication.json'
        if publication.exists() and load(publication).get('uploaded'):
            if not load(publication).get('attribution_files'):
                raise ValueError('Concurrent publication lacks correction attachment; do not overwrite')
        else:
            release(root,'wikipedia-sr',upload=True,task=task)
        print('PUBLISHED',task,load(publication)['hf_revision'],flush=True)
    write_json(output/'publication-complete.json',dict(status='accepted_uploaded',
        retry_snapshot_sha256=file_hash(snapshot),terminal_status_sha256=file_hash(output/'terminal-status.json'),
        publications={task:load(ledger/task/'publication.json') for task in
            ('denoising','paragraph-reordering','prefix-continuation','span-filling')}))


if __name__=='__main__': main()
