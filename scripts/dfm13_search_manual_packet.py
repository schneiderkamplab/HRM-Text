"""Blind manual packets bound to exact saved candidate text and tool evidence."""
import json
from pathlib import Path

from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_cached_repairs as repairs

ROOT = Path('data/dfm13/search-manual-heldout-20261001-v2')
SOURCE = Path('data/dfm13/search-calibration-100-20261001-followup2')


def packet(candidate, sample):
    messages = candidate['messages']
    if messages[-1]['role'] != 'assistant' or messages[-1].get('tool_calls'):
        raise ValueError('missing final saved answer')
    pages = {}
    observations = []
    for index, message in enumerate(messages):
        if message['role'] != 'tool':
            continue
        value = base.strict_json(message['content'])
        observations.append(dict(message_index=index, value=value))
        for page in value.get('results', []):
            if not isinstance(page.get('body'), str) or not page['body'].strip():
                continue
            url = page['url']
            if url in pages and pages[url] != page:
                raise ValueError('conflicting delivered page versions')
            pages[url] = page
    if not pages:
        raise ValueError('no actual delivered page content')
    return dict(id=sample['id'], sample=sample, answer=messages[-1]['content'],
                candidate=candidate, pages=pages, tool_observations=observations,
                admission_authorized=False)


def main():
    if ROOT.exists():
        raise ValueError('new root required')
    source = repairs.SOURCE / 'jobs.json'
    jobs = repairs.read(source)
    pins = {str(source.resolve()): base.file_hash(source), str(Path(__file__).resolve()): base.file_hash(Path(__file__))}
    rows = []
    for job in jobs:
        if job['id'][:8] not in repairs.HELDOUT:
            continue
        path = SOURCE / 'records' / job['id'] / 'candidate.json'
        if path.exists():
            candidate = repairs.read(path)
            source_path = path
        else:
            candidate = job['candidate']
            source_path = source
        value = packet(candidate, job['sample'])
        value['source_candidate'] = str(source_path)
        value['source_sha256'] = base.file_hash(source_path)
        folder = ROOT / job['id']
        base.atomic(folder / 'packet.json', value)
        pins[str(source_path.resolve())] = base.file_hash(source_path)
        pins[str((folder / 'packet.json').resolve())] = base.file_hash(folder / 'packet.json')
        rows.append(dict(id=job['id'], packet=str(folder / 'packet.json'), manual_review='pending'))
    if len(rows) != 8:
        raise ValueError('eight heldout cases required')
    base.atomic(ROOT / 'queue.json', dict(cases=rows, pins=pins, admission_authorized=False,
        supersedes=str(repairs.ROOT / 'manual-heldout/queue.json'),
        correction='Bind answer and evidence to exact saved candidate rather than mixed-version reviewer inventory.',
        scope='Fresh to recent repair/control experiments, not unseen by all earlier model reviews.',
        review_instructions='Assess requirements, historical date, concrete facts, source quality and completeness. No model verdict supplied. Distinguish defects from evidence gaps; do not certify solely by source agreement.'))
    print(json.dumps(dict(manual_cases=len(rows), root=str(ROOT))))


if __name__ == '__main__':
    main()
