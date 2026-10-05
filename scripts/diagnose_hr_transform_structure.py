"""Croatian-only, read-only structural diagnostics; no semantic certification."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from dfm12.io import digest, file_hash, load, write_json

# Exact Croatian labels, not a translation/reuse of the Persian classifier.
HEADINGS = frozenset(('Izvori', 'Izvor', 'Literatura', 'Vanjske poveznice', 'Poveznice',
    'Bilješke', 'Napomene', 'Reference', 'Sestrinski projekti', 'Vidi još',
    'Povezani članci', 'Životopis', 'Biografija', 'Povijest', 'Zemljopis',
    'Stanovništvo', 'Gospodarstvo', 'Promet', 'Kultura', 'Sport', 'Radnja',
    'Kritike', 'Nastanak', 'Ratna upotreba', 'Oprema', 'O procesu civilizacije'))
REFERENCE = frozenset(('Izvori', 'Izvor', 'Literatura', 'Vanjske poveznice', 'Poveznice',
                       'Bilješke', 'Napomene', 'Reference'))
LIST_HEADINGS = frozenset(('Diskografija', 'Filmografija', 'Bibliografija', 'Djela',
    'Vrste', 'Sinonimi', 'Popis vrsta', 'Glavne uloge', 'Uloge', 'Poznate osobe',
    'Ostale znamenitosti', 'Nagrade', 'Albumi', 'Singlovi'))
CATEGORY = re.compile(r'^(?:Životopisi, .+|Naselja u .+|Gradovi u .+|Općine u .+|'
    r'Sela u .+|Rijeke u .+|Planine u .+|Otoci u .+|Ratovi \d+\. stoljeća|'
    r'(?:Hrvatski|Hrvatske|Hrvatska|Srpski|Srpske|Bosanskohercegovački|Slovenski|'
    r'Njemački|Francuski|Britanski|Američki|Talijanski|Ruski|Španjolski|Austrijski) '
    r'(?:pjesnici|književnici|pisci|pjevači|pop pjevači|operni pjevači|glazbenici|'
    r'glumci|redatelji|sociolozi|filozofi|znanstvenici|astronomi|političari|'
    r'nogometaši|sportaši|slikari|skladatelji|prezimena|filmovi|gradovi)(?: iz [^.]+)?|'
    r'Otkrivači asteroida|Enologija|Sociolozi|Psihotropne tvari|Biljne porodice|'
    r'Biljke mesožderke|Filmski likovi)$')
FINITE = re.compile(r'\b(?:je|su|bio|bila|bilo|bili|bile|nije|nisu|ima|imaju|'
    r'nalazi|nalaze|pripada|pripadaju|živi|žive|postaje|postaju|rođen|rođena|'
    r'osnovan|osnovana|opisao|opisala|oženio|udala|umro|umrla|napisao|napisala|'
    r'dobio|dobila|sudjelovao|sudjelovala|počinje|završava|smatra|koristi|koriste)\b', re.I)
SENTENCE = re.compile(r'[.!?](?:\s|$)')
LIST_MARKER = re.compile(r'^(?:[-*•]|\d{1,3}[.)])\s+')
DATE_OPEN = re.compile(r'^\d{1,2}\.\s+(?:siječnja|veljače|ožujka|travnja|svibnja|lipnja|'
                       r'srpnja|kolovoza|rujna|listopada|studenog|studenoga|prosinca)\b', re.I)


def prose(line):
    # Short complete sentences remain eligible; punctuation alone is not enough
    # because years, bibliographic abbreviations and taxon authors contain dots.
    return len(line.split()) >= 4 and bool(FINITE.search(line)) and bool(SENTENCE.search(line))


def classify(text):
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
    result = []
    for i, block in enumerate(blocks):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        first = lines[0].rstrip(' :')
        if len(lines) == 1 and first in HEADINGS | LIST_HEADINGS:
            kind = 'heading'
        elif i == len(blocks)-1 and all(len(line) <= 120 and CATEGORY.fullmatch(line) for line in lines):
            kind = 'category_tail'
        elif first in LIST_HEADINGS:
            kind = 'meaningful_list_or_inventory'
        elif all(LIST_MARKER.match(line) and not DATE_OPEN.match(line) for line in lines):
            kind = 'meaningful_list_or_inventory'
        elif first in REFERENCE:
            # Reference sections may include substantive annotations. Keep them
            # unresolved unless all content is plainly short link/citation text.
            content = lines[1:]
            citation = bool(content) and all(len(line) <= 240 and (
                'http://' in line or 'https://' in line or re.search(r'\b\S+\.(?:hr|org|com|net)\b', line)
                or line.startswith(('urednik:', 'ISBN', 'doi:'))) for line in content)
            kind = 'reference_furniture' if citation else 'uncertain_reference'
        elif any(prose(line) for line in lines) and not any(line.startswith(('|', '{{', '}}')) for line in lines):
            kind = 'detected_prose'
        elif len(lines) >= 2 and all(len(line) <= 180 for line in lines):
            kind = 'unresolved_list_or_short_lines'
        else:
            kind = 'unresolved'
        result.append(dict(index=i, kind=kind, chars=len(block)))
    counts = Counter(b['kind'] for b in result)
    nprose = counts['detected_prose']
    furniture = counts['heading'] + counts['category_tail'] + counts['reference_furniture']
    unresolved = len(blocks) - nprose - furniture
    return dict(blocks=result, detected_prose_blocks=nprose, furniture_blocks=furniture,
        unresolved_or_list_blocks=unresolved,
        classification=('at_least_two_detected_prose' if nprose >= 2 else
                        'below_two_furniture_only_remainder' if unresolved == 0 else
                        'below_two_with_unresolved_or_list_blocks'),
        flags=dict(at_least_two_detected_prose=nprose >= 2,
            below_two_furniture_only_remainder=nprose < 2 and unresolved == 0,
            below_two_with_unresolved_or_list_blocks=nprose < 2 and unresolved > 0,
            recognized_category_heading_only=nprose == 0 and unresolved == 0
                and counts['category_tail'] > 0 and counts['reference_furniture'] == 0,
            recognized_furniture_only=nprose == 0 and unresolved == 0,
            meaningful_list_detected=counts['meaningful_list_or_inventory'] > 0,
            unresolved_structure=unresolved > 0))


def census(registry, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Use a fresh diagnostic directory')
    entries = sorted((e for e in load(registry)['additions'] if
        e['name'].startswith('dfm13_wave4_wikipedia_hr_')), key=lambda e:e['task'])
    if len(entries) != 4:
        raise ValueError('Require four Croatian publications')
    output.mkdir(parents=True)
    results = {}; examples = defaultdict(list); pins = {}
    with (output / 'flags.jsonl').open('w') as out:
        for entry in entries:
            counts, histogram = Counter(), Counter()
            hasher = hashlib.sha256()
            with Path(entry['output']).open('rb') as handle:
                for ordinal, raw in enumerate(handle):
                    hasher.update(raw)
                    row = json.loads(raw)
                    if row['language'] != 'hr' or row['task'] != entry['task']:
                        raise ValueError('Unexpected task/language')
                    window = row['audit_context']['original']
                    c = classify(window)
                    counts['rows'] += 1
                    histogram[str(c['detected_prose_blocks'])] += 1
                    for key, flag in c['flags'].items():
                        if flag:
                            counts[key] += 1
                    groups = [c['classification']]
                    if c['flags']['meaningful_list_detected']: groups.append('meaningful_list_detected')
                    if c['flags']['recognized_category_heading_only']: groups.append('recognized_category_heading_only')
                    if c['flags']['recognized_furniture_only']: groups.append('recognized_furniture_only')
                    for group in groups:
                        key = row['task'] + ':' + group
                        # Four hash-ranked cases per bucket, independent of file ordinal.
                        rank = digest(['hr-diagnostic-20261003', row['id']])
                        bucket = examples[key]
                        if len(bucket) < 4 or rank < bucket[-1]['rank']:
                            bucket.append(dict(rank=rank, id=row['id'], ordinal=ordinal,
                                record_sha256=digest(row), provenance=row['provenance'],
                                window=window, messages=row['messages'], structure=c))
                            bucket.sort(key=lambda x:x['rank'])
                            del bucket[4:]
                    out.write(json.dumps(dict(id=row['id'], ordinal=ordinal, task=row['task'],
                        record_sha256=digest(row), window_sha256=digest(window), **c), ensure_ascii=False)+'\n')
            if hasher.hexdigest() != entry['output_sha256'] or counts['rows'] != entry['rows']:
                raise ValueError('Published pin/count mismatch')
            pins[entry['output']] = entry['output_sha256']
            results[entry['task']] = dict(counts=dict(counts), detected_prose_histogram=dict(histogram),
                hf_repo_id=entry['hf_repo_id'], hf_revision=entry['hf_revision'],
                published_path=entry['output'], published_sha256=entry['output_sha256'])
    write_json(output / 'examples.json', dict(examples))
    report = dict(schema='hr-structural-diagnostic-v1', results=results, input_pins=pins,
        classifier_sha256=file_hash(__file__), filtering_applied=False, publication_mutated=False,
        limitation='Exact counts of explicit structural rules, not certified counts of meaningful paragraphs or semantic quality.',
        proposal_scope='Reordering only. Below-two furniture-only is a review candidate, not automatic exclusion. Lists/unknown blocks unresolved.',
        files={p:file_hash(output/p) for p in ('flags.jsonl','examples.json')})
    write_json(output / 'report.json', report)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, default=Path('config/dfm13_sources.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    census(args.registry, args.output)
