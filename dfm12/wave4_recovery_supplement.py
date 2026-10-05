"""CPU-only exact empty-rationale recovery; never writes campaign databases."""
import argparse
import base64
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import time

from . import compact_keep_recovery as recovery
from . import wave4_compact_handoff as campaign
from .io import digest, file_hash, load, lock, write_json

VERSION = 'wave4-empty-rationale-supplement-v1'


def ro(path):
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=60)
    db.row_factory = sqlite3.Row
    return db


def raw_proof(directory, key, stage, strict_json):
    state_path = directory/'stages'/f'{key}-{stage}.json'
    state = load(state_path)
    rid = state['raw']['raw_request_id']
    if not rid or Path(rid).name != rid:
        raise ValueError('Unsafe raw request id')
    request_path = directory/'raw'/f'{rid}.request.json'
    response_path = directory/'raw'/f'{rid}.response.json'
    request, response = load(request_path), load(response_path)
    saved_request_path = directory/'requests'/f'{key}-{stage}.json'
    saved = load(saved_request_path)
    wire = dict(saved['request'], stream=True, stream_options={'include_usage':True})
    if (request['request_id'] != rid or response['request_id'] != rid
            or request['request'] != wire or response.get('status') != 200
            or response.get('transport_error') is not None
            or digest(saved['request']) != state['request_sha256']):
        raise ValueError('Raw transport/request binding mismatch')
    body = base64.b64decode(response['raw_body_base64'], validate=True).decode('utf-8')
    text, finish = [], None
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith('data: ') or line == 'data: [DONE]':
            continue
        event = strict_json(line[6:])
        if event.get('error'):
            raise ValueError('Raw server error')
        for choice in event.get('choices', []):
            if choice.get('index', 0) != 0:
                raise ValueError('Unexpected multiple choices')
            text.append(choice.get('delta', {}).get('content') or '')
            finish = choice.get('finish_reason') or finish
    if (finish != 'stop' or state['raw'].get('finish_reason') != 'stop'
            or ''.join(text) != state['raw']['content']
            or response.get('content') != ''.join(text)):
        raise ValueError('Raw response incomplete or content drift')
    return {str(p):file_hash(p) for p in (state_path,request_path,response_path,saved_request_path)}


def check_job(job, folder, bundle, c, sources, seeds, registry, allowed_roots, held):
    directory = Path(job['workdir']).resolve()
    if not any(directory.is_relative_to(root/'work') for root in allowed_roots):
        raise ValueError('Work directory outside verified campaign lineage')
    outcome = json.loads(job['outcome_json'])
    if (outcome.get('status') != 'review_invalid_output'
            or outcome.get('review_status') != 'invalid_output'
            or 'should be non-empty' not in outcome.get('error','')):
        raise ValueError('Not the exact schema-failure class')
    spec = json.loads(job['spec_json'])
    selection = sources.execute('SELECT spec,seed_hash FROM selections WHERE id=?',
        (digest([job['language'],job['family'],spec['slot']]),)).fetchone()
    if selection is None or digest(json.loads(selection[0])) != digest(spec):
        raise ValueError('Durable source selection mismatch')
    source = spec.get('source')
    if source:
        pool = 'openhermes' if job['family']=='openhermes' else job['language']
        original = seeds.execute('SELECT payload FROM available_seeds WHERE language=? AND pool=? AND source_id=?',
            (job['language'],pool,source['id'])).fetchone()
        if original is None or digest(json.loads(original[0])) != digest(source) or selection[1] != digest(source):
            raise ValueError('Source payload/eligibility mismatch')
    owner = registry.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(job['fingerprint'],)).fetchone()
    local = ro(folder/'jobs.sqlite')
    try:
        local_owner = local.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(job['fingerprint'],)).fetchone()
    finally:
        local.close()
    if owner is None or local_owner is None or owner[0] != job['id'] or local_owner[0] != job['id']:
        raise ValueError('Global/local fingerprint ownership mismatch')
    # Original checks reassemble from saved generation and render every assistant
    # target untruncated through student_validate, retaining the 4096 limit.
    common = Path(__import__('os').path.commonpath([str(r) for r in allowed_roots]))
    receipt = recovery.inspect_job(common, job, owner[0], c, held)
    receipt['pins'].update(raw_proof(directory,job['id'],'generate',c.v6.strict_json))
    receipt['pins'].update(raw_proof(directory,job['id'],'review',c.v6.strict_json))
    candidate = load(receipt['candidate_path'])
    receipt.update(version=VERSION, bundle=str(bundle), shard=str(folder),
        source_payload_sha256=digest(source) if source else None,
        selection_sha256=digest(spec), rendered_training_tokens=candidate['rendered_training_tokens'],
        admission_state='eligible_pending_terminal_quota', original_files_unchanged=True)
    return receipt


