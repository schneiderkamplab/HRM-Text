"""Successor-only full-article QA consumer and resumable native31B CPU preflight."""
import argparse
import asyncio
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
import json
import multiprocessing
from pathlib import Path
import sqlite3
import time

from . import baltic_qa31_article_adapter as adapter
from . import baltic_article_adapter_verify as retrieval
from . import baltic_qa31_consumer as base
from . import fars_summary_consumer as common
from . import fars_summary_handoff as budget
from . import held31_capacity_consumer as capacity
from .io import digest, file_hash, load, lock, write_json

SCHEMA = 'baltic-qa31-full-article-consumer-v1'
CONTEXT = 32768


def checked_pins(pins):
    for path, sha in pins.items():
        if file_hash(path) != sha:
            raise ValueError('Pinned dependency/input drift: '+path)


def inputs(evidence, source, ready_path):
    manifest = load(evidence/'manifest.json')
    verification = load(evidence/'verification.json')
    source_manifest = load(source/'manifest.json')
    ready = load(ready_path)
    if (not manifest.get('complete') or manifest.get('sample') is not False
            or manifest['rows'] != sum(base.COUNTS.values())
            or verification['rows'] != manifest['rows']
            or verification['manifest_sha256'] != file_hash(evidence/'manifest.json')
            or verification['database_sha256'] != manifest['database_sha256']
            or verification.get('full_article_hashes_verified') is not True
            or verification.get('source_messages_unchanged') is not True
            or verification.get('review_labels_excluded') is not True):
        raise ValueError('Complete verified full retrieval required')
    if (file_hash(evidence/'pins.json') != manifest['input_pins_sha256']
            or file_hash(source/'manifest.json') != load(source/'seal.json')['manifest_sha256']
            or ready['model'] != base.MODEL or ready.get('all_files_verified') is not True):
        raise ValueError('Source/model receipt mismatch')
    pins = dict(source_manifest['pins'])
    pins.update({str(Path(p).resolve()):s for p,s in load(evidence/'pins.json')['files'].items()})
    pins[str((source/'packets.sqlite').resolve())] = source_manifest['packets_sha256']
    pins[str((evidence/'evidence.sqlite').resolve())] = manifest['database_sha256']
    for path in (evidence/'manifest.json', evidence/'verification.json', evidence/'pins.json',
                 source/'manifest.json', source/'seal.json', ready_path,
                 Path(__file__), Path(adapter.__file__), Path(retrieval.__file__),
                 Path(capacity.__file__), Path(capacity.capacity.__file__),
                 Path('dfm12/wave4_gemma31_download.py'),
                 Path('tests/test_baltic_qa31_article_consumer.py')):
        pins[str(path.resolve())] = file_hash(path)
    for name in ('tokenizer.json','tokenizer_config.json','chat_template.jinja','config.json'):
        entry = next(f for f in ready['files'] if f['name']==name)
        pins[str((Path(ready['snapshot'])/name).resolve())] = entry['local_sha256']
    checked_pins(pins)
    return dict(schema=SCHEMA, pins=pins, snapshot=ready['snapshot'],model=base.MODEL,
        revision=ready['revision'], expected_count=manifest['rows'],
        expected_histogram=manifest['candidate_count_histogram'],
        calibration_diagnostic_ids=source_manifest['diagnostic_ids'],
        evidence_sha256=manifest['database_sha256'],context_limit=CONTEXT,
        policy_sha256=digest([adapter.REVIEW_POLICY,adapter.REPAIR_POLICY]),
        workers_maximum=16,fix_mistral_regex=False,enable_thinking=True,
        truncated=False,server_context_verified=False)


def worker_init(evidence, source, snapshot):
    global EVIDENCE, SOURCE
    EVIDENCE = budget.readonly(Path(evidence)/'evidence.sqlite')
    SOURCE = budget.readonly(Path(source)/'packets.sqlite')
    budget.tokenizer_init(snapshot)


def article_packet(original, sidecar, articles):
    if (sidecar['source_packet_sha256'] != digest(original)
            or sidecar['original_generation_source_verified'] is not False
            or sidecar['review_verdicts_included'] is not False
            or sidecar['admission_authorized'] is not False):
        raise ValueError('Source binding/identity contract drift')
    candidate = original['candidate']
    for field in ('messages','language','target_message_index','provenance'):
        if sidecar[field] != candidate[field]:
            raise ValueError('Candidate changed: '+field)
    if sidecar['upstream_record'] != original['upstream_record']:
        raise ValueError('Upstream record changed')
    if len(articles) != len(sidecar['candidate_articles']) or len(articles)>3:
        raise ValueError('Evidence coverage mismatch')
    if any(a['language'] != candidate['language'] for a in articles):
        raise ValueError('Wrong article language')
    result = dict(original, candidate_articles=[{k:a[k] for k in adapter.ARTICLE_FIELDS} for a in articles],
        exact_generation_source_verified=False,admission_authorized=False,publication_allowed=False,
        retrieval_packet_sha256=digest(sidecar))
    result['audit_request'] = adapter.request(result)
    return result


