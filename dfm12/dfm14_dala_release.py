"""Export and integrate the sixteen-language, eight-shard DFM14 DaLA audit."""
import argparse,gzip,json,os,sqlite3,subprocess,sys,time,hashlib,shutil
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from contextlib import ExitStack
import orjson
from .io import load,write_json,file_hash,digest,lock
from .dala_compact_finalize import CONTRACT,accepted,canonical,task_row,split_name,text_key,build_heldout,exclusion,readonly,pin

LANGUAGES={'tr':'Turkish','ru':'Russian','zh':'Chinese','ar':'Modern Standard Arabic','ga':'Irish','ko':'Korean','ja':'Japanese','gl':'Galician','eu':'Basque','cy':'Welsh','hi':'Hindi','he':'Hebrew','id':'Indonesian','vi':'Vietnamese','mt':'Maltese','mk':'Macedonian'}
SCOPES=('train_representative','validation_representative','validation_challenge','test_representative','test_challenge')
TASKS=('acceptability','correction')


def rows(path):
    with gzip.open(path,'rb') as stream:
        for line in stream:yield orjson.loads(line)


def partition_decisions(job):
    audit,root,item=job;audit=Path(audit);root=Path(root);index=item['index'];folder=root/'decisions'/str(index);marker=folder/'complete.json'
    if marker.exists():
        result=load(marker)
        if result['source']!=item:raise ValueError('Decision source drift')
        for p in result['files'].values():
            if file_hash(p['path'])!=p['sha256']:raise ValueError('Decision partition drift')
        return result
    if file_hash(item['path'])!=item['sha256']:raise ValueError('Merged decision drift')
    folder.mkdir(parents=True,exist_ok=True);counts=Counter();files={}
    with ExitStack() as stack:
        streams={lang:stack.enter_context(gzip.open(folder/(lang+'.jsonl.gz'),'wb',compresslevel=1)) for lang in LANGUAGES}
        for row in rows(item['path']):
            record=row['record'];lang=record['language']
            if row['id']!=record['id'] or canonical(record,lang,record['kind'])!=record or int(row['id'],16)%8!=index:raise ValueError('Canonical decision drift')
            streams[lang].write(orjson.dumps(dict(id=row['id'],kind=record['kind'],status=row['status'],result=row['result']))+b'\n');counts[lang]+=1
    if sum(counts.values())!=item['jobs']:raise ValueError('Merged decision count drift')
    for lang in LANGUAGES:files[lang]=dict(pin(folder/(lang+'.jsonl.gz')),rows=counts[lang])
    result=dict(source=item,files=files,rows=sum(counts.values()));write_json(marker,result);return result


def publication_row(value):
    # Stable HF schema across heterogeneous source/checker metadata.
    return {**{k:v for k,v in value.items() if k not in ('provenance','compact_audit')},
            'provenance_json':orjson.dumps(value['provenance']).decode(),
            'audit_json':orjson.dumps(value['compact_audit']).decode()}


class Shards:
    def __init__(self,root,limit=50000):self.root=root;self.limit=limit;self.files=[];self.handles={};self.counts=Counter();self.current={}
    def emit(self,task,scope,row):
        key=task,scope;n=self.counts[key]
        if n%self.limit==0:
            if key in self.handles:self.handles[key].close()
            relative=f'data/{task}/{scope}-{n//self.limit:05d}.jsonl.gz';path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True)
            self.handles[key]=gzip.open(path,'wb',compresslevel=1);item=dict(relative=relative,path=str(path),task=task,scope=scope,rows=0);self.files.append(item);self.current[key]=item
        self.handles[key].write(orjson.dumps(row)+b'\n');self.counts[key]+=1;self.current[key]['rows']+=1
    def close(self):
        for f in self.handles.values():f.close()
        for f in self.files:f['sha256']=file_hash(f['path']);f['bytes']=Path(f['path']).stat().st_size


def release_conflict(db,row,kind):
    scope=split_name(row);values=[('text',text_key(row[k])) for k in ('original','corrupted') if k in row]
    values += [('document',row[k]) for k in ('document_id','document_sha256') if row.get(k)]
    for category,key in values:
        old=db.execute('SELECT scope FROM release_scopes WHERE kind=? AND key=?',(category,key)).fetchone()
        if old and old[0]!=scope:return 'release_split_view_conflict'
    return None


