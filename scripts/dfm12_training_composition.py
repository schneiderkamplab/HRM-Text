"""Read-only accounting of the actual XL no-identity epoch, not source estimates.

Run from the repository root. Only the requested JSON report is written.
Broad mixed sources are not treated as instruction-following benchmark training.
"""
import argparse
import ast
from collections import defaultdict
import fnmatch
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np

ACTIVE = Path('data/sampled_dfm12_xl_epoch11_noidentity')
ADDED = Path('data/sampled_dfm12_xl_epoch11_noidentity_additions')
BASE = Path('data/sampled_dfm11')
BUILD = Path('data/dfm12/training-build-completed-campaign-20260929')
TOKENIZED = Path('data/tokenized_dfm12_additions-completed-campaign-20260929')
RECEIPTS = Path('data/dfm12/xl-epoch11-noidentity')
LANGUAGES = 'da en nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk'.split()
FAMILIES = ['instruction_following', 'gec', 'acceptability', 'summary', 'reasoning',
            'knowledge', 'ner', 'sentiment', 'qa', 'translation', 'reordering',
            'tool_use', 'math_code', 'summary_rewrite', 'mixed_instruction_unclassified',
            'mixed_text_tasks_unclassified', 'gec_acceptability_unsplit', 'unclassified',
            'denoising', 'prefix_continuation', 'span_filling', 'common_sense', 'code', 'math']
METRICS = ('rows', 'rendered_tokens', 'response_tokens')


def language_code(value):
    """Canonicalize explicit locale aliases, never generic Norwegian or Portuguese."""
    if not isinstance(value, str):
        return value
    key = value.lower().replace('_', '-')
    return {'pt-pt': 'pt_pt', 'nb-no': 'nb', 'nn-no': 'nn'}.get(key, value)


def add_percentages(report):
    denominators = report['totals']['combined']
    fields = {'rows': 'row_percent_of_epoch',
              'rendered_tokens': 'rendered_token_percent_of_epoch',
              'response_tokens': 'response_token_percent_of_epoch'}
    report['percentage_definitions'] = {
        field: {'numerator': metric, 'denominator': denominators[metric],
                'unit': 'percent', 'scope': 'whole active sampled epoch; not within-language',
                'missing': 'null means unallocated/unknown, not zero'}
        for metric, field in fields.items()}
    rows = [r for key in ('language_family_rows', 'source_rows', 'unknowns') for r in report[key]]
    rows.extend(r for r in report['totals'].values() if isinstance(r, dict))
    for row in rows:
        for metric, field in fields.items():
            value = row.get(metric)
            row[field] = None if value is None else 100.0 * value / denominators[metric]
    return report


def publish_percentages(output):
    report = add_percentages(load(output))
    for metric, field in [('rows', 'row_percent_of_epoch'), ('rendered_tokens', 'rendered_token_percent_of_epoch')]:
        assert sum((r[metric] or 0) for r in report['language_family_rows']) + sum(r[metric] for r in report['unknowns']) == report['totals']['combined'][metric]
        assert abs(sum((r[field] or 0) for r in report['language_family_rows']) + sum(r[field] for r in report['unknowns']) - 100.0) < 1e-9
    report['provenance'][str(Path(__file__))] = dict(sha256=digest(__file__), bytes=Path(__file__).stat().st_size)
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(output)
    print('Published whole-epoch row/rendered-token/response-token percentages', flush=True)


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def array(path):
    return np.load(path, mmap_mode='r', allow_pickle=False)


def family(source, shard):
    if source.startswith('dfm12-dala-'):
        if source.endswith('-acceptability'):
            return 'acceptability', 'Dedicated acceptability export component'
        if source.endswith('-correction'):
            return 'gec', 'Dedicated correction export component'
        return 'gec_acceptability_unsplit', 'Combined DaLA package; no proportional split'
    if source.startswith('dfm12-opus-') or source == 'dfm12-fleurs-alpaca-en-no':
        return 'translation', 'Dedicated translation component; bilingual token language not apportioned'
    if source.startswith('dfm12-reordering-integrated-'):
        return 'reordering', 'Dedicated native paragraph or synthetic text-block reordering'
    if source == 'dfm12-norquad-wikipedia':
        return 'qa', 'Dedicated NorQuAD QA component'
    if source == 'dfm12-amalia-if':
        return 'instruction_following', 'Explicit persona_instruction_following source (not all instruction data)'
    if source == 'dfm12-amalia-summarize':
        return 'summary', 'Dedicated smol_summarize_pt source'
    if source == 'dfm12-norwegian-inclusive-reasoning-norwegian':
        return 'reasoning', 'Explicit reasoning component; Norwegian variant unspecified'
    if source.startswith('dfm12-multilingual-synthetic-'):
        task = shard.removeprefix('train-').removesuffix('.jsonl.gz')
        value = {'math-code': 'math_code', 'summary-rewrite': 'summary_rewrite',
                 'tool-dialogue': 'tool_use'}.get(task, 'mixed_instruction_unclassified')
        return value, 'Sealed synthetic family filename; combined families not split into guessed proportions'
    if source.startswith(('dfm12-text-', 'dfm12-dynaword-')):
        return 'mixed_text_tasks_unclassified', 'Text-derived mixed tasks; not assigned to knowledge by source topic'
    return 'mixed_instruction_unclassified', 'Broad/mixed source; no validated eval-family allocation'


def totals(directory, chunk):
    inst = array(directory / 'inst_len.npy'); resp = array(directory / 'resp_len.npy')
    assert len(inst) == len(resp)
    result = dict(rows=len(inst), rendered_tokens=0, response_tokens=0)
    for lo in range(0, len(inst), chunk):
        result['rendered_tokens'] += int(inst[lo:lo+chunk].sum(dtype=np.uint64)) + int(resp[lo:lo+chunk].sum(dtype=np.uint64))
        result['response_tokens'] += int(resp[lo:lo+chunk].sum(dtype=np.uint64))
    result['next_token_positions'] = result['rendered_tokens'] - result['rows']
    return result


