#!/usr/bin/env python3
"""Bounded metadata-only DFM inventory. Never opens dataset rows or numpy arrays."""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml


def assessment(name):
    """Triage only: identifiers do not establish labels or valid negatives."""
    name = name.lower()
    rules = [
        (r'preference|preferred|helpsteer|simpo|(?<![a-z])dpo(?![a-z])', 'preference', 'C', 'preference-and-audit-evidence'),
        (r'paragraph.*reorder|reorder.*paragraph', 'paragraph_order', 'B', 'paragraph-permutations-b'),
        (r'prefix.continu', 'continuation_needs_validated_negatives', 'C', 'denoising-span-filling-and-prefix-continuation-bc'),
        (r'denois|span.fill|error.correct|(?<![a-z])gec(?![a-z])', 'text_reconstruction', 'B', 'denoising-span-filling-and-prefix-continuation-bc'),
        (r'(?<![a-z])(?:nli|cola|dane|ner|arc|dala)(?![a-z])|sentiment|acceptability|skillspan|kompetencer|scicite|boolq|hellaswag|winogrande|openbookqa|commonsenseqa|piqa', 'existing_label_candidate', 'A', 'labelled-tasks-a'),
        (r'tool|agentic|terminal|repochat|swe|search', 'tool_agentic', 'C', 'tool-use-and-agentic-trajectories-abc'),
        (r'math|gsm|reason|code|sudoku|amps|scibench|platypus', 'math_code_reasoning', 'C', 'math-code-and-reasoning-abc'),
        (r'summar|translation|opus|chat|arena|instruct|qa|wiki|lexdk|dbc|flan|tulu|dolci|hermes', 'grounded_or_open_response', 'C', 'grounded-qa-summary-translation-and-chat-mostly-c'),
        (r'dynaword|common.pile|raw', 'raw_or_transform_unresolved', 'D', 'grounded-qa-summary-translation-and-chat-mostly-c'),
    ]
    for pattern, family, rubric, recipe in rules:
        if re.search(pattern, name):
            return dict(assessment_family=family, rubric= rubric, recipe=recipe,
                        assessment_confidence='inferred_name_only',
                        assessment_status='requires_source_schema_and_target_validation')
    return dict(assessment_family='unmapped_unknown', rubric='D', recipe='unmapped_unknown',
                assessment_confidence='unknown', assessment_status='deferred_not_evidence_of_poor_quality')


def source_key(task):
    # Keep heterogeneous Sapient subdatasets, not just the umbrella collection.
    if task.startswith(('sapient_cleaned__', 'Platypus__', 'flan__', 'tasksource__')):
        return task.removesuffix('.parquet').removesuffix('.jsonl')
    return task.split('__')[0]


