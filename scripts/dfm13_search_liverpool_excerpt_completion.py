"""Complete one cached evidence excerpt, preserving the earlier draft and review."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path

import aiohttp
from scripts import dfm13_search_source_checked_drafts as drafts
from scripts import dfm13_search_cached_repairs as repairs
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_critic_free_control as criticfree
from scripts import dfm13_search_json_mode_probe as probe
from scripts import dfm13_search_adjudication_retry as bounded

ROOT = Path('data/dfm13/search-source-checked-drafts-20261001-v2')


async def run():
    if ROOT.exists():
        raise ValueError('new root required')
    manifest = repairs.verify(drafts.ROOT)
    job = deepcopy(next(j for j in repairs.read(drafts.ROOT / 'jobs.json') if j['id'].startswith('0cfb74ac')))
    raw = repairs.read(Path(job['cache_snapshot']))
    page = next(p for p in raw['data'] if p['url'] == drafts.LFC)
    extra = drafts.exact_passage(page['content'], 'Alisson reserved special praise',
                                "I think this is what is making us win these games at the beginning of the season.")
    job['pages'][drafts.LFC]['excerpts'].append(extra)
    job['pages'][drafts.LFC]['body'] += '\n\n' + extra['text']
    candidate = repairs.repaired_candidate(job, job['candidate']['messages'][-1]['content'])
    candidate['correction_provenance'].update(author_type='coding_agent_manual_draft', teacher_generated=False,
        evidence_correction='Previous excerpt ended before the Salah/Diaz paragraph; append exact cached paragraph. Answer unchanged.')
    folder = ROOT / 'records' / job['id']
    base.atomic(folder / 'candidate.json', candidate)
    base.atomic(ROOT / 'job.json', job)
    paths = [Path(__file__), Path(drafts.__file__), Path(repairs.__file__), Path(criticfree.__file__),
             Path(probe.__file__), Path(bounded.__file__), drafts.ROOT / 'campaign-ledger.json',
             Path(job['cache_snapshot']), ROOT / 'job.json', folder / 'candidate.json']
    base.atomic(ROOT / 'manifest.json', dict(pins={str(p.resolve()): base.file_hash(p) for p in paths},
        paid_calls=0, generation_calls=0, review_calls=1, admission_authorized=False))
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), calls=1, paid_calls=0))
    os.environ.pop('JINA_API_KEY', None)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(manifest['tokenizer_dir'], local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        try:
            tokens = tokenizer.apply_chat_template(candidate['messages'], tools=candidate['tools'],
                tokenize=True, add_generation_prompt=False, enable_thinking=False)
            if len(tokens) > manifest['context_tokens']:
                raise ValueError('context exceeded')
            base.atomic(folder / 'render.json', dict(teacher_rendered_tokens=len(tokens), student_window_validation='pending'))
            payload = dict(requirements=dict(original_user_prompt=job['sample']['prompt'],
                original_timestamp=job['sample']['original_timestamp'], retrieval_date='2026-10-01'),
                answer=candidate['messages'][-1]['content'], pages=job['pages'], verified_checks=[])
            model = base.Model(probe.ModeSession(session, 'json_object', folder), tokenizer,
                               manifest, manifest['endpoints'][0], 600)
            raw = await model.ask(criticfree.messages(payload), bounded.SCHEMA, None, folder, 'review')
            base.atomic(folder / 'raw-review.json', raw)
            reviewed = bounded.derive(raw, job['pages'], payload['answer'])
            base.atomic(folder / 'review.json', reviewed)
            outcome = dict(status='reviewed', **repairs.gated_outcome(job['id'], reviewed['verdict'], True))
        except Exception as error:
            outcome = dict(status='error', error=str(error), admission_authorized=False)
    base.atomic(folder / 'outcome.json', outcome)
    ledger = repairs.read(drafts.ROOT / 'campaign-ledger.json')
    for row in ledger['rows']:
        if row['id'] == job['id']:
            row.update(selected=None, source_checked_draft=str(folder / 'candidate.json'),
                       source_checked_review=str(folder / 'outcome.json'),
                       disposition='source_checked_draft_pending_manual_review')
    base.atomic(ROOT / 'campaign-ledger.json', ledger)
    base.atomic(ROOT / 'finished.json', dict(outcome=outcome, paid_calls=0, admission_authorized=False))


if __name__ == '__main__':
    asyncio.run(run())