def table_rows(tasks):
    inherited = any(t.get('component') == 'inherited_dfm11' for t in tasks)
    grouped = defaultdict(lambda: dict(rows=0, rendered_tokens=0, response_tokens=0, sources=set()))
    for task in tasks:
        if not task['rows']:
            continue
        group = grouped[task['language'], task['family']]
        for m in METRICS:
            group[m] += task[m]
        group['sources'].add(task['source'])
    table = []
    for lang in LANGUAGES:
        for fam in FAMILIES:
            group = grouped.get((lang, fam))
            coverage = 'unavailable_not_zero'
            if group:
                coverage = 'mixed_or_combined_additions_only' if ('mixed' in fam or fam in ('math_code', 'summary_rewrite', 'gec_acceptability_unsplit')) else 'dedicated_additions_lower_bound'
            if inherited:
                coverage = coverage.replace('additions', 'attributed_sources')
            row = dict(language=lang, family=fam, coverage=coverage,
                       classification_basis='Source/shard role or aligned per-row task and export language; ' +
                       ('includes attributable inherited DFM11 sources' if inherited else 'inherited DFM11 excluded'))
            row.update({m: group[m] if group else None for m in METRICS})
            row['sources'] = sorted(group['sources']) if group else []
            table.append(row)
    return table


def refine(output, chunk):
    """Only split shards when emitted assistant enumeration exactly matches indices."""
    try:
        from scripts.tokenize_chat_template import examples_from_messages
    except ModuleNotFoundError:
        from tokenize_chat_template import examples_from_messages
    report = load(output)
    if report.get('row_alignment_refinement'):
        raise ValueError('Already refined; rebuild base report to reproduce')
    mapping = {'acceptability': 'acceptability', 'correction': 'gec', 'denoising': 'denoising',
               'prefix-continuation': 'prefix_continuation', 'span-filling': 'span_filling',
               'paragraph-reordering': 'reordering', 'text-block-reordering': 'reordering'}
    starts = []; label_arrays = []; groups = []; refined = set(); failures = []
    for task in report['source_rows']:
        source = task['source']
        if not task['rows'] or not (source.startswith(('dfm12-dynaword-', 'dfm12-text-')) or source in ('dfm12-dala-en', 'dfm12-dala-nl')):
            continue
        shard = task['task'].split('__', 1)[1]
        raw = BUILD / 'accepted_inputs' / source / shard
        directory = TOKENIZED / task['task']
        count = len(array(directory / 'inst_start.npy'))
        labels = []; local_groups = {}; newgroups = []
        with gzip.open(raw, 'rt') as handle:
            for line in handle:
                row = json.loads(line)
                label = language_code(row.get('language'))
                language = label if label in LANGUAGES else 'unknown_or_multilingual'
                fam = mapping.get(row.get('task'), 'unclassified')
                key = language, fam
                if key not in local_groups:
                    local_groups[key] = len(groups) + len(newgroups)
                    newgroups.append(dict(task, language=language, family=fam, rows=0, rendered_tokens=0, response_tokens=0,
                        classification_basis='Exact raw assistant-target enumeration aligned with tokenized shard, then actual sampled token offsets',
                        original_source_family=task['family']))
                for _ in examples_from_messages(row['messages'], row.get('tools'), row.get('target_message_index')):
                    labels.append(local_groups[key])
        if len(labels) != count:
            failures.append(dict(task=task['task'], emitted=len(labels), tokenized=count,
                                 disposition='leave source unsplit; cannot locate tokenizer drops without retokenization'))
            continue
        groups.extend(newgroups)
        starts.append(np.asarray(array(directory / 'inst_start.npy')) + task['token_start'])
        label_arrays.append(np.array(labels, dtype=np.int32))
        refined.add(task['task'])
        report['provenance'][str(raw)] = dict(sha256=digest(raw), bytes=raw.stat().st_size)
        if len(refined) % 25 == 0:
            print('Row-aligned shards:', len(refined), flush=True)
    if starts:
        allstarts = np.concatenate(starts); alllabels = np.concatenate(label_arrays)
        assert np.all(allstarts[1:] > allstarts[:-1])
        bounds = np.array([t['token_end'] for t in report['source_rows']], dtype=np.uint64)
        selected_tasks = np.array([t['task'] in refined for t in report['source_rows']])
        arrays = {f: array(ADDED / 'epoch_0' / (f + '.npy')) for f in ('inst_start', 'inst_len', 'resp_len')}
        counts = np.zeros((len(groups), 3), dtype=np.uint64)
        for lo in range(0, len(arrays['inst_start']), chunk):
            a = {k: v[lo:lo+chunk] for k, v in arrays.items()}
            mask = selected_tasks[np.searchsorted(bounds, a['inst_start'], side='right')]
            positions = np.searchsorted(allstarts, a['inst_start'][mask])
            assert np.all(allstarts[positions] == a['inst_start'][mask])
            ids = alllabels[positions]
            counts[:, 0] += np.bincount(ids, minlength=len(groups)).astype(np.uint64)
            counts[:, 1] += np.bincount(ids, weights=(a['inst_len'][mask]+a['resp_len'][mask]), minlength=len(groups)).astype(np.uint64)
            counts[:, 2] += np.bincount(ids, weights=a['resp_len'][mask], minlength=len(groups)).astype(np.uint64)
        for group, values in zip(groups, counts):
            group.update(zip(METRICS, map(int, values)))
        oldtotals = {m: sum(t[m] for t in report['source_rows'] if t['task'] in refined) for m in METRICS}
        assert all(sum(g[m] for g in groups) == oldtotals[m] for m in METRICS)
        report['source_rows'] = [t for t in report['source_rows'] if t['task'] not in refined] + groups
    report['language_family_rows'] = table_rows(report['source_rows'])
    # Rebuild unknown addition buckets after recovering NB/NN from row labels.
    report['unknowns'] = [x for x in report['unknowns'] if x['component'] == 'inherited_dfm11']
    buckets = defaultdict(lambda: dict(rows=0, rendered_tokens=0, response_tokens=0, sources=set()))
    for task in report['source_rows']:
        if task['language'] != 'unknown_or_multilingual' or not task['rows']:
            continue
        bucket = buckets[task['family']]
        for m in METRICS:
            bucket[m] += task[m]
        bucket['sources'].add(task['source'])
    for fam, bucket in sorted(buckets.items()):
        report['unknowns'].append(dict(language='unknown_or_multilingual', family=fam, component='dfm12_additions',
            **{m: bucket[m] for m in METRICS}, sources=sorted(bucket['sources']), reason='Unresolved row language; never apportioned by guessed proportions'))
    report['row_alignment_refinement'] = dict(shards=len(refined), failures=failures,
        tokenizer_enumeration='scripts/tokenize_chat_template.py:examples_from_messages',
        count_match_required=True, sampled_offsets_matched=True,
        inherited_recovery='Recover original sorted tokenized DFM11 union with exact backing lengths/source manifests or a pinned offset map from originating machine; then map sampled epoch_0 offsets. Prefix weights alone cannot recover it.')
    report['provenance'][str(Path(__file__))] = dict(sha256=digest(__file__), bytes=Path(__file__).stat().st_size)
    report['provenance']['scripts/tokenize_chat_template.py'] = dict(sha256=digest('scripts/tokenize_chat_template.py'))
    for m in METRICS:
        assert sum(t[m] for t in report['source_rows']) == report['totals']['dfm12_additions'][m]
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(output)
    print('Refined', len(refined), 'shards; failures', len(failures), flush=True)


