"""CPU-only, source-bound replay inventory for every pending3150K eval task."""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'eval_scheduler'))
from dfm12.io import atomic,digest,file_hash,load,write_json
from eval_scheduler.model import read_plan,JobStatus
from eval_scheduler.locking import PlanLock

PLAN=ROOT/'logs/scheduler/dfm12_XL_epoch11_noidentity'
OUTPUT=ROOT/'data/dfm13/xl3143-all-task-calibration'
MODEL=ROOT/'exports/dfm12_XL_epoch11_step_3100000_ema_hf'
TEMPLATE=ROOT/'evaluation/chat_templates/gemma4_native_chat.jinja'
PROBES={'X','Test message json','Test message','Hello','Hello!'}


def resolve(value,attachments):
    if isinstance(value,str) and value.startswith('attachment://'):
        return attachments[value.split('://',1)[1]]
    if isinstance(value,list):return [resolve(v,attachments) for v in value]
    if isinstance(value,dict):return {k:resolve(v,attachments) for k,v in value.items()}
    return value


def quantiles(values):
    if not values:return {'p50':None,'p90':None,'max':None}
    values=sorted(values)
    return {k:values[min(len(values)-1,round((len(values)-1)*q))] for k,q in [('p50',.5),('p90',.9),('max',1)]}


def stratify(rows,limit):
    rows=sorted(rows,key=lambda r:(r['prompt_tokens'],r['id']))
    if len(rows)<=limit:return rows
    return [rows[round(i*(len(rows)-1)/(limit-1))] for i in range(limit)]


def artifacts(jobs,pattern):
    files=set()
    for job in jobs:
        directory=Path(job.log_dir.replace('step_3150000','step_3100000'))
        if not directory.is_absolute():directory=ROOT/directory
        files.update(directory.rglob(pattern))
    return sorted(files)


def proxy_rows(files,stats):
    for path in files:
        with path.open() as handle:
            for number,line in enumerate(handle):
                if number>=8192:stats['scan_limit_files']+=1;break
                row=json.loads(line);payload=row.get('outgoing');route=row.get('endpoint')
                if not payload or route not in ('/v1/chat/completions','/v1/completions'):continue
                messages=payload.get('messages',[])
                if len(messages)==1 and messages[0].get('content') in PROBES:
                    stats['capability_probes_excluded']+=1;continue
                yield dict(endpoint=route,payload=payload,source_path=str(path),source_record=number,
                           fidelity='exact_proxy_outgoing',historical_output_tokens=None)


def inspect_rows(files,stats):
    for path in files:
        with zipfile.ZipFile(path) as archive:
            names=sorted(n for n in archive.namelist() if n.startswith('samples/') and n.endswith('.json'))
            for name in names[:512]:
                row=json.loads(archive.read(name));attachments=row.get('attachments',{})
                events=[e for e in row.get('events',[]) if e.get('event')=='model']
                if not events:stats['no_model_event']+=1;continue
                event=resolve(events[0],attachments);call=event.get('call') or {}
                payload=call.get('request')
                if not payload or not isinstance(payload,dict) or 'messages' not in payload:
                    stats['missing_actual_request']+=1;continue
                payload={k:v for k,v in payload.items() if k not in ('extra_headers','extra_query','timeout')}
                if 'extra_body' in payload:
                    extra=payload.pop('extra_body')
                    if extra:payload.update(extra)
                usage=(call.get('response') or {}).get('usage') or {}
                yield dict(endpoint='/v1/chat/completions',payload=payload,source_path=str(path),source_record=name,
                           fidelity='actual_inspect_model_call',historical_output_tokens=usage.get('completion_tokens'))
            if len(names)>512:stats['scan_limit_files']+=1


def standard_rows(files,job,stats):
    import yaml
    config_path=ROOT/job.metadata['standard_config'];config=yaml.safe_load(config_path.read_text())
    benchmark=next(b for b in config['benchmarks'] if b['name']==job.name)
    settings={**config.get('generation_config',{}),**benchmark.get('generation_config',{})}
    for path in files:
        with path.open() as handle:
            for number,line in enumerate(handle):
                if number>=1024:stats['scan_limit_files']+=1;break
                row=json.loads(line)
                # Saved standard generations already contain prompt_template output.
                payload=dict(model='xl-capacity',messages=[dict(role='user',content=row['prompt'].strip())],
                    max_tokens=settings.get('max_tokens',1024),temperature=settings.get('temperature',0),
                    skip_special_tokens=settings.get('skip_special_tokens',False))
                for key in ('stop','stop_token_ids'):
                    if key in settings:payload[key]=settings[key]
                yield dict(endpoint='/v1/chat/completions',payload=payload,source_path=str(path),source_record=number,
                    fidelity='saved_actual_prompt_plus_production_OpenAIEngine_config',
                    sampling_config_path=str(config_path),sampling_config_sha256=file_hash(config_path),
                    historical_output_text=row.get('generation'),historical_output_tokens=None)


