#!/usr/bin/env python3
"""Metadata-only decision-source ranking; never reads token arrays or row payloads."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re

try:
    from .decision_source_overlap import annotate
except ImportError:
    from decision_source_overlap import annotate

CLUSTERS = {
    'direct_labels': 'Classification/NLI/MCQ', 'tool_actions': 'Tools/actions',
    'instruction_constraints': 'Instruction constraints', 'math': 'Math',
    'code': 'Code', 'reasoning_mixed': 'Mixed reasoning', 'qa_evidence': 'QA/evidence',
}


def dataset_key(source):
    source = source.removesuffix(':native')
    bits = source.split('__')
    if bits[0] in ('flan', 'flan_factual', 'posttrain_natural_instructions'):
        # Keep independently defined tasks/prompts; combine only formatting modes.
        tail = '__'.join(bits[2:]) if len(bits) > 2 else bits[-1]
        tail = re.sub(r'\.(parquet|jsonl)(\.gz)?$', '', tail)
        return bits[0] + '/' + tail
    if bits[0] in ('tasksource', 'Platypus'):
        return bits[0] + '/' + re.sub(r'\.(parquet|jsonl)$', '', '__'.join(bits[1:]))
    if bits[0].startswith('dfm12-multilingual-synthetic-') and len(bits) > 1:
        return bits[0] + '/' + bits[1].split('.')[0]
    return bits[0]


def scores(name, cluster):
    """Explicit expert-prior heuristics, not measured or row-audited efficacy."""
    s = name.lower()
    defaults = {
        'direct_labels': (4, 4, 4, 'Recover original label/options; verify generative variants.'),
        'tool_actions': (5, 5, 3, 'Select available tool/action; validate state and alternatives.'),
        'instruction_constraints': (4, 4, 3, 'Choose compliant response; recover executable constraints.'),
        'math': (2, 4, 2, 'Verify answer equivalence and construct checked distractors.'),
        'code': (2, 4, 2, 'Recover tests or execution targets before generating alternatives.'),
        'reasoning_mixed': (3, 4, 2, 'Separate reasoning domains and verify targets.'),
        'qa_evidence': (4, 4, 2, 'Recover supporting context and independently validate distractors.'),
    }
    td, di, ease, reason = defaults[cluster]
    if re.search(r'entail|(?:^|[_/])(?:nli|snli|mnli|rte|qnli)|boolq|answer_verification|fact.verif', s):
        td, di, ease, reason = 5, 5, 4, 'Evidence-conditioned truth/entailment; preserve label semantics.'
    elif re.search(r'intent|banking|clinc|when2call|air_dialogue', s):
        td, di, ease, reason = 5, 5, 4, 'Intent or call/no-call decision; retain OOS and available actions.'
    elif re.search(r'sentiment|sarcas|stance|emotion', s):
        td, di, ease, reason = 3, 4, 4, 'Existing bounded label; check label set and domain shift.'
    elif re.search(r'(?:^|[/_-])(?:ner|dane)(?:$|[/_-])|skillspan|kompetencer', s):
        td, di, ease, reason = 3, 3, 3, 'Convert structured spans to candidate/entity-type decisions.'
    elif re.search(r'winograd|hellaswag|commonsense|openbookqa|scienceqa|piqa|copa', s):
        td, di, ease, reason = 3, 5, 4, 'Recover original commonsense/science alternatives and labels.'
    if cluster == 'tool_actions' and re.search(r'terminal|swe|repochat', s):
        td, di, ease, reason = 4, 4, 2, 'Long interactive trajectories require valid state/action reconstruction.'
    if cluster == 'tool_actions' and re.search(r'native.tool|tool.call|function.call|xlam|glaive', s):
        td, di, ease, reason = 5, 5, 4, 'Extract tool name from structured call; audit tools/history and negatives.'
    if cluster == 'instruction_constraints' and re.search(r'verified|ifbench|verifier', s):
        ease, reason = 4, 'Reuse retained instruction checks; verify that checkers survived SFT export.'
    if cluster == 'math' and re.search(r'dmmath|amps|sudoku|gsm|algebra|symbolic', s):
        ease, reason = 3, 'Numeric/symbolic target supports mechanical checking; validate equivalence.'
    if cluster == 'code' and re.search(r'debug|unit.test|execution|opencoder', s):
        ease, reason = 3, 'Potential execution/test labels; verify tests are available, not just code prose.'
    if cluster == 'qa_evidence' and re.search(r'squad|quac|coqa|extract|drop', s):
        ease, reason = 3, 'Context-plus-answer supports evidence selection; alternative truths remain valid.'
    if re.search(r'question_generation|answer_generation|explanation|generate_question|country_calling_code', s):
        ease = min(ease, 2)
        reason = 'Generative/name-match caveat: recover a bounded target; not a ready labelled decision.'
    if re.search(r'dfm14-(?!en-)[a-z]{2}-|dfm12-multilingual-synthetic-|dfm13_(?:baltic|wave4)_synthetic_', s):
        td, di = max(1, td - 0.5), max(1, di - 0.5)
        reason += ' Non-English transfer rather than direct English benchmark match.'
    if re.search(r'(?:^|[/_])(?:test|validation|heldout)(?:[/_.-]|$)', s):
        ease, reason = 0, 'HOLD: held-out/test-labelled source; must not become benchmark training data.'
    relevance = (td + di) / 2
    return dict(typed_decisions=td, decision_index=di, relevance=relevance,
                ease=ease, aggregate=20 * math.sqrt(relevance * ease), rationale=reason)


def text_index(root):
    """Only enumerate curated text trees, excluding model/token/cache payloads."""
    roots = [p for p in (root/'data').iterdir() if p.is_dir() and
             (p.name.startswith('converted') or 'sources' in p.name)]
    roots += [p for p in root.glob('exports_dfm*') if p.is_dir()]
    roots += [p for p in root.glob('export-upload*') if p.is_dir()]
    roots += [root/'data/mimir_benchmark_campaigns/accepted']
    roots += [root/'data/dfm15/small-additions/gsm-symbolic-en-train/input']
    roots += [root/'data/downloads/datasets']
    exact, packages = defaultdict(set), defaultdict(set)
    for base in roots:
        if not base.exists():
            continue
        for directory, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = [d for d in dirs if not any(t in d for t in
                       ('tokenized', 'sampled', '.cache', '.git', 'checkpoint'))]
            for f in files:
                if not f.endswith(('.parquet', '.jsonl', '.jsonl.gz', '.json.gz')):
                    continue
                path = Path(directory)/f
                rel = path.relative_to(base)
                exact['__'.join(rel.parts)].add(str(path))
                if base.name.startswith(('exports_dfm', 'export-upload')) and len(rel.parts) > 2 and rel.parts[1] == 'data':
                    packages[rel.parts[0]].add(str(path.parent))
    return exact, packages


def build(root):
    volume_path = root/'docs/reports/decision_dataset_volumes_20261021.json'
    volume = json.loads(volume_path.read_text())
    with gzip.open(root/'wiki/pages/decision-datasets/source-inventory.json.gz') as f:
        ledger = json.load(f)['sources']
    exact, packages = text_index(root)
    registry = {}
    remote_text = defaultdict(set)
    def collect_parts(obj):
        if isinstance(obj, dict):
            if isinstance(obj.get('task'), str) and isinstance(obj.get('source'), str):
                remote_text[obj['task']].add(obj['source'])
            for v in obj.values():
                collect_parts(v)
        elif isinstance(obj, list):
            for v in obj:
                collect_parts(v)
    collect_parts(json.loads((root/'data/dfm14/inheritance-reconciliation/remote/full_reference.json').read_text()))
    for e in json.loads((root/'data/dfm14/inheritance-reconciliation/dfm13-approved-sources.json').read_text()):
        registry[e['name']] = e
    for path in (root/'config').glob('dfm*_sources.json'):
        for e in json.loads(path.read_text()).get('additions', []):
            if 'name' in e:
                registry[e['name']] = {**registry.get(e['name'], {}), **e}
    evidence = {s['name']: s for s in ledger if s['kind'] == 'source_key'}
    grouped = defaultdict(list)
    for r in volume['ranges']:
        if r['cluster'] in CLUSTERS:
            grouped[(r['cluster'], dataset_key(r['source']))].append(r)
    rows = []
    for (cluster, name), ranges in grouped.items():
        originals = sorted({r['source'].removesuffix(':native') for r in ranges})
        prefix = originals[0].split('__')[0]
        paths, hf = {}, set()
        for source in originals:
            candidates = exact.get(source, set())
            if source.startswith('nemotron_terminal_corpus_native__'):
                candidates = candidates | exact.get('nemotron_terminal_corpus_native__'+source, set())
            if source.startswith(('flan__', 'flan_factual__', 'tasksource__', 'Platypus__', 'ampsmathematica__', 'dmmath__', 'acereason__', 'openthoughts2__', 'textbookreasoning__', 'sudoku_extreme__', 'openmathinstruct2__')):
                base = source.replace('flan_factual__', 'flan__', 1)
                for pre in ('sapient_cleaned__data_clustered__', 'sapient_cleaned__data__', 'sapient_cleaned__'):
                    candidates = candidates | exact.get(pre+base, set())
            for p in candidates:
                paths[p] = 'available text variant; see filename/tree for conversion stage'
            for p in remote_text.get(source, set()):
                paths[p] = 'exact pre-tokenization source from assembly receipt; producer filesystem, not checked remotely'
        e = registry.get(prefix, {})
        for key in ('hf_repo_id', 'repo_id'):
            if e.get(key):
                hf.add(e[key])
        for p in packages.get(prefix, set()):
            paths[p] = 'published pre-tokenization data directory'
        if prefix == 'gsm-symbolic-en-train':
            p = root/'data/dfm15/small-additions/gsm-symbolic-en-train/input'
            if p.exists():
                paths[str(p)] = 'prepared pre-tokenization input directory'
        if prefix.startswith('math-answer-conditioning-'):
            anchors = json.loads((root/'incoming/mimir-xl-20261015/data/dfm15/math-answer-conditioning-v2/source-ranges.json').read_text())
            for anchor in anchors:
                for p in exact.get(anchor['name'], set()):
                    paths[p] = 'upstream text from conditioning family; no standalone pre-tokenization conditioned dataset was materialized'
        # Producer paths are useful even when that machine is not mounted here.
        for key in ('output', 'source_root', 'source'):
            if e.get(key):
                p = Path(e[key]); p = p if p.is_absolute() else root/p
                paths[str(p)] = 'registry text path; ' + ('exists locally' if p.exists() else 'not present locally (producer path)')
        for ev in evidence.get(prefix, {}).get('evidence', []):
            d = ev.get('details', {})
            hf.update(d.get('repos', []))
            if d.get('repo'):
                hf.add(d['repo'])
            p = d.get('source_root')
            if p:
                p = Path(p); p = p if p.is_absolute() else root/p
                if p.exists():
                    paths[str(p)] = 'registered pre-tokenization source directory'
        if prefix in ('flan', 'flan_factual', 'tasksource', 'Platypus', 'dmmath', 'ampsmathematica'):
            hf.add('sapientinc/HRM-Text-data-io-cleaned-20260515 (umbrella; subtask shown)')
        score = scores(name, cluster)
        if prefix.startswith('math-answer-conditioning-'):
            score['rationale'] = 'Storage-only answer-conditioning variant, not an independent dataset; use parent text and reapply contract.'
        rows.append(dict(dataset=name, cluster=cluster, **score,
            epoch_rows=sum(r['epoch0_rows'] for r in ranges),
            epoch_tokens=sum(r['epoch0_tokens'] for r in ranges),
            stored_tokens=sum(r['reservoir_tokens'] for r in ranges),
            hf_ids=sorted(hf), text_paths=paths, source_keys=originals,
            range_ids=[r['range_id'] for r in ranges],
            native_repair=any(r['stage']=='native-repair' for r in ranges)))
    rows.sort(key=lambda r: (-r['aggregate'], -r['relevance'], -r['ease'], r['dataset'], r['cluster']))
    for i, r in enumerate(rows, 1):
        r['rank'] = i
    for key, field in [('epoch_rows', 'epoch0_rows'), ('epoch_tokens', 'epoch0_tokens'), ('stored_tokens', 'reservoir_tokens')]:
        assert sum(r[key] for r in rows) == sum(r[field] for r in volume['ranges'] if r['cluster'] in CLUSTERS)
    return annotate(dict(input_sha256=hashlib.sha256(volume_path.read_bytes()).hexdigest(), datasets=rows), root)


def render(report):
    rows = report['datasets']
    missing = sum(not r['text_paths'] for r in rows)
    lines = ['# Ranked Decision-Dataset Candidates: Top Seven Clusters', '',
        'Generated 2026-10-22. Scope: the seven clusters in the October 21 DFM15-backed census, including inherited DFM1-14 sources. Not an exhaustive union of every historical variant.', '',
        '## Scoring', '',
        '- TD and DI: relevance to Typed Decisions and the Decision Index public skill map, each 1-5 (1 indirect, 3 useful transfer, 5 direct skill match).',
        '- R = (TD + DI) / 2. E = ease of conversion, 0-5: 0 held-out/HOLD; 1 unresolved; 2 new validated alternatives/adjudication; 3 recoverable targets plus substantial checks; 4 structured labels/calls or recoverable checks; 5 verified turnkey conversion (not awarded without row validation).',
        '- Score = 20 * sqrt(R * E), on 0-100. Equal importance, penalizing a weak dimension. Ties use R, E, then dataset name, not dataset size.',
        '- Explicit non-English multilingual synthetic packages receive a 0.5-point relevance discount on both benchmarks; this is a transfer assumption, not a measured language penalty.',
        '- Scores are explicit source/task-name and documented-format judgments, not measured gains or a row-level audit. False-positive family matches are retained for count reconciliation and downgraded when recognizable. Membership here is not permission to train on benchmark test data.',
        '- Rows/epoch are sampled occurrences, including repeats. Tokens/epoch and stored tokens are billions of existing serialized tokens, not post-conversion yield. Stored tokens include superseded variants. Sources with zero exposure remain listed.',
        '- Shards and FLAN shot modes are grouped; distinct Natural Instructions tasks, prompt variants and source revisions remain distinct dataset/subdataset rows. A dataset spanning clusters can have multiple explicit subdataset rows. Counts are not unique-content counts.',
        '- Filesystem links below are PRE-TOKENIZATION text files/directories only. Producer-only paths are labelled. Upstream/older representations must not be confused with the exact repaired representation. Native reasoning repair may have happened during tokenization; those entries explicitly warn that listed text precedes that repair.', '',
        'Benchmark basis: [Typed Decisions](https://huggingface.co/datasets/LocalLLaMA/typed-decisions), [Decision Index](https://github.com/apolinario/decision-index), and the [local benchmark assessment](../wiki/pages/decision-datasets/benchmark-priorities.md). Decision Index 0.4 full ranking is private; these scores concern known skills, not private test overlap.', '',
        f'**{len(rows):,} dataset/subdataset entries; {sum(r["epoch_rows"] for r in rows):,} sampled rows/epoch; {sum(r["epoch_tokens"] for r in rows)/1e9:.6f}B tokens/epoch. {missing} entries have no resolved pre-tokenization path and are explicitly flagged.**', '',
        '## Ranked Table', '',
        '| Rank | Dataset/subdataset | Cluster | TD | DI | R | E | Score /100 | Rows/epoch | Tokens/epoch B | Stored B | Conversion / caution | JEV sources overlap | Pre-tokenization paths |',
        '|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|']
    if 'jev_manifest_overlap' in report:
        m = report['jev_manifest_overlap']
        pos = lines.index('## Ranked Table')
        lines[pos:pos] = ['## JEV Source Overlap', '',
            f'Checked against [the pinned sources.yaml]({m["url"]}): **{m["repository_count"]} repositories / {m["task_count"]} task/config entries**. Snapshot SHA-256: `{m["sha256"]}`.', '',
            '; '.join(f'**{key}: {value}**' for key, value in sorted(m['counts'].items()))+'.', '',
            '**EXACT REPO** = same recorded HF source ID; **TASK/FAMILY MATCH** = matching named task/alias; **POSSIBLE DERIVATIVE** = synthetic/repaired family match requiring lineage confirmation; **NOT IDENTIFIED** = no identified match, not certified disjointness.', '',
            'These are source-level flags, NOT proof of duplicate rows, matching splits or benchmark contamination. This Tasksource training collection is distinct from LocalLLaMA/typed-decisions. Scores/ranks, counts and pre-tokenization paths are unchanged. See each dataset entry for matched manifest task keys. An exact repo flag can cover multiple configs; it does not certify their inclusion in our subset.', '']
    for r in rows:
        n = r['rank']
        status = r.get('jev_overlap', {}).get('status', 'NOT CHECKED')
        lines.append(f'| {n} | `{r["dataset"]}` | {CLUSTERS[r["cluster"]]} | {r["typed_decisions"]} | {r["decision_index"]} | {r["relevance"]:.1f} | {r["ease"]} | {r["aggregate"]:.2f} | {r["epoch_rows"]:,} | {r["epoch_tokens"]/1e9:.6f} | {r["stored_tokens"]/1e9:.6f} | {r["rationale"]} | **{status}** | [Full paths / overlap](#dataset-{n}) |')
    lines += ['', '## Full Pre-Tokenization Paths', '', 'Path lists include available representations, not independent additional datasets. Parent directories contain the source shards. Counts above remain those of the frozen token census, not re-counts of these text files.', '']
    for r in rows:
        lines += [f'<a id="dataset-{r["rank"]}"></a>', f'### {r["rank"]}. {r["dataset"]}', '',
                  'HF: ' + (', '.join(f'`{h}`' for h in r['hf_ids']) or 'Not confidently resolved from source registry; local identifier retained.'), '']
        if 'jev_overlap' in r:
            o = r['jev_overlap']
            lines += [f'**JEV overlap: {o["status"]}.** {o["basis"]}', '',
                      'Matched `sources.yaml` entries: ' + (', '.join(f'`{k}`' for k in o['tasks']) or 'None identified.'), '']
        if r['native_repair']:
            lines += ['**Representation warning:** includes appended native-reasoning replacements. Listed upstream text is not asserted to contain the final repaired representation.', '']
        if not r['text_paths']:
            lines += ['**UNRESOLVED:** no verified pre-tokenization path found. No tokenized substitute is listed.', '']
        for p, status in sorted(r['text_paths'].items()):
            lines.append(f'- `{p}` ({status}).')
        lines += ['', 'Exact source keys: ' + ', '.join(f'`{s}`' for s in r['source_keys']), '']
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = build(args.root)
    path = args.root/'docs/decision-datasets-ranked.md'
    path.write_text(render(report))
    path.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(path=str(path), datasets=len(report['datasets']),
        missing_paths=[r['dataset'] for r in report['datasets'] if not r['text_paths']]), indent=2))


if __name__ == '__main__':
    main()
