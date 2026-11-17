"""Insert three pinned Mimir semantic evaluations before the next training row."""
import argparse,hashlib,json,os,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job,Action
from eval_scheduler.store import SQLiteJobStore,_validate_graph
from eval_scheduler.preflight import check_job
PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
DB=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite')
OUT=PLAN/'danish-semantic-mimir-20261112'
FAMILIES=['inference','entailment','danwic','synonymy','similarity','sentiment','dameta']
MODELS={
 'mimir-v1':('/home/ucloud/.cache/huggingface/hub/models--danish-foundation-models--DFM-Mimir/snapshots/396df886074e3e43f30792fbf393b9a019fe28f7','396df886074e3e43f30792fbf393b9a019fe28f7'),
 'mimir-v1.5':('/home/ucloud/.cache/huggingface/hub/models--danish-foundation-models--DFM-Mimir-v1.5/snapshots/521b40b36a79918014544b970d4c2669ff1530eb','521b40b36a79918014544b970d4c2669ff1530eb'),
 'mimir-v1.8':('/work/dfm/euroeval-runs/mimir-v1.8-3800000-validation/model','step_3800000_ema'),
}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    a=argparse.ArgumentParser();a.add_argument('--execute',action='store_true');args=a.parse_args()
    OUT.mkdir(exist_ok=True);manifest_path=OUT/'manifest.json'
    if not manifest_path.exists():
        from transformers import AutoTokenizer
        data=ROOT/'evaluation/data/danish_semantic_reasoning';dm=json.loads((data/'manifest.json').read_text())
        rows=[json.loads(l) for l in (data/'records.jsonl').read_text().splitlines()]
        primary=[r for r in rows if r['family']!='danwic' or r['subset']=='danwic_poly_selection'];assert len(primary)==8501
        manifest={'data_dir':str(data),'records_sha256':dm['records_sha256'],'upstream_revision':dm['upstream_revision'],'models':{},'headline':'headline_danish_semantic_v1','weighting':'equal mean of seven family accuracies','primary_samples_per_model':8501}
        for name,(path,revision) in MODELS.items():
            model=Path(path);hashes={f:digest(model/f) for f in ['config.json','model.safetensors','tokenizer.json','tokenizer_config.json','chat_template.jinja']}
            tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True,fix_mistral_regex=False)
            longest=max(len(tokenizer.encode(tokenizer.apply_chat_template([{'role':'user','content':r['input']}],tokenize=False,add_generation_prompt=True),add_special_tokens=False)) for r in primary)
            assert longest+16<=4096,(name,longest)
            manifest['models'][name]={'display_name':name.replace('mimir','Mimir'),'path':path,'revision':revision,'sha256':hashes,'max_prompt_tokens':longest,'result_root':str(OUT/name),'wandb_run_id':'danish-semantic-v1-'+name+'-20261112'}
        assert manifest['models']['mimir-v1.5']['sha256']['model.safetensors']=='226257d0d6c5dc04d920e48bb7079c3361dcf0866a950f4667bfcc9ae7bb6e48'
        assert manifest['models']['mimir-v1.8']['sha256']['model.safetensors']=='07e031ed49b740591a97039de4bad73e46f2818ee9d244631dabb6ad82190c27'
        manifest_path.write_text(json.dumps(manifest,indent=2))
    manifest=json.loads(manifest_path.read_text());store=SQLiteJobStore(DB);jobs=store.load_jobs()
    assert not any(j.job_id.startswith('dsrb-') for j in jobs),'Already inserted'
    previous=[j.job_id for j in jobs if j.job_id.startswith('bprefix-dfm11-step_200000-') and (j.action.startswith('eval_') or j.action in ('export_hf','wait_checkpoint'))]
    assert len(previous)==1047
    added=[];heads=[]
    for name,model in manifest['models'].items():
        ids=[]
        for family in FAMILIES:
            jid=f'dsrb-{name}-{family}'
            md={'external_model':model['path'],'external_served_model_name':name+'-dsrb','ckpt_tag':model['revision'],'host':'127.0.0.1','port_base':26000,'python_bin':'/home/ucloud/miniforge3/envs/hrm/bin/python','vllm_python':'/home/ucloud/miniforge3/envs/hrm/bin/python','vllm_dtype':'bfloat16','vllm_max_model_len':4096,'vllm_gpu_memory_utilization':.95,'vllm_max_num_seqs':512,'vllm_max_num_batched_tokens':8192,'vllm_attention_backend':'FLASH_ATTN','vllm_extra_args':'--attention-backend FLASH_ATTN','dfm_evals_dir':str(ROOT/'dfm-evals'),'dfm_single_tasks_config':str(ROOT/'config/dfm_evals_danish_semantic_reasoning.yaml'),'dfm_suite':'danish_semantic_'+family,'dfm_context_length':4096,'max_connections':64,'defer_dfm_export':True,'plan_dir':str(PLAN)}
            j=Job(job_id=jid,action=Action.EVAL_DFM,family='danish_semantic',name=family,deps=tuple(previous),deps_mode='terminal',initial_batch=64,max_retries=1,metadata=md,log_dir=str(Path(model['result_root'])/family))
            added.append(j);ids.append(jid)
        jid=f'dsrb-{name}-headline';heads.append(jid)
        added.append(Job(job_id=jid,action=Action.AVERAGE,family='danish_semantic',name='danish_semantic_headline',deps=tuple(ids),deps_mode='terminal',max_retries=1,metadata={'average_prefix':'headline_danish_semantic_v1','semantic_manifest':str(manifest_path),'semantic_model':name,'python_bin':str(ROOT/'dfm-evals/.venv/bin/python'),'plan_dir':str(PLAN)},log_dir=str(Path(model['result_root'])/'publication')))
        previous=ids
    tid='transformer48-step_250000-train';train=next(j for j in jobs if j.job_id==tid);assert train.status=='pending'
    updated=train.with_updates(deps=tuple(dict.fromkeys([*train.deps,*heads])),metadata={**train.metadata,'user_training_pause':False})
    candidate=[updated if j.job_id==tid else j for j in jobs]+added;_validate_graph(candidate)
    for j in added:
        errors=check_job(j,ROOT);assert not errors,(j.job_id,errors)
    if args.execute:
        c=sqlite3.connect(DB,timeout=60);b=sqlite3.connect(OUT/f'before-{int(time.time())}.sqlite');c.backup(b);b.close()
        assert (PLAN/'stop.request').exists(), 'Fence dispatch before inserting the training gate'
        assert not c.execute("select count(*) from jobs where status='running' and json_extract(definition,'$.action')='train_until_step'").fetchone()[0], 'Training already started'
        c.execute('begin immediate');assert c.execute('select status from jobs where job_id=?',(tid,)).fetchone()[0]=='pending'
        pos=c.execute('select max(position) from jobs').fetchone()[0]+1
        for i,j in enumerate(added):
            d=j.to_row();d.pop('status',None);d.pop('attempt',None);d.pop('log_dir',None)
            c.execute('insert into jobs values (?,?,?,?,?,?,?,?,?)',(j.job_id,pos+i,json.dumps(d),j.deps_mode,0,'pending',0,j.log_dir,None));c.executemany('insert into dependencies values (?,?)',[(j.job_id,x) for x in j.deps])
        d=updated.to_row();d.pop('status',None);d.pop('attempt',None);d.pop('log_dir',None)
        c.execute('update jobs set definition=? where job_id=?',(json.dumps(d),tid));c.execute('delete from dependencies where job_id=?',(tid,));c.executemany('insert into dependencies values (?,?)',[(tid,x) for x in updated.deps]);c.commit()
    result={'jobs':len(added),'inference_jobs':21,'headlines':heads,'generations':25503,'next_train':tid,'later_training_still_paused':7,'executed':args.execute}
    (OUT/('receipt.json' if args.execute else 'preflight.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
