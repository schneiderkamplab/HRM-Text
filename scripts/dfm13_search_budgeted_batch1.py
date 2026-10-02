"""First eight screened remaining cases; stop for independent manual review."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
from pathlib import Path
import re

from scripts import dfm13_search_budgeted_pilot as pilot

base = pilot.base
ROOT = Path('data/dfm13/search-budgeted-remaining-batch1-20261001-v2')
RECEIPT = Path('docs/reports/dfm13_search_budgeted_pilot8_manual_assessment_20261001.json')
SELECTION = {
    '07b395e8': ['https://pl.wikisource.org/wiki/Encyklopedia_staropolska/Imiona_staro-polskie', 'https://pl.wikipedia.org/wiki/Imiona_s%C5%82owia%C5%84skie'],
    'ea5c02b1': ['https://segu-geschichte.de/deutsche-teilung/', 'https://www.planet-schule.de/schwerpunkt/ticktack-zeitreise-mit-lisa-und-lena/ddr-unterricht-100.html'],
    '5235c2dc': ['https://www.jra.go.jp/keiba/overseas/country/america/santaanitapark.html', 'https://www.jairs.jp/contents/courses/us.html'],
    '7213d507': ['https://next.gazeta.pl/next/7,151003,12858742,biedronka-przegrala-w-sadzie-spor-o-nazwe-forum-pracownikow.html'],
    'ea1b1cdd': ['https://rmsandu.net/blog/2024-06-15-sdxlfinetuning.html', 'https://replicate.com/blog/fine-tune-sdxl'],
    'e7e61db7': ['https://www.litcharts.com/lit/sinners-in-the-hands-of-an-angry-god/literary-devices', 'https://www.supersummary.com/sinners-in-the-hands-of-an-angry-god/literary-devices/'],
    '82071459': ['https://en.moonbooks.org/Articles/How-to-list-and-download-all-files-from-an-url-directory-using-python-/', 'https://alexwlchan.net/2020/downloading-files-with-python/'],
    'ae46b63d': ['https://www.waze.com/discuss/t/live-map-parameter-for-permit/203381'],
}
NOTES = {
    '07b395e8': 'Historical compound-name sources; distinguish name elements from productive affixes.',
    'ea5c02b1': 'Teaching material for German division; proposed lesson design is creative, not a verified curriculum mandate.',
    '5235c2dc': 'Japanese racing authorities describing US venues; amenities proposal must be labelled hypothetical.',
    '7213d507': 'Dated 2012 article directly concerns the requested domain dispute; attribute reporting, not legal advice.',
    'ea1b1cdd': 'SDXL-specific training accounts; exclude blocked Reddit and 2026 paper. Do not generalize one experiment to all fine-tunes.',
    'e7e61db7': 'Available literary analysis passages; exclude paid-only/navigation material and distinguish interpretation from textual fact.',
    '82071459': 'File-download examples relevant to href extraction; generated code remains unexecuted and must not claim testing.',
    'ae46b63d': 'Direct Live Map permit discussion; do not substitute mobile-app settings or claim universal/current support.',
}
INSTRUCTION = (
    '\nGeneration-only evidence discipline: Answer concisely enough to finish within 512 output tokens. '
    'Do not say latest, current, newest, or best without dated comparative evidence at the original question date. '
    'Keep model/product versions and variants separate, especially Base versus Instruct/post-trained; preserve benchmark settings. '
    'Attribute source claims and qualify uncertain technical or promotional claims; agreement with a page is not independent verification. '
    'Do not infer missing result rows, dates, numbers, or universal conclusions from navigation or titles. '
    'Creative proposals and examples may be original but must be identified as proposals, not source facts. '
    'Cite exact observed URLs for factual source claims. Preserve the original date; do not relabel historical questions as current. '
    'If essential evidence is absent, identify the specific limitation without inventing an answer.')
ORIGINAL_PARAGRAPHS = pilot.paragraphs


def filtered_paragraphs(payload, allowed):
    result = []
    candidates = ORIGINAL_PARAGRAPHS(payload, allowed)
    # Preserve short but essential native permit syntax with its exact offsets.
    for page in payload.get('data', []):
        if page.get('url') in allowed and '/live-map-parameter-for-permit/' in page['url']:
            for match in re.finditer(r'\S[^\n]*(?:\n(?!\n)[^\n]*)*', page.get('content', '')):
                if 'rp_subscription=' in match.group() or 'Where <name>' in match.group():
                    candidates.append(dict(url=page['url'], title=page.get('title', ''),
                        start=match.start(), end=match.end(), text=match.group(),
                        full_content_sha256=pilot.hashlib.sha256(page['content'].encode()).hexdigest()))
    for chunk in candidates:
        text = chunk['text']
        lower = text.lower()
        url = chunk['url']
        if '/live-map-parameter-for-permit/' in url:
            if not any(x in lower for x in ('parameter', 'rp_subscription=', 'where <name>', 'vignette', '2019', 'infrastructure')):
                continue
            if text.startswith('!['):
                continue
            result.append(chunk)
            continue
        if 'jairs.jp' in url or 'santaanitapark' in url:
            if not any(x in text for x in ('レストラン', 'レジャー', 'ブティック', 'カジノ', 'アールデコ')):
                continue
        if 'litcharts' in url or 'supersummary' in url:
            if not any(x in lower for x in ('accumulatio', 'metaphor', 'simile', 'imagery', 'thus it is that natural men')):
                continue
        if 'segu-geschichte' in url or 'planet-schule' in url:
            if not any(x in lower for x in ('alliierten', 'grotewohl', 'regierungserklärungen', 'demokratie und diktatur')):
                continue
        if any(term in lower for term in ('cookie', 'sign up', 'log in', 'subscribe',
                'privacy policy', 'all rights reserved', 'skip to content', 'performing security verification')):
            continue
        plain = re.sub(r'!?\[[^\]]*\]\([^)]*\)', '', text)
        if text.startswith('[![') or sum(c.isalpha() for c in plain) < 70 or text.count('https://') > 3:
            continue
        result.append(chunk)
    return result


class GenerationSession(pilot.GenerationSession):
    def post(self, *args, **kwargs):
        request = deepcopy(kwargs['json'])
        request['messages'][0]['content'] += INSTRUCTION + '\nCase-specific caution: ' + NOTES[self.folder.parent.name[:8]]
        kwargs['json'] = request
        return super().post(*args, **kwargs)


def prepare():
    receipt = pilot.previous.read(RECEIPT)
    for item in receipt['pins']:
        if base.file_hash(Path(item['path'])) != item['sha256']:
            raise ValueError('manual receipt parent changed')
    pilot.PLANS = {key: (urls, []) for key, urls in SELECTION.items()}
    pilot.paragraphs = filtered_paragraphs
    pilot.prepare(ROOT)
    manifest = pilot.previous.read(ROOT / 'manifest.json')
    for path in (Path(__file__), RECEIPT):
        manifest['pins'][str(path.resolve())] = base.file_hash(path)
    manifest.update(batch_gate='Stop after these eight; independent manual assessment before any remaining generation.',
                    next_batch_authorized=False)
    base.atomic(ROOT / 'manifest.json', manifest)
    holds = [dict(id=row['id'], candidate=row['candidate'], reason=row.get('correction', row.get('caveat')),
                  admission_authorized=False) for row in receipt['pilot']
             if row['id'].startswith(('0bdd931b', '64b59e0d', 'bfd8c382'))]
    base.atomic(ROOT / 'manual-holds.json', dict(receipt=str(RECEIPT), receipt_sha256=base.file_hash(RECEIPT), rows=holds))
    base.atomic(ROOT / 'screening.json', dict(selected=SELECTION, rationales=NOTES,
        remaining_unlaunched=48, remaining_status='Await first-batch manual review and individual evidence selection',
        factual_eligibility_certified=False, generation_batch_limit=8, paid_calls=0, admission_authorized=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    else:
        with (ROOT / 'run.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            pilot.GenerationSession = GenerationSession
            asyncio.run(pilot.run(argparse.Namespace(root=ROOT, concurrency_per_server=8, timeout=600)))
