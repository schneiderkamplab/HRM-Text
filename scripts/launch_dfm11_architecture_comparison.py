"""Validate the prepared alternating plan; launch only with --execute."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training_suspend.protocol import read_json,validate_process
from eval_scheduler.store import SQLiteJobStore
from eval_scheduler.preflight import check_job, check_artifact_isolation
from eval_scheduler.runtime import checkpoint_ready
from prepare_dfm11_architecture_comparison import PLAN,DB,OUT,TCONTROL,PYTHON


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    os.chdir(ROOT)
    manifest=read_json(PLAN/'manifest.json')
    assert hashlib.sha256((OUT/'resolved-config.yaml').read_bytes()).hexdigest()==manifest['config_sha256']
    jobs=SQLiteJobStore(DB).load_jobs()
    collisions=check_artifact_isolation(jobs,ROOT)
    assert not collisions, collisions[:10]
    errors={j.job_id:e for j in jobs if (e:=check_job(j,ROOT))}
    assert not errors,f'{len(errors)} job preflight failures'
    for path in ['metadata.json','tokens.npy',*[f'epoch_0/{k}.npy' for k in ['inst_start','inst_len','resp_start','resp_len']]]:
        assert (ROOT/'data/sampled_dfm11'/path).is_file(),path
    blockers=[]
    receipt=ROOT/'logs/scheduler/transformer48_dfm11_causal_epoch1_20261109/stop-after-150k/receipt.json'
    if not receipt.exists():blockers.append('Transformer 150K stop receipt not yet present')
    if (TCONTROL/'launcher.json').exists():
        try:validate_process(read_json(TCONTROL/'launcher.json')['identity']);blockers.append('Transformer launcher still alive')
        except (OSError,RuntimeError):pass
    resume=next(j for j in jobs if j.job_id=='transformer48-step_200000-train')
    ready,why=checkpoint_ready(resume.with_updates(metadata={**resume.metadata,'ckpt_tag':'step_150000'}))
    if not ready:blockers.append('Transformer 150K checkpoint: '+why)
    command=[PYTHON,'-m','eval_scheduler','run','--plan-dir',str(PLAN),'--gpus','0,1,2,3,4,5,6,7',
             '--persistent-vllm','--backend','sqlite','--cpu-cores','256','--reserve-cores','8','--max-clients','128','--server-concurrency','1024']
    result={'jobs':len(jobs),'path_errors':len(errors),'start_blockers':blockers,'command':command}
    (PLAN/'launch-preflight.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    if args.execute:
        assert not blockers,'; '.join(blockers)
        assert not any(j.status.value=='running' for j in jobs),'Scheduler already running'
        env={**os.environ,'TMPDIR':'/dev/shm/hrm-b-recovery','PATH':str(Path(PYTHON).parent)+':'+os.environ['PATH']}
        with (PLAN/'runner.log').open('ab') as log:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
        print('Scheduler launched',process.pid)

if __name__=='__main__':main()