def measure(row,tokenizer,template):
    payload=row['payload']
    if row['endpoint']=='/v1/chat/completions':
        kwargs=payload.get('chat_template_kwargs') or {}
        rendered=tokenizer.apply_chat_template(payload['messages'],tools=payload.get('tools'),
            chat_template=template,tokenize=False,add_generation_prompt=payload.get('add_generation_prompt',True),**kwargs)
        count=len(tokenizer.encode(rendered,add_special_tokens=False))
    else:
        prompt=payload['prompt']
        if isinstance(prompt,str):count=len(tokenizer.encode(prompt,add_special_tokens=payload.get('add_special_tokens',True)))
        elif isinstance(prompt,list) and all(type(x) is int for x in prompt):count=len(prompt)
        elif isinstance(prompt,list) and all(isinstance(x,str) for x in prompt):
            counts=[len(tokenizer.encode(x,add_special_tokens=payload.get('add_special_tokens',True))) for x in prompt]
            count=max(counts);row['prompt_batch_tokens']=counts
        else:raise ValueError('Unsupported completion prompt shape')
    row['prompt_tokens']=count
    if count>=4096:raise ValueError('Recorded prompt does not fit current4096 context')
    if row['fidelity'].startswith('saved_actual_prompt'):
        # Exact OpenAIEngine.generate policy: reduce output budget, never prompt text.
        payload['max_tokens']=max(1,min(payload['max_tokens'],4096-count))
    reserve=payload.get('max_tokens',payload.get('max_completion_tokens'))
    if reserve is not None and count+reserve>4096:
        raise ValueError('Recorded explicit output budget exceeds current4096 context')
    row['max_tokens_explicit']=reserve is not None
    row['max_tokens']=reserve if reserve is not None else 4096-count
    if row.get('historical_output_text') is not None:
        row['historical_output_tokens']=len(tokenizer.encode(row.pop('historical_output_text'),add_special_tokens=False))
        row['historical_output_tokens_basis']='retokenized_saved_generation'
    row['id']=digest([row['endpoint'],payload])
    return row


def task(key,jobs,tokenizer,template,limit):
    job=jobs[0];action=job.action.value;stats=Counter()
    if action.startswith('eval_euroeval'):
        files=artifacts(jobs,'proxy_payloads.jsonl');iterator=proxy_rows(files,stats)
    elif action=='eval_standard':
        files=artifacts(jobs,'*.generations.jsonl');iterator=standard_rows(files,job,stats)
    else:
        files=artifacts(jobs,'*.eval');iterator=inspect_rows(files,stats)
    pool={};errors=[]
    for row in iterator:
        signature=digest([row['endpoint'],row['payload']])
        if signature in pool:stats['duplicates']+=1;continue
        try:pool[signature]=measure(row,tokenizer,template)
        except (ValueError,TypeError,KeyError) as exc:
            stats['ineligible_recorded_request']+=1
            if len(errors)<8:errors.append(dict(source=row['source_path'],record=row['source_record'],error=str(exc)))
        if len(pool)>=1024:
            stats['candidate_pool_capped']=1;break
    rows=stratify(list(pool.values()),limit)
    source_hashes={p:file_hash(p) for p in {r['source_path'] for r in rows}}
    for row in rows:row['source_sha256']=source_hashes[row['source_path']]
    inputs=quantiles([r['prompt_tokens'] for r in pool.values()])
    outputs=quantiles([r['historical_output_tokens'] for r in pool.values() if r['historical_output_tokens'] is not None])
    return dict(key=key,action=action,name=job.name,utilization=float(job.metadata.get('vllm_gpu_memory_utilization',.95)),
        current_batch=job.initial_batch,rows=rows,prompt_p50=inputs['p50'],prompt_p90=inputs['p90'],
        prompt_max=inputs['max'],historical_output_tokens=outputs,
        max_tokens=max((r['max_tokens'] for r in rows),default=None),
        status='ready' if rows else 'missing_evidence',source_artifacts=len(files),candidate_pool=len(pool),
        statistics_scope='bounded unique recorded3100 request pool, not entire benchmark population',
        stats=dict(stats),errors=errors,shard_samples={j.job_id:j.shard for j in jobs},
        judged=bool(job.metadata.get('judge_server_model')),judge_model=job.metadata.get('judge_server_model'),
        judge_scope='student requests only; judge throughput not measured' if job.metadata.get('judge_server_model') else None)