def measure_one(key):
    raw, sha = EVIDENCE.execute('SELECT packet,sha256 FROM packets WHERE id=?',(key,)).fetchone()
    sidecar = json.loads(raw)
    if digest(sidecar) != sha:
        raise ValueError('Retrieval packet drift')
    original_raw, original_sha = SOURCE.execute('SELECT packet,sha256 FROM packets WHERE component=? AND id=?',
        (sidecar['component'],key)).fetchone()
    original = json.loads(original_raw)
    if digest(original) != original_sha:
        raise ValueError('Original packet drift')
    packet = article_packet(original,sidecar,retrieval.hydrate(EVIDENCE,sidecar))
    # Integrity/render failures abort preparation, never silently remove a row.
    measured = budget.measure_request(packet['audit_request'],budget.TOKENIZER,CONTEXT)
    measured['request_sha256'] = digest(packet['audit_request'])
    return key,json.dumps(packet,ensure_ascii=False),json.dumps(measured),len(packet['candidate_articles'])


def catalog_schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS catalog(id TEXT PRIMARY KEY,packet TEXT,prior_evidence TEXT,origin TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS budgets(id TEXT PRIMARY KEY,result TEXT,article_count INTEGER)')


def inventory(db):
    count = db.execute('SELECT count(*) FROM catalog').fetchone()[0]
    measured, oversized, maximum = db.execute("SELECT count(*),coalesce(sum(json_extract(result,'$.fits')=0),0),"
        "max(json_extract(result,'$.total_tokens')) FROM budgets").fetchone()
    if count != measured:
        raise ValueError('Catalog/budget mismatch')
    return dict(count=count,measured=measured,dispatchable=count-oversized,
        unresolved_context=oversized,max_total_tokens=maximum,
        article_count_histogram={str(n):c for n,c in db.execute('SELECT article_count,count(*) FROM budgets GROUP BY article_count')},
        gpu_requests=0,truncated=0)


def seal(root, config, stats, diagnostic):
    pins = dict(config['pins'])
    pins[str((root/'catalog.sqlite').resolve())] = file_hash(root/'catalog.sqlite')
    pins[str((root/'prepare-config.json').resolve())] = file_hash(root/'prepare-config.json')
    manifest = dict(config, pins=pins, **stats, diagnostic_only=diagnostic,
        calibration_required_before_bulk=not diagnostic,capacity_wave='baltic',
        consumer_kind='baltic_articles',max_attempts_per_stage=3,
        endpoints=[f'http://127.0.0.1:{n}/v1' for n in range(8800,8808)],
        no_hit_is_not_rejection=True,publication_allowed=False,admission_authorized=False)
    write_json(root/'manifest.json',manifest)
    write_json(root/'seal.json',dict(manifest_sha256=file_hash(root/'manifest.json')))
    write_json(root/'launch-handoff.template.json',dict(run_authorized=False,model=base.MODEL,
        manifest_sha256=file_hash(root/'manifest.json'),calibration_approval=None,capacity_reservation=None))
    return dict(root=str(root),manifest_sha256=file_hash(root/'manifest.json'),**stats)


def prepare(root, evidence, source, ready, workers=16):
    if type(workers) is not int or not 1<=workers<=16:
        raise ValueError('One to sixteen CPU workers required')
    root.mkdir(parents=True,exist_ok=True)
    with lock(root/'consumer.lock'):
        if (root/'manifest.json').exists():
            raise ValueError('Sealed root is immutable; choose new successor')
        config = inputs(evidence,source,ready)
        if (root/'prepare-config.json').exists():
            if load(root/'prepare-config.json') != config:
                raise ValueError('Resumable preparation pin drift')
        else:
            if any(p.name!='consumer.lock' for p in root.iterdir()):
                raise ValueError('Fresh root required')
            write_json(root/'prepare-config.json',config)
        with closing(sqlite3.connect(root/'catalog.sqlite')) as db, closing(budget.readonly(evidence/'evidence.sqlite')) as src:
            catalog_schema(db)
            completed={r[0] for r in db.execute('SELECT id FROM catalog')}
            keys=[r[0] for r in src.execute('SELECT id FROM packets ORDER BY language,id')]
            if len(keys)!=config['expected_count'] or not completed.issubset(keys):
                raise ValueError('Population mismatch')
            todo=[k for k in keys if k not in completed]
            with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),
                    initializer=worker_init,initargs=(str(evidence),str(source),config['snapshot'])) as pool:
                for offset in range(0,len(todo),512):
                    for key,raw,measured,narticles in pool.map(measure_one,todo[offset:offset+512],chunksize=4):
                        packet=json.loads(raw)
                        prior=dict(published_record=packet['candidate'],binding=packet['binding'],
                            published_record_sha256=packet['candidate_sha256'])
                        db.execute('INSERT INTO catalog VALUES(?,?,?,?)',
                            (key,raw,json.dumps(prior,ensure_ascii=False),str(evidence.resolve())))
                        db.execute('INSERT INTO budgets VALUES(?,?,?)',(key,measured,narticles))
                    db.commit()
                    stats=inventory(db)
                    write_json(root/'progress.json',dict(stats,remaining=config['expected_count']-stats['count'],time=time.time()))
            stats=inventory(db)
            if stats['count']!=config['expected_count'] or stats['article_count_histogram']!=config['expected_histogram']:
                raise ValueError('Full population/retrieval coverage mismatch')
        checked_pins(config['pins'])
        return seal(root,config,stats,False)


