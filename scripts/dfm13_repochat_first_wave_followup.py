"""One localized repair and one fresh failed-generation retry, separately reviewed."""
import asyncio
import fcntl
from pathlib import Path
import time
from types import SimpleNamespace
from scripts import dfm13_repochat_qa_filtered as f
from scripts import dfm13_repochat_targeted_repair as repair

b = f.n.b
ROOT = f.n.ROOT/'first-wave-followup'
SCRCPY = '56ca164595e062eb23b9f4b18cadd36663ded8c2f400fab8aa72c1dd43341dab'
WACOM = '3ccaaed101420e4aa390861ee76957e22ba728e6710274cd1cdddefadcf846b2'


async def run():
    f.selected_tasks()
    f.verify_gate()
    original = f.n.ROOT/'first'
    tasks = b.load(original/'selection.json')['tasks']
    paths = [Path(__file__), Path(repair.__file__), f.n.ROOT/'filtered-manual-gate.json',
             original/'selection.json', original/'trajectories'/WACOM/'outcome.json']
    receipt = {'pins': {str(p.resolve()): b.file_sha(p) for p in paths},
               'authorization': 'User requests localized scrcpy OTG qualification and one separate bounded fresh Wacom retry.',
               'wait_for': str(f.ROOT/'completion.json'), 'max_wait_seconds': 7200,
               'wacom_attempts': 1, 'admission': False}
    if (ROOT/'queue.json').exists() and b.load(ROOT/'queue.json') != receipt:
        raise ValueError('followup pin drift')
    b.save(ROOT/'queue.json', receipt)
    deadline = time.monotonic()+7200
    while not (f.ROOT/'completion.json').exists():
        if time.monotonic() >= deadline:
            raise TimeoutError('preceding QA run did not complete; no inference launched')
        await asyncio.sleep(10)
    # Hold the shared campaign lock through both followups to prevent client overlap.
    with (f.n.ROOT/'controller.lock').open('a') as campaign:
        while True:
            try:
                fcntl.flock(campaign, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('campaign lock not released')
                await asyncio.sleep(1)
        f.selected_tasks()
        f.verify_gate()
        for path, digest in receipt['pins'].items():
            if b.file_sha(path) != digest:
                raise ValueError('queued input drift')
        repair.ROOT = ROOT/'scrcpy'
        repair.FEEDBACK = {SCRCPY: 'Narrow factual qualification only: the pinned README explicitly says USB debugging is not required in OTG mode. Your answer lists OTG but states USB debugging is required without exception. Read README and doc/otg.md. Qualify that requirement for normal mirroring/control while noting the OTG exception. Preserve the supported overview. Do not execute commands or claim device testing.'}
        repair.q = SimpleNamespace(SOURCE=original, BASELINE=f.n.ROOT,
                                   probe=repair.q.probe, __file__=repair.q.__file__)
        await repair.run()
        await f.n.previous.audit.run(SimpleNamespace(source=repair.ROOT, root=repair.ROOT/'independent-review', ids=None, thinking=True))
        retry = ROOT/'wacom'
        selected = [t for t in tasks if t['id'] == WACOM]
        if len(selected) != 1:
            raise ValueError('retry identity')
        b.save(retry/'selection.json', {'tasks': selected, 'admission': False})
        ready = b.load(f.n.ROOT/'ready.json')
        b.save(retry/'ready.json', {**ready, 'selection_sha256': b.file_sha(retry/'selection.json'),
            'pins': {**ready['pins'], **receipt['pins']}})
        f.n.previous.generation.CONTROLS = ()
        await f.n.previous.generation.run(SimpleNamespace(root=retry, authorized=True,
            endpoints=','.join(f'http://localhost:{p}/v1' for p in range(8800,8808)),
            model='dfm13-gemma4', per_endpoint=8, max_turns=16, max_tokens=8192))
        await f.n.previous.audit.run(SimpleNamespace(source=retry, root=retry/'independent-review', ids=None, thinking=True))
        b.save(ROOT/'completion.json', {'admission': False,
            'scrcpy_review_sha256': b.file_sha(repair.ROOT/'independent-review/summary.json'),
            'wacom_review_sha256': b.file_sha(retry/'independent-review/summary.json')})


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run())
