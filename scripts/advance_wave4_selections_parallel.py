"""Opt-in bounded CPU selector; takes the existing exclusive controller lock."""
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import multiprocessing
from pathlib import Path
import signal
import threading
import time

from dfm12.io import load, lock, write_json
from scripts.advance_wave4_selections import freeze
from scripts.select_baltic_translations import select


def select_one(root,pair,manifest):
    try:
        receipt=root/'translation-release'/pair/'receipt.json'
        if not receipt.exists() or not load(receipt).get('ready'):
            select(root,pair,manifest_path=manifest)
        return 'ready' if load(receipt)['ready'] else 'awaiting_reviews'
    except Exception as exc:
        return {'error':f'{type(exc).__name__}: {exc}'}


def cycle(root,manifest,workers,stop,executor_factory=None):
    if not 1<=workers<=4:raise ValueError('Use1..4 CPU selection workers')
    pairs=['-'.join(p) for p in load(root/'translations/config.json')['requested_pairs']]
    if len(pairs)!=len(set(pairs)):raise ValueError('Duplicate requested pair')
    components=[e['component'] for e in load(manifest)['components']]
    if len(components)!=len(set(components)):raise ValueError('Duplicate manifest component')
    tasks=[];outcomes={};owners={}
    for pair in pairs:
        matched=[n for n in components if any(n==r+'-'+pair or n.startswith(r+'-'+pair+'-part')
            for r in ('direct','institutional','pivot'))]
        for name in matched:
            if name in owners:raise ValueError('Component assigned to multiple pairs')
            owners[name]=pair
        if matched:tasks.append(pair)
        else:outcomes[pair]='no_available_parallel_supply'
    factory=executor_factory or (lambda:ProcessPoolExecutor(max_workers=workers,
        mp_context=multiprocessing.get_context('spawn')))
    iterator=iter(tasks);exhausted=False;pending={}
    def report():
        write_json(root/'translation-release/selection-status.json',dict(time=time.time(),
            pairs=outcomes,workers=workers,inflight=sorted(pending.values()),
            draining=stop.is_set(),cycle_complete=exhausted and not pending))
    with factory() as pool:
        while pending or not exhausted:
            while not exhausted and not stop.is_set() and len(pending)<workers:
                try:pair=next(iterator)
                except StopIteration:exhausted=True;break
                pending[pool.submit(select_one,root,pair,manifest)]=pair
            report()
            if not pending:break
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                pair=pending.pop(future)
                try:outcomes[pair]=future.result()
                except Exception as exc:outcomes[pair]={'error':f'{type(exc).__name__}: {exc}'}
            report()
    return outcomes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('data/dfm13/wave4'))
    parser.add_argument('--workers',type=int,choices=range(1,5),default=4)
    args=parser.parse_args();stop=threading.Event()
    # SIGTERM stops new dispatch, then drains current pair workers.
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    with lock(args.root/'translation-release/selection-advance.lock'):
        while not stop.is_set():
            manifest=freeze(args.root,Path('data/dfm13/baltic/translations/token-budgets.json'))
            if manifest is None:stop.wait(300);continue
            cycle(args.root,manifest,args.workers,stop)
            stop.wait(600)


if __name__=='__main__':main()