def diagnostic(root, full):
    manifest=common.verify(full)
    root.mkdir(parents=True,exist_ok=True)
    with lock(root/'consumer.lock'):
        if any(p.name!='consumer.lock' for p in root.iterdir()):
            raise ValueError('Fresh diagnostic successor required')
        config=dict(load(full/'prepare-config.json'))
        config['pins']=dict(config['pins'])
        for path in (full/'manifest.json',full/'seal.json',full/'catalog.sqlite'):
            config['pins'][str(path.resolve())]=file_hash(path)
        write_json(root/'prepare-config.json',config)
        with closing(budget.readonly(full/'catalog.sqlite')) as src,closing(sqlite3.connect(root/'catalog.sqlite')) as db:
            catalog_schema(db)
            for key in manifest['calibration_diagnostic_ids']:
                row=src.execute('SELECT * FROM catalog WHERE id=?',(key,)).fetchone()
                measured=src.execute('SELECT * FROM budgets WHERE id=?',(key,)).fetchone()
                if row is None or measured is None:raise ValueError('Missing diagnostic case')
                db.execute('INSERT INTO catalog VALUES(?,?,?,?)',row)
                db.execute('INSERT INTO budgets VALUES(?,?,?)',measured)
            db.commit();stats=inventory(db)
            if stats['count']!=20:raise ValueError('Diagnostic population mismatch')
        return seal(root,config,stats,True)


def engine():
    module=adapter.engine()
    original_database=module.database
    def database(root):
        db=original_database(root)
        db.execute("UPDATE jobs SET state='needs_review_context' WHERE state='pending_review' AND id IN "
            "(SELECT id FROM catalog.budgets WHERE json_extract(result,'$.fits')=0)")
        return db
    module.database=database
    return module


def check_calibration(manifest, approval):
    base.check_calibration(manifest,approval)
    if manifest['diagnostic_only']:return
    value=load(approval['calibration_approval'])
    diagnostic_manifest=common.verify(Path(value['diagnostic_root']))
    for field in ('schema','policy_sha256','evidence_sha256'):
        if diagnostic_manifest.get(field)!=manifest.get(field):
            raise ValueError('Calibration must cover article-aware policy/evidence')
    for module in (__file__,adapter.__file__):
        if diagnostic_manifest['pins'].get(str(Path(module).resolve()))!=file_hash(module):
            raise ValueError('Calibration adapter/code drift')


async def run(root, authorization, concurrency=4, profile=None):
    with lock(root/'consumer.lock'):
        manifest=common.verify(root);approval=load(authorization)
        if (manifest.get('schema')!=SCHEMA or approval.get('run_authorized') is not True
                or approval.get('manifest_sha256')!=file_hash(root/'manifest.json')
                or approval.get('model')!=base.MODEL):
            raise ValueError('Explicit article successor launch approval required')
        check_calibration(manifest,approval)
        receipt=capacity.capacity_limit(manifest,approval,concurrency,profile)
        with lock(capacity.RESERVATIONS/'baltic.lock'):
            write_json(root/'capacity-runtime.json',dict(receipt,time=time.time()))
            return await capacity.execute(engine(),root,authorization,concurrency)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','diagnostic','verify','run','calibration-report','retry-technical'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--evidence',type=Path,default=Path('data/dfm13/baltic/article-adapter-full-20261003-v2'))
    p.add_argument('--source',type=Path,default=Path('data/dfm13/baltic/qa31-full-packets-v1'))
    p.add_argument('--ready',type=Path,default=Path('data/dfm13/wave4/gemma31-download/ready.json'))
    p.add_argument('--full',type=Path)
    p.add_argument('--workers',type=int,default=16)
    p.add_argument('--authorization',type=Path)
    p.add_argument('--concurrency',type=int,default=4)
    p.add_argument('--capacity-profile',type=Path)
    p.add_argument('--allow-unknown',action='store_true')
    a=p.parse_args()
    if a.command=='prepare':result=prepare(a.root,a.evidence,a.source,a.ready,a.workers)
    elif a.command=='diagnostic':result=diagnostic(a.root,a.full)
    elif a.command=='verify':
        m=common.verify(a.root);result=dict(valid=True,count=m['count'],unresolved_context=m['unresolved_context'])
    elif a.command=='calibration-report':result=base.calibration_report(a.root)
    elif a.command=='retry-technical':result=engine().retry_technical(a.root,a.allow_unknown)
    else:
        if a.authorization is None:raise ValueError('Authorization required')
        result=asyncio.run(run(a.root,a.authorization,a.concurrency,a.capacity_profile))
    print(json.dumps(result))


if __name__=='__main__':main()
