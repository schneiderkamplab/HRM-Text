"""CPU-only accepted release: evidence, native chats, exports and publication."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time

import jinja2
from tokenizers import Tokenizer

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm14.release_inputs import accepted, checked, inventory
from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
from scripts.decontaminate_mimir_grounded_500k_exact import instruction_units

ROOT = Path('data/dfm14/release-v1')
EXPORT = Path('exports_dfm14')
TOKENIZER = TEMPLATE = BENCHMARK = None


def init_worker(info, benchmark):
    global TOKENIZER, TEMPLATE, BENCHMARK
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    TOKENIZER = Tokenizer.from_file(info['tokenizer_path'])
    TEMPLATE = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    BENCHMARK = set(benchmark)


def repeat_for(row):
    from dfm14.english_additions import sources
    provenance = row.get('provenance') or {}
    if isinstance(provenance, dict):
        for source in sources():
            if (source['repo'], source['component']) == (provenance.get('repo'), provenance.get('component')):
                return source['repeat']
    return 1


def package_name(row, repeat):
    language = row['language']
    if not re.fullmatch(r'[a-z]{2,3}(?:[-_][a-z0-9]+)?', language):
        raise ValueError('Unexpected language code: '+language)
    task = re.sub(r'[^a-z0-9-]', '-', row.get('task', row.get('family', 'instruction')).lower())
    return f'dfm14-{language.replace("_", "-")}-{task}-r{repeat}'


def directions(row):
    if not row.get('reverse_messages'):
        yield row
        return
    a, b = row['pair'].split('-')
    for language, messages, suffix in ((b, row['messages'], a+'-'+b),
                                       (a, row['reverse_messages'], b+'-'+a)):
        yield dict(row, messages=messages, language=language, id=row['id']+'-'+suffix)


def prepare_job(args):
    job, root = args
    path = root/'prepared'/(job['name']+'.jsonl')
    receipt_path = path.with_suffix('.receipt.json')
    if receipt_path.exists():
        receipt = load(receipt_path)
        if receipt['job'] != job:
            raise ValueError('Prepared input drift')
        checked(path, receipt['sha256'])
        return receipt
    counts = Counter()
    with atomic(path) as output:
        for raw, evidence in accepted(job):
            counts['accepted_source_rows'] += 1
            for row in directions(raw):
                messages, tools = row['messages'], row.get('tools') or []
                if any(hashlib.sha256(unit.encode()).hexdigest() in BENCHMARK
                       for message in messages if message['role'] == 'user'
                       for unit in instruction_units(message.get('content') or '')):
                    counts['benchmark_exact_hold'] += 1
                    continue
                if tools or any(m.get('tool_calls') for m in messages):
                    from dfm14.native_instructions import validate
                    validate(messages, tools)
                target = max(i for i, m in enumerate(messages) if m['role'] == 'assistant')
                if target != len(messages)-1:
                    raise ValueError('Trailing non-assistant messages')
                examples = list(examples_from_messages(messages, tools, target))
                if len(examples) != 1:
                    raise ValueError('Missing final assistant target')
                encoded = tokenize_example(TOKENIZER, TEMPLATE, examples[0], False, max_seq_len=None)
                if encoded is None or not encoded[1]:
                    raise ValueError('Empty native target')
                n = sum(map(len, encoded))
                if n > 4096:
                    counts['over_4k_hold'] += 1
                    continue
                repeat = repeat_for(row)
                source = package_name(row, repeat)
                value = dict(id=row['id'], language=row['language'], task=row.get('task', row.get('family')),
                    messages=messages, tools=tools, target_message_index=target,
                    provenance=row.get('provenance'), audit=evidence, repeat=repeat, source=source,
                    native_tokens=n, content_sha256=digest(dict(messages=messages, tools=tools)))
                output.write(json.dumps(value, ensure_ascii=False)+'\n')
                counts['eligible_rows'] += 1
                counts['native_tokens'] += n
    receipt = dict(job=job, path=str(path), sha256=file_hash(path), counts=dict(counts))
    write_json(receipt_path, receipt)
    return receipt


def benchmarks(root):
    path = root/'benchmark-hashes.json'
    if not path.exists():
        from scripts.decontaminate_mimir_grounded_500k_exact import benchmark_hashes
        hashes, evidence = benchmark_hashes(load('config/mimir_exact_decontamination_benchmarks.json'))
        write_json(path, dict(hashes=hashes, evidence=evidence,
            scope='normalized exact user/question matches; not semantic or translated decontamination'))
    return load(path)['hashes']


def prepare(root, workers):
    manifest = inventory()
    info = load('data/sampled_dfm13/metadata.json')['tokenizer_info']
    contract = dict(inputs=manifest, tokenizer={k:file_hash(info[k]) for k in ('tokenizer_path','chat_template_path')},
                    target_policy='final_assistant_complete_untruncated_4k', version=1)
    path = root/'contract.json'
    if path.exists() and load(path) != contract:
        raise ValueError('Release contract changed')
    write_json(path, contract)
    benchmark = benchmarks(root)
    reports, counts = [], Counter()
    with ProcessPoolExecutor(max_workers=workers, initializer=init_worker, initargs=(info, benchmark)) as pool:
        for report in pool.map(prepare_job, ((j,root) for j in manifest['jobs']), chunksize=4):
            reports.append(report); counts.update(report['counts'])
            if len(reports)%100 == 0:
                write_json(root/'progress.json', dict(phase='accepted_native_preparation',
                    done=len(reports), total=len(manifest['jobs']), counts=dict(counts), time=time.time()))
                print('prepared', len(reports), '/', len(manifest['jobs']), dict(counts), flush=True)
    write_json(root/'prepared.json', dict(reports=reports, counts=dict(counts)))


def package(root, export):
    import pyarrow as pa
    import pyarrow.parquet as pq
    manifest_path = export/'manifest.json'
    if manifest_path.exists():
        return load(manifest_path)
    # Restart only our unfinished staging area; published packages are immutable.
    staging = export.with_name(export.name+'.building')
    staging.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE seen (hash TEXT PRIMARY KEY)')
    buffers, counts, files, repeats, origins = defaultdict(list), Counter(), defaultdict(list), {}, defaultdict(set)
    dropped = Counter()
    schema = pa.schema([(k, pa.string()) for k in
        ('id','language','task','messages_json','tools_json','provenance_json','audit_json')]
        + [('target_message_index',pa.int32()),('native_tokens',pa.int64())])

    def flush(name):
        batch = buffers[name]
        if not batch:
            return
        folder = staging/name/'data'; folder.mkdir(parents=True, exist_ok=True)
        relative = f'data/train-{len(files[name]):05d}.parquet'
        path = staging/name/relative
        public = []
        local = root/'training'/name/(path.stem+'.jsonl')
        with atomic(local) as handle:
            for row in batch:
                handle.write(json.dumps(row,ensure_ascii=False)+'\n')
                public.append({**{k:row[k] for k in ('id','language','task','target_message_index','native_tokens')},
                    **{k+'_json':json.dumps(row[k],ensure_ascii=False,sort_keys=True) for k in ('messages','tools','provenance','audit')}})
        pq.write_table(pa.Table.from_pylist(public,schema=schema),path,compression='zstd')
        files[name].append(dict(file=relative,sha256=file_hash(path),rows=len(batch)))
        counts[name] += len(batch)
        buffers[name].clear()

    prepared = load(root/'prepared.json')
    for report in prepared['reports']:
        checked(report['path'], report['sha256'])
        for row in rows(report['path']):
            if not db.execute('INSERT OR IGNORE INTO seen VALUES (?)',(row['content_sha256'],)).rowcount:
                dropped['cross_addition_exact_duplicates'] += 1
                continue
            name = row['source']; repeats[name] = row['repeat']
            provenance = row.get('provenance') or {}
            if isinstance(provenance,dict):
                origins[name].add(provenance.get('repo') or provenance.get('corpus') or 'generated; see row provenance')
            buffers[name].append(row)
            if len(buffers[name]) >= 1000:
                flush(name)
    for name in buffers:
        flush(name)
    packages = []
    for name in sorted(files):
        folder=staging/name
        record=dict(name=name,hf_repo_id='schneiderkamplab/'+name,rows=counts[name],repeat=repeats[name],
            files=files[name],origins=sorted(origins[name]),target_policy='final_assistant_complete_untruncated_4k')
        write_json(folder/'metadata/manifest.json',record)
        card = ('---\nlanguage:\n- '+name.split('-')[1]+'\nlicense: other\n'
            'license_name: source-and-teacher-conditions\nlicense_link: https://huggingface.co/datasets/schneiderkamplab/'+name+'/blob/main/README.md#terms\n'
            'configs:\n- config_name: default\n  data_files:\n  - split: train\n    path: data/*.parquet\n---\n'
            '# '+name+'\n\nAccepted-only DFM14 data, automatically reviewed with Gemma 4 26B-A4B. '
            'This is not human quality certification. Rejections, repair requests and failed reviews are excluded. '
            'Some early synthetic accepts predate the compact reviewer; their audit provenance is retained.\n\n'
            f'Rows: {counts[name]:,}. All final assistant targets fit the native Gemma 4 template within 4,096 tokens, '
            'without truncation. Complete chat history is preserved. Training supervises the indicated final assistant.\n\n'
            'Nested values are losslessly encoded in `messages_json`, `tools_json`, `provenance_json` and `audit_json` '
            'to avoid incompatible Arrow schemas for different tool signatures. Decode these with `json.loads`; '
            'pass messages and tools to the Gemma 4 chat template with `enable_thinking=False`. '
            'Do not train on the JSON serialization itself.\n\n'
            '## Selection\n\nNormalized exact benchmark-question checks and exact cross-addition chat deduplication '
            'were performed. These are not semantic or translated benchmark decontamination. '
            'Inherited DFM13 overlap is removed separately in mixture sampling, not claimed absent from this standalone dataset.\n\n'
            '## Terms\n\nUpstream attribution, source revision and document/row references are retained in provenance. '
            'Source terms and applicable Gemma generated-output conditions remain in force; this release does not '
            'relicense third-party material under one blanket permissive license. Consult the referenced upstream sources.\n\n'
            'Sources: '+', '.join(record['origins'])+'\n')
        with atomic(folder/'README.md') as handle:
            handle.write(card)
        packages.append(record)
    result=dict(packages=packages,counts=dict(counts),exclusions=dict(dropped),
                prepared_sha256=file_hash(root/'prepared.json'),status='accepted_packaged')
    write_json(staging/'manifest.json',result)
    staging.rename(export)
    return result


def upload(export):
    from huggingface_hub import HfApi, hf_hub_download
    from dfm14.publication_assets import attach
    api=HfApi(); receipts=export/'upload-receipts.json'
    done=load(receipts) if receipts.exists() else {}
    for package in load(export/'manifest.json')['packages']:
        name=package['name']; repo=package['hf_repo_id']; folder=export/name
        card=folder/'README.md'
        text=card.read_text()
        if 'license_link: README.md#terms' in text:
            with atomic(card) as handle:
                handle.write(text.replace('license_link: README.md#terms',
                    'license_link: https://huggingface.co/datasets/'+repo+'/blob/main/README.md#terms'))
        attribution=attach(folder,ROOT/'training'/name)
        sha=file_hash(folder/'metadata/manifest.json')
        if repo in done:
            if done[repo]['manifest_sha256']!=sha:
                raise ValueError('Published package changed')
            continue
        for item in [*package['files'],attribution]:
            checked(folder/item['file'],item['sha256'])
        api.create_repo(repo,repo_type='dataset',exist_ok=True)
        commit=api.upload_folder(repo_id=repo,repo_type='dataset',folder_path=folder,
            commit_message='Publish audited DFM14 accepted-only release')
        revision=commit.oid
        remote=hf_hub_download(repo,'metadata/manifest.json',repo_type='dataset',revision=revision)
        checked(remote,sha)
        remote_files={f.rfilename:f for f in api.dataset_info(repo,revision=revision,files_metadata=True).siblings}
        for item in [*package['files'],attribution]:
            f=remote_files[item['file']]
            lfs=f.lfs
            remote_sha = lfs.get('sha256') if isinstance(lfs,dict) else getattr(lfs,'sha256',None)
            if remote_sha:
                if remote_sha!=item['sha256']:
                    raise ValueError('Remote data hash mismatch')
            else:
                checked(hf_hub_download(repo,item['file'],repo_type='dataset',revision=revision),item['sha256'])
        done[repo]=dict(status='verified',revision=revision,manifest_sha256=sha,rows=package['rows'])
        write_json(receipts,done)
        print('uploaded',repo,package['rows'],revision,flush=True)


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('phase',choices=['prepare','package','upload','all'])
    p.add_argument('--workers',type=int,default=16)
    args=p.parse_args()
    with lock(ROOT/'.lock'):
        if args.phase in ('prepare','all'):
            prepare(ROOT,args.workers)
        if args.phase in ('package','all'):
            package(ROOT,EXPORT)
        if args.phase in ('upload','all'):
            upload(EXPORT)


if __name__=='__main__':main()
