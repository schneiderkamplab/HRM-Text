"""Repair PrefixLM artifact isolation after a clean scheduler drain."""
import json,sqlite3,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from eval_scheduler.store import SQLiteJobStore,_validate_graph
from eval_scheduler.preflight import check_job
from scripts.prepare_transformer48_eval_plan import replace
DB=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite')
PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
OLD='B_dfm11_causal_lrauto_bpwarmup'
NEW='B_dfm11_prefixlm_lrauto_bpwarmup'

def main():
    c=sqlite3.connect(DB,timeout=60)
    assert c.execute("select count(*) from jobs where status='running'").fetchone()[0]==0,'Drain scheduler first'
    out=PLAN/'prefixlm-path-repair';out.mkdir(exist_ok=True)
    backup=sqlite3.connect(out/f'before-{int(time.time())}.sqlite');c.backup(backup);backup.close()
    store=SQLiteJobStore(DB);jobs=store.load_jobs();updates={};reset={}
    for j in jobs:
        if not j.job_id.startswith('bprefix-dfm11-') or str(j.action)=='train_until_step':continue
        m=replace(j.metadata,[(OLD,NEW)])
        log=replace(j.log_dir,[(OLD,NEW)])
        m['model_prefix']='B-dfm11-prefixlm'
        assert OLD not in json.dumps(m) and OLD not in log
        updated=j.with_updates(metadata=m,log_dir=log)
        assert not check_job(updated,ROOT),(j.job_id,check_job(updated,ROOT))
        updates[j.job_id]={'metadata':m,'log_dir':log}
        if j.job_id.startswith('bprefix-dfm11-step_50000-'):
            reset[j.job_id]={'status':'pending','attempt':0}
    store.update_jobs(updates)
    store.update_jobs(reset)
    jobs=store.load_jobs();_validate_graph(jobs)
    # Distinct experiments must never share exports or inference result directories.
    peers={j.log_dir for j in jobs if j.job_id.startswith('bauto-') and str(j.action).startswith('eval_')}
    exports={j.metadata.get('hf_export_dir') for j in jobs if j.job_id.startswith('bauto-') and str(j.action)=='export_hf'}
    for j in jobs:
        if j.job_id.startswith('bprefix-'):
            if str(j.action).startswith('eval_'):assert j.log_dir not in peers,j.job_id
            if str(j.action)=='export_hf':assert j.metadata['hf_export_dir'] not in exports,j.job_id
    result={'edited':len(updates),'reset':len(reset),'graph':'valid','preflight':'passed','artifact_isolation':'passed','time':time.time()}
    (out/'receipt.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
