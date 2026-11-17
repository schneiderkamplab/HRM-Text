"""Conservative manifest-level overlap annotation, not row-level deduplication."""
from collections import Counter, defaultdict
import hashlib
import re
import yaml

REVISION = '8b1afcc6ad12554b347134a91b5f0dc6ae2361db'
SNAPSHOT = 'docs/reports/tasksource-jev-sources-20261022.yaml'
URL = f'https://huggingface.co/datasets/tasksource/tasksource-jev-typed-decisions/blob/{REVISION}/sources.yaml'
GENERIC = {'default', 'all', 'train', 'test', 'validation', 'classification',
           'nli', 'qa', 'mc', 'binary', 'math', 'code', 'social', 'atomic',
           'reasoning', 'search', 'sentiment', 'emotion', 'glue', 'super_glue',
           'multilingual', 'extraction', 'intent', 'instruction', 'science'}


def normalize(value):
    return re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_')


def repositories(entry):
    result = set()
    for key in ('dataset', 'originals', 'data_files_from'):
        value = entry.get(key, [])
        if isinstance(value, str):
            value = [value]
        result.update(x for x in value if isinstance(x, str) and '/' in x)
    result.update(entry.get('revisions', {}))
    return result


def compile_manifest(manifest):
    by_repo, aliases = defaultdict(set), defaultdict(set)
    for task, entry in manifest['sources'].items():
        for repo in repositories(entry):
            by_repo[repo.lower()].add(task)
        # Exact task/config is preferable to a broad repo leaf such as GLUE.
        candidates = {task, task.split('/')[0]}
        candidates.update(repo.split('/')[-1] for repo in repositories(entry))
        if task.startswith(('glue/', 'super_glue/')):
            # NI/FLAN often names the task without the umbrella collection.
            candidates.add(task.split('/')[1])
        for candidate in candidates:
            name = normalize(candidate)
            if (len(name) >= 4 or name in {'rte', 'wic'}) and name not in GENERIC:
                aliases[name].add(task)
                if len(name.replace('_', '')) >= 6:
                    # Known publisher punctuation variants: social_i_qa vs socialiqa,
                    # math_qa vs mathqa. Still require complete token boundaries.
                    aliases[name.replace('_', '')].add(task)
    return by_repo, aliases


def match(row, compiled):
    by_repo, aliases = compiled
    exact = set()
    for repo in row.get('hf_ids', []):
        exact.update(by_repo.get(repo.lower(), set()))
    if exact:
        return dict(status='EXACT REPO', tasks=sorted(exact),
                    basis='Recorded HF repository ID matches dataset/original/revision provenance; config and row overlap not established.')
    name = normalize(row['dataset'])
    found = []
    for alias, tasks in aliases.items():
        if re.search(r'(?:^|_)' + re.escape(alias) + r'(?:_|$)', name):
            found.append((alias, tasks))
    # A specific matching alias supersedes a shorter contained alias. This
    # prevents glue/mnli from claiming every GLUE view or SNLI derivative.
    found = [(a, tasks) for a, tasks in found if not any(
        a != b and re.search(r'(?:^|_)'+re.escape(a)+r'(?:_|$)', b)
        for b, _ in found)]
    if not found:
        return dict(status='NOT IDENTIFIED', tasks=[],
                    basis='No repository or bounded task-name match; not proof of disjoint rows.')
    derived = bool(re.search(r'synth|repaired|entailment\.jsonl|_worked|_translated', row['dataset'].lower()))
    return dict(status='POSSIBLE DERIVATIVE' if derived else 'TASK/FAMILY MATCH',
                tasks=sorted(set().union(*(tasks for _, tasks in found))),
                basis='Bounded identifier aliases: '+', '.join(a for a, _ in found)+
                '. Shared upstream task inferred; prompt/config/split/row identity unverified.')


def annotate(report, root):
    path = root/SNAPSHOT
    manifest = yaml.safe_load(path.read_text())
    compiled = compile_manifest(manifest)
    for row in report['datasets']:
        row['jev_overlap'] = match(row, compiled)
    report['jev_manifest_overlap'] = dict(url=URL, revision=REVISION,
        snapshot=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        tasksource_commit=manifest['tasksource_commit'],
        repository_count=len(manifest['datasets']), task_count=len(manifest['sources']),
        counts=dict(Counter(r['jev_overlap']['status'] for r in report['datasets'])),
        scope='Source/task-level overlap only; no sample payload comparison or contamination finding.')
    return report
