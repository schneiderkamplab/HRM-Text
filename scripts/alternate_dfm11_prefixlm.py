"""Replace future full-BP B blocks with the existing PrefixLM run, pending-only."""
import argparse,json,sqlite3,time,sys,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job
from eval_scheduler.store import _validate_graph
from eval_scheduler.preflight import check_job
from training_suspend.supervisor import overrides
from scripts.prepare_transformer48_eval_plan import replace
DB=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite')
PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
OUT=PLAN/'prefixlm-alternation'
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'
TAGS=['step_200000','step_250000','step_300000','step_350000','epoch_1']
PAIRS=[('bfull-dfm11','bprefix-dfm11'),
 ('B-dfm11-causal-fullbp-alltokens-epoch1','B-dfm11-prefixlm-lrauto-bpwarmup-targetonly-epoch1'),
 ('B_dfm11_causal_fullbp_20261110','B_dfm11_prefixlm_lrauto_bpwarmup_20261111'),
 ('B_dfm11_causal_fullbp','B_dfm11_prefixlm_lrauto_bpwarmup')]

def prepare(rows):
    definitions={r[0]:json.loads(r[2]) for r in rows}
    template=json.loads(definitions['bprefix-dfm11-step_150000-train']['metadata_json'])['cooperative_training']['command']
    command=overrides(template,{'suspend_after_steps':'[50000,100000,150000,200000,250000,300000,350000]'})
    retired={jid for jid in definitions if any(jid.startswith(f'bfull-dfm11-{tag}-') for tag in TAGS)}
    assert len(retired)==5*2204, len(retired)
    changes=[];candidate=[]
    for row in rows:
        jid,pos,raw,mode,optional,status,attempt,log,token=row
        d=json.loads(raw);newlog=log
        if jid in retired:
            assert status=='pending' and token is None,(jid,status)
            d=replace(d,PAIRS);newlog=replace(log,PAIRS)
            m=json.loads(d['metadata_json']);m.pop('recurrent_causal',None);m.pop('transformer_single_pass',None)
            m['model_prefix']='B-dfm11-prefixlm'
            if d['action']=='train_until_step':m['cooperative_training']['command']=command
            d['metadata_json']=json.dumps(m)
            assert 'B_dfm11_causal_fullbp' not in json.dumps(d)
            assert 'B-dfm11-causal-fullbp' not in json.dumps(d)
        else:
            deps=d['deps'].split(',');newdeps=[replace(x,PAIRS) if x in retired else x for x in deps]
            if newdeps!=deps:
                assert status=='pending',(jid,status)
                d['deps']=','.join(newdeps)
                m=json.loads(d['metadata_json'])
                if m.get('cooperative_training',{}).get('disk_handoff_from'):
                    m['cooperative_training']['disk_handoff_from']=replace(m['cooperative_training']['disk_handoff_from'],PAIRS)
                d['metadata_json']=json.dumps(m)
        job=Job.from_row(d).with_updates(log_dir=newlog)
        candidate.append(job)
        if d!=json.loads(raw) or newlog!=log:
            assert status=='pending' and token is None,(jid,status)
            errors=check_job(job,ROOT);assert not errors,(jid,errors)
            changes.append((row,d,newlog))
    _validate_graph(candidate)
    byid={j.job_id:j for j in candidate}
    for j in candidate:
        if j.job_id.startswith('bprefix-') and j.action=='train_until_step':
            m=j.metadata;co=m['cooperative_training'];cmd=co['command']
            assert '+arch.attn_type=prefixlm' in cmd and 'data.target_only=true' in cmd and 'lr_auto=true' in cmd
            assert '+arch.bp_min_steps=2' in cmd and 'arch.bp_max_steps=8' in cmd
            assert 'arch.bp_warmup_ratio=0.12698993223817215' in cmd
            assert all(byid[x].action.startswith('eval_') or byid[x].action in ('export_hf','wait_checkpoint') for x in j.deps)
    return changes,command,candidate

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    c=sqlite3.connect(DB,timeout=60);rows=c.execute('select * from jobs order by position').fetchall()
    changes,command,candidate=prepare(rows)
    OUT.mkdir(exist_ok=True)
    idx=command.index('pretrain.py')
    cfg=subprocess.check_output([PYTHON,'pretrain.py',*command[idx+1:],'--cfg','job','--resolve'],cwd=ROOT,
        env={**os.environ,'TMPDIR':'/dev/shm/hrm-b-recovery'})
    (OUT/'resolved-continuation.yaml').write_bytes(cfg)
    result={'changed_rows':len(changes),'replacement_blocks':TAGS,'graph':'passed','artifact_isolation':'passed','changed_row_preflight':'passed','hydra_resolution':'passed','executed':args.execute}
    if args.execute:
        backup=sqlite3.connect(OUT/f'before-{int(time.time())}.sqlite');c.backup(backup);backup.close()
        (OUT/'previous-rows.json').write_text(json.dumps([old for old,_,_ in changes]))
        c.execute('begin immediate')
        for old,d,log in changes:
            current=c.execute('select * from jobs where job_id=?',(old[0],)).fetchone()
            assert current==old, f'Concurrent modification: {old[0]}'
        for old,d,log in changes:
            c.execute('delete from dependencies where job_id=?',(old[0],))
            c.execute('delete from jobs where job_id=?',(old[0],))
        for old,d,log in changes:
            c.execute('insert into jobs values (?,?,?,?,?,?,?,?,?)',(d['job_id'],old[1],json.dumps(d),old[3],old[4],'pending',0,log,None))
            c.executemany('insert into dependencies values (?,?)',[(d['job_id'],dep) for dep in d['deps'].split(',') if dep])
        c.commit()
        path=PLAN/'manifest.json';manifest=json.loads(path.read_text())
        for entry in manifest['order']:
            if entry['model']=='B' and entry['boundary'] in TAGS:entry['model']='B-prefixlm-targetonly'
        path.write_text(json.dumps(manifest,indent=2)+'\n')
    (OUT/('receipt.json' if args.execute else 'dry-run.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
if __name__=='__main__':main()