def enrich_judges(tasks):
    for task_row in tasks:
        if not task_row.get('judged'):continue
        for row in task_row['rows']:
            with zipfile.ZipFile(row['source_path']) as archive:
                sample=json.loads(archive.read(row['source_record']))
            events=[e for e in sample.get('events',[]) if e.get('event')=='model'
                    and 'judge' in e.get('model','').lower()]
            if not events:raise ValueError('Missing recorded judge request: '+row['id'])
            event=resolve(events[0],sample.get('attachments',{}))
            call=event.get('call') or {};payload=call.get('request')
            if not payload or 'messages' not in payload:raise ValueError('Invalid recorded judge request')
            payload={k:v for k,v in payload.items() if k not in ('extra_headers','extra_query','timeout')}
            extra=payload.pop('extra_body',None)
            if extra:payload.update(extra)
            row.update(judge_payload=payload,judge_endpoint='/v1/chat/completions',
                judge_source_model=event['model'],judge_historical_output_tokens=
                ((call.get('response') or {}).get('usage') or {}).get('completion_tokens'))
        task_row['judge_scope']='paired student plus recorded historical judge request; capacity only, not rescoring'


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--root',type=Path,default=OUTPUT)
    parser.add_argument('--workers',type=int,default=8);parser.add_argument('--limit',type=int,default=64)
    parser.add_argument('--enrich-judges',action='store_true')
    args=parser.parse_args()
    if args.enrich_judges:
        path=args.root/'manifest.json';manifest=load(path)
        previous=file_hash(path)
        enrich_judges(manifest['tasks'])
        write_json(args.root/'manifest-before-judge-enrichment.json',load(path))
        manifest['previous_manifest_sha256']=previous
        manifest['pins'][str(Path(__file__).resolve())]=file_hash(Path(__file__))
        manifest['judge_payloads_complete']=True
        write_json(path,manifest)
        write_json(args.root/'complete.json',dict(manifest_sha256=file_hash(path),
            task_count=manifest['task_count'],ready_count=manifest['ready_count'],missing=manifest['missing'],
            judge_payloads_complete=True))
        return
    if not 1<=args.workers<=16 or not 2<=args.limit<=64:parser.error('workers1..16; limit2..64')
    os.environ['TOKENIZERS_PARALLELISM']='false'
    from transformers import AutoTokenizer
    if load(MODEL/'tokenizer_config.json').get('fix_mistral_regex') is not False:raise ValueError('Wrong tokenizer')
    args.root.mkdir(parents=True,exist_ok=True)
    if (args.root/'manifest.json').exists():raise FileExistsError('Preserve completed preparation')
    with PlanLock(PLAN,exclusive=False):
        plan=read_plan(PLAN/'plan.tsv');plan_sha=file_hash(PLAN/'plan.tsv')
    groups=defaultdict(list);excluded=defaultdict(list)
    for job in plan:
        if job.metadata.get('xl_boundary')!=3150000 or not job.action.value.startswith('eval_'):continue
        key=job.action.value+':'+job.name
        (groups if job.status==JobStatus.PENDING else excluded)[key].append(job)
    write_json(args.root/'inventory.json',dict(pending_keys=sorted(groups),pending_count=len(groups),
        nonpending={k:sorted({j.status.value for j in js}) for k,js in excluded.items()},plan_sha256=plan_sha))
    tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True,fix_mistral_regex=False)
    template=TEMPLATE.read_text();tasks=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(task,k,js,tokenizer,template,args.limit):k for k,js in groups.items()}
        for future in as_completed(futures):
            key=futures[future]
            try:result=future.result()
            except Exception as exc:
                job=groups[key][0];result=dict(key=key,action=job.action.value,name=job.name,rows=[],
                    status='preparation_error',error=repr(exc))
            tasks.append(result)
            write_json(args.root/'tasks'/f'{hashlib.sha256(key.encode()).hexdigest()[:16]}.json',result)
            write_json(args.root/'progress.json',dict(completed=len(tasks),total=len(groups),last=key,status=result['status'],time=time.time()))
            print(len(tasks),'/',len(groups),key,result['status'],len(result['rows']),flush=True)
    tasks.sort(key=lambda t:t['key'])
    enrich_judges(tasks)
    manifest=dict(schema='all-eval-capacity-v1',source_step=3100000,target_step=3150000,
        tasks=tasks,task_count=len(tasks),ready_count=sum(t['status']=='ready' for t in tasks),
        missing=[t['key'] for t in tasks if t['status']!='ready'],expected_count_claim=267,
        count_discrepancy=len(tasks)!=267,inventory=str(args.root/'inventory.json'),plan_sha256=plan_sha,
        model=str(MODEL),template=str(TEMPLATE),pins={str(p):file_hash(p) for p in
        [Path(__file__).resolve(),MODEL/'tokenizer.json',MODEL/'tokenizer_config.json',TEMPLATE]},
        no_wandb=True,no_gpu=True,plan_changed=False,source_context_not_truncated=True,judge_payloads_complete=True)
    write_json(args.root/'manifest.json',manifest)
    write_json(args.root/'complete.json',dict(manifest_sha256=file_hash(args.root/'manifest.json'),
        task_count=len(tasks),ready_count=manifest['ready_count'],missing=manifest['missing']))


if __name__=='__main__':main()