def normalize_report(output):
    report = load(output)
    if report.get('inherited_source_recovery'):
        raise ValueError('Use --reclassify-inherited after inherited integration; do not discard inherited buckets')
    changed = []
    for task in report['source_rows']:
        langs = task.get('source_languages', [])
        if task['language'] == 'unknown_or_multilingual' and len(langs) == 1:
            normalized = language_code(langs[0])
            if normalized in LANGUAGES:
                task['language'] = normalized
                task['classification_basis'] += '; explicit locale alias ' + langs[0] + ' -> ' + normalized
                changed.append(task['task'])
    report['language_family_rows'] = table_rows(report['source_rows'])
    report['unknowns'] = [x for x in report['unknowns'] if x['component'] == 'inherited_dfm11']
    buckets = defaultdict(lambda: dict(rows=0, rendered_tokens=0, response_tokens=0, sources=set()))
    for task in report['source_rows']:
        if task['language'] != 'unknown_or_multilingual' or not task['rows']:
            continue
        bucket = buckets[task['family']]
        for metric in METRICS:
            bucket[metric] += task[metric]
        bucket['sources'].add(task['source'])
    for fam, bucket in sorted(buckets.items()):
        report['unknowns'].append(dict(language='unknown_or_multilingual', family=fam, component='dfm12_additions',
            **{m: bucket[m] for m in METRICS}, sources=sorted(bucket['sources']),
            reason='Unresolved or multilingual source language; no proportional allocation'))
    report['language_aliases'] = {'pt-PT': 'pt_pt', 'pt-pt': 'pt_pt', 'nb-no': 'nb', 'nn-no': 'nn'}
    report['provenance'][str(Path(__file__))] = dict(sha256=digest(__file__), bytes=Path(__file__).stat().st_size)
    for metric in METRICS:
        assert sum((r[metric] or 0) for r in report['language_family_rows']) + sum(r[metric] for r in report['unknowns']) == report['totals']['combined'][metric]
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(output)
    print('Normalized alias shards:', len(changed), flush=True)


def export_language_rules():
    """Read declarative export provenance without importing/executing its builder."""
    path = Path('scripts/prepare_dfm10_hf_exports.py')
    rules = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != 'ExportSpec' or len(node.args) < 6:
            continue
        try:
            name, root, patterns, upstream, languages, category = [ast.literal_eval(a) for a in node.args[:6]]
        except (ValueError, TypeError):
            continue
        rules.append(dict(name=name, root=Path(root).name, patterns=patterns, languages=languages,
                          category=category, evidence=str(path) + ':' + str(node.lineno)))
    path = Path('scripts/download_training_datasets.py')
    aliases = {'danish': 'da', 'english': 'en'}
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != 'HFDataset':
            continue
        fields = {k.arg: k.value for k in node.keywords}
        try:
            name = ast.literal_eval(fields['name'])
            groups = ast.literal_eval(fields['groups'])
        except (KeyError, ValueError, TypeError):
            continue
        languages = [aliases[g] for g in groups if g in aliases]
        if not languages or 'multilingual' in groups or 'translation' in groups:
            continue
        rules.append(dict(name=name, root=name, patterns=(), languages=languages,
                          category='source-declared language group, not a task-family classification',
                          evidence=str(path) + ':' + str(node.lineno)))
    return rules


