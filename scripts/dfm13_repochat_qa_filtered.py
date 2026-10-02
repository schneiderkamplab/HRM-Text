"""Launch only independently scope-approved QA IDs after a pinned manual gate."""
import asyncio
import fcntl
from pathlib import Path
from types import SimpleNamespace
from scripts import dfm13_repochat_qa_next as n

ASSESSMENT = Path('docs/reports/dfm13_repochat_next_source_assessment_20261001.json')
DECISIONS = Path('docs/reports/dfm13_repochat_next_source_decisions_20261001.json')
ROOT = n.ROOT/'eligible-74'


def selected_tasks():
    b = n.b
    receipt = b.load(ASSESSMENT)
    for path, digest in [(n.ROOT/'ready.json', receipt['ready_sha256']),
                         (n.ROOT/'selection.json', receipt['selection_sha256']),
                         (DECISIONS, receipt['manual_decisions_sha256'])]:
        if b.file_sha(path) != digest:
            raise ValueError('assessment pin drift: '+str(path))
    ready = b.load(n.ROOT/'ready.json')
    for path, digest in ready['pins'].items():
        if b.file_sha(path) != digest:
            raise ValueError('implementation/source pin drift: '+path)
    tasks = b.load(n.ROOT/'selection.json')['tasks'][8:]
    records = receipt['records']
    if len(records) != 81 or len({r['id'] for r in records}) != 81:
        raise ValueError('scope record coverage')
    if {r['id'] for r in records} != {t['id'] for t in tasks}:
        raise ValueError('scope identity mismatch')
    by_id = {t['id']: t for t in tasks}
    for record in records:
        task = by_id[record['id']]
        if any(record[k] != task[k] for k in ('query','repository','source_index','winner')):
            raise ValueError('task provenance drift')
        if b.file_sha(record['snapshot_path']) != record['snapshot_sha256']:
            raise ValueError('snapshot drift')
        if b.load(record['snapshot_path'])['commit'] != record['commit']:
            raise ValueError('commit drift')
        for evidence in record['evidence']:
            if b.file_sha(evidence['path']) != evidence['sha256']:
                raise ValueError('evidence drift')
    eligible = {r['id'] for r in records if r['status'] == 'eligible'}
    held = {r['id'] for r in records if r['status'] != 'eligible'}
    if len(eligible) != 74 or len(held) != 7 or eligible != set(receipt['eligible_ids']) or held != set(receipt['held_ids']):
        raise ValueError('exact eligible IDs mismatch')
    return [t for t in tasks if t['id'] in eligible], ready


def verify_gate():
    gate = n.b.load(n.ROOT/'filtered-manual-gate.json')
    if gate.get('release_eligible_74') is not True or gate.get('admission') is not False:
        raise ValueError('manual gate not released')
    required = {str(ASSESSMENT), str(n.ROOT/'first/completion.json')}
    if not required.issubset(gate['evidence_pins']) or not gate.get('independent_manual_report'):
        raise ValueError('missing independent assessment')
    if gate['independent_manual_report'] not in gate['evidence_pins']:
        raise ValueError('unpinned manual assessment')
    for path, digest in gate['evidence_pins'].items():
        if n.b.file_sha(path) != digest:
            raise ValueError('gate evidence drift')
    return gate


async def run():
    tasks, ready = selected_tasks()
    verify_gate()
    b = n.b
    selection = {'tasks': tasks, 'admission': False}
    if (ROOT/'selection.json').exists() and b.load(ROOT/'selection.json') != selection:
        raise ValueError('filtered selection drift')
    b.save(ROOT/'selection.json', selection)
    pins = {**ready['pins'], **{str(Path(p).resolve()): b.file_sha(p) for p in
            [__file__, ASSESSMENT, DECISIONS, n.ROOT/'filtered-manual-gate.json']}}
    filtered_ready = {**ready, 'pins': pins, 'selection_sha256': b.file_sha(ROOT/'selection.json')}
    if (ROOT/'ready.json').exists() and b.load(ROOT/'ready.json') != filtered_ready:
        raise ValueError('filtered ready drift')
    b.save(ROOT/'ready.json', filtered_ready)
    b.save(ROOT/'scope-readiness.json', n.previous.controls_ready())
    n.previous.generation.CONTROLS = ()
    await n.previous.generation.run(SimpleNamespace(root=ROOT, authorized=True,
        endpoints=','.join(f'http://localhost:{p}/v1' for p in range(8800,8808)),
        model='dfm13-gemma4', per_endpoint=8, max_turns=16, max_tokens=8192))
    await n.previous.audit.run(SimpleNamespace(source=ROOT, root=ROOT/'independent-review', ids=None, thinking=True))
    b.save(ROOT/'completion.json', {'admission': False,
           'review_sha256': b.file_sha(ROOT/'independent-review/summary.json')})


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    # Same campaign lock excludes the unfiltered rest runner and duplicate clients.
    with (n.ROOT/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run())