def worker(args):
    bundle, output, index = Path(args[0]),Path(args[1]),args[2]
    folder=bundle/f'shard-{index}'; destination=output/f'shard-{index}.sqlite'
    initial=load(output/'initial.json'); manifest=load(folder/'manifest.json')
    allowed=[Path(initial['source_root'])]+[Path(initial['predecessor_root'])/f'shard-{i}' for i in range(8)]+[bundle/f'shard-{i}' for i in range(8)]
    c=campaign.controller();counts=Counter()
    with ro(folder/'jobs.sqlite') as jobs, ro(folder/'spec-selections.sqlite') as sources, \
         ro(Path(manifest['seeds_root'])/'seeds.sqlite') as seeds, ro(bundle/'fingerprints.sqlite') as registry, \
         sqlite3.connect(destination) as out:
        out.execute('PRAGMA journal_mode=WAL');out.execute('PRAGMA synchronous=FULL')
        out.execute('CREATE TABLE IF NOT EXISTS results(id TEXT PRIMARY KEY,language TEXT,family TEXT,eligible INTEGER,receipt TEXT,error TEXT,fingerprint TEXT UNIQUE)')
        ids=[r[0] for r in jobs.execute("SELECT id FROM jobs WHERE status='review_invalid_output' ORDER BY id")]
        write_json(output/f'shard-{index}-inventory.json',dict(ids=ids,started=time.time()))
        for key in ids:
            if out.execute('SELECT 1 FROM results WHERE id=?',(key,)).fetchone():continue
            job=dict(jobs.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone())
            try:
                receipt=check_job(job,folder,bundle,c,sources,seeds,registry,allowed,set(initial['held_ids']))
                out.execute('INSERT INTO results VALUES(?,?,?,?,?,?,?)',
                    (key,job['language'],job['family'],1,json.dumps(receipt,ensure_ascii=False),None,receipt['fingerprint']))
                counts['eligible']+=1
            except Exception as exc:
                out.execute('INSERT INTO results VALUES(?,?,?,?,?,?,?)',
                    (key,job['language'],job['family'],0,None,f'{type(exc).__name__}: {exc}',None))
                counts['excluded']+=1
            counts['checked']+=1
            if counts['checked']%100==0:
                out.commit();write_json(output/f'shard-{index}-progress.json',dict(counts,total=len(ids),time=time.time()))
        out.commit()
        write_json(output/f'shard-{index}-progress.json',dict(counts,total=len(ids),complete=True,time=time.time()))
    return dict(counts)


def summarize(bundle, output):
    rows=[]
    for i in range(8):
        with ro(bundle/f'shard-{i}'/'jobs.sqlite') as db, ro(output/f'shard-{i}.sqlite') as results:
            for group in db.execute('SELECT * FROM groups ORDER BY language,family'):
                g=dict(group);key=(g['language'],g['family'])
                eligible=results.execute('SELECT count(*) FROM results WHERE language=? AND family=? AND eligible=1',key).fetchone()[0]
                excluded=results.execute('SELECT count(*) FROM results WHERE language=? AND family=? AND eligible=0',key).fetchone()[0]
                gap=max(0,g['target']-g['accepted'])
                g.update(eligible_recoveries=eligible,excluded_recoveries=excluded,
                    projected_recovery=min(gap,eligible),projected_shortfall=max(0,gap-eligible),
                    quota_final=False,shard=i)
                rows.append(g)
    if len(rows)!=66 or len({(r['language'],r['family']) for r in rows})!=66:
        raise ValueError('Expected exactly66 groups')
    result=dict(version=VERSION,groups=rows,eligible=sum(r['eligible_recoveries'] for r in rows),
        projected_recovery=sum(r['projected_recovery'] for r in rows),
        projected_shortfall=sum(r['projected_shortfall'] for r in rows),
        quota_final=False,ledger_applied=False,admission_authorized=False,time=time.time())
    write_json(output/'report.json',result)
    return result


def prepare(bundle, output, workers=2):
    bundle,output=Path(bundle).resolve(),Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    receipt=load(bundle/'prepared.json');manifest=load(bundle/'shard-0/manifest.json')
    c=campaign.controller();c.v6.verify_pins(bundle/'shard-0',manifest)
    held=set()
    for root in (Path(receipt['source_root']),bundle,Path(receipt['predecessor_root'])):
        path=root/'historical-holds.json'
        if path.exists():held.update(h['job_id'] for h in load(path).get('holds',[]))
    pins={str(Path(p).resolve()):sha for p,sha in manifest['external_pins'].items()}
    pins.update(manifest['implementation_pins'])
    for module in (__import__(__name__,fromlist=['']),recovery,recovery.private,recovery.original):
        pins[str(Path(module.__file__).resolve())]=file_hash(module.__file__)
    write_json(output/'initial.json',dict(version=VERSION,bundle=str(bundle),
        source_root=receipt['source_root'],predecessor_root=receipt['predecessor_root'],
        held_ids=sorted(held),pins=pins,prepared_sha256=file_hash(bundle/'prepared.json'),
        runtime_sha256=file_hash(bundle/'shard-runtime.json'),workers=workers,
        admission_authorized=False,started=time.time()))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        list(pool.map(worker,[(str(bundle),str(output),i) for i in range(8)]))
    report=summarize(bundle,output)
    write_json(output/'prepared.json',dict(version=VERSION,report_sha256=file_hash(output/'report.json'),
        initial_sha256=file_hash(output/'initial.json'),
        result_pins={str(output/f'shard-{i}.sqlite'):file_hash(output/f'shard-{i}.sqlite') for i in range(8)},
        eligible=report['eligible'],admission_authorized=False,requires_terminal_quota=True))
    return report


