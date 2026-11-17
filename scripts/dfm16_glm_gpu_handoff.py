"""Wait for genuinely free GPUs, launch owned GLM replicas, drain/reassign safely."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request
from dfm12.io import load,lock,write_json

ROOT=Path('/work/dfm/HRM-Text')
STATE=ROOT/'logs/dfm16/glm-handoff-20261030'
CAMPAIGN=ROOT/'data/dfm16/english-production-fullscale-v1-20261030'
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'
SERVER_PYTHON='/home/ucloud/miniforge3/envs/euroeval/bin/python'
MODEL='zai-org/GLM-5.3-Flash'
GENERATION_PID=ROOT/'logs/dfm16/english-production-fullscale-v1-20261030/generation.pid'


def owner_command(pid):
    try:return (Path(f'/proc/{pid}')/'cmdline').read_bytes()
    except (FileNotFoundError,ProcessLookupError,PermissionError):return b''


def owner_environ(pid):
    try:return (Path(f'/proc/{pid}')/'environ').read_bytes().split(b'\0')
    except (FileNotFoundError,ProcessLookupError,PermissionError):return []


def odin_owner(pid_path=None):
    """Resolve the Odin generation owner as present, absent, or fail closed."""
    try:pid=int(Path(pid_path or GENERATION_PID).read_text())
    except (OSError,ValueError):return dict(state='absent',pid=None)
    old_id=identity(pid)
    if not old_id:return dict(state='absent',pid=pid)
    if b'scripts.dfm16_english_fullscale_generate' not in owner_command(pid):raise RuntimeError('Unexpected Odin process')
    credential=next((v.split(b'=',1)[1].decode() for v in owner_environ(pid) if v.startswith(b'ODIN_API_KEY=')),None)
    if not credential:raise RuntimeError('Odin owner lacks ODIN_API_KEY')
    return dict(state='present',pid=pid,identity=old_id,credential=credential)


def gpu_free(memory,processes):
    lines=[line for line in memory.strip().splitlines() if line.strip()]
    return len(lines)==8 and all(int(line.strip())<500 for line in lines) and not processes.strip()


def identity(pid):
    try:return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[19]
    except FileNotFoundError:return None


def launch(command,name,env):
    with (STATE/f'{name}.log').open('ab') as stream:
        p=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    write_json(STATE/f'{name}-process.json',dict(pid=p.pid,identity=identity(p.pid),command=command))
    return p


def health(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/models',timeout=3) as response:
            return MODEL in {r['id'] for r in json.load(response)['data']}
    except Exception:return False


def main():
    STATE.mkdir(parents=True,exist_ok=True)
    with lock(STATE/'.controller.lock'):
        if (STATE/'handoff-complete.json').exists():return
        owner=odin_owner()
        if owner['state']=='absent' and not os.environ.get('ODIN_API_KEY'):
            raise RuntimeError('No ODIN_API_KEY in environment and no live Odin owner; refusing to arm')
        stable=0
        while True:
            memory=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True)
            processes=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True)
            free=gpu_free(memory,processes)
            stable=stable+1 if free else 0
            downloaded=(STATE/'download-complete.json').exists()
            try:
                write_json(STATE/'status.json',dict(phase='waiting_for_free_gpus_and_weights',gpus_free=free,
                    consecutive_free_checks=stable,weights_ready=downloaded,existing_work_untouched=True,
                    last_checked=time.time()))
            except OSError as exc:
                # A transient workspace/mount outage must not disarm the wait.
                # Do not launch or signal anything until state is writable again.
                stable=0
                print(f'Workspace unavailable; retrying in 30 seconds: {type(exc).__name__}',flush=True)
                time.sleep(30)
                continue
            if stable>=3 and downloaded:break
            time.sleep(30)
        env=dict(os.environ,PYTHONPATH=str(ROOT),VLLM_USE_RUST_FRONTEND='0')
        env['PATH']='/home/ucloud/miniforge3/envs/euroeval/bin:'+env.get('PATH','')
        servers=[]
        # Never adopt or stop a pre-existing process on these ports.
        import socket
        for port in (8890,8891):
            with socket.socket() as sock:sock.bind(('127.0.0.1',port))
        for name,devices,port in [('generation','0,1,2,3',8890),('auditing','4,5,6,7',8891)]:
            command=[SERVER_PYTHON,'-m','vllm.entrypoints.openai.api_server',
                '--model','/work/dfm/models/GLM-5.3-Flash','--served-model-name',MODEL,
                '--host','127.0.0.1','--port',str(port),'--tensor-parallel-size','4',
                '--gpu-memory-utilization','0.85','--max-model-len','16384',
                '--max-num-seqs','128','--max-num-batched-tokens','16384',
                '--enable-prefix-caching','--enable-chunked-prefill','--kv-cache-dtype','fp8',
                '--reasoning-parser','glm47','--limit-mm-per-prompt','{"image":0,"video":0}']
            servers.append(launch(command,'server-'+name,dict(env,CUDA_VISIBLE_DEVICES=devices)))
        write_json(STATE/'status.json',dict(phase='starting_glm_servers'))
        deadline=time.time()+3600
        while not all(health(p) for p in (8890,8891)):
            if any(p.poll() is not None for p in servers) or time.time()>deadline:
                raise RuntimeError('GLM startup failed; Odin was not interrupted. Inspect server logs.')
            time.sleep(15)
        # Verify actual final-content decoding before moving production ownership.
        for port in (8890,8891):
            payload=dict(model=MODEL,messages=[dict(role='user',content='Reply with exactly accept.')],
                max_tokens=2048,temperature=0,chat_template_kwargs={'reasoning_effort':'low'})
            req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=300) as response:body=json.load(response)
            write_json(STATE/f'smoke-{port}.json',body)
            if body['choices'][0]['finish_reason']!='stop' or body['choices'][0]['message']['content'].strip()!='accept':
                raise RuntimeError('GLM final-content smoke failed; Odin remains active')
        owner=odin_owner()
        if owner['state']=='present':
            credential=owner['credential']
            os.kill(owner['pid'],signal.SIGTERM)  # shared runtime drains active rows
            write_json(STATE/'status.json',dict(phase='draining_original_odin',pid=owner['pid']))
            while identity(owner['pid'])==owner['identity']:time.sleep(5)
        else:
            credential=os.environ.get('ODIN_API_KEY')
            if not credential:raise RuntimeError('Odin owner absent at handoff and no ODIN_API_KEY in environment')
            write_json(STATE/'status.json',dict(phase='original_odin_absent_env_credential'))
        subprocess.run([PYTHON,'-m','scripts.dfm16_dual_generation','prepare'],cwd=ROOT,env=env,check=True)
        odin=launch([PYTHON,'-m','scripts.dfm16_dual_generation','odin'],'odin-worker',dict(env,ODIN_API_KEY=credential))
        glm=launch([PYTHON,'-m','scripts.dfm16_dual_generation','glm'],'glm-worker',env)
        audit=launch([PYTHON,'-m','scripts.dfm16_glm_live_audit'],'glm-audit-worker',env)
        time.sleep(10)
        if any(p.poll() is not None for p in (odin,glm,audit)):raise RuntimeError('A handoff worker exited; inspect logs')
        write_json(STATE/'handoff-complete.json',dict(generation_pid=glm.pid,odin_pid=odin.pid,audit_pid=audit.pid,
            models=['odin-2-large',MODEL],source_candidates=502000,production_admitted=False))
        write_json(STATE/'status.json',dict(phase='glm_and_odin_running',source_candidates=502000))
        write_json(CAMPAIGN/'status.json',dict(phase='dual_generation_and_additional_glm_audit',source_candidates=502000,admitted=0))


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        # Failed startup releases only the server process groups created here.
        if not (STATE/'handoff-complete.json').exists():
            for name in ('generation','auditing'):
                path=STATE/f'server-{name}-process.json'
                if path.exists():
                    owned=load(path)
                    if identity(owned['pid'])==owned['identity']:
                        try:os.killpg(owned['pid'],signal.SIGTERM)
                        except ProcessLookupError:pass
        write_json(STATE/'failure.json',dict(error=type(exc).__name__,message=str(exc)))
        raise
