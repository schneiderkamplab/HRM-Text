"""Unchanged critic-free reviewer on eight exact saved manual-packet candidates."""
import asyncio
from collections import Counter
import os
from pathlib import Path

import aiohttp
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_cached_repairs as repairs
from scripts import dfm13_search_manual_packet as packets
from scripts import dfm13_search_critic_free_control as criticfree
from scripts import dfm13_search_json_mode_probe as probe
from scripts import dfm13_search_adjudication_retry as bounded

ROOT = Path('data/dfm13/search-heldout-cached-review-20261001')


def payload(packet):
    if packet['answer'] != packet['candidate']['messages'][-1]['content']:
        raise ValueError('answer/candidate mismatch')
    return dict(requirements=dict(original_user_prompt=packet['sample']['prompt'],
        original_timestamp=packet['sample']['original_timestamp'], retrieval_date='2026-10-01'),
        answer=packet['answer'], pages=packet['pages'], verified_checks=[])


async def run():
    if ROOT.exists():
        raise ValueError('new root required')
    queue_path = packets.ROOT / 'queue.json'
    queue = repairs.read(queue_path)
    for path, value in queue['pins'].items():
        if base.file_hash(Path(path)) != value:
            raise ValueError('manual packet pin mismatch')
    manifest = repairs.verify(repairs.ROOT)
    if len(queue['cases']) != 8:
        raise ValueError('bounded eight-case review required')
    paths = [Path(__file__), Path(packets.__file__), Path(criticfree.__file__), Path(probe.__file__),
             Path(bounded.__file__), queue_path, *[Path(r['packet']) for r in queue['cases']]]
    base.atomic(ROOT / 'manifest.json', dict(pins={str(p.resolve()): base.file_hash(p) for p in paths},
        total=8, paid_calls=0, generation_calls=0, manual_review_not_consulted=True,
        reviewer='unchanged critic-free compact JSON', max_attempts=1, admission_authorized=False))
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), queued=8, max_requests_per_endpoint=1))
    os.environ.pop('JINA_API_KEY', None)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(manifest['tokenizer_dir'], local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def one(index, entry):
            packet = repairs.read(Path(entry['packet']))
            folder = ROOT / 'records' / packet['id']
            try:
                model = base.Model(probe.ModeSession(session, 'json_object', folder), tokenizer,
                                   manifest, manifest['endpoints'][index], 600)
                raw = await model.ask(criticfree.messages(payload(packet)), bounded.SCHEMA, None, folder, 'review')
                base.atomic(folder / 'raw-review.json', raw)
                try:
                    reviewed = bounded.derive(raw, packet['pages'], packet['answer'])
                except ValueError as error:
                    reviewed = dict(verdict='needs_verification', reason=str(error))
                base.atomic(folder / 'review.json', reviewed)
                result = dict(status='reviewed', **repairs.gated_outcome(packet['id'], reviewed['verdict'], True))
            except Exception as error:
                result = dict(status='error', error=str(error), admission_authorized=False)
            base.atomic(folder / 'outcome.json', dict(result, packet=str(entry['packet']),
                packet_sha256=base.file_hash(Path(entry['packet']))))
            rows = [repairs.read(p) for p in (ROOT / 'records').glob('*/outcome.json')]
            base.atomic(ROOT / 'progress.json', dict(terminal=len(rows), total=8,
                counts=dict(Counter(r.get('verdict', r['status']) for r in rows)), paid_calls=0))
        await asyncio.gather(*(one(i, entry) for i, entry in enumerate(queue['cases'])))
    base.atomic(ROOT / 'finished.json', dict(repairs.read(ROOT / 'progress.json'), admission_authorized=False))


if __name__ == '__main__':
    asyncio.run(run())
