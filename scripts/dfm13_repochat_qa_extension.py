"""Three explicitly scope-rechecked descriptive QA attempts, without admission."""
import asyncio
import fcntl
from pathlib import Path
from types import SimpleNamespace
from scripts import dfm13_repochat_remaining_candidates as prepared

ROOT = Path('data/dfm13/repochat-qa-extension-20261001-v1')
REPOSITORIES = {'langchain-ai/langgraph', 'eschnett/NotDijkstra.jl', 'DavidO000/non_empty_continuous'}


async def run():
    b = prepared.b
    source = b.load(prepared.ROOT / 'ready.json')
    for path, digest in source['pins'].items():
        if b.file_sha(path) != digest:
            raise ValueError('source pin drift: ' + path)
    tasks = [t for t in b.load(prepared.ROOT / 'selection.json')['tasks'] if t['repository'] in REPOSITORIES]
    if len(tasks) != 3:
        raise ValueError('expected three bounded descriptive tasks')
    selection = {'tasks': tasks, 'admission': False}
    path = ROOT / 'selection.json'
    if path.exists() and b.load(path) != selection:
        raise ValueError('selection drift')
    b.save(path, selection)
    ready = {**source, 'selection_sha256': b.file_sha(path),
             'scope': 'project purpose and documented usage/use case; no implementation or exhaustive claims',
             'pins': {**source['pins'], str(Path(__file__).resolve()): b.file_sha(__file__)}}
    if (ROOT / 'ready.json').exists() and b.load(ROOT / 'ready.json') != ready:
        raise ValueError('configuration drift')
    b.save(ROOT / 'ready.json', ready)
    prepared.generation.CONTROLS = ()
    await prepared.generation.run(SimpleNamespace(root=ROOT, authorized=True,
        endpoints=','.join(f'http://localhost:{p}/v1' for p in range(8800,8808)),
        model='dfm13-gemma4', per_endpoint=8, max_turns=16, max_tokens=8192))
    await prepared.audit.run(SimpleNamespace(source=ROOT, root=ROOT/'independent-review', ids=None, thinking=True))
    b.save(ROOT/'completion.json', {'admission': False,
        'review_sha256': b.file_sha(ROOT/'independent-review/summary.json')})


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run())
