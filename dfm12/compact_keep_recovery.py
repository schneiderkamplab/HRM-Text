"""Read-only exact technical-recovery preparation; ledger apply requires coordination."""
import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path
import sqlite3

from . import baltic_compact_successor as campaign
from . import compact_keep_rationale as private
from . import wave_compact_review as original
from .io import digest,file_hash,load,write_json,lock


def controller():
    """Private runtime and completion-proof factory; shared modules stay frozen."""
    c=private.install(campaign.controller()); retained=c.validate_saved_keep
    def saved(directory,key,spec,outcome,adapters=None):
        if 'technical_recovery_receipt' not in outcome:
            record=c.v6.audit_record(load(directory/'candidates'/f'{key}.json'))
            schema=load(directory/'requests'/f'{key}-review.json')['schema']
            adapter=private if schema==private.schema(record) else original
            return retained(directory,key,spec,outcome,(adapter,c.v6.adapters()[1]))
        path=Path(outcome['technical_recovery_receipt'])
        if file_hash(path)!=outcome['technical_recovery_sha256']:raise ValueError('Recovery receipt drift')
        receipt=load(path);root=Path(receipt['root'])
        for p,sha in receipt['pins'].items():
            if file_hash(p)!=sha:raise ValueError('Recovered source evidence drift')
        old=load(directory/'outcomes'/f'{key}.json')
        job=dict(id=key,status='review_invalid_output',origin='production',workdir=str(directory),
            outcome_json=json.dumps(old),spec_json=json.dumps(spec),fingerprint=outcome['fingerprint'],
            language=receipt['language'],family=receipt['family'])
        with sqlite3.connect((root/'jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
            owner=db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(receipt['fingerprint'],)).fetchone()
        held={h['job_id'] for h in load(root/'historical-holds.json').get('holds',[])}
        checked=inspect_job(root,job,owner[0] if owner else None,c,held)
        if checked!=receipt or outcome.get('effective_keep') is not True:raise ValueError('Recovery proof mismatch')
        return load(receipt['candidate_path']),[Path(p) for p in receipt['pins']]+[path]
    c.validate_saved_keep=saved
    def verify(root):
        manifest=campaign.verify(root,c)
        if manifest.get('technical_review_adapter')!='dfm12.compact_keep_rationale':
            raise ValueError('Explicit private-adapter manifest migration required')
        return manifest
    c.verify=verify
    return c


def migrate(prepared,coordination):
    """Called only after apply and watcher coordination; never restarts anything."""
    info=load(prepared/'manifest.json');root=Path(info['root']);agreement=load(coordination)
    if (not (prepared/'applied.json').exists() or agreement.get('watcher_paused') is not True
            or agreement.get('recovery_aware_handoff_ready') is not True
            or agreement.get('prepared_manifest_sha256')!=file_hash(prepared/'manifest.json')):
        raise ValueError('Apply receipt and parent coordination required')
    with lock(root/'controller.lock'),sqlite3.connect(root/'jobs.sqlite') as db:
        if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0] or db.execute('SELECT sum(active) FROM groups').fetchone()[0]:
            raise ValueError('Controller not drained')
        manifest=campaign.verify(root);write_json(prepared/'previous-campaign-manifest.json',manifest)
        write_json(prepared/'previous-campaign-seal.json',load(root/'seal.json'))
        for path in (Path(__file__).resolve(),Path(private.__file__).resolve()):
            manifest['implementation_pins'][str(path)]=file_hash(path)
        manifest.update(technical_review_adapter='dfm12.compact_keep_rationale',
            technical_recovery_manifest=str((prepared/'manifest.json').resolve()),
            technical_recovery_manifest_sha256=file_hash(prepared/'manifest.json'))
        write_json(root/'manifest.json',manifest);sha=file_hash(root/'manifest.json')
        write_json(root/'seal.json',dict(manifest_sha256=sha))
        db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'",(sha,));db.commit()
        write_json(prepared/'migration.json',dict(manifest_sha256=sha,watcher_rearm_required=True,
            completion_controller='dfm12.compact_keep_recovery.controller',restarted=False))
    controller().verify(root)


