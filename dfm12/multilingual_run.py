"""Own eight pilot servers, release them on completion/failure, never own training."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
import json

from .audit_pilot_gpu import TOKENIZER_DIR
from .io import file_hash, load, lock, write_json
from .multilingual_tasks import MODEL

AUDIT_ENV = Path('/home/ucloud/miniforge3/envs/audit')


def ready(endpoint):
    try:
        with urllib.request.urlopen(endpoint + '/models', timeout=2) as response:
            return MODEL in {m['id'] for m in json.load(response)['data']}
    except Exception:
        return False


def run(root):
    import psutil
    servers, owned, client = [], [], None
    start = time.monotonic()
    def interrupted(*_):
        raise InterruptedError('Pilot stop requested')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    # Proven server command from the preceding DFM12 audit, now sized for
    # generation rather than short classification. Distinct internal ports.
    def remember():
        known = {(p.pid,p.create_time()) for p in owned if p.is_running()}
        for process in servers + ([client] if client else []):
            if process.poll() is not None:
                continue
            try:
                parent = psutil.Process(process.pid)
                for child in [parent] + parent.children(recursive=True):
                    identity = (child.pid, child.create_time())
                    if identity not in known:
                        owned.append(child)
                        known.add(identity)
            except psutil.NoSuchProcess:
                pass
    try:
        if ((root / 'calibration').exists() or (root / 'cpu-preflight-passed.json').exists()
                or (root / 'pilot-config.json').exists() and load(root / 'pilot-config.json').get('calibration_policy')):
            from .multilingual_trial import verify_inputs
            verify_inputs(root)
        expected = load(root / 'seeds-ready.json')
        if any(file_hash(root/name) != value for name,value in expected.items()):
            raise RuntimeError('Seed manifest changed')
        gpu_pids = subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True)
        if gpu_pids.strip():
            raise RuntimeError('GPUs not free; refusing to compete with another job')
        endpoints = [f'http://127.0.0.1:{8500+i}/v1' for i in range(8)]
        for gpu, endpoint in enumerate(endpoints):
            if ready(endpoint):
                raise RuntimeError('Pilot port already occupied')
            command = [str(AUDIT_ENV/'bin/python'),'-m','vllm.entrypoints.openai.api_server',
                '--model',str(TOKENIZER_DIR),'--served-model-name',MODEL,'--host','127.0.0.1',
                '--port',str(8500+gpu),'--max-model-len','8192',
                '--limit-mm-per-prompt','{"image":0,"video":0,"audio":0}',
                '--gpu-memory-utilization','0.90','--max-num-seqs','128','--enforce-eager']
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), VLLM_PORT=str(28000+gpu*100),
                PATH=str(AUDIT_ENV/'bin')+':'+os.environ['PATH'], CUDA_HOME=str(AUDIT_ENV),
                CONDA_PREFIX=str(AUDIT_ENV), VLLM_USE_FLASHINFER_SAMPLER='0',
                CPATH=str(AUDIT_ENV/'targets/x86_64-linux/include'),
                LIBRARY_PATH=str(AUDIT_ENV/'targets/x86_64-linux/lib'),
                OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',MAX_JOBS='16')
            with (root/f'server-gpu{gpu}.log').open('a') as log:
                process = subprocess.Popen(command,env=env,stdin=subprocess.DEVNULL,stdout=log,
                                           stderr=subprocess.STDOUT,start_new_session=True)
            servers.append(process)
            remember()
            write_json(root/'servers.json',{'servers':[{'gpu':i,'pid':p.pid,'endpoint':endpoints[i]}
                       for i,p in enumerate(servers)],'model':MODEL,'utilization':0.9})
        while not all(ready(e) for e in endpoints):
            remember()
            if any(p.poll() is not None for p in servers):
                raise RuntimeError('Pilot server exited during startup')
            if time.monotonic()-start > 3600:
                raise TimeoutError('Server startup exceeded one hour')
            write_json(root/'server-status.json',{'phase':'starting','ready':[ready(e) for e in endpoints], 'time':time.time()})
            time.sleep(10)
        with (root/'client.log').open('a') as log:
            client = subprocess.Popen([sys.executable,'-u','-m','dfm12.multilingual_pilot','--root',str(root),
                '--endpoints',*endpoints,'--concurrency','64'],stdin=subprocess.DEVNULL,stdout=log,
                stderr=subprocess.STDOUT,start_new_session=True)
        write_json(root/'server-status.json',{'phase':'generating_and_auditing','client_pid':client.pid,'time':time.time()})
        while client.poll() is None:
            remember()
            if any(p.poll() is not None for p in servers):
                raise RuntimeError('Pilot server exited; stop clients and release GPUs')
            if time.monotonic()-start > 22*3600:
                raise TimeoutError('Pilot time budget exhausted; retain rows and resume training')
            time.sleep(10)
        if client.returncode:
            raise RuntimeError(f'Pilot client exited {client.returncode}')
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        remember()
        if client and client.poll() is None:
            client.send_signal(signal.SIGTERM)
            try:
                client.wait(timeout=630)
            except subprocess.TimeoutExpired:
                client.kill()
        for process in servers:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        _, remaining = psutil.wait_procs(owned,timeout=60)
        for process in remaining:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(remaining,timeout=60)
        write_json(root/'servers-released.json',{'time':time.time(),'owned_pids':[p.pid for p in owned]})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args = parser.parse_args()
    with lock(args.root/'.servers.lock'):
        run(args.root)
