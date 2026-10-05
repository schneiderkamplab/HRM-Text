"""Read-only structural census of pinned Persian Wikipedia transform exports."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from dfm12.io import digest, file_hash, load, write_json

HEADINGS = frozenset('منابع|پانویس|پانویس‌ها|پیوند به بیرون|پیوندهای بیرونی|جستارهای وابسته|نگارخانه|یادداشت‌ها|واژه‌نامه|کتاب‌شناسی|منبع|یادداشت|ارجاعات|منابع و مآخذ|منابع و پیوندها|پیوندهای خارجی'.split('|'))
CATEGORY = re.compile(r'^(?:افراد زنده$|افراد درگذشته$|افراد .+تبار$|اهالی |زادگان |درگذشتگان |'
    r'بازیکنان |مربیان |ورزشکاران |نویسندگان |بازیگران |خوانندگان |موسیقی‌دانان |'
    r'رمان‌نویسان |دانش‌آموختگان |برندگان |دریافت‌کنندگان |مدال‌آوران |'
    r'شرکت‌کنندگان |قایقرانان |کشتی‌گیران |شناگران |دوچرخه‌سواران |دوندگان |'
    r'دروازه‌بانان |مهاجمان |مدافعان |هافبک‌های |دور از وطن‌های |'
    r'شوالیه‌های |افسران |فرماندهان |فیلدمارشال‌های |نظامیان |سیاستمداران |'
    r'اعضای |رؤسای |روسای |بارون‌های |راه‌یافتگان |'
    r'فیلم‌های |رمان‌های |کتاب‌های |آلبوم‌های |ترانه‌های |مجموعه‌های تلویزیونی |'
    r'بنیان‌گذاری‌های |انحلال‌های |ساختمان‌ها و سازه‌های |مناطق مسکونی |'
    r'روستاهای |شهرهای |دهستان‌های |بخش‌های |شهرستان‌های |استان‌های |'
    r'ویکی‌سازی رباتیک$|مقاله‌های |صفحه‌های |فهرست‌های |نام‌های خانوادگی )')
VERB = re.compile(r'(?:^|\s)(?:است|هستند|بود|بودند|شد|شده|شدند|دارد|دارند|می‌شود|می‌شوند|می‌کند|می‌کنند)(?:\s|[.،؛؟!]|$)')
EMPTY = re.compile(r'(?<![\w])\(\s*\)|(?:زاده[ٔ‌]?|متولد|درگذشته)[\sٔ‌]*(?=\))|[–—]\s*(?=\))')
SENTENCE = re.compile(r'[.!؟?](?:\s|$)')


def line_kind(line):
    text = line.strip().strip('*# ').strip()
    if text in HEADINGS:
        return 'heading'
    if len(text) <= 180 and CATEGORY.search(text) and not VERB.search(text) and not SENTENCE.search(text):
        return 'category'
    if re.match(r'^(?:[-*•]|\d+[.)])\s+', line.strip()):
        return 'list_item'
    if len(text) >= 35 and len(text.split()) >= 6 and (VERB.search(text) or SENTENCE.search(text)):
        return 'prose'
    return 'unknown'


def classify(text):
    blocks = [b for b in re.split(r'\n\s*\n', text) if b.strip()]
    effective = uncertain = lists = headings = clean = affected = prose_chars = 0
    kinds = Counter()
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        labels = [line_kind(line) for line in lines]
        kinds.update(labels)
        if all(k == 'heading' for k in labels):
            headings += 1
        elif all(k in ('heading', 'category', 'list_item') for k in labels):
            lists += 1
        elif 'prose' in labels:
            effective += 1
            prose_chars += sum(len(line.strip()) for line, kind in zip(lines, labels) if kind == 'prose')
            if EMPTY.search(block):
                affected += 1
            else:
                clean += 1
        elif len(lines) >= 3 and all(len(line) < 180 for line in lines):
            # Short unknown multi-line noun inventories are not certified categories.
            lists += 1
            uncertain += 1
        else:
            uncertain += 1
    category_only = kinds['category'] >= 3 and not (kinds['prose'] or kinds['unknown'] or kinds['list_item'])
    heading_only = bool(kinds) and kinds['heading'] == sum(kinds.values())
    empty = len(EMPTY.findall(text))
    return dict(blocks=len(blocks), effective_prose_paragraphs=effective,
        heading_blocks=headings, list_or_category_blocks=lists, uncertain_blocks=uncertain, prose_chars=prose_chars,
        line_kinds=dict(kinds), empty_fields=empty, empty_affected_prose_blocks=affected,
        flags=dict(category_only=category_only, heading_only=heading_only,
            no_detected_prose=effective == 0, uncertain_structure=uncertain > 0,
            empty_field_present=empty > 0,
            empty_field_heavy=empty >= 2 or (empty > 0 and affected > 0 and clean == 0 and prose_chars <= 300)))


def census(registry, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Use fresh diagnostic output')
    entries = [e for e in load(registry)['additions'] if e['name'].startswith('dfm13_wave4_wikipedia_fa_')]
    if len(entries) != 4 or {e['task'] for e in entries} != {'denoising','paragraph-reordering','prefix-continuation','span-filling'}:
        raise ValueError('Expected exactly four published tasks')
    output.mkdir(parents=True)
    results = {}; examples = defaultdict(list); pins = {}
    with (output / 'flags.jsonl').open('w') as flags_out:
        for entry in entries:
            counts, histogram = Counter(), Counter()
            path = Path(entry['output']); pins[str(path)] = entry['output_sha256']
            hasher = hashlib.sha256()
            with path.open('rb') as handle:
                for raw in handle:
                    hasher.update(raw)
                    row = json.loads(raw)
                    text = row['audit_context']['original']
                    item = classify(text)
                    is_reorder = row['task'] == 'paragraph-reordering'
                    item['flags'].update(
                        reorder_below_two_prose=is_reorder and item['effective_prose_paragraphs'] < 2,
                        reorder_below_three_prose=is_reorder and item['effective_prose_paragraphs'] < 3)
                    # Exclude only recognized metadata, or nonambiguous reorder windows with <2 prose units.
                    item['flags']['minimal_filter_candidate'] = (item['flags']['category_only']
                        or item['flags']['heading_only'] or (is_reorder
                            and item['effective_prose_paragraphs'] < 2 and item['uncertain_blocks'] == 0))
                    item['flags']['prose_present_no_empty_fields'] = item['effective_prose_paragraphs'] > 0 and item['empty_fields'] == 0
                    counts['rows'] += 1
                    histogram[str(item['effective_prose_paragraphs'])] += 1
                    for key, flag in item['flags'].items():
                        if flag:
                            counts[key] += 1
                            group = row['task'] + ':' + key
                            if len(examples[group]) < 4:
                                examples[group].append(dict(candidate_id=row['id'], record_sha256=digest(row),
                                    provenance=row['provenance'], messages=row['messages'], window=text,
                                    structural=item))
                    flags_out.write(json.dumps(dict(candidate_id=row['id'], task=row['task'],
                        record_sha256=digest(row), window_sha256=digest(text), **item), ensure_ascii=False) + '\n')
            if hasher.hexdigest() != entry['output_sha256'] or counts['rows'] != entry['rows']:
                raise ValueError('Published pin/count mismatch')
            results[entry['task']] = dict(counts=dict(counts), effective_paragraph_histogram=dict(histogram),
                hf_repo_id=entry['hf_repo_id'], hf_revision=entry['hf_revision'],
                published_path=str(path), published_sha256=entry['output_sha256'])
    write_json(output / 'examples.json', dict(examples))
    report = dict(schema='fa-transform-structural-diagnostic-v2', results=results, inputs=pins,
        classifier_sha256=file_hash(__file__), publication_mutated=False, filtering_applied=False,
        limitation='Deterministic lexical/structural flags, not semantic quality rates. Unknown blocks are not confirmed bad categories. Effective prose count is conservative and can undercount Persian prose.',
        policy=dict(category_only='At least 3 recognized category lines; every other line a recognized heading.',
            heading_only='Every nonblank line a recognized standalone heading.',
            empty_field_heavy='At least 2 malformed empty fields, or an affected prose block with no clean prose block and at most 300 detected prose characters. Excludes identifier-adjacent function calls.',
            minimal_filter_candidate='Category-only or heading-only, plus reordering with <2 detected prose blocks AND zero uncertain blocks. Proposal only.',
            retained_not_certified='Rows outside proposed minimal filter are not automatically semantically approved.'),
        files={name:file_hash(output/name) for name in ('flags.jsonl','examples.json')})
    write_json(output / 'report.json', report)
    print(json.dumps(results, indent=2))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--registry', type=Path, default=Path('config/dfm13_sources.json'))
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    census(args.registry, args.output)
