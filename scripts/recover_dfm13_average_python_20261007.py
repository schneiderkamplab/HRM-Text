"""One-shot plan-only repair of inherited training wrappers; never launches."""
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.schedule_dfm13_wave34_baseline import (
    PLAN,Action,JobStatus,PlanLock,read_plan,write_plan,check_graph,load,write_json,file_hash)
FAILED='dfm13-xl-wave34-step_3150000-average'
BAD=str(ROOT/'scripts/resume_xl_dfm12_epoch11.sh')
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'
OUT=ROOT/'data/dfm13/average-python-recovery-20261007'


def recover():
    OUT.mkdir(parents=True,exist_ok=True)
    with PlanLock(PLAN):
        before=read_plan(PLAN/'plan.tsv');by={j.job_id:j for j in before}
        if any(j.status==JobStatus.RUNNING for j in before):raise ValueError('Running jobs; refuse offline recovery')
        if by[FAILED].status!=JobStatus.FAILED:raise ValueError('Expected exact failed average')
        after=[];changed=[]
        for j in before:
            old=j
            if j.action==Action.AVERAGE and j.status in (JobStatus.PENDING,JobStatus.FAILED) and j.metadata.get('python_bin')==BAD:
                if j.status==JobStatus.FAILED and j.job_id!=FAILED:raise ValueError('Unexpected failed row')
                j=j.with_updates(metadata={**j.metadata,'python_bin':PYTHON})
                if j.job_id==FAILED:j=j.with_updates(status=JobStatus.PENDING,attempt=0)
                changed.append(dict(job_id=j.job_id,before=old.to_row(),after=j.to_row()))
            after.append(j)
        check_graph(after)
        assert all(a==b for a,b in zip(before,after) if a.status==JobStatus.DONE)
        assert all(a==b for a,b in zip(before,after) if a.action==Action.TRAIN_UNTIL_STEP)
        backup=OUT/'plan-before.tsv'
        if backup.exists():raise ValueError('Existing recovery evidence; do not replay')
        write_plan(backup,before)
        log=Path(by[FAILED].log_dir)/'multilingual_average.log'
        if log.exists():shutil.copy2(log,OUT/'failed-multilingual-average.log')
        write_plan(PLAN/'plan.tsv',after)
        write_json(OUT/'recovery.json',dict(changes=changed,changed_count=len(changed),
            reset_failed_job=FAILED,all_done_preserved=True,all_training_rows_preserved=True,
            before_sha256=file_hash(backup),after_sha256=file_hash(PLAN/'plan.tsv'),
            recovery_script_sha256=file_hash(__file__),scheduler_launched=False))
        print('Corrected',len(changed),'averages; reset only',FAILED)

if __name__=='__main__':recover()
