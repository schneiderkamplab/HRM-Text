"""One operational entry point; adapters do not own scheduling loops."""
import argparse
import asyncio
from collections import Counter
import multiprocessing as mp
import os
from pathlib import Path
import signal

from dfm12.io import file_hash, load, lock, write_json
from . import dfm14, review, runtime


def verify(kind,root,output):
    manifest=load(root/'manifest.json')
    if kind=='generate':
        from dfm14.production import pins
        if manifest['code_pins']!=pins():raise ValueError('Generation dependencies changed')
        if manifest['attempts_per_slot']!=2:raise ValueError('Expected one retry')
        if file_hash(root/'authorization.json')!=manifest['authorization_sha256'] or not load(root/'authorization.json')['production_authorized']:
            raise ValueError('Generation authorization changed')
        if not (root/'seed-manifest.json').exists():raise ValueError('Missing seed manifest')
    else:
        ready=load(root/'readiness.json')
        if ready['status']!='cpu_complete_ready_for_gpu' or ready['manifest_sha256']!=file_hash(root/'manifest.json'):
            raise ValueError('Input readiness changed')
        if manifest['status']!='ready_for_gpu_audit':raise ValueError('Unprepared audit')
        old=load(output/'configuration.json') if (output/'configuration.json').exists() else None
        if old and (old['manifest_sha256']!=file_hash(root/'manifest.json') or old['model']!=dfm14.Audit.model):
            raise ValueError('Wrong historical audit campaign')
    config=dict(kind=kind,source_manifest_sha256=file_hash(root/'manifest.json'),
        review_policy=review.VERSION,thinking=False,retries=1,admission_spacing=0,backoff_seconds=0,
        implementation={str(p.resolve()):file_hash(p) for p in Path(__file__).parent.glob('*.py')},
        legacy_manifest_unchanged=True)
    path=output/'pipeline/configuration.json'
    if path.exists() and load(path)!=config:raise ValueError('Shared runtime changed; review migration before resealing')
    write_json(path,config)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=('audit','generate'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--concurrency',type=int,default=256)
    parser.add_argument('--ports',default='8800,8801,8802,8803,8804,8805,8806,8807')
    args=parser.parse_args()
    ports=[int(p) for p in args.ports.split(',')]
    if len(ports)!=len(set(ports)) or not 1<=args.concurrency<=1024:parser.error('Unique ports; concurrency 1..1024')
    root=args.root.resolve();output=(args.output or root).resolve()
    with lock(output/'.controller.lock'):
        verify(args.kind,root,output)
        ctx=mp.get_context('spawn');children=[];stopping=False
        def stop(*_):
            nonlocal stopping
            stopping=True
            for child in children:
                if child.is_alive():os.kill(child.pid,signal.SIGTERM)
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        state=output/'pipeline/state.json'
        try:
            for port in ports:
                child=ctx.Process(target=runtime.worker,args=(args.kind,root,output,f'http://127.0.0.1:{port}/v1',args.concurrency))
                child.start();children.append(child)
            write_json(state,dict(phase='running',pid=os.getpid(),worker_pids=[c.pid for c in children],
                                 concurrency_per_endpoint=args.concurrency,ports=ports))
            # Supervise all children; a failed child must not remain unnoticed behind a busy one.
            while any(c.is_alive() for c in children):
                for child in children:
                    child.join(timeout=.1)
                    if child.exitcode not in (None,0):
                        stop()
                        raise RuntimeError(f'Worker {child.pid} exited {child.exitcode}')
            counts=Counter()
            pattern='jobs/*/receipt.json' if args.kind=='generate' else '*/receipt.json'
            for path in output.glob(pattern):counts.update(load(path).get('counts',{}))
            write_json(state,dict(phase='stopped' if stopping else 'complete',counts=dict(counts),training_ready=False))
        except BaseException as exc:
            write_json(state,dict(phase='failed',error=repr(exc)))
            raise
        finally:
            for child in children:
                if child.is_alive():os.kill(child.pid,signal.SIGTERM)
            for child in children:child.join()


if __name__=='__main__':main()
