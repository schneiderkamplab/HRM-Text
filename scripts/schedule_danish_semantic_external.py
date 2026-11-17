"""Queue pinned Gemma/Qwen comparisons after Transformer 250K GPU evaluations."""
import argparse, hashlib, json, sqlite3, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job,Action
from eval_scheduler.store import SQLiteJobStore,_validate_graph
from eval_scheduler.preflight import check_job
from scripts.schedule_danish_semantic_mimir import PLAN,DB,FAMILIES
OUT=PLAN/'danish-semantic-external-20261112'
RELEASES={
'gemma4-e2b':('google/gemma-4-E2B-it','4adf15748de9e1a0097b6274cee9c15836c41c37'),
'gemma4-e4b':('google/gemma-4-E4B-it','4ecc2ba63bcac23ba4a767fc87025b1450f84c9c'),
'gemma4-26b-a4b':('google/gemma-4-26B-A4B-it','4d7ae4984b7db7de8f8457170b3f1a419ee76d52'),
'gemma4-31b':('google/gemma-4-31B-it','842da3794eaa0b77d5f08bae87a17459d91ff475'),
'qwen35-0.8b':('Qwen/Qwen3.5-0.8B','2fc06364715b967f1860aea9cf38778875588b17'),
'qwen35-2b':('Qwen/Qwen3.5-2B','15852e8c16360a2fea060d615a32b45270f8a8fc'),
'qwen35-4b':('Qwen/Qwen3.5-4B','851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'),
'qwen35-9b':('Qwen/Qwen3.5-9B','c202236235762e1c871ad0ccb60c8ee5ba337b9a'),
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');a=parser.parse_args()
    from transformers import AutoTokenizer
    OUT.mkdir(exist_ok=True)
    data=ROOT/'evaluation/data/danish_semantic_reasoning'
    rows=[json.loads(l) for l in (data/'records.jsonl').read_text().splitlines()]
    rows=[r for r in rows if r['family']!='danwic' or r['subset']=='danwic_poly_selection']
    assert len(rows)==8501
    manifest={'data_dir':str(data),'records_sha256':sha(data/'records.jsonl'),'models':{},'primary_samples_per_model':8501,'headline':'headline_danish_semantic_v1','weighting':'equal mean of seven family accuracies','enable_thinking':False,'software_sha256':{str(ROOT/p):sha(ROOT/p) for p in ['evaluation/danish_semantic_reasoning_eval.py','scripts/log_danish_semantic_headline.py','config/dfm_evals_danish_semantic_reasoning.yaml']}}
    for name,(repo,rev) in RELEASES.items():
        path=Path('/home/ucloud/.cache/huggingface/hub')/('models--'+repo.replace('/','--'))/'snapshots'/rev
        assert path.is_dir(),path
        index=path/'model.safetensors.index.json'
        weights=sorted(set(json.loads(index.read_text())['weight_map'].values())) if index.exists() else ['model.safetensors']
        assert all((path/w).is_file() and (path/w).stat().st_size>0 for w in weights)
        tok=AutoTokenizer.from_pretrained(path,local_files_only=True)
        longest=max(len(tok.encode(tok.apply_chat_template([{'role':'user','content':r['input']}],tokenize=False,add_generation_prompt=True,enable_thinking=False),add_special_tokens=False)) for r in rows)
        assert longest+16<=4096,(name,longest)
        manifest['models'][name]={'display_name':repo,'path':str(path),'revision':rev,'repo_id':repo,'max_prompt_tokens':longest,'result_root':str(OUT/name),'wandb_run_id':'danish-semantic-v1-'+name+'-20261112','sha256':{p.name:sha(p) for p in path.iterdir() if p.suffix in ('.json','.jinja')},'weight_blobs':{w:{'blob':(path/w).resolve().name,'bytes':(path/w).stat().st_size} for w in weights}}
        print(name,longest,flush=True)
    mp=OUT/'manifest.json'
    if mp.exists():assert json.loads(mp.read_text())==manifest,'Frozen manifest differs'
    else:mp.write_text(json.dumps(manifest,indent=2))
    store=SQLiteJobStore(DB);jobs=store.load_jobs();assert not any(j.job_id.startswith('dsrb-ext-') for j in jobs),'Already scheduled'
    base=next(j for j in jobs if j.job_id=='dsrb-mimir-v1-inference')
    previous=[j.job_id for j in jobs if j.job_id.startswith('transformer48-step_250000-') and (j.action.startswith('eval_') or j.action in ('train_until_step','export_hf','wait_checkpoint'))]
    assert 'transformer48-step_250000-train' in previous and len(previous)>100
    initial=previous[:];added=[]
    for name,m in manifest['models'].items():
        ids=[]
        for family in FAMILIES:
            jid=f'dsrb-ext-{name}-{family}';ids.append(jid)
            md={**base.metadata,'external_model':m['path'],'external_served_model_name':name+'-dsrb','ckpt_tag':m['revision'],'dfm_suite':'danish_semantic_'+family,'vllm_extra_args':'--attention-backend FLASH_ATTN --language-model-only --default-chat-template-kwargs \'{"enable_thinking":false}\''}
            if name.startswith('gemma4-'):
                md['vllm_attention_backend']='TRITON_ATTN'
                md['cuda_home']='/home/ucloud/miniforge3/envs/audit'
                md['vllm_python']=str(ROOT/'scripts/gemma_cuda_python')
                md['vllm_extra_args']=md['vllm_extra_args'].replace('FLASH_ATTN','TRITON_ATTN')
            added.append(Job(job_id=jid,action=Action.EVAL_DFM,family='danish_semantic',name=family,deps=tuple(previous),deps_mode='terminal',initial_batch=64,max_retries=1,metadata=md,log_dir=str(Path(m['result_root'])/family)))
        added.append(Job(job_id=f'dsrb-ext-{name}-headline',action=Action.AVERAGE,family='danish_semantic',name='danish_semantic_headline',deps=tuple(ids),deps_mode='terminal',max_retries=1,metadata={'average_prefix':'headline_danish_semantic_v1','semantic_manifest':str(mp),'semantic_model':name,'python_bin':str(ROOT/'dfm-evals/.venv/bin/python'),'plan_dir':str(PLAN)},log_dir=str(Path(m['result_root'])/'publication')))
        previous=ids
    _validate_graph(jobs+added)
    for j in added:assert not check_job(j,ROOT),(j.job_id,check_job(j,ROOT))
    if a.execute:
        c=sqlite3.connect(DB,timeout=60);b=sqlite3.connect(OUT/f'before-{int(time.time())}.sqlite');c.backup(b);b.close();c.close()
        # Additive transaction: never round-trip existing definitions. Legacy
        # serialized rows may differ from canonical serialization while claimed.
        c=sqlite3.connect(DB,timeout=60)
        with c:
            c.execute('BEGIN IMMEDIATE')
            assert not c.execute("select 1 from jobs where job_id like 'dsrb-ext-%'").fetchone()
            pos=c.execute('select max(position) from jobs').fetchone()[0]+1
            for i,j in enumerate(added):
                d=j.to_row()
                for field in ('status','attempt','log_dir'):d.pop(field,None)
                c.execute('insert into jobs values (?,?,?,?,?,?,?,?,?)',(j.job_id,pos+i,json.dumps(d),j.deps_mode,0,'pending',0,j.log_dir,None))
                c.executemany('insert into dependencies values (?,?)',[(j.job_id,x) for x in j.deps])
        c.close()
        actual={j.job_id:j for j in store.load_jobs()}
        assert all(actual[j.job_id].status=='pending' for j in added)
        assert all(actual[j.job_id].metadata==j.metadata for j in jobs if j.action==Action.TRAIN_UNTIL_STEP)
    receipt={'executed':a.execute,'inference_jobs':56,'headline_jobs':8,'generations':68008,'initial_dependencies':initial,'added_jobs':[j.job_id for j in added],'training_definitions_unchanged':True}
    (OUT/('receipt.json' if a.execute else 'preflight.json')).write_text(json.dumps(receipt,indent=2))
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('initial_dependencies','added_jobs')}))
if __name__=='__main__':main()