def credit(db,receipt,outcome):
    """Caller holds controller.lock and transaction; never consume active slots."""
    key=receipt['id']
    row=db.execute('SELECT status,outcome_json,fingerprint,language,family FROM jobs WHERE id=?',(key,)).fetchone()
    if row is None or row[0]!='review_invalid_output' or digest(json.loads(row[1]))!=receipt['original_outcome_sha256']:
        raise ValueError('Recovery job drift or already credited')
    if db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(receipt['fingerprint'],)).fetchone()!=(key,):
        raise ValueError('Fingerprint ownership drift')
    if row[2]!=receipt['fingerprint'] or (row[3],row[4])!=(receipt['language'],receipt['family']):
        raise ValueError('Recovery identity drift')
    changed=db.execute('UPDATE groups SET accepted=accepted+1 WHERE language=? AND family=? AND active=0 AND accepted<target',
        (row[3],row[4])).rowcount
    if changed!=1:raise ValueError('Quota full or controller not drained')
    db.execute('INSERT INTO compact_recoveries VALUES(?,?,?)',(key,row[1],json.dumps(receipt)))
    db.execute("UPDATE jobs SET status='accepted',outcome_json=? WHERE id=?",(json.dumps(outcome),key))


def apply_prepared(prepared,coordination):
    """Explicit parent-only operation; not invoked by the preparation CLI."""
    manifest=load(prepared/'manifest.json'); root=Path(manifest['root']); agreed=load(coordination)
    if (agreed.get('prepared_manifest_sha256')!=file_hash(prepared/'manifest.json')
            or agreed.get('root')!=str(root.resolve()) or agreed.get('watcher_paused') is not True
            or agreed.get('recovery_aware_handoff_ready') is not True):
        raise ValueError('Parent drain/migration/handoff coordination required')
    if file_hash(prepared/'eligible.jsonl')!=manifest['eligible_sha256']:raise ValueError('Prepared rows drift')
    for p,sha in manifest['code_pins'].items():
        if file_hash(p)!=sha:raise ValueError('Recovery implementation drift')
    for p,sha in manifest['source_pins'].items():
        if file_hash(p)!=sha:raise ValueError('Source pins drift; apply before explicit manifest migration')
    with lock(root/'controller.lock'),sqlite3.connect(root/'jobs.sqlite') as db:
        if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0] or db.execute('SELECT coalesce(sum(active),0) FROM groups').fetchone()[0]:
            raise ValueError('Controller must drain completely')
        db.execute('CREATE TABLE IF NOT EXISTS compact_recoveries(id TEXT PRIMARY KEY,original_outcome TEXT,receipt TEXT)')
        db.commit();count=0
        for line in (prepared/'eligible.jsonl').open():
            receipt=json.loads(line);key=receipt['id']
            if db.execute('SELECT 1 FROM compact_recoveries WHERE id=?',(key,)).fetchone():continue
            for p,sha in receipt['pins'].items():
                if file_hash(p)!=sha:raise ValueError('Recovery evidence drift')
            row=db.execute('SELECT outcome_json,workdir FROM jobs WHERE id=?',(key,)).fetchone()
            original_outcome=json.loads(row[0]); recovered=dict(original_outcome)
            path=prepared/'receipts'/f'{key}.json'; write_json(path,receipt)
            recovered.update(status='valid',review_status='recovered_empty_rationale',effective_keep=True,
                semantic_keep=True,deterministic_pass=True,deterministic_checks=receipt['deterministic_checks'],
                compact_verdict='keep',compact_reason='',repair_requested=False,
                technical_recovery_receipt=str(path.resolve()),technical_recovery_sha256=file_hash(path))
            recovered.pop('error',None)
            candidate=load(receipt['candidate_path']);candidate['id']=digest(dict(campaign=manifest['campaign'],fingerprint=receipt['fingerprint']))
            accepted=Path(row[1])/'accepted'/f'{key}.json'
            if accepted.exists() and load(accepted)!=candidate:raise ValueError('Existing accepted artifact differs')
            write_json(accepted,candidate)
            db.execute('BEGIN IMMEDIATE')
            try:credit(db,receipt,recovered);db.commit();count+=1
            except BaseException:db.rollback();raise
        write_json(prepared/'applied.json',dict(credited=count,coordination_sha256=file_hash(coordination),
            source_outcomes_unchanged=True,manifest_migration_and_watcher_rearm_still_required=True))