def export_language(job):
    root,language=Path(job[0]),job[1];plan=load(root/'plan.json');group=root/'groups'/language;group.mkdir(parents=True,exist_ok=True)
    package=Path(plan['packages_root'])/('dfm14-dala-v2-'+language+'-compact');marker=group/'export.json'
    if marker.exists():
        result=load(marker)
        for item in result['files']:
            if file_hash(item['path'])!=item['sha256']:raise ValueError('Export drift')
        return result
    stage=package.with_name(package.name+'.building')
    if stage.exists():raise ValueError('Partial language export requires inspected recovery: '+str(stage))
    stage.mkdir(parents=True);sources=[s for s in plan['sources'] if s['language']==language];inventories=[];profiles=[];prior=None;producer_priors={}
    for source in sources:
        p=Path(source['path']).parent.parent/'inventory.json'
        if load(Path(source['path']).parent/'identity.json')['inventory_sha256']!=file_hash(p):raise ValueError('Producer inventory identity changed')
        inv=load(p);entry=next(e for e in inv['languages'] if e['language']==language)
        if file_hash(source['receipt'])!=source['receipt_sha256'] or not load(source['receipt'])['passed']:raise ValueError('Source mechanical receipt changed')
        if file_hash(entry['prior_release']['path'])!=entry['prior_release']['sha256']:raise ValueError('Prior index changed')
        if entry['prior_release']['prior_release_policy']!='none_first_release_v2' or any(entry['prior_release']['counts'].values()):raise ValueError('Unexpected inherited language release')
        candidate=entry['prior_release']
        if candidate['path'] not in producer_priors:
            with readonly(candidate['path']) as check:
                actual={t:check.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('pairs','clean','texts','documents')}
            producer_priors[candidate['path']]=dict(candidate,actual_counts=actual)
            # Additive indexes include parents from THIS campaign, not prior publications.
            if not any(actual.values()):prior=candidate
        profiles.append(entry['profile']['prompts']);inventories.append(pin(p))
    if any(p!=profiles[0] for p in profiles):raise ValueError('Mixed prompt contracts')
    if prior is None:raise ValueError('No verified empty first-release baseline prior index')
    prompts=profiles[0];decisions={};audit_counts=Counter()
    for part in plan['decision_parts']:
        item=part['files'][language]
        if file_hash(item['path'])!=item['sha256']:raise ValueError('Decision partition changed')
        for row in rows(item['path']):
            if row['id'] in decisions:raise ValueError('Duplicate audit ID')
            decisions[row['id']]=row
    held,held_count=build_heldout(sources,':memory:');held.execute('PRAGMA cache_size=-524288');held.execute('CREATE TABLE release_scopes(kind TEXT,key TEXT,scope TEXT,PRIMARY KEY(kind,key)) WITHOUT ROWID')
    prior_db=readonly(prior['path']);prior_db.execute('BEGIN');counts=Counter();family=Counter();licenses=Counter();source_counts=Counter();writer=Shards(stage);seen_ids=set();validation_count=0
    exclusions=gzip.open(group/'exclusions.jsonl.gz','wb',compresslevel=1)
    try:
        for source in sorted(sources,key=lambda s:(s['kind']!='clean_control',s['component'])):
            n=0
            for ordinal,row in enumerate(rows(source['path'])):
                n+=1;record=canonical(row,language,source['kind']);key=record['id'];saved=decisions.get(key)
                if saved is None or saved['kind']!=source['kind']:raise ValueError('Source not covered by audit')
                if key in seen_ids:raise ValueError('Unexpected duplicate canonical input')
                seen_ids.add(key);result=saved['result'];audit_counts[saved['status'] if saved['status']!='done' else result['decision']]+=1
                reason=None
                if not accepted(record,result,saved['status']):reason='audit_'+(saved['status'] if saved['status']!='done' else result.get('decision','invalid'))
                if reason is None:reason=release_conflict(held,row,source['kind'])
                if reason is None:reason=exclusion(row,source['kind'],prior_db,held)
                if reason:
                    counts['excluded:'+reason]+=1;exclusions.write(orjson.dumps(dict(id=key,source_component=source['component'],ordinal=ordinal,reason=reason,split=row['split'],view=row['view']))+b'\n');continue
                scope=split_name(row);counts['accepted:'+scope+':'+source['kind']]+=1
                values=[('text',text_key(row[k]),scope) for k in ('original','corrupted') if k in row]
                values += [('document',row[k],scope) for k in ('document_id','document_sha256') if row.get(k)]
                held.executemany('INSERT OR IGNORE INTO release_scopes VALUES(?,?,?)',values)
                evidence=dict(contract=CONTRACT,decision=result,audit_merge_sha256=plan['audit_merge']['sha256'],source_component=source['component'],ordinal=ordinal,source_row_sha256=digest(row),producer_v2_audit_equivalent=False)
                for task in TASKS:writer.emit(task,scope,publication_row(task_row(row,record,task,prompts,evidence)))
                for edit in row.get('edits',[]):family[scope+':'+str(edit.get('taxonomy',{}).get('family',edit.get('rule_id')))]+=1
                licenses[row.get('license','unspecified')]+=1;source_counts[row.get('source_dataset','unspecified')]+=1
                if n%4096==0:held.commit()
            if n!=source['rows']:raise ValueError('Source row count changed')
        if len(seen_ids)!=len(decisions):raise ValueError('Unused audit decisions')
    finally:
        writer.close();exclusions.close();held.commit()
        with sqlite3.connect(group/'heldout.sqlite') as snapshot:held.backup(snapshot)
        held.close();prior_db.close()
    # Independent second pass validates every chat row against the audit and original provenance.
    checked=Counter();missing=set(SCOPES)
    for item in writer.files:
        n=0;missing.discard(item['scope'])
        for row in rows(item['path']):
            source=orjson.loads(row['provenance_json']);kind='clean_control' if row['variant']=='clean' else 'pair';record=canonical(source,language,kind);saved=decisions[record['id']];ev=orjson.loads(row['audit_json'])
            if not accepted(record,saved['result'],saved['status']) or ev['decision']!=saved['result'] or ev['source_row_sha256']!=digest(source):raise ValueError('Invalid exported audit binding')
            if row!=publication_row(task_row(source,record,item['task'],prompts,ev)) or split_name(source)!=item['scope']:raise ValueError('Chat/split reconstruction differs')
            n+=1
        if n!=item['rows']:raise ValueError('Export row count differs')
        checked[item['task']+':'+item['scope']]+=n
    if missing:raise ValueError('Missing evaluation scopes: '+str(missing))
    del decisions
    result=dict(status='accepted_subset_exported',language=language,contract=CONTRACT,counts=dict(counts),audit_counts=dict(audit_counts),task_rows=dict(checked),families=dict(family),licenses=dict(licenses),source_counts=dict(source_counts),source_rows=len(seen_ids),raw_heldout_rows=held_count,raw_heldout_sources=sources,producer_inventories=inventories,prior_index=prior,producer_prior_indexes=list(producer_priors.values()),audit_merge=plan['audit_merge'],prompts=prompts,producer_v2_audit_equivalent=False,human_validation=False,balanced_producer_release=False,tokenizer_inputs_train_only=True,screening='Exact NFC/whitespace-normalized text and document protection across all raw DFM14 runs of this language, including rejected heldouts; released split/view isolation and clean/noisy input deduplication. Not inherited-corpus-wide or semantic decontamination.',validation=dict(status='passed',exact_chat_recreation=True,accepted_only=True,rows=sum(checked.values())),files=writer.files)
    metadata=stage/'metadata';metadata.mkdir();write_json(metadata/'release.json',{k:v for k,v in result.items() if k!='files'});write_json(metadata/'audit-contract.json',dict(contract=CONTRACT,fields=list(__import__('dfm12.dala_batch_review',fromlist=['FIELDS']).FIELDS),prompt=__import__('dfm12.dala_batch_review',fromlist=['PROMPT']).PROMPT,model=plan['model'],human_validation=False,producer_v2_audit_equivalent=False))
    import yaml
    front=dict(language=[language],license='other',license_name='source-specific',license_link='LICENSE.md',task_categories=['text-classification','text-generation'],configs=[dict(config_name=t,data_files=[dict(split='train' if s=='train_representative' else s,path=f'data/{t}/{s}-*.jsonl.gz') for s in SCOPES]) for t in TASKS])
    table='\n'.join(f'| {s} | {checked["acceptability:"+s]:,} | {checked["correction:"+s]:,} |' for s in SCOPES)
    (stage/'README.md').write_text('---\n'+yaml.safe_dump(front,sort_keys=False)+'---\n'+f'''# DaLA v2 — {LANGUAGES[language]} — DFM14 compact audit subset

One language dataset combining all selected base and additive runs. Two task views share the same accepted source records; they are not independent observations. Each independently audited clean control contributes one correct input per task; each passing pair contributes one corrupted input per task. No extra clean controls are synthesized.

| Split/view | Acceptability rows | Correction rows |
| --- | ---: | ---: |
{table}

Only completed, correctly formed automated audit passes with a nonempty rationale are included. Flagged, uncertain, failed and otherwise invalid decisions are excluded. Automated Gemma judgments are fallible, not native-speaker validation, and not the producer's isolated-edit certification. Audit filtering changes family counts and class balance; this is not a claim of balanced producer release or gold evaluation data.

Only `messages` are model input, with `target_message_index=1`. Other fields expose labels, full original source text, edits, provenance and audit evidence. Preserve the original validation/test representative/challenge views; only train is integrated into DFM14. Language-specific prompts are preserved.

Source text, titles, URLs, revisions, licenses and transformation spans remain in each row's lossless `provenance_json` (parse with `json.loads`); audit decisions are in `audit_json`. These JSON strings give every shard the same portable Hugging Face schema. Publisher endorsement is not implied. No blanket relicensing: retain applicable attribution/share-alike and source-specific terms in LICENSE.md and row metadata. See metadata/release.json for measured composition, exact-overlap screening and its limits. Both task views reproduce the same source excerpts.
''')
    (stage/'LICENSE.md').write_text('# Source-specific terms\n\nThis package does not replace underlying source licenses. Source excerpts and altered grammar/spelling variants retain per-row source attribution, revision and license metadata. Retain original URLs/titles, applicable attribution and share-alike notices when redistributing. No publisher endorsement is implied.\n\n'+''.join(f'- {name}: {count:,} retained source records\n' for name,count in sorted(licenses.items())))
    (stage/'.gitattributes').write_text('*.gz filter=lfs diff=lfs merge=lfs -text\n')
    files={str(p.relative_to(stage)):dict(sha256=file_hash(p),bytes=p.stat().st_size) for p in sorted(stage.rglob('*')) if p.is_file()}
    package_proof=dict(schema='dfm14-dala-hf-v1',repo_id='schneiderkamplab/'+package.name,language=language,files=files,counts=dict(checked),validation=result['validation'],audit_merge=plan['audit_merge'],one_dataset_per_language=True,uploaded=False)
    write_json(stage/'manifest.json',package_proof);stage.rename(package)
    for item in result['files']:item['path']=str(package/item['relative'])
    result.update(package=str(package),package_manifest=pin(package/'manifest.json'),heldout_index=pin(group/'heldout.sqlite'))
    write_json(marker,result);print('EXPORTED',language,dict(counts),flush=True);return result