def inherited_classification(task, rules):
    name = task['task']; prefix = name.split('__')[0]
    matches = []
    for rule in rules:
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in rule['patterns'] if '__' in pattern or not any(c in pattern for c in '*?')):
            matches.append(rule)
        elif prefix == rule['root']:
            matches.append(rule)
    languages = sorted({lang for rule in matches for lang in rule['languages']})
    basis = [r['evidence'] + ' ' + r['name'] for r in matches]
    # Explicit language-bearing release/task names only; broad FLAN/Tasksource
    # and translated collections are never assigned English by default.
    if not languages:
        if prefix == 'giannor_tv2r_instruction':
            languages = ['da']
            basis.append('scripts/convert_dfm8_giannor_tv2r.py:converted_row sets language=da')
        elif prefix == 'dfm8-synthetic-danish-summarization-rewrite-controls':
            languages = ['da']
        elif prefix.startswith(('danish-', 'danish_', 'folketingets-', 'dfm11-folketingets-',
                              'dfm11-fineinstructions-da', 'dfm11-koolbardi-da', 'dfm8-openhermes-da')):
            languages = ['da']
        elif prefix.startswith(('dfm11-fineinstructions-en', 'dfm11-koolbardi-en', 'dfm8-openhermes-en')):
            languages = ['en']
        elif name.startswith('nemotron_multilingual__'):
            match = re.search(r'_(de|es|fr|it|ja|zh)_translated', name)
            if match:
                languages = [match[1]]
        elif prefix == 'transformations-danish-danish':
            languages = ['da']
        elif prefix == 'transformations-english-english':
            languages = ['en']
        elif prefix.startswith('dsldk_danish_') or prefix in ('synquid_ifbench_train', 'synquid_danish_verifiable_reasoning', 'gsm_symbolic_da'):
            languages = ['da']
            basis.append('Danish release identity; wiki/pages/dfm10-danish-hf-gap-integration-plan.md and dfm10-danish-corpus-expansion.md')
        if languages:
            basis.append('Explicit language-bearing source/task identifier in corrected sampling inventory')
    language = languages[0] if len(languages) == 1 and languages[0] in LANGUAGES else 'unknown_or_multilingual'
    fam = 'mixed_instruction_unclassified'
    dedicated = {
        'alexandra_dane': 'ner', 'alexandra_scandi_qa_da': 'qa',
        'dsldk_danish_sentiment_lexicon.jsonl': 'sentiment',
        'dsldk_danish_sentiment_lexicon_natural.jsonl': 'sentiment',
        'dfm11-folketingets-dokumenter-error-correction': 'gec',
        'allenai_if_sft_verified': 'instruction_following',
        'allenai_tulu_3_personas_if': 'instruction_following',
        'synquid_ifbench_train': 'instruction_following', 'ifeval_verifier.jsonl': 'instruction_following',
        'dfm8-synthetic-constrained-format-following': 'instruction_following',
        'dfm8-synthetic-danish-summarization-rewrite-controls': 'summary_rewrite',
        'scientific_summaries_repaired': 'summary', 'govreport_summarization_repaired': 'summary',
        'wiki_cat_sum_repaired': 'summary', 'nordjylland_news_repaired': 'summary',
        'dfm4_arxiv_paper_summarization': 'summary', 'dfm4_govreport_summarization': 'summary',
        'dfm4_wiki_cat_sum_summarization': 'summary', 'dfm4_laion_scientific_summaries': 'summary',
        'synquid_danish_verifiable_reasoning': 'reasoning', 'alexandra_multi_zebra': 'reasoning',
        'event_coreference.jsonl': 'common_sense', 'drop_reasoning.jsonl': 'reasoning',
        'oliverkinch_danish_qa': 'qa', 'medquad_danish.jsonl': 'qa', 'medquad_english.jsonl': 'qa',
        'dfm11-mathagentic-gsm8k-prolog': 'math_code', 'dfm11-mathagentic-tinygsm-python': 'math_code',
    }
    if prefix in dedicated:
        fam = dedicated[prefix]
    elif prefix == 'giannor_tv2r_instruction':
        fam = 'gec' if '__giannor_gec_dala_tv2r_it__' in name else 'acceptability'
    elif prefix == 'nemotron_multilingual':
        fam = 'code' if '_code_' in name else ('math' if '_math_' in name else 'reasoning')
    elif prefix.startswith(('danish-dynaword-', 'folketingets-dokumenter-', 'common-pile-')):
        fam = next((v for k, v in [('denoising', 'denoising'), ('prefix-continuation', 'prefix_continuation'),
                    ('span-filling', 'span_filling'), ('paragraph-reordering', 'reordering')] if prefix.endswith(k)), 'mixed_text_tasks_unclassified')
    elif prefix.startswith(('opus', 'machine_translation_', 'oliverkinch_machine_translation_', 'synquid_translation_', 'elrc_medical_', 'bornholmsk_parallel')):
        fam = 'translation'
    elif 'tool-use' in prefix or 'tool_use' in prefix or 'tool-calling' in prefix or 'tool_calling' in prefix or prefix == 'zai_deepdive_trajectories_sft':
        fam = 'tool_use'
    elif prefix in ('dmmath', 'ampsmathematica', 'openmathinstruct2_repaired', 'numinamath_1_5', 'gsm_symbolic_da'):
        fam = 'math'
    elif prefix in ('code_meta_reasoning_repaired', 'nemotron_swe_repaired', 'nemotron_swe_windowed', 'dfm8-synthetic-code-debugging'):
        fam = 'code'
    elif prefix.startswith('transformations-'):
        fam = 'mixed_text_tasks_unclassified'
    if fam != 'mixed_instruction_unclassified':
        basis.append('Explicit dedicated source role; general reasoning is not commonsense')
    if not basis:
        basis.append('Source identity recovered; no validated language/task-family allocation')
    return language, fam, languages, '; '.join(basis)


