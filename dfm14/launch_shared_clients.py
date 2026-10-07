"""Start calibration and source audit together after all owned replicas are healthy."""
import os
from pathlib import Path
import subprocess
import sys
import time
import httpx
from dfm12.io import load, lock, write_json

ROOT=Path('logs/dfm14/shared-gemma-20261007')


def main():
    endpoints=[f'http://127.0.0.1:{8800+i}/v1' for i in range(8)]
    with lock(ROOT/'clients.lock'):
        if (ROOT/'clients.json').exists():
            raise RuntimeError('Clients already launched; inspect existing ownership first')
        deadline=time.monotonic()+7200
        while True:
            if (ROOT/'servers/stopped.json').exists():
                raise RuntimeError('Server supervisor stopped')
            flags=[]
            for endpoint in endpoints:
                try:
                    r=httpx.get(endpoint+'/models',timeout=2); r.raise_for_status()
                    flags.append(any(m['id']=='google/gemma-4-26B-A4B-it' and m.get('max_model_len',0)>=32768 for m in r.json()['data']))
                except (httpx.HTTPError,ValueError,KeyError): flags.append(False)
            write_json(ROOT/'clients-wait.json',dict(time=time.time(),ready=flags))
            if all(flags): break
            if time.monotonic()>deadline: raise TimeoutError('Servers not ready')
            time.sleep(10)
        launched=[]
        for module,concurrency in [('dfm14.calibrate',128),('dfm14.audit',256)]:
            command=[sys.executable,'-u','-m',module,'--concurrency',str(concurrency)]
            if module=='dfm14.audit':
                command=[sys.executable,'-u','-m','audit_pipeline','audit',
                         '--root','data/dfm14/gpu-ready','--output','data/dfm14/audit-v1',
                         '--concurrency',str(concurrency)]
            else:
                for endpoint in endpoints: command.extend(['--endpoint',endpoint])
            log=ROOT/(module.rsplit('.',1)[1]+'.log')
            with log.open('x') as handle:
                p=subprocess.Popen(command,stdout=handle,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,
                    env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false'))
            launched.append(dict(pid=p.pid,command=command,log=str(log),time=time.time()))
            write_json(ROOT/'clients.json',launched)
        print('Started both clients',launched,flush=True)


if __name__=='__main__': main()