def inspect_job(root,job,owner,controller,held):
    key=job['id']; outcome=json.loads(job['outcome_json']); spec=json.loads(job['spec_json'])
    directory=Path(job['workdir']).resolve()
    if (job['status']!='review_invalid_output' or job['origin']!='production'
            or outcome.get('completed',0)<1791078108 or key in held
            or not directory.is_relative_to(root.resolve())):
        raise ValueError('Not an eligible new-campaign review failure')
    paths={name:directory/folder/f'{key}{suffix}.json' for name,folder,suffix in [
        ('candidate','candidates',''),('generation','stages','-generate'),
        ('review','stages','-review'),('request','requests','-review'),('outcome','outcomes','')]}
    candidate,gen,audit,request,saved=(load(paths[k]) for k in ('candidate','generation','review','request','outcome'))
    if digest(saved)!=digest(outcome) or outcome.get('spec_sha256')!=digest(spec):raise ValueError('Outcome/spec drift')
    if gen.get('status')!='complete' or gen.get('raw',{}).get('finish_reason')!='stop':raise ValueError('Generation incomplete')
    if audit.get('raw',{}).get('finish_reason')!='stop':raise ValueError('Review incomplete')
    decoded=controller.v6.strict_json(audit['raw']['content'])
    if decoded!=dict(verdict='keep',issues=[],reason='') or audit.get('output')!=decoded:
        raise ValueError('Not exact empty-rationale clean keep')
    if controller.v6.strict_json(gen['raw']['content'])!=gen['output']:raise ValueError('Generation raw drift')
    if audit.get('request_sha256')!=digest(request['request']):raise ValueError('Review request drift')
    _,generation=controller.v6.adapters()
    if digest(controller.v6.generation_assemble(spec,gen['output'],generation))!=digest(candidate):
        raise ValueError('Candidate fails original assembly/native validation')
    record=controller.v6.audit_record(candidate)
    if request['schema']!=original.schema(record):raise ValueError('Different original audit contract')
    expected=controller.v6.compact_request(original.request(record))[0]
    if request['request']!=expected:raise ValueError('Review omitted or changed actual candidate/source input')
    fingerprint=digest({k:candidate[k] for k in ('messages','tools')})
    if fingerprint!=outcome.get('fingerprint') or fingerprint!=job['fingerprint'] or owner!=key:
        raise ValueError('Fingerprint is not exclusively owned by this job')
    if candidate.get('id') in held or candidate.get('provenance',{}).get('source',{}).get('id') in held:
        raise ValueError('Explicit candidate/source hold')
    checks=private.deterministic_checks(record)
    if not private.keeps(decoded,record):raise ValueError('Unchanged deterministic gates fail')
    return dict(id=key,root=str(root.resolve()),language=job['language'],family=job['family'],fingerprint=fingerprint,
        original_outcome_sha256=digest(outcome),spec_sha256=digest(spec),
        pins={str(p):file_hash(p) for p in paths.values()},candidate_path=str(paths['candidate']),
        raw_decision=decoded,deterministic_checks=checks,recovery_basis='empty-rationale-only-v1',
        fabricated_rationale=False,ledger_applied=False)


def prepare(root,output):
    output.mkdir(parents=True,exist_ok=False)
    manifest=campaign.verify(root)
    controller=campaign.controller()
    holds=load(root/'historical-holds.json')
    held={h['job_id'] for h in holds.get('holds',[])}
    counts=Counter(); pins={str(root/name):file_hash(root/name) for name in
        ('manifest.json','seal.json','historical-holds.json')}
    with sqlite3.connect((root/'jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row; db.execute('BEGIN')
        jobs=db.execute("SELECT j.*,f.owner AS fingerprint_owner FROM jobs j LEFT JOIN fingerprints f ON f.fingerprint=j.fingerprint WHERE j.status='review_invalid_output' AND json_extract(j.outcome_json,'$.completed')>=1791078108 ORDER BY j.id").fetchall()
    with (output/'eligible.jsonl').open('x') as accepted,(output/'excluded.jsonl').open('x') as excluded:
        for job in jobs:
            counts['inspected']+=1
            try:
                result=inspect_job(root,job,job['fingerprint_owner'],controller,held)
                accepted.write(json.dumps(result,ensure_ascii=False)+'\n'); counts['eligible']+=1
            except Exception as exc:
                excluded.write(json.dumps(dict(id=job['id'],reason=str(exc)),ensure_ascii=False)+'\n')
                counts['excluded']+=1
            if counts['inspected']%100==0:write_json(output/'progress.json',dict(counts))
    write_json(output/'manifest.json',dict(version='compact-empty-rationale-recovery-v1',root=str(root.resolve()),
        campaign=manifest['campaign'],counts=dict(counts),source_pins=pins,
        code_pins={str(Path(p).resolve()):file_hash(p) for p in (__file__,private.__file__,original.__file__)},
        eligible_sha256=file_hash(output/'eligible.jsonl'),excluded_sha256=file_hash(output/'excluded.jsonl'),
        ledger_applied=False,requires_controller_drain=True,requires_parent_coordination=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--action',choices=['prepare','apply','migrate','run','verify'],default='prepare')
    p.add_argument('--root',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--coordination',type=Path)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.root,a.output)
    elif a.action=='apply':apply_prepared(a.output,a.coordination)
    elif a.action=='migrate':migrate(a.output,a.coordination)
    elif a.action=='verify':print(controller().verify(a.root)['target'])
    else:asyncio.run(controller().execute(a.root,endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)],
        concurrency=128,timeout=600,max_kv_cache_utilization=.90))