def integrate_language(job):
    root,language=Path(job[0]),job[1];plan=load(root/'plan.json');group=root/'groups'/language;export=load(group/'export.json');marker=group/'integration.json'
    if marker.exists():return load(marker)
    import numpy as np
    components=[]
    for task in TASKS:
        train=group/'train'/task;train.mkdir(parents=True,exist_ok=True);expected=0
        for item in export['files']:
            if item['task']==task and item['scope']=='train_representative':
                target=train/Path(item['path']).name
                if not target.exists():os.link(item['path'],target)
                if file_hash(target)!=item['sha256']:raise ValueError('Train export changed')
                expected+=item['rows']
        output=group/'tokenized'/task
        with (group/(task+'-tokenization.log')).open('a') as log:
            subprocess.run([sys.executable,str(Path(plan['hrm_root'])/'scripts/tokenize_chat_template.py'),str(train),'--output-dir',str(output),'--tokenizer-path',plan['tokenizer']['path'],'--chat-template',plan['template']['path'],'--workers','8','--max-seq-len','4096','--preserve-first-user'],cwd=plan['hrm_root'],check=True,stdout=log,stderr=subprocess.STDOUT)
        completion=load(output/'completion.json')
        if completion['rows']!=expected or completion['skipped_rows_this_run']:raise ValueError('Tokenization dropped rows')
        count=tokens=0;arrays={}
        for part in sorted(output.iterdir()):
            if not part.is_dir():continue
            il=np.load(part/'inst_len.npy',mmap_mode='r');rl=np.load(part/'resp_len.npy',mmap_mode='r');n=int(il.sum())+int(rl.sum())
            if len(il)!=len(rl) or np.any(rl<=0) or np.any(il+rl>4096) or len(np.load(part/'tokens.npy',mmap_mode='r'))!=n:raise ValueError('Token array mismatch')
            count+=len(il);tokens+=n;arrays.update({str(p):file_hash(p) for p in part.glob('*.npy')})
        if count!=expected:raise ValueError('Tokenized row count mismatch')
        components.append(dict(name=f'dfm14_dala_v2_compact_{language}_{task}',language=language,task=task,status='accepted_local_tokenized',split='train',repeat=1,rows=count,tokens=tokens,tokenized_path=str(output),array_pins=arrays,tokenizer=plan['tokenizer'],template=plan['template'],export_receipt=pin(group/'export.json'),audit_contract=CONTRACT,producer_v2_audit_equivalent=False,train_files=[x for x in export['files'] if x['task']==task and x['scope']=='train_representative'],hf_repo_id='schneiderkamplab/'+Path(export['package']).name))
    result=dict(status='complete_train_only',language=language,components=components,export=pin(group/'export.json'),contract=CONTRACT);write_json(marker,result);print('INTEGRATED',language,sum(c['tokens'] for c in components),flush=True);return result


