"""Two explicitly agent-authored cached-source corrections, then unchanged review."""
import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import aiohttp

from scripts import dfm13_search_cached_repairs as repairs
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_critic_free_control as criticfree
from scripts import dfm13_search_json_mode_probe as probe
from scripts import dfm13_search_adjudication_retry as bounded

ROOT = Path('data/dfm13/search-source-checked-drafts-20261001')
MS = 'https://www.businessinsider.com/microsoft-layoffs-hit-security-devices-sales-gaming-2025-1'
LFC = 'https://www.liverpoolfc.com/news/alisson-becker-why-i-believe-we-have-started-season-so-well'
ANSWERS = {
    '12490c96': (
        "The available January 2025 report describes cuts affecting several Microsoft departments, including security, rather than the elimination of the entire security unit. A Microsoft spokesperson characterized the cuts as small and said they were separate from the performance-based job cuts reported elsewhere. "
        "[Source](" + MS + ").\n\n"
        "That report does not establish a specific motive for the security-unit cuts. It would therefore be speculation to say that AI automation or reduced commitment to cybersecurity caused them. The report also describes Microsoft's expanded Secure Future Initiative and security's role in employee evaluations. "
        "[Source](" + MS + ")."),
    '0cfb74ac': (
        "For Liverpool's 2024-25 season, a useful explanation comes from Alisson's September 10, 2024 interview: Slot's clear tactical instructions, strong work-rate, and defending as a whole team. He also highlighted Salah and Luis Diaz contributing without the ball, not just in attack. "
        "[Liverpool's interview](" + LFC + ").\n\n"
        "Those are plausible foundations for a strong season: players understand their roles, and the forwards help the team defend. This is an explanation based on the early-season interview, not a verified assessment of every match up to your March 27, 2025 question. I would not use later title results, final scoring totals or subsequent transfers to explain what had happened by that date."),
}
FINDINGS = {
    '0cfb74ac': 'Repair still mixes later transfers and Jota tragedy into the 2024-25 as-of answer; no citations. Raw reviewer missed the temporal defect.',
    '12490c96': 'Automated keep still cites July 2026 AI investment as context for April 2025. Withheld independently; do not promote.',
    '25bdd9ac': 'Verified image URLs reduced, but links still do not display logos; no citation to supporting page. Asset URL is not independently retrieved page content.',
    '42c1b060': 'Some later events removed, but 50-percent steel/aluminum claim lacks explicit April 15 date support and answer has no citations.',
    '4f8af9d1': 'Generator admits incomplete checklist and dependence on prior answer for rarity; essential evidence false remains authoritative.',
    'b528d937': 'Generator admits absent qualifying price data, yet opening claims all constraints met and includes a 2024-listed restaurant. Not a completed recommendation.',
    'ceffc54d': 'Retains commercial numerical efficacy/research claims without reliable dated study support or citations. Medical truth not certified by agreement with cached commercial text.',
    'e19e0b36': 'Still asserts exhaustive absence of a federal Bluetooth law and broad applicability from summaries; no answer citations. Legal scope remains unverified.',
}


def exact_passage(body, start_text, end_text):
    start = body.index(start_text)
    end = body.index(end_text, start) + len(end_text)
    return dict(start=start, end=end, text=body[start:end])