def recover_inherited(output, provenance, chunk):
    report = load(output)
    if report.get('inherited_source_recovery'):
        raise ValueError('Inherited map already integrated; rebuild base report to reproduce')
    source_map = load(provenance / 'source-map.json')
    receipt = load(provenance / 'transfer-receipt.json')
    assert digest(provenance / 'source-map.json') == receipt['source_map_sha256']
    for path, descriptor in source_map['files'].items():
        assert digest(provenance / path) == descriptor['sha256'], path
    token_store = array(BASE / 'tokens.npy')
    assert len(token_store) == source_map['stored_tokens']
    log_tasks = set(); in_tasks = False
    for line in (provenance / 'logs/dfm11/sample_corrected.log').read_text().splitlines():
        if line == '### Task Coverage Stats':
            in_tasks = True
        elif line.startswith('### '):
            in_tasks = False
        if in_tasks and line.startswith('| **'):
            log_tasks.add(line.split('|')[1].strip().strip('*'))
    actual_tasks = {t['task'] for t in source_map['tasks']}
    if log_tasks != actual_tasks:
        raise ValueError('Remote union/log task mismatch: ' + str((len(actual_tasks-log_tasks), len(log_tasks-actual_tasks))))
    checks = 0; previous = 0
    for task in source_map['tasks']:
        assert task['token_start'] == previous
        previous = task['token_end']
        for probe in task['token_probes']:
            pos = task['token_start'] + probe['relative_position']
            raw = token_store[pos:pos+probe['tokens']].astype('<u4').tobytes()
            assert hashlib.sha256(raw).hexdigest() == probe['sha256'], ('Local token boundary mismatch', task['task'], pos)
            checks += 1
    assert previous == len(token_store)
    print('Verified local token probes', checks, 'and log task inventory', len(actual_tasks), flush=True)
    bounds = np.array([t['token_end'] for t in source_map['tasks']], dtype=np.uint64)
    counts = np.zeros((len(bounds), 3), dtype=np.uint64)
    arrays = {f: array(BASE / 'epoch_0' / (f + '.npy')) for f in ('inst_start', 'resp_start', 'inst_len', 'resp_len')}
    for lo in range(0, len(arrays['inst_start']), chunk):
        a = {k: v[lo:lo+chunk] for k, v in arrays.items()}
        ids = np.searchsorted(bounds, a['inst_start'], side='right')
        assert np.all(ids < len(bounds))
        assert np.all(a['resp_start']+a['resp_len'] <= bounds[ids])
        counts[:, 0] += np.bincount(ids, minlength=len(bounds)).astype(np.uint64)
        counts[:, 1] += np.bincount(ids, weights=a['inst_len']+a['resp_len'], minlength=len(bounds)).astype(np.uint64)
        counts[:, 2] += np.bincount(ids, weights=a['resp_len'], minlength=len(bounds)).astype(np.uint64)
        if lo % (50*chunk) == 0:
            print('Inherited sampled rows mapped', lo, flush=True)
    rules = export_language_rules()
    recovered = []
    for task, values in zip(source_map['tasks'], counts):
        language, fam, languages, basis = inherited_classification(task, rules)
        recovered.append(dict(source=task['task'].split('__')[0], task=task['task'], component='inherited_dfm11',
            language=language, family=fam, source_languages=languages, classification_basis=basis,
            token_start=task['token_start'], token_end=task['token_end'], **dict(zip(METRICS, map(int, values)))))
    for metric in METRICS:
        assert sum(t[metric] for t in recovered) == report['totals']['inherited_dfm11'][metric]
    for task in report['source_rows']:
        task['component'] = 'dfm12_additions'
    report['source_rows'].extend(recovered)
    report['language_family_rows'] = table_rows(report['source_rows'])
    report['unknowns'] = []
    grouped = defaultdict(lambda: dict(rows=0, rendered_tokens=0, response_tokens=0, sources=set()))
    for task in report['source_rows']:
        if task['language'] != 'unknown_or_multilingual' or not task['rows']:
            continue
        group = grouped[task['component'], task['family']]
        for metric in METRICS:
            group[metric] += task[metric]
        group['sources'].add(task['source'])
    for (component, fam), group in sorted(grouped.items()):
        report['unknowns'].append(dict(component=component, language='unknown_or_multilingual', family=fam,
            **{m: group[m] for m in METRICS}, sources=sorted(group['sources']),
            reason='Source counts exact; language unverified, multilingual, or outside the 21-language table; no proportional split'))
    report['inherited_source_recovery'] = dict(provenance_root=str(provenance), source_tasks=len(recovered),
        sampled_nonempty_tasks=sum(bool(t['rows']) for t in recovered), stored_tokens=len(token_store),
        source_log_task_set_exact_match=True, local_source_token_probes_verified=checks,
        selected_epoch='epoch_0', token_payload_transferred=False,
        qualification='Three bounded source-token probes per nonempty task, not full token-payload hash equality; complete sampled range accounting',
        supersedes='Initial report treated all inherited DFM11 as source-unattributable; source mapping now recovered, semantic unknowns remain explicit')
    report['scope']['inherited_source_attribution'] = 'Recovered remote sorted union verified against corrected log and local token probes'
    report['limitations'].append('Inherited source/category attribution does not assert every example belongs to an eval family; broad multilingual mixtures remain unallocated.')
    if 'row_alignment_refinement' in report:
        report['row_alignment_refinement']['inherited_recovery'] = 'Completed; see inherited_source_recovery'
    for path in (provenance / 'source-map.json', provenance / 'transfer-receipt.json',
                 Path('scripts/prepare_dfm10_hf_exports.py'), Path(__file__)):
        report['provenance'][str(path)] = dict(sha256=digest(path), bytes=path.stat().st_size)
    for metric in METRICS:
        assert sum((r[metric] or 0) for r in report['language_family_rows']) + sum(r[metric] for r in report['unknowns']) == report['totals']['combined'][metric]
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(output)
    print('Inherited source accounting complete', flush=True)