def run(a):
    root=a.output.resolve();root.mkdir(parents=True,exist_ok=True);audit=a.audit.resolve();hrm=Path(__file__).resolve().parents[1]
    os.environ.update(CUDA_VISIBLE_DEVICES='',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    if not (root/'plan.json').exists():
        proof=load(audit/'merged/complete.json');prepared=load(audit/'prepared.json');inputs=load(audit/'inputs.json')
        if not proof['verified'] or file_hash(audit/'inputs.json')!=prepared['inputs_sha256'] or proof['canonical_jobs']!=inputs['rows']:raise ValueError('Audit merge not verified')
        if set(s['language'] for s in inputs['sources'])!=set(LANGUAGES):raise ValueError('Language scope mismatch')
        with ProcessPoolExecutor(max_workers=8) as pool:parts=list(pool.map(partition_decisions,[(str(audit),str(root),item) for item in proof['shards']]))
        config=load(audit/'shard-0/config.json')
        plan=dict(schema='dfm14-dala-release-v1',authorized='User: export, integrate and upload to HF',audit_merge=pin(audit/'merged/complete.json'),audit_inputs=pin(audit/'inputs.json'),sources=inputs['sources'],decision_parts=parts,packages_root=str(a.packages.resolve()),hrm_root=str(hrm),tokenizer=pin(a.tokenizer.resolve()),template=pin(a.template.resolve()),model=config['model'],code=pin(__file__),languages=LANGUAGES,gpu_actions=False)
        write_json(root/'plan.json',plan)
    else:
        plan=load(root/'plan.json')
        for key in ('audit_merge','audit_inputs','tokenizer','template'):
            if file_hash(plan[key]['path'])!=plan[key]['sha256']:raise ValueError('Release input drift: '+key)
    a.packages.mkdir(parents=True,exist_ok=True);exports=[];integrations=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(export_language,(str(root),lang)):('export',lang) for lang in LANGUAGES}
        while futures:
            future=next(as_completed(futures));kind,lang=futures.pop(future)
            try:result=future.result()
            except Exception as error:
                write_json(root/'failure.json',dict(stage=kind,language=lang,error=repr(error),at=time.time()));print('FAILED',kind,lang,repr(error),flush=True);raise
            if kind=='export':
                exports.append(result)
                if a.tokenize:futures[pool.submit(integrate_language,(str(root),lang))]=('integrate',lang)
            else:integrations.append(result)
            write_json(root/'progress.json',dict(exports=len(exports),integrations=len(integrations),languages=len(LANGUAGES),at=time.time()))
    write_json(root/'packages.json',dict(packages=[dict(language=x['language'],path=x['package'],manifest=x['package_manifest']) for x in exports],validated=True))
    if a.tokenize:
        registry=dict(schema=CONTRACT,version='dfm14',additions=[c for x in integrations for c in x['components']],source_plan=pin(root/'plan.json'),train_only=True,human_validation=False)
        write_json(root/'registry.json',registry);write_json(hrm/'data/dfm14/local-audited-dala-additions.json',dict(registry,registry=pin(root/'registry.json')))
    write_json(root/'complete.json',dict(success=True,exports=len(exports),integrations=len(integrations),registry=pin(root/'registry.json') if a.tokenize else None,packages=pin(root/'packages.json'),at=time.time(),gpu_actions=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--packages',type=Path,required=True);p.add_argument('--workers',type=int,default=8);p.add_argument('--tokenize',action='store_true');p.add_argument('--tokenizer',type=Path,default=Path('/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json'));p.add_argument('--template',type=Path,default=Path('/work/dfm/HRM-Text/data_io/chat_templates/gemma4_native_chat.jinja'));a=p.parse_args()
    with lock(a.output/'.release.lock'):run(a)
