"""Local-only fixed-language export from read-only accepted-ledger snapshots."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from .io import digest, file_hash, load, write_json
from . import multilingual_quarter as quarter

LANGUAGES=('de','el','es','fi','fr','it','nb','nl','nn','pl','ro','sv','uk')
FINAL_LANGUAGES=('ca','cs','et','fo','is','pt_pt')
ALL_LANGUAGES=LANGUAGES+FINAL_LANGUAGES
PRIORITY_LANGUAGES={'nb','nn','ca','et','fo','is'}
ROOTS=(Path('data/dfm12/multilingual-quarter-native-20260927'),
       Path('data/dfm12/european-synthetic-tenth-20260928'))
FAMILIES={'multiturn','grounded-instruct','openhermes','summary-rewrite','math-code','tool-dialogue'}


def read_json(path,evidence):
    path=Path(path);raw=path.read_bytes()
    evidence[str(path)]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def training_record(candidate,campaign,fingerprint):
    if digest({k:candidate[k] for k in ('messages','tools')})!=fingerprint:
        raise ValueError('Candidate fingerprint mismatch')
    # Never use the generic text-only export adapter: native calls must survive.
    return dict(id=quarter.candidate_id(campaign,fingerprint),language=candidate['language'],
                family=candidate['family'],messages=copy.deepcopy(candidate['messages']),
                tools=copy.deepcopy(candidate['tools']))


def language_target(language):
    if language not in ALL_LANGUAGES:raise ValueError('Unsupported language: '+language)
    return 70000 if language in PRIORITY_LANGUAGES else 35000


def cohort(languages):
    languages=tuple(languages)
    if not languages or len(set(languages))!=len(languages):raise ValueError('Empty or duplicate languages')
    return languages,sum(language_target(language) for language in languages)


def snapshot(output,roots=ROOTS,languages=LANGUAGES):
    languages,total=cohort(languages)
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    (output/'private').mkdir(parents=True)
    dest=sqlite3.connect(output/'private/accepted.sqlite')
    dest.executescript('''CREATE TABLE jobs(id TEXT PRIMARY KEY,language TEXT,family TEXT,role TEXT,job TEXT);
      CREATE TABLE imports(id TEXT PRIMARY KEY,plan TEXT);''')
    sources={};counts=Counter();pilot_specs={};smoke={}
    try:
        for role,root in zip(('original','european'),roots):
            root=Path(root).resolve();manifest=load(root/'manifest.json')
            seal=load(root/'seal.json')
            if seal['manifest_sha256']!=file_hash(root/'manifest.json'):raise ValueError('Source manifest drift')
            source=dict(root=str(root),manifest=manifest,manifest_sha256=file_hash(root/'manifest.json'),groups=[])
            db=sqlite3.connect((root/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)
            db.row_factory=sqlite3.Row;db.execute('BEGIN')
            try:
                groups=[dict(g) for g in db.execute('SELECT * FROM groups') if g['language'] in languages]
                selected=sorted({g['language'] for g in groups})
                for lang in selected:
                    subset=[g for g in groups if g['language']==lang]
                    if {g['family'] for g in subset}!=FAMILIES or any(g['accepted']!=g['target'] or g['active'] for g in subset):
                        raise ValueError('Incomplete selected language: '+lang)
                    if sum(g['accepted'] for g in subset)!=language_target(lang):
                        raise ValueError('Unexpected target: '+lang)
                source['groups']=groups
                for meta in db.execute("SELECT value FROM metadata WHERE key LIKE 'first-pilot-quarter-import-v1:%'"):
                    receipt=json.loads(meta[0]);path=Path(receipt['journal'])
                    if receipt['state']!='committed' or file_hash(path)!=receipt['journal_sha256']:
                        raise ValueError('Import journal drift')
                    for plan in load(path)['plans']:
                        dest.execute('INSERT INTO imports VALUES (?,?)',(plan['id'],json.dumps(plan,ensure_ascii=False)))
                marks=','.join('?' for _ in selected)
                query=f"SELECT j.*,f.owner AS fingerprint_owner FROM jobs j LEFT JOIN fingerprints f ON j.fingerprint=f.fingerprint WHERE j.status='accepted' AND j.language IN ({marks})"
                for row in db.execute(query,selected):
                    job=dict(row)
                    if job['fingerprint_owner']!=job['id']:raise ValueError('Fingerprint ownership mismatch')
                    if job['origin']=='pilot' and not job['spec_json']:
                        folder=job['workdir']
                        if folder not in pilot_specs:
                            path=Path(folder)/'specifications.json'
                            pilot_specs[folder]={quarter.pilot.slot_key(s):s for s in load(path)}
                            source.setdefault('pilot_spec_pins',{})[str(path)]=file_hash(path)
                        job['spec_json']=json.dumps(pilot_specs[folder][job['id']],ensure_ascii=False)
                    dest.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(job['id'],job['language'],job['family'],role,json.dumps(job,ensure_ascii=False)))
                    smoke.setdefault((role,job['origin'],job['family']),dict(role=role,job=job))
                    counts[(job['language'],job['family'])]+=1
                    if sum(counts.values())%5000==0:
                        dest.commit();print('SNAPSHOT',sum(counts.values()),flush=True)
                for group in groups:
                    if counts[(group['language'],group['family'])]!=group['accepted']:raise ValueError('Ledger/group count mismatch')
            finally:db.rollback();db.close()
            if file_hash(root/'manifest.json')!=source['manifest_sha256']:raise ValueError('Source changed during snapshot')
            sources[role]=source
        if sum(counts.values())!=total or {k[0] for k in counts}!=set(languages):raise ValueError('Fixed cohort mismatch')
        dest.execute('CREATE INDEX language_rows ON jobs(language,family,id)');dest.commit()
    finally:dest.close()
    write_json(output/'private/sources.json',sources)
    write_json(output/'private/smoke.json',list(smoke.values()))
    write_json(output/'snapshot.json',dict(languages=languages,rows=total,time=time.time(),
        sqlite_sha256=file_hash(output/'private/accepted.sqlite'),sources=sources,
        controller_lock_acquired=False,live_databases_read_only=True))


def validate_job(job,source,db,controller,adapters):
    import jsonschema
    from . import multilingual_first_pilot_reaudit as reaudit
    review,generation=adapters;v6=controller.v6
    evidence={};key=job['id'];folder=Path(job['workdir'])
    outcome=json.loads(job['outcome_json'])
    if job['status']!='accepted' or outcome.get('terminal') is not True or outcome.get('status')!='valid' or outcome.get('effective_keep') is not True:
        raise ValueError('Not an accepted terminal row')
    if outcome['id']!=key or outcome['fingerprint']!=job['fingerprint'] or read_json(folder/'outcomes'/f'{key}.json',evidence)!=outcome:
        raise ValueError('Outcome identity mismatch')
    if job['origin']=='first-pilot-reaudit':
        provenance=outcome['import_provenance'];plan_row=db.execute('SELECT plan FROM imports WHERE id=?',(key,)).fetchone()
        if not plan_row:raise ValueError('Missing committed import plan')
        plan=json.loads(plan_row[0])
        if plan['outcome']!=outcome or plan['fingerprint']!=job['fingerprint'] or plan['workdir']!=job['workdir']:
            raise ValueError('Import plan mismatch')
        for path,sha in provenance['evidence_pins'].items():
            if file_hash(path)!=sha:raise ValueError('Re-audit evidence drift')
        evidence.update(provenance['evidence_pins'])
        audit_key=provenance['audit_key'];audit_dir=reaudit.directory(provenance['audit_root'],audit_key)
        candidate=read_json(audit_dir/'candidates'/f'{audit_key}.json',evidence)
        if evidence[str(audit_dir/'candidates'/f'{audit_key}.json')]!=provenance['source_identity']['candidate_sha256']:
            raise ValueError('Imported candidate hash mismatch')
        record=reaudit.review_record(candidate)
        if not all(c['passed'] for c in reaudit.identifier_grounding(candidate)):raise ValueError('Imported tool grounding failed')
        state=read_json(audit_dir/'stages'/f'{audit_key}-review.json',evidence)
        request=read_json(audit_dir/'requests'/f'{audit_key}-review.json',evidence)
        spec=None
    else:
        if job['origin'] not in ('pilot','production'):raise ValueError('Unknown origin')
        spec=json.loads(job['spec_json'])
        if digest(spec)!=outcome['spec_sha256'] or (spec['language_code'],spec['family'],spec['slot'])!=(job['language'],job['family'],job['slot']):
            raise ValueError('Specification mismatch')
        candidate=read_json(folder/'candidates'/f'{key}.json',evidence)
        if any(candidate['provenance'].get(k)!=v for k,v in spec.items()):raise ValueError('Candidate source provenance drift')
        generated=read_json(folder/'stages'/f'{key}-generate.json',evidence)
        if generated.get('status')!='complete' or generated.get('raw',{}).get('finish_reason')!='stop' or v6.strict_json(generated['raw']['content'])!=generated['output']:
            raise ValueError('Incomplete generation evidence')
        if digest(v6.generation_assemble(spec,generated['output'],generation))!=digest(candidate):
            raise ValueError('Generation assembly mismatch')
        record=v6.audit_record(candidate)
        state=read_json(folder/'stages'/f'{key}-review.json',evidence)
        request=read_json(folder/'requests'/f'{key}-review.json',evidence)
    if candidate['language']!=job['language'] or candidate['family']!=job['family']:raise ValueError('Candidate group mismatch')
    row=training_record(candidate,source['manifest']['campaign'],job['fingerprint'])
    accepted_path=folder/'accepted'/f'{key}.json'
    if job['origin']!='pilot' or accepted_path.exists():
        materialized=read_json(accepted_path,evidence)
        if materialized!=dict(candidate,id=row['id']):raise ValueError('Materialized record mismatch')
    if state.get('status')!='complete' or state.get('raw',{}).get('finish_reason')!='stop' or v6.strict_json(state['raw']['content'])!=state['output']:
        raise ValueError('Incomplete independent review')
    if state.get('request_sha256')!=digest(request['request']):raise ValueError('Review request hash mismatch')
    expected=v6.review_request(record,review);expected.update(temperature=0,frequency_penalty=.5)
    expected,schema=v6.compact_request(expected)
    if request['request']!=expected or request['schema']!=schema:raise ValueError('Review not bound to candidate')
    jsonschema.Draft202012Validator(schema).validate(state['output'])
    decision=v6.review_result(state['output'],record,review)
    if not decision['effective_keep']:raise ValueError('Saved audit fails existing gates')
    receipt=dict(id=row['id'],job_id=key,origin=job['origin'],fingerprint=job['fingerprint'],
        training_row_sha256=digest(row),provenance=candidate.get('provenance'),outcome=outcome,
        source_spec_sha256=digest(spec) if spec else None,evidence_pins=evidence,
        audit=state['output'],audit_raw=state['raw'],audit_request_sha256=state['request_sha256'],
        deterministic_checks=decision['deterministic_checks'])
    return row,receipt


def export_language(output,language):
    from . import european_synthetic_campaign
    output=Path(output);sources=load(output/'private/sources.json')
    db=sqlite3.connect((output/'private/accepted.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    controllers={'original':quarter,'european':european_synthetic_campaign.isolated_controller()}
    adapters={k:v.v6.adapters() for k,v in controllers.items()}
    name=f'dfm12-multilingual-synthetic-{language}';folder=output/name
    (folder/'data').mkdir(parents=True);(folder/'metadata').mkdir()
    handles={};counts=Counter();origins=Counter();seen=set();ids=set()
    try:
        for family in sorted(FAMILIES):
            handles[family]=(gzip.open(folder/'data'/f'train-{family}.jsonl.gz','wt',encoding='utf-8',compresslevel=1),
                             gzip.open(folder/'metadata'/f'audits-{family}.jsonl.gz','wt',encoding='utf-8',compresslevel=1))
        for role,encoded in db.execute('SELECT role,job FROM jobs WHERE language=? ORDER BY family,id',(language,)):
            job=json.loads(encoded);row,receipt=validate_job(job,sources[role],db,controllers[role],adapters[role])
            if row['id'] in ids or job['fingerprint'] in seen:raise ValueError('Duplicate accepted conversation')
            ids.add(row['id']);seen.add(job['fingerprint'])
            a,b=handles[job['family']]
            a.write(json.dumps(row,ensure_ascii=False)+'\n');b.write(json.dumps(receipt,ensure_ascii=False)+'\n')
            counts[job['family']]+=1;origins[job['origin']]+=1
            if sum(counts.values())%1000==0:
                write_json(output/'progress'/f'{language}.json',dict(language=language,rows=sum(counts.values()),time=time.time()))
        expected=language_target(language)
        if sum(counts.values())!=expected:raise ValueError('Export row count mismatch')
    finally:
        for pair in handles.values():
            for handle in pair:handle.close()
        db.close()
    manifest=dict(schema='dfm12-multilingual-completed-export-v1',language=language,rows=sum(counts.values()),
        families=dict(counts),origins=dict(origins),local_only=True,upload_authorized=False,
        validation='ledger/spec/fingerprint/materialization; raw independent review and unchanged CPU gates',
        native_tools_preserved=True,snapshot_sha256=file_hash(output/'snapshot.json'),
        files={str(p.relative_to(folder)):dict(sha256=file_hash(p),bytes=p.stat().st_size) for p in folder.rglob('*') if p.is_file()})
    write_json(folder/'metadata/manifest.json',manifest)
    (folder/'README.md').write_text('---\nlanguage:\n- '+language+'\ntask_categories:\n- text-generation\nconfigs:\n- config_name: default\n  data_files:\n  - split: train\n    path: data/train-*.jsonl.gz\n---\n# '+name+'\n\n'+str(manifest['rows'])+' accepted conversations across six families. Local-only export; no upload authorized.\n\nNative messages, tool calls, arguments, call IDs and top-level tools are unchanged. Only data/ is training input; audit decisions, source provenance and evidence hashes are in metadata/. Automated review is not human/native-speaker certification. Original source attribution and rights follow retained provenance; no blanket relicensing is asserted.\n')
    manifest['bytes']=sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
    print('EXPORTED',language,manifest['rows'],manifest['bytes'],flush=True)
    return dict(name=name,language=language,rows=manifest['rows'],bytes=manifest['bytes'],families=dict(counts),origins=dict(origins))


def verify_snapshot(output,languages=LANGUAGES):
    languages,total=cohort(languages)
    output=Path(output);receipt=load(output/'snapshot.json')
    if load(output/'private/sources.json')!=receipt['sources']:
        raise ValueError('Snapshot sources mismatch')
    if file_hash(output/'private/accepted.sqlite')!=receipt['sqlite_sha256']:
        raise ValueError('Snapshot database hash mismatch')
    if receipt['rows']!=total or set(receipt['languages'])!=set(languages):
        raise ValueError('Snapshot cohort mismatch')
    write_json(output/'snapshot-verification.json',dict(time=time.time(),sqlite_sha256=receipt['sqlite_sha256'],
        snapshot_sha256=file_hash(output/'snapshot.json'),sources_equal=True))


def archive_partial(output,languages=LANGUAGES):
    output=Path(output);archive=output/'interrupted'/str(time.time_ns())
    archive.mkdir(parents=True)
    for name in [*(f'dfm12-multilingual-synthetic-{l}' for l in languages),
                 'progress','manifest.json','completion.json','smoke-receipt.json']:
        path=output/name
        if path.exists():path.rename(archive/name)


def run(output,workers=8,resume_snapshot=False,languages=LANGUAGES):
    languages,total=cohort(languages)
    if not 1<=workers<=8:raise ValueError('Maximum eight CPU workers')
    output=Path(output)
    if not resume_snapshot:snapshot(output,languages=languages)
    # Hash the large immutable database once in the parent, before any workers.
    verify_snapshot(output,languages)
    if resume_snapshot:archive_partial(output,languages)
    from . import european_synthetic_campaign
    sources=load(output/'private/sources.json')
    controllers={'original':quarter,'european':european_synthetic_campaign.isolated_controller()}
    adapters={role:c.v6.adapters() for role,c in controllers.items()}
    with sqlite3.connect(output/'private/accepted.sqlite') as db:
        for sample in load(output/'private/smoke.json'):
            role=sample['role'];job=sample['job']
            validate_job(job,sources[role],db,controllers[role],adapters[role])
            print('SMOKE',role,job['origin'],job['family'],'PASS',flush=True)
    write_json(output/'smoke-receipt.json',dict(passed=len(load(output/'private/smoke.json')),time=time.time()))
    packages=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(export_language,str(output),lang) for lang in sorted(languages,key=lambda l:l not in PRIORITY_LANGUAGES)]
        for future in as_completed(futures):packages.append(future.result())
    write_json(output/'manifest.json',dict(packages=sorted(packages,key=lambda p:p['language']),rows=sum(p['rows'] for p in packages),
        bytes=sum(p['bytes'] for p in packages),languages=languages,local_only=True,upload_performed=False,workers=workers))
    write_json(output/'completion.json',dict(completed=time.time(),rows=total,packages=len(languages),bytes=sum(p['bytes'] for p in packages),upload_performed=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--resume-snapshot',action='store_true')
    parser.add_argument('--languages',nargs='+',choices=ALL_LANGUAGES,default=LANGUAGES)
    args=parser.parse_args();run(args.output,args.workers,args.resume_snapshot,args.languages)