def finalize(bundle, output, release):
    """Separate packages only after all owners are stopped; no live ledger writes."""
    bundle,output,release=map(lambda p:Path(p).resolve(),(bundle,output,release))
    initial=load(output/'initial.json');prepared=load(output/'prepared.json')
    if initial['bundle']!=str(bundle) or prepared['initial_sha256']!=file_hash(output/'initial.json'):
        raise ValueError('Preparation binding drift')
    for path,sha in {**initial['pins'],**prepared['result_pins']}.items():
        if file_hash(path)!=sha:raise ValueError('Preparation/evidence code drift: '+path)
    with ExitStack() as stack:
        stack.enter_context(lock(bundle/'supervisor.lock'))
        for i in range(8):stack.enter_context(lock(bundle/f'shard-{i}'/'controller.lock'))
        terminal=load(bundle/'terminal.json')
        if terminal.get('active')!=0:raise ValueError('Campaign must be terminal')
        groups=[]
        for i in range(8):
            with ro(bundle/f'shard-{i}'/'jobs.sqlite') as db:
                if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:raise ValueError('Running jobs')
                groups.extend(dict(r,shard=i) for r in db.execute('SELECT * FROM groups'))
        release.mkdir(parents=True,exist_ok=False)
        with sqlite3.connect(release/'supplement.sqlite') as supplement, ro(bundle/'fingerprints.sqlite') as global_db:
            supplement.execute('CREATE TABLE accepted(id TEXT PRIMARY KEY,fingerprint TEXT UNIQUE,language TEXT,family TEXT,receipt_sha256 TEXT,candidate_sha256 TEXT)')
            for g in groups:
                remaining=g['target']-g['accepted'];added=0
                i=g['shard']
                with ro(output/f'shard-{i}.sqlite') as results,ro(bundle/f'shard-{i}'/'jobs.sqlite') as jobs:
                    for row in results.execute('SELECT * FROM results WHERE language=? AND family=? AND eligible=1 ORDER BY id LIMIT ?',
                            (g['language'],g['family'],remaining)):
                        proof=json.loads(row['receipt'])
                        current=jobs.execute('SELECT status,outcome_json FROM jobs WHERE id=?',(row['id'],)).fetchone()
                        owner=global_db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(row['fingerprint'],)).fetchone()
                        if current is None or current[0]!='review_invalid_output' or digest(json.loads(current[1]))!=proof['original_outcome_sha256'] or owner is None or owner[0]!=row['id']:
                            raise ValueError('Recovery ownership/outcome drift')
                        for path,sha in proof['pins'].items():
                            if file_hash(path)!=sha:raise ValueError('Recovery evidence drift')
                        candidate=load(proof['candidate_path'])
                        p=release/'receipts'/f"{row['id']}.json";write_json(p,proof)
                        target=release/'accepted'/f"{row['id']}.json";write_json(target,candidate)
                        supplement.execute('INSERT INTO accepted VALUES(?,?,?,?,?,?)',(row['id'],row['fingerprint'],g['language'],g['family'],file_hash(p),file_hash(target)))
                        added+=1
                g.update(recovered=added,combined_accepted=g['accepted']+added,shortfall=remaining-added)
            supplement.commit()
        write_json(release/'manifest.json',dict(version=VERSION,groups=groups,
            recovered=sum(g['recovered'] for g in groups),shortfall=sum(g['shortfall'] for g in groups),
            terminal_sha256=file_hash(bundle/'terminal.json'),preparation_sha256=file_hash(output/'prepared.json'),
            supplement_sha256=file_hash(release/'supplement.sqlite'),source_ledgers_unchanged=True,
            source_outcomes_unchanged=True,new_gpu_calls=0,human_reviewed=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','finalize'])
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--release',type=Path);p.add_argument('--workers',type=int,choices=[1,2,4],default=2)
    a=p.parse_args()
    if a.action=='prepare':print(json.dumps(prepare(a.bundle,a.output,a.workers)))
    else:finalize(a.bundle,a.output,a.release)