def reclassify_inherited(output):
    """Refresh documented classifications without repeating validated token I/O."""
    report = load(output)
    assert report.get('inherited_source_recovery')
    rules = export_language_rules()
    for task in report['source_rows']:
        if task.get('component') == 'inherited_dfm11':
            lang, fam, langs, basis = inherited_classification(task, rules)
            task.update(language=lang, family=fam, source_languages=langs, classification_basis=basis)
    report['language_family_rows'] = table_rows(report['source_rows'])
    buckets = defaultdict(lambda: dict(rows=0, rendered_tokens=0, response_tokens=0, sources=set()))
    for task in report['source_rows']:
        if task['language'] != 'unknown_or_multilingual' or not task['rows']:
            continue
        bucket = buckets[task['component'], task['family']]
        for m in METRICS:
            bucket[m] += task[m]
        bucket['sources'].add(task['source'])
    report['unknowns'] = [dict(component=component, language='unknown_or_multilingual', family=fam,
        **{m: bucket[m] for m in METRICS}, sources=sorted(bucket['sources']),
        reason='Exact source accounting; language unverified/multilingual/outside the 21-language table; no proportional split')
        for (component, fam), bucket in sorted(buckets.items())]
    for path in ('scripts/prepare_dfm10_hf_exports.py', 'scripts/download_training_datasets.py', 'scripts/convert_dfm8_giannor_tv2r.py',
                 'wiki/pages/dfm10-danish-hf-gap-integration-plan.md', 'wiki/pages/dfm10-danish-corpus-expansion.md', str(Path(__file__))):
        report['provenance'][path] = dict(sha256=digest(path), bytes=Path(path).stat().st_size)
    for metric in METRICS:
        assert sum((r[metric] or 0) for r in report['language_family_rows']) + sum(r[metric] for r in report['unknowns']) == report['totals']['combined'][metric]
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(output)
    print('Inherited classification refreshed without rescanning token payload', flush=True)


def error_row_counts(provenance, output, chunk):
    """Retain original index arrays and exact selected multiplicity for error joins."""
    report = load(output)
    if not report.get('inherited_source_recovery'):
        raise ValueError('Verify and integrate inherited source map first')
    source_map = load(provenance / 'source-map.json')
    assert digest(provenance / 'source-map.json') == load(provenance / 'transfer-receipt.json')['source_map_sha256']
    prefixes = ('giannor_tv2r_instruction__', 'dfm11-folketingets-dokumenter-error-correction__',
                'danish-dynaword-denoising__', 'common-pile-denoising__',
                'folketingets-dokumenter-denoising__', 'posttrain_coedit__',
                'dfm8-synthetic-danish-summarization-rewrite-controls__')
    tasks = [t for t in source_map['tasks'] if t['task'].startswith(prefixes)]
    target = provenance / 'sampled_error_rows'
    if (target / 'receipt.json').exists():
        raise FileExistsError('Completed per-row accounting already exists')
    original = provenance / 'original_error_indices'
    starts = []; lengths = []; response_starts = []; response_lengths = []; offsets = []; n = 0
    descriptors = {}
    for task in tasks:
        directory = original / task['task']; directory.mkdir(parents=True, exist_ok=True)
        for field in ('inst_start', 'inst_len', 'resp_start', 'resp_len', 'metadata'):
            filename = field + ('.json' if field == 'metadata' else '.npy')
            dest = directory / filename
            remote = 'ssh.cloud.sdu.dk:/work/dfm/HRM-Text/data/tokenized_dfm11/' + task['task'] + '/' + filename
            if not dest.exists():
                subprocess.run(['rsync', '-aL', '-e', 'ssh -o BatchMode=yes -p 6768', remote, str(dest)], check=True)
            descriptors[str(dest)] = dict(sha256=digest(dest), bytes=dest.stat().st_size)
        assert digest(directory / 'metadata.json') == task['metadata_sha256']
        a = {f: array(directory / (f + '.npy')) for f in ('inst_start', 'inst_len', 'resp_start', 'resp_len')}
        assert len(a['inst_start']) == task['original_targets']
        assert int(a['inst_len'].sum(dtype=np.uint64))+int(a['resp_len'].sum(dtype=np.uint64)) == task['tokens']
        starts.append(np.asarray(a['inst_start']) + task['token_start'])
        response_starts.append(np.asarray(a['resp_start']) + task['token_start'])
        lengths.append(a['inst_len']); response_lengths.append(a['resp_len'])
        offsets.append((n, n+len(a['inst_start'])))
        n += len(a['inst_start'])
        print('Transferred error indices', task['task'], flush=True)
    allstarts = np.concatenate(starts); allresponses = np.concatenate(response_starts)
    alllengths = np.concatenate(lengths); allresplengths = np.concatenate(response_lengths)
    assert np.all(allstarts[1:] > allstarts[:-1])
    counts = np.zeros((n, 3), dtype=np.uint64)
    selected = {t['task'] for t in tasks}
    bounds = np.array([t['token_end'] for t in source_map['tasks']], dtype=np.uint64)
    selected_tasks = np.array([t['task'] in selected for t in source_map['tasks']])
    arrays = {f: array(BASE / 'epoch_0' / (f + '.npy')) for f in ('inst_start', 'inst_len', 'resp_start', 'resp_len')}
    for lo in range(0, len(arrays['inst_start']), chunk):
        a = {k: v[lo:lo+chunk] for k, v in arrays.items()}
        mask = selected_tasks[np.searchsorted(bounds, a['inst_start'], side='right')]
        indices = np.searchsorted(allstarts, a['inst_start'][mask])
        assert np.all(allstarts[indices] == a['inst_start'][mask])
        assert np.all(allresponses[indices] == a['resp_start'][mask])
        assert np.all(alllengths[indices] == a['inst_len'][mask])
        assert np.all(allresplengths[indices] >= a['resp_len'][mask])
        np.add.at(counts[:, 0], indices, np.uint64(1))
        np.add.at(counts[:, 1], indices, a['inst_len'][mask]+a['resp_len'][mask])
        np.add.at(counts[:, 2], indices, a['resp_len'][mask])
    target.mkdir(parents=True, exist_ok=True)
    outputs = []; source_counts = {t['task']: t for t in report['source_rows'] if t.get('component') == 'inherited_dfm11'}
    for task, (lo, hi) in zip(tasks, offsets):
        values = counts[lo:hi]
        for column, metric in enumerate(METRICS):
            assert int(values[:, column].sum(dtype=np.uint64)) == source_counts[task['task']][metric]
        path = target / (task['task'] + '.npz')
        directory = original / task['task']
        np.savez_compressed(path, tokenized_ordinal=np.arange(hi-lo, dtype=np.uint64),
            sampled_multiplicity=values[:, 0], rendered_tokens=values[:, 1], response_tokens=values[:, 2],
            **{f: array(directory / (f + '.npy')) for f in ('inst_start', 'inst_len', 'resp_start', 'resp_len')})
        outputs.append(dict(task=task['task'], component=task['task'], path=str(path), sha256=digest(path),
            original_targets=hi-lo, selected_targets=int(np.count_nonzero(values[:, 0])),
            **{m: int(values[:, i].sum(dtype=np.uint64)) for i, m in enumerate(METRICS)}))
    (target / 'receipt.json').write_text(json.dumps(dict(schema='dfm11-sampled-error-row-counts-v1',
        status='complete_tokenized_ordinal_counts_raw_source_alignment_not_claimed',
        selected_epoch='data/sampled_dfm11/epoch_0', source_map_sha256=digest(provenance / 'source-map.json'),
        index_files=descriptors, outputs=outputs, sampled_start_and_length_checks=True,
        raw_row_alignment='Downstream must independently establish assistant expansion and tokenizer skip mapping; raw source ordinal is not tokenized ordinal',
        tv2r='Whole source retained; downstream must separate acceptability from correction by row metadata'), indent=2) + '\n')
    print('Completed sampled error row counts:', len(outputs), flush=True)


