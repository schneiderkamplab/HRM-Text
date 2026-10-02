#!/usr/bin/env python3
"""Seal evaluation-only bilingual compositions, disjoint from prior prompt text."""
import argparse
import gzip
import json
from pathlib import Path
import sys
import unicodedata

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import digest, file_hash, load, write_json


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def exclusion_text(paths):
    corpus, pins = set(), {}
    for path in paths:
        path = Path(path).resolve()
        files = sorted(path.rglob('*')) if path.is_dir() else [path]
        for file in files:
            if not file.is_file() or not file.name.endswith(('.json', '.jsonl', '.jsonl.gz', '.yaml')):
                continue
            pins[str(file)] = file_hash(file)
            opener = gzip.open if file.name.endswith('.gz') else open
            with opener(file, 'rt', encoding='utf-8') as handle:
                if '.jsonl' in file.name:
                    for line in handle:
                        if line.strip():
                            corpus.update(normalize(s) for s in strings(json.loads(line)))
                else:
                    document = yaml.safe_load(handle) if file.suffix == '.yaml' else json.load(handle)
                    corpus.update(normalize(s) for s in strings(document))
    if not pins:
        raise ValueError('No exclusion sources read')
    return corpus, pins


def cases_from(spec, excluded):
    cases, names, prompts = [], set(), set()
    if len(spec['cases']) != 20:
        raise ValueError('Require twenty paired compositions')
    for case in spec['cases']:
        if case['id'] in names or not case['facts'] or len(case['criteria']) != 2:
            raise ValueError('Invalid family or rubric')
        names.add(case['id'])
        for language in ('da', 'en'):
            users = case[language]
            if len(users) != 2 or not all(isinstance(s, str) and s.strip() for s in users):
                raise ValueError('Require two nonempty user turns')
            for prompt in users:
                key = normalize(prompt)
                if key in excluded or key in prompts:
                    raise ValueError('Prompt overlaps prior corpus or another holdout: ' + prompt)
                prompts.add(key)
            cases.append(dict(id=digest([case['id'], language, users]), family=case['id'],
                language=language, suite='sealed_identity_compositions', users=users,
                criteria=case['criteria'], facts=case['facts'], training_allowed=False,
                history_policy='Generate each followup using this rollout history; never supply gold answers'))
    return cases


def seal(spec_path, output, exclusions, authority):
    excluded, pins = exclusion_text(exclusions)
    spec = yaml.safe_load(Path(spec_path).read_text())
    cases = cases_from(spec, excluded)
    authority = Path(authority).resolve()
    authorities = {name: file_hash(authority/name) for name in ('facts.json', 'authority-supplement.json')}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'cases.json', cases)
    write_json(output/'rubric.json', dict(
        scoring='Semantic per-turn factual assessment, not anchor matching or exact wording',
        correct='All requested supported facts present, roles/scopes correct; no unsupported additions',
        partial='Correct but missing requested information, without factual contradiction',
        fail='Contradiction, invented identity claim, unsupported attribution or failure to answer',
        invalid='Infrastructure failure or incomplete output; never count as a semantic pass',
        caveat='Same known facts and themes; prompt-composition holdout, not unseen-knowledge or native-human gold'))
    manifest = dict(schema='sealed-identity-compositions-v1', conversations=len(cases), turns=80,
        source=str(Path(spec_path).resolve()), source_sha256=file_hash(spec_path),
        authority=str(authority), authority_pins=authorities, exclusions=pins,
        normalized_exclusion_strings=len(excluded), exact_normalized_overlap=0,
        language_counts={'da': 20, 'en': 20}, training_allowed=False, evaluated=False,
        model_outputs_used=False, evidence_scope='Exact normalized disjointness, not semantic-topic disjointness',
        files={name: file_hash(output/name) for name in ('cases.json', 'rubric.json')})
    write_json(output/'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exclude', type=Path, action='append', required=True)
    parser.add_argument('--authority', type=Path, required=True)
    args = parser.parse_args()
    result = seal(args.spec, args.output, args.exclude, args.authority)
    print(json.dumps({k: result[k] for k in ('conversations','turns','language_counts','exact_normalized_overlap')}, indent=2))