class Inventory:
    def __init__(self, root):
        self.root = Path(root)
        self.records = {}
        self.tasks = defaultdict(set)
        self.inputs = {}
        self.gaps = []
        self.task_evidence = {}

    def read(self, path):
        path = Path(path)
        relative = str(path.relative_to(self.root))
        if not path.exists():
            self.gaps.append(dict(path=relative, reason='missing_local_metadata'))
            return None
        if path.stat().st_size > 64 * 1024 * 1024:
            self.gaps.append(dict(path=relative, reason='metadata_exceeds_64MiB_limit'))
            return None
        data = path.read_bytes()
        self.inputs[relative] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        if path.suffix == '.json':
            return json.loads(data)
        if path.suffix in ('.yaml', '.yml'):
            return yaml.safe_load(data)
        return data.decode()

    def add(self, name, kind, version, membership, path, pointer='', details=None):
        if not isinstance(name, str) or not name:
            return
        key = f'{kind}:{name}'
        record = self.records.setdefault(key, dict(id=key, name=name, kind=kind,
            **assessment(name), evidence=[]))
        evidence = dict(dfm=version, membership=membership,
                        file=str(Path(path).relative_to(self.root)), pointer=pointer)
        if details:
            evidence['details'] = details
        if evidence not in record['evidence']:
            record['evidence'].append(evidence)

    def task(self, name, version, membership, path, pointer='', details=None):
        key = source_key(name)
        self.tasks[key].add(name)
        group = (key, version, membership, str(path))
        if group not in self.task_evidence:
            self.add(key, 'source_key', version, membership, path)
            evidence = self.records[f'source_key:{key}']['evidence'][-1]
            evidence.update(pointers=[], task_observations=0)
            self.task_evidence[group] = evidence
        evidence = self.task_evidence[group]
        evidence['pointers'].append(pointer)
        evidence['task_observations'] += 1
        for field in ('sampled_rows_report_total', 'sampled_tokens_report_total'):
            if details and field in details:
                evidence[field] = evidence.get(field, 0) + details[field]

    def build(self):
        root = self.root
        for version in range(1, 16):
            stem = 'dfm' if version == 1 else f'dfm{version}'
            self.read(root / f'config/data/{stem}.yaml')
            prefix = root / f'data_io/prefix_config_{stem}.yaml'
            if version <= 11:
                for i, item in enumerate(self.read(prefix) or []):
                    self.add(item['prefix'], 'sampling_prefix', version, 'declared_sampling_rule', prefix, f'/{i}', item)
            report = root / f'data/show_analytics_{stem}.md'
            if report.exists():
                active = False
                for line_no, line in enumerate(self.read(report).splitlines(), 1):
                    if line.startswith('### '):
                        active = line == '### Task Coverage Stats'
                    if not active or not line.startswith('| **'):
                        continue
                    cells = next(csv.reader([line], delimiter='|'))
                    name = cells[1].strip().strip('*')
                    if name == 'GLOBAL':
                        continue
                    values = [int(c.strip().split(' ')[0].replace(',', '')) for c in cells[2:8]]
                    self.task(name, version, 'reported_sampled_positive' if values[2] > 0 else 'reported_sampled_zero',
                              report, f'line:{line_no}', dict(task=name, available_rows=values[0],
                              available_tokens=values[1], sampled_rows_report_total=values[2],
                              sampled_tokens_report_total=values[3]))
            else:
                self.gaps.append(dict(dfm=version, reason='no_canonical_per_task_analytics_report'))

        # Immediate directory entries only: no traversal into payload directories.
        for version in (6, 11):
            directory = root / f'data/tokenized_dfm{version}'
            if directory.exists():
                names = sorted(p.name for p in directory.iterdir() if p.is_dir() or p.is_symlink())
                self.inputs[str(directory.relative_to(root))] = dict(
                    kind='immediate_directory_name_snapshot', entries=len(names),
                    sha256=hashlib.sha256(json.dumps(names).encode()).hexdigest())
                for name in names:
                    self.task(name, version, 'tokenized_directory_not_sample_proof', directory, name)

        # Parse static constructors without importing the downloader or accessing HF.
        downloader = root / 'scripts/download_training_datasets.py'
        tree = ast.parse(self.read(downloader))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('HFDataset', 'LocalDataset'):
                try:
                    fields = {k.arg: ast.literal_eval(k.value) for k in node.keywords}
                except (ValueError, TypeError):
                    self.gaps.append(dict(path=str(downloader.relative_to(root)), line=node.lineno, reason='nonliteral_manifest_constructor'))
                    continue
                name = fields.get('repo_id', fields.get('name'))
                self.add(name, 'repository' if 'repo_id' in fields else 'local_collection', None,
                         'registered_candidate_not_membership', downloader, f'line:{node.lineno}', fields)

        for path in sorted((root / 'config').glob('dfm*_sources.json')):
            version = int(re.search(r'dfm(\d+)', path.name)[1])
            data = self.read(path)
            def visit(value, pointer=''):
                if isinstance(value, dict):
                    repo = value.get('repo_id') or value.get('hf_repo_id') or value.get('repo')
                    name = value.get('name') or value.get('source')
                    details = {k: value[k] for k in ('name', 'source', 'repo_id', 'hf_repo_id', 'repo', 'rows', 'selected_rows', 'tokens', 'sampled', 'status', 'revision', 'task', 'category') if k in value}
                    if repo:
                        self.add(repo, 'repository', version, 'declared_registry', path, pointer, details)
                    if name and (repo or 'parts' in value):
                        self.add(name, 'source_key', version, 'declared_registry', path, pointer, details)
                    for key, item in value.items():
                        if key not in ('parts', 'files'):
                            visit(item, pointer + '/' + key)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        visit(item, pointer + '/' + str(i))
            visit(data)

        for version in (10, 11):
            paths = sorted((root / f'exports_dfm{version}').glob('*/metadata/manifest.json'))
            top = root / f'exports_dfm{version}/manifest.json'
            if top.exists():
                paths.append(top)
            for path in paths:
                data = self.read(path)
                for i, item in enumerate(data.get('packages', [data])):
                    name = item.get('name', path.parent.parent.name)
                    self.add(name, 'export_package', version, 'export_manifest_not_sample_proof', path, f'/packages/{i}',
                             {k: item[k] for k in ('category', 'rows', 'status', 'upstream', 'transformation', 'source_root') if k in item})
                    for upstream in item.get('upstream', []):
                        self.add(upstream, 'repository', version, 'upstream_attribution_not_direct_membership', path, f'/packages/{i}/upstream')

        path = root / 'docs/reports/dfm8_to_dfm13_lineage_20261006.json'
        for i, row in enumerate((self.read(path) or {}).get('rows', [])):
            self.add(row['original'], 'repository' if '/' in row['original'] else 'local_collection', 8,
                     'historical_lineage_report', path, f'/rows/{i}', row)
            for repo in row['current_repositories']:
                self.add(repo, 'repository', 13, 'successor_lineage_report', path, f'/rows/{i}')
        path = root / 'docs/reports/dfm13_hf_repository_counts_20261006.json'
        data = self.read(path) or {}
        for group in ('inherited', 'additions'):
            for i, row in enumerate(data.get(group, [])):
                self.add(row['source'], 'source_key', 13, 'reported_included_source', path, f'/{group}/{i}', row)
                for repo in row.get('repos', [row['repo']] if 'repo' in row else []):
                    self.add(repo, 'repository', 13, 'reported_included_repository', path, f'/{group}/{i}', row)
        path = root / 'data/dfm14/inheritance-reconciliation/component-inventory.json'
        for i, row in enumerate(self.read(path) or []):
            self.task(row['part'], int(row['group'].removeprefix('dfm')), 'reconciled_component_inventory',
                      path, f'/{i}', row)
        path = root / 'data/category_preparation/dfm15-epoch0-source-domains-published-20261020/category-manifest.json'
        for i, row in enumerate((self.read(path) or {}).get('ranges', [])):
            self.task(row['source'], 15, 'stored_token_range_not_positive_sample_proof', path, f'/ranges/{i}',
                      {k: row[k] for k in ('source', 'start', 'end', 'stage')})

        records = sorted(self.records.values(), key=lambda r: r['id'])
        for record in records:
            record['task_names'] = sorted(self.tasks.get(record['name'], [])) if record['kind'] == 'source_key' else []
            versions = sorted({e['dfm'] for e in record['evidence'] if e['dfm'] is not None})
            record['mentioned_dfm_versions'] = versions
            record['not_observed_same_identifier_in_dfm15_metadata'] = bool(versions) and max(versions) < 15
        self.gaps.extend([
            dict(reason='canonical_analytics_are_historical_snapshots_not_certified_latest', dfm=9,
                 detail='The canonical DFM9 report has the same task counts as DFM8; later extension coverage is not proved by that report.'),
            dict(reason='variant_configs_and_archived_sampling_reports_not_exhaustively_ingested',
                 detail='Canonical versions, registries, lineage, exports and DFM15 ranges are covered; mini/post/smoke/context-window variant-only membership can remain unknown.'),
            dict(reason='alias_resolution_incomplete',
                 detail='Exact names are retained; source-key, export-package and repository identity are not globally reconciled.'),
        ])
        return dict(schema='decision-source-inventory-v1', scope='Exact identifier union over enumerated local metadata inputs; not unique underlying datasets or row census',
                    regenerate='python scripts/build_decision_dataset_inventory.py',
                    artifacts=dict(full_evidence='source-inventory.json.gz', index='source-inventory.tsv', overview='source-inventory-summary.json'),
                    rubric=dict(A='existing label/options candidate', B='mechanical target candidate; corruption-validity filtering required', C='validated negatives/new adjudication needed', D='unmapped/deferred; not a quality verdict'),
                    limitations=[
                        'All recipe assignments are inferred from identifiers, not verified source schemas or checked rows.',
                        'No accepted/generated reference is assumed uniquely best; eligibility requires recipe safeguards.',
                        'Repositories, export packages, sampling prefixes and source keys overlap; their counts must not be summed as unique datasets.',
                        'not_observed_same_identifier_in_dfm15_metadata does not imply removal; renames/replacements may retain lineage.',
                        'Sampling report totals can span multiple epochs and are not unique rows or per-epoch counts.',
                        'Stored ranges can contain zero-selected or superseded rows; registry and downloader declarations do not prove training exposure.',
                        'DFM9 union_manifest is known stale and deliberately unused; no implicit inheritance or name-based repository alias merging.',
                        'Only enumerated metadata inputs are exhaustive; unregistered/deleted historical inputs and original label availability remain unknown.',
                    ], summary=dict(records=len(records), by_kind=dict(Counter(r['kind'] for r in records)),
                       by_assessment_family=dict(Counter(r['assessment_family'] for r in records)),
                       exact_task_names=len(set().union(*self.tasks.values())) if self.tasks else 0,
                       per_dfm_evidence_observations={str(v): dict(sum_counters(records, v)) for v in range(1, 16)},
                       per_dfm_identifier_counts={str(v): len([r for r in records if v in r['mentioned_dfm_versions']]) for v in range(1, 16)}),
                    inputs=self.inputs, gaps=self.gaps, sources=records)