def prepare():
    if ROOT.exists():
        raise ValueError('new root required')
    manifest = repairs.verify(repairs.ROOT)
    jobs = []
    pins = {str(p.resolve()): base.file_hash(p) for p in
            (Path(__file__), Path(repairs.__file__), Path(criticfree.__file__), Path(probe.__file__),
             Path(bounded.__file__), repairs.ROOT / 'jobs.json', repairs.ROOT / 'campaign-ledger.json')}
    for source_job in repairs.read(repairs.ROOT / 'jobs.json'):
        prefix = source_job['id'][:8]
        if prefix not in ANSWERS:
            continue
        job = deepcopy(source_job)
        cache_path = Path(job['cache_snapshot'])
        pins[str(cache_path.resolve())] = base.file_hash(cache_path)
        url = MS if prefix == '12490c96' else LFC
        page = next(p for p in repairs.read(cache_path)['data'] if p['url'] == url)
        body = page['content']
        if prefix == '12490c96':
            passages = [exact_passage(body, '[Microsoft](https://www.businessinsider.com/recent-company-layoffs',
                                     'wrote in an email to Microsoft employees last year.')]
        else:
            passages = [exact_passage(body, 'Published 10th September 2024', 'By Glenn Price'),
                        exact_passage(body, "Alisson Becker believes Liverpool's strong start", 'at the beginning of the season.')]
        # Exact cached substrings, with offsets; no navigation or unrelated later article.
        job['pages'] = {url: dict(url=url, title=page.get('title', ''),
            body='\n\n'.join(p['text'] for p in passages), excerpts=passages,
            full_content_sha256=hashlib.sha256(body.encode()).hexdigest())}
        job['hint'] = 'Agent-authored source-checked draft, not a new teacher generation: ' + FINDINGS[prefix]
        candidate = repairs.repaired_candidate(job, ANSWERS[prefix])
        candidate['correction_provenance']['author_type'] = 'coding_agent_manual_draft'
        candidate['correction_provenance']['teacher_generated'] = False
        folder = ROOT / 'records' / job['id']
        base.atomic(folder / 'candidate.json', candidate)
        job['candidate'] = candidate
        jobs.append(job)
        pins[str((folder / 'candidate.json').resolve())] = base.file_hash(folder / 'candidate.json')
    if len(jobs) != 2:
        raise ValueError('two corrections required')
    base.atomic(ROOT / 'jobs.json', jobs)
    pins[str((ROOT / 'jobs.json').resolve())] = base.file_hash(ROOT / 'jobs.json')
    base.atomic(ROOT / 'independent-findings.json', dict(source=str(repairs.ROOT), findings=FINDINGS,
        scope='Agent inspection of saved text, not external factual certification.', admission_authorized=False))
    base.atomic(ROOT / 'manifest.json', dict(
        **{k: manifest[k] for k in ('tokenizer_dir', 'context_tokens', 'model', 'endpoints')},
        pins=pins, total=2, paid_calls=0, generation_calls=0, admission_authorized=False))


async def run():
    manifest = repairs.verify(ROOT)
    os.environ.pop('JINA_API_KEY', None)
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), calls=2, max_requests_per_endpoint=1, paid_calls=0))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(manifest['tokenizer_dir'], local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def one(index, job):
            folder = ROOT / 'records' / job['id']
            try:
                candidate = job['candidate']
                tokens = tokenizer.apply_chat_template(candidate['messages'], tools=candidate['tools'],
                    tokenize=True, add_generation_prompt=False, enable_thinking=False)
                if len(tokens) > manifest['context_tokens']:
                    raise ValueError('context exceeded')
                base.atomic(folder / 'render.json', dict(teacher_rendered_tokens=len(tokens),
                    student_window_validation='pending', admission_authorized=False))
                payload = dict(requirements=dict(original_user_prompt=job['sample']['prompt'],
                    original_timestamp=job['sample']['original_timestamp'], retrieval_date='2026-10-01'),
                    answer=candidate['messages'][-1]['content'], pages=job['pages'], verified_checks=[])
                model = base.Model(probe.ModeSession(session, 'json_object', folder), tokenizer,
                                   manifest, manifest['endpoints'][index], 600)
                raw = await model.ask(criticfree.messages(payload), bounded.SCHEMA, None, folder, 'review')
                base.atomic(folder / 'raw-review.json', raw)
                reviewed = bounded.derive(raw, job['pages'], payload['answer'])
                base.atomic(folder / 'review.json', reviewed)
                outcome = dict(status='reviewed', **repairs.gated_outcome(job['id'], reviewed['verdict'], True))
            except Exception as error:
                outcome = dict(status='error', error=str(error), admission_authorized=False)
            base.atomic(folder / 'outcome.json', outcome)
            return outcome
        results = await asyncio.gather(*(one(i, j) for i, j in enumerate(repairs.read(ROOT / 'jobs.json'))))
    ledger = repairs.read(repairs.ROOT / 'campaign-ledger.json')
    for row in ledger['rows']:
        prefix = row['id'][:8]
        if prefix in FINDINGS:
            row.update(selected=None, independent_repair_findings=FINDINGS[prefix], disposition='independent_repair_hold')
            path = ROOT / 'records' / row['id'] / 'outcome.json'
            if path.exists():
                row['source_checked_draft'] = str(path.parent / 'candidate.json')
                row['source_checked_review'] = str(path)
                row['disposition'] = 'source_checked_draft_pending_manual_review'
        if prefix in repairs.inventory.HOLDS:
            row.update(selected=None, disposition='independent_hold', independent_hold=repairs.inventory.HOLDS[prefix])
    from collections import Counter
    ledger.update(counts=dict(Counter(r['disposition'] for r in ledger['rows'])),
                  admission_authorized=False, production_ready=False)
    base.atomic(ROOT / 'campaign-ledger.json', ledger)
    base.atomic(ROOT / 'finished.json', dict(results=results, paid_calls=0, admission_authorized=False))


if __name__ == '__main__':
    prepare()
    asyncio.run(run())
