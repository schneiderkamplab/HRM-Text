#!/usr/bin/env python3
"""Pinned, train-only jjzha additions; CroCo remains an audit candidate."""
import argparse
from collections import Counter
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
    Path(f.name).replace(path)


def records(path):
    if path.suffix == '.parquet':
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(batch_size=256):
            yield from batch.to_pylist()
    else:
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def key(row, kind):
    if kind == 'bio':
        value = ' '.join(row['tokens'])
    elif kind == 'mcq':
        value = row['question']
    elif kind == 'instruct':
        # Templates vary: compare the review, not its instruction prefix.
        value = row['inputs'].split('\n\n', 1)[-1]
    else:
        value = json.dumps(row['messages'], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(' '.join(value.split()).encode()).hexdigest()


def spans(tokens, tags):
    if len(tokens) != len(tags):
        raise ValueError('BIO length mismatch')
    result, start, label = [], None, None
    for i, tag in enumerate([*tags, 'O']):
        prefix, _, category = tag.partition('-')
        category = category or 'SPAN'
        if prefix not in ('B', 'I', 'O'):
            raise ValueError('Unknown BIO tag')
        if prefix == 'I' and (start is None or category != label):
            raise ValueError('Orphan or conflicting I tag')
        if start is not None and prefix != 'I':
            result.append(dict(label=label, start_token=start, end_token=i,
                               text=' '.join(tokens[start:i])))
            start = None
        if prefix == 'B':
            start, label = i, category
    return result


def convert(row, spec):
    kind = spec['kind']
    if kind == 'bio':
        tokens = row['tokens']
        if not tokens or not all(isinstance(t, str) and t for t in tokens):
            raise ValueError('Invalid tokens')
        answer = {k: spans(tokens, v) for k, v in row.items() if k.startswith('tags_')}
        if not answer:
            raise ValueError('Missing annotations')
        if spec['language'] == 'da':
            prompt = ('Udtræk annoterede kompetence- og vidensspænd fra denne tokeniserede jobtekst. '
                      'Svar som JSON med tags_skill og tags_knowledge. Hvert spænd skal have label '
                      '(SPAN), start_token (0-baseret), end_token (eksklusiv) og text '
                      '(tokens adskilt af mellemrum). Brug tomme lister, hvis der ingen spænd er.\n\n')
        else:
            labels = ('SKILL, QUALIFICATION, EXPERIENCE, OCCUPATION, DOMAIN' if spec['name'] == 'jjzha_green' else 'SPAN')
            prompt = (f'Extract annotated spans from this tokenized job text. Return JSON with keys {", ".join(answer)}. '
                      f'Each span has label ({labels}), start_token (zero-based), end_token (exclusive), '
                      'and text (tokens joined by spaces). Skills are abilities/tasks; knowledge is subject expertise. '
                      'Use empty lists when no spans are present.\n\n')
        prompt += json.dumps(tokens, ensure_ascii=False)
        response = json.dumps(answer, ensure_ascii=False)
    elif kind == 'instruct':
        prompt, response = row['inputs'], row['targets']
    elif kind == 'mcq':
        if row.get('split') != 'train':
            raise ValueError('Non-training exam row')
        options = row['options']
        answer = int(row['answer']) - 1
        if not 0 <= answer < len(options) <= 26:
            raise ValueError('Invalid 1-based answer')
        prompt = 'Kies het juiste antwoord. Geef de letter en de antwoordtekst.\n\n' + row['question'] + '\n\n'
        prompt += '\n'.join(f'{chr(65+i)}. {v}' for i, v in enumerate(options))
        response = f'{chr(65+answer)}. {options[answer]}'
    else:
        messages = []
        for m in row['messages']:
            if m.get('function_calls') or m.get('functions') or m.get('tool_calls'):
                raise ValueError('Tool conversion required')
            if m['role'] not in ('system', 'user', 'assistant') or not isinstance(m.get('content'), str) or not m['content'].strip():
                raise ValueError('Invalid text message')
            messages.append(dict(role=m['role'], content=m['content']))
        roles = [m['role'] for m in messages]
        roles = roles[1:] if roles and roles[0] == 'system' else roles
        if not roles or roles != ['user', 'assistant'] * (len(roles)//2):
            raise ValueError('Incomplete or nonalternating conversation')
        return messages
    if not isinstance(prompt, str) or not isinstance(response, str) or not prompt.strip() or not response.strip():
        raise ValueError('Empty prompt/response')
    return [dict(role='user', content=prompt), dict(role='assistant', content=response)]


def prepare(spec, output_root, download_root):
    from huggingface_hub import hf_hub_download
    output = output_root / spec['name']
    if output.exists():
        raise ValueError(f'Refusing to overwrite {output}')
    raw = download_root / spec['name'] / spec['revision']
    paths = {f: Path(hf_hub_download(spec['repo_id'], f, repo_type='dataset',
             revision=spec['revision'], local_dir=raw)) for f in ['README.md', *spec['files']]}
    heldout = set()
    if spec.get('train_file'):
        for name in spec['files']:
            if name != spec['train_file']:
                heldout.update(key(r, spec['kind']) for r in records(paths[name]))
    output.mkdir(parents=True)
    counts, languages, sources, seen = Counter(), Counter(), Counter(), set()
    audit_required = spec['kind'] in ('chat_audit', 'instruct')
    destination = output / ('candidates.jsonl' if audit_required else 'train.jsonl')
    (output/'metadata').mkdir()
    with destination.open('w') as out, (output/'metadata/rejected.jsonl').open('w') as reject:
        for name in ([spec['train_file']] if spec.get('train_file') else spec['files']):
            for ordinal, row in enumerate(records(paths[name])):
                counts['input_rows'] += 1
                try:
                    digest = key(row, spec['kind'])
                    if digest in heldout:
                        raise ValueError('heldout_overlap')
                    if digest in seen:
                        raise ValueError('duplicate_input')
                    messages = convert(row, spec)
                    if any(marker in m['content'] for m in messages for marker in ('<|im_start|>', '<start_of_turn>', '[INST]')):
                        raise ValueError('Embedded chat template')
                    seen.add(digest)
                    language = spec.get('language', Path(name).stem)
                    example = dict(id=f'{spec["name"]}:{name}:{ordinal}', messages=messages,
                        target_message_index=len(messages)-1, chat_template_kwargs={'enable_thinking': False},
                        metadata=dict(source=spec['repo_id'], revision=spec['revision'], file=name,
                            row=ordinal, source_id=row.get('id', row.get('idx')), language=language,
                            source_dataset=row.get('source_dataset'), domain=row.get('domain'),
                            license=spec['license'], audit_required=audit_required))
                    out.write(json.dumps(example, ensure_ascii=False)+'\n')
                    counts['output_rows'] += 1
                    languages[language] += 1
                    sources[str(row.get('source_dataset', spec['repo_id']))] += 1
                except (ValueError, KeyError, TypeError) as e:
                    counts['rejected'] += 1
                    counts['reason:'+str(e)] += 1
                    reject.write(json.dumps(dict(file=name, row=ordinal, reason=str(e)))+'\n')
    manifest = dict(spec=spec, counts=counts, languages=languages, source_datasets=sources,
        output=str(destination.resolve()), output_sha256=sha(destination),
        raw_sha256={str(p):sha(p) for p in paths.values()},
        converter_sha256=sha(Path(__file__)), repeat=1,
        split_policy='train only; own heldout normalized input exclusion; CroCo lacks split and needs audit',
        overlap_scope='Own-source heldout and exact normalized input duplicates only; not full inherited-corpus deduplication',
        template_policy='native Gemma messages, final assistant target; no pre-rendered chat tokens',
        status='pending_audit' if audit_required else 'prepared')
    write_json(output/'manifest.json', manifest)
    return manifest


def register(manifests, config):
    with config.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = sha(config)
        data = json.loads(config.read_text())
        for m in manifests:
            spec = m['spec']
            field = 'pending_audit' if m['status']=='pending_audit' else 'additions'
            entries = data.setdefault(field, [])
            if any(e['name']==spec['name'] for e in entries):
                raise ValueError('Already registered: '+spec['name'])
            entries.append(dict(name=spec['name'], repo_id=spec['repo_id'], revision=spec['revision'],
                license=spec['license'], output=m['output'], output_sha256=m['output_sha256'],
                rows=m['counts']['output_rows'], repeat=1, status=m['status'],
                converter='scripts/prepare_dfm13_jjzha.py', tokenization_performed=False,
                target_policy='final_assistant_only_native_gemma',
                manifest=str(Path(m['output']).parent/'manifest.json')))
        if sha(config) != before:
            raise ValueError('Concurrent registry modification')
        write_json(config, data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources', type=Path, default=ROOT/'config/dfm13_jjzha_sources.json')
    p.add_argument('--output', type=Path, default=ROOT/'data/converted_sources/dfm13_jjzha')
    p.add_argument('--downloads', type=Path, default=ROOT/'data/downloads/datasets')
    p.add_argument('--register', action='store_true')
    args = p.parse_args()
    manifests = []
    for spec in json.loads(args.sources.read_text())['sources']:
        m = prepare(spec, args.output, args.downloads)
        manifests.append(m)
        print(spec['name'], dict(m['counts']), flush=True)
    if args.register:
        register(manifests, ROOT/'config/dfm13_sources.json')


if __name__ == '__main__':
    main()