def sum_counters(records, version):
    counts = Counter()
    for record in records:
        for evidence in record['evidence']:
            if evidence['dfm'] == version:
                counts[evidence['membership']] += evidence.get('task_observations', 1)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('wiki/pages/decision-datasets/source-inventory.json.gz'))
    args = parser.parse_args()
    result = Inventory(args.root).build()
    output = args.output if args.output.is_absolute() else args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip.compress((json.dumps(result, separators=(',', ':'), ensure_ascii=True) + '\n').encode(), mtime=0))
    columns = ['id', 'name', 'kind', 'assessment_family', 'rubric', 'recipe', 'assessment_confidence', 'mentioned_dfm_versions', 'not_observed_same_identifier_in_dfm15_metadata', 'task_count', 'evidence_files', 'membership_types']
    with output.with_name('source-inventory.tsv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        for row in result['sources']:
            row = dict(row, task_count=len(row['task_names']),
                       evidence_files=sorted({e['file'] for e in row['evidence']}),
                       membership_types=sorted({e['membership'] for e in row['evidence']}))
            writer.writerow({k: json.dumps(v, ensure_ascii=True) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    summary = {k: v for k, v in result.items() if k != 'sources'}
    output.with_name('source-inventory-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    output.with_name('source-inventory.json').unlink(missing_ok=True)
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
