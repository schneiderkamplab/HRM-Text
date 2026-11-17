"""Release the paused memory-resume orchestrator only after verified26B success."""
import json,os,signal,sqlite3,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'logs/scheduler/gemma_semantic_memory_interlude_20261112'
receipt=json.loads((p/'resume-gated-on-26b.json').read_text());pid=receipt['orchestrator_pid']
start=Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[19]
while True:
    with sqlite3.connect('/var/tmp/gemma-semantic-memory-interlude-20261112/jobs.sqlite') as c:
        rows=c.execute("select job_id,status from jobs where job_id like 'dsrb-ext-gemma4-26b-a4b-%'").fetchall()
        active=c.execute("select count(*) from jobs where status in ('pending','running')").fetchone()[0]
    if len(rows)==8 and all(s=='done' for _,s in rows) and active==0:
        report=json.loads((ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110/danish-semantic-external-20261112/gemma4-26b-a4b/headline.json').read_text())
        assert report['publication']=='wandb_finished'
        assert report['metrics']['headline_danish_semantic_v1/sample_count']==8501
        assert Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[19]==start
        assert 'run_gemma_semantic_memory_interlude.py' in Path(f'/proc/{pid}/cmdline').read_text()
        (p/'26b-success-resume-gate.json').write_text(json.dumps({'time':time.time(),'jobs':rows,'publication':'wandb_finished','resume_orchestrator':pid},indent=2))
        os.kill(pid,signal.SIGCONT)
        print('26B successful, all evals terminal; released existing memory-resume orchestrator',flush=True)
        break
    time.sleep(5)