def main(output, chunk):
    specification = load(RECEIPTS / 'specification.json')
    assert specification['base_epoch_index'] == 0 and specification['output_epoch_index'] == 10
    assert specification['identity_repeat'] == 0
    assert load(ACTIVE / 'epoch-mapping.json') == specification
    assert digest(BUILD / 'sources.json') == specification['source_manifest_sha256']
    registered = {r['name']: r for r in load(BUILD / 'sources.json')}
    policy = specification['policy']
    evidence = {}
    def pin(path):
        path = Path(path)
        evidence[str(path)] = {'sha256': digest(path), 'bytes': path.stat().st_size}
    for path in (RECEIPTS / 'specification.json', RECEIPTS / 'budget-indices.json',
                 RECEIPTS / 'ready.json', ACTIVE / 'epoch-mapping.json', ACTIVE / 'metadata.json',
                 BUILD / 'sources.json', BASE / 'metadata.json', Path(__file__)):
        pin(path)
    manifests = {}
    tasks = []; end = 0
    for directory in sorted(TOKENIZED.iterdir()):
        if not directory.is_dir():
            continue
        matches = [p for p in policy if directory.name.startswith(p['prefix'])]
        if not matches:
            continue
        source, shard = directory.name.split('__', 1)
        if source not in manifests:
            raw = next((BUILD / 'accepted_inputs' / source).iterdir()).resolve()
            path = raw.parent.parent / 'metadata/manifest.json'
            expected = registered[source].get('manifest_sha256')
            if expected is None:
                path = raw.parent.parent.parent / 'integration.json'
                integration = load(path)
                manifest = next(c for c in integration['components'] if c['name'] == source)
                expected = registered[source]['integration_sha256']
            else:
                manifest = load(path)
            pin(path)
            if digest(path) != expected:
                raise ValueError('Registered export manifest changed: ' + source)
            langs = list(manifest.get('languages', {}))
            if not langs and manifest.get('language'):
                langs = [manifest['language']]
            manifests[source] = (langs, str(path))
        langs, path = manifests[source]
        language = language_code(langs[0]) if len(langs) == 1 and language_code(langs[0]) in LANGUAGES else 'unknown_or_multilingual'
        fam, basis = family(source, shard)
        length = len(array(directory / 'tokens.npy'))
        original_length = int(array(directory / 'inst_len.npy').sum(dtype=np.uint64)) + int(array(directory / 'resp_len.npy').sum(dtype=np.uint64))
        assert length == original_length, directory
        tasks.append(dict(source=source, task=directory.name, language=language, family=fam,
            source_languages=langs, classification_basis=basis, manifest=path, repeat=matches[0]['repeat'],
            token_start=end, token_end=end+length, rows=0, rendered_tokens=0, response_tokens=0))
        end += length
    assert end == len(array(ADDED / 'tokens.npy')), 'Backing store differs from reconstructed sorted task union'
    print('Verified source range inventory:', len(tasks), flush=True)
    boundaries = np.array([t['token_end'] for t in tasks], dtype=np.uint64)
    arrays = {f: array(ADDED / 'epoch_0' / (f + '.npy')) for f in ('inst_start', 'resp_start', 'inst_len', 'resp_len')}
    # Integer accumulation preserves exact counts; float bincount weights are exact
    # here because every chunk sum is bounded far below 2**53.
    accum = np.zeros((len(tasks), 3), dtype=np.uint64)
    for lo in range(0, len(arrays['inst_len']), chunk):
        a = {k: v[lo:lo+chunk] for k, v in arrays.items()}
        indices = np.searchsorted(boundaries, a['inst_start'], side='right')
        if np.any(indices >= len(tasks)):
            raise ValueError('Unmapped sampled source')
        if np.any(a['resp_start'] + a['resp_len'] > boundaries[indices]):
            raise ValueError('Response crosses source boundary')
        accum[:, 0] += np.bincount(indices, minlength=len(tasks)).astype(np.uint64)
        accum[:, 1] += np.bincount(indices, weights=a['inst_len'] + a['resp_len'], minlength=len(tasks)).astype(np.uint64)
        accum[:, 2] += np.bincount(indices, weights=a['resp_len'], minlength=len(tasks)).astype(np.uint64)
    for task, counts in zip(tasks, accum):
        task.update(zip(METRICS, map(int, counts)))
        if task['repeat'] == 0:
            assert task['rows'] == 0, 'Excluded source sampled'
    base = totals(BASE / 'epoch_0', chunk)
    added = {metric: sum(t[metric] for t in tasks) for metric in METRICS}
    added['next_token_positions'] = added['rendered_tokens'] - added['rows']
    actual = totals(ACTIVE / 'epoch_10', chunk)
    assert all(actual[m] == base[m] + added[m] for m in actual), 'Active epoch reconciliation failed'
    budget = load(RECEIPTS / 'budget-indices.json')['report']
    assert base['rendered_tokens'] == budget['base'] and added['rendered_tokens'] == budget['additions']
    assert actual['rendered_tokens'] == load(ACTIVE / 'metadata.json')['total_length']
    grouped = defaultdict(lambda: dict(rows=0, rendered_tokens=0, response_tokens=0, sources=set()))
    for task in tasks:
        if not task['rows']:
            continue
        group = grouped[task['language'], task['family']]
        for m in METRICS:
            group[m] += task[m]
        group['sources'].add(task['source'])
    table = []
    for lang in LANGUAGES:
        for fam in FAMILIES:
            group = grouped.get((lang, fam))
            row = dict(language=lang, family=fam, coverage='dedicated_additions_lower_bound' if group else 'unavailable_not_zero',
                       classification_basis='Source/shard role and export language; inherited DFM11 excluded')
            row.update({m: group[m] if group else None for m in METRICS})
            row['sources'] = sorted(group['sources']) if group else []
            table.append(row)
    unknown = [dict(language='unknown', family='unclassified', component='inherited_dfm11', **base,
        reason='Transferred sampled backing store has no source-offset map; original tokenized union and corrected sampling log unavailable locally')]
    for (lang, fam), group in sorted(grouped.items()):
        if lang == 'unknown_or_multilingual':
            unknown.append(dict(language=lang, family=fam, component='dfm12_additions',
                                **{m: group[m] for m in METRICS}, sources=sorted(group['sources']),
                                reason='Do not apportion bilingual/multilingual tokens by row fractions; no does not identify nb versus nn'))
    report = dict(schema='dfm12-training-composition-v1', scope=dict(dataset=str(ACTIVE), epoch_directory='epoch_10',
        trainer_epoch=11, inherited_selection='data/sampled_dfm11/epoch_0', languages=LANGUAGES,
        definition='Selected whole-epoch rendered input plus response tokens, including repetitions and templates; not unique tokens or consumed-so-far',
        response_definition='Sampled resp_len sum; supervised response spans, distinct from all rendered tokens',
        packing_note='Next-token positions subtract one per target. Multipack/drop-last may leave positions unconsumed; not allocated per family here.'),
        totals=dict(combined=actual, inherited_dfm11=base, dfm12_additions=added,
                    dfm11_metadata_mean_not_selected_epoch=load(BASE / 'metadata.json')['total_length']),
        language_family_rows=table, source_rows=tasks, unknowns=unknown,
        limitations=['Missing cells are unknown, not zero exposure.',
            'Task-source taxonomy is not measured transfer to evaluation tasks.',
            'Mixed instruction, grounded instructions, knowledge chats and source topics do not prove dedicated instruction-following or knowledge training.',
            'Combined math/code and summary/rewrite are kept combined.',
            'Dedicated identity sources are verified zero in additions; noidentity does not assert absence of identity-like text in inherited data.',
            'Source attribution uses reconstructed source ranges and checks backing length/bounds; no full 894GB token-byte comparison.'],
        reconciliation=dict(active_equals_base_plus_additions=True, additions_equals_published_budget=True,
                            identity_sampled_rows=sum(t['rows'] for t in tasks if t['source'].startswith('dfm12-identity-'))),
        provenance=evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report['totals'], indent=2), flush=True)
    print('Wrote', output, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, default=Path('docs/reports/dfm12_training_composition.json'))
    parser.add_argument('--chunk-rows', type=int, default=1000000)
    parser.add_argument('--refine-only', action='store_true', help='Refine an existing base report using safe row-label alignment')
    parser.add_argument('--normalize-only', action='store_true', help='Normalize confirmed language aliases in an existing report')
    parser.add_argument('--inherited-provenance', type=Path, help='Verified recovered remote source-map directory')
    parser.add_argument('--error-row-provenance', type=Path, help='Produce sampled per-target multiplicities for inherited error metadata joins')
    parser.add_argument('--reclassify-inherited', action='store_true', help='Refresh source-category rules without repeating token validation')
    parser.add_argument('--percentages-only', action='store_true', help='Add/recompute percentages without rescanning source data')
    args = parser.parse_args()
    if args.percentages_only:
        pass
    elif args.reclassify_inherited:
        reclassify_inherited(args.output)
    elif args.error_row_provenance:
        error_row_counts(args.error_row_provenance, args.output, args.chunk_rows)
    elif args.inherited_provenance:
        recover_inherited(args.output, args.inherited_provenance, args.chunk_rows)
    elif args.normalize_only:
        normalize_report(args.output)
    elif args.refine_only:
        refine(args.output, args.chunk_rows)
    else:
        main(args.output, args.chunk_rows)
    if not args.error_row_provenance:
        publish_percentages(args.output)
