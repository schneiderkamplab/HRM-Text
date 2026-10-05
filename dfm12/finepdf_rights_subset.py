"""Publish independently rights-verified exact LT/LV FinePDF documents.

No queue mutation, raw acceptance fallback, domain-wide grant or GPU work.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

from .baltic_audit import MODEL
from .blkt_export import checked
from .io import digest, file_hash, load, lock, rows, write_json
from .jobs import audit_payload, validate_audit
from .records import validate_messages
from .wave_release import TRANSFORM_TASKS

COMPONENT = 'transform-baltic_lt_finepdfs'
REPO = 'HuggingFaceFW/finepdfs-edu'
REVISION = '9cfabe2127faca99b3d5c4dc6d1fcb397399ebde'
DOCS = {
    '<urn:uuid:c17f598e-5c6c-4687-99d8-a96ce4dcaab8>': dict(
        row=10000, url='https://gamlec.eu/wp-content/uploads/2021/07/GAMLEC_Z%CC%8CaidimoTaisykle%CC%87s.pdf',
        author='Sylvie Schoch; GAMLEC Consortium; IP-International GmbH',
        title='GAMLEC game rules, Lithuanian, version V04 (2020-12-03)', evidence='gamlec.pdf'),
    '<urn:uuid:19820ad1-560b-49c0-b4c6-f4eedee62be7>': dict(
        row=29493, url='https://cemivet.eu/wp-content/uploads/2022/08/Factsheet-for-the-VET-schools-and-teachers_LT.pdf',
        author='CEMIVET project consortium',
        title='Factsheet for VET schools and teachers, Lithuanian', evidence='cemivet.pdf'),
}
PARQUET_SHA = '85c84f6111f240bb0639c77ce99e00279d1cef211f094bb70f829829b8a5a379'
EVIDENCE_SHA = 'a526ac34450a7b0a3d62aa8dd33c1a05bbc739c170e6554c598ca31f228c686b'
LV_DOCS = {'<urn:uuid:37076053-bd9b-4805-891f-5e5a51191efe>': dict(row=31841,
    url='http://journals.rta.lv/index.php/ER/article/download/6497/5538',
    author='Inese Brivere; Livija Levinska',
    title='Elements of Escape Games in Latvian History Lessons in Primary School Classes (2021)',
    evidence='article.pdf')}


def scope(language):
    if language == 'lt':
        return DOCS, PARQUET_SHA, EVIDENCE_SHA
    if language == 'lv':
        return (LV_DOCS, 'c2f2ec2a30dbe78bdc9ed891930c9b386b47fa2f54a40388fd4259d8652006ba',
                'bbecaab2751ff316099892327ff8eb88d7b5278708efd3d63b523cd1c7277b29')
    raise ValueError('Unreviewed language scope')


def grant(row, language='lt'):
    docs, parquet_sha, _ = scope(language)
    p = row['provenance']
    doc = docs.get(p.get('source_document_id'))
    if doc is None:
        return None
    if (row.get('component') != f'transform-baltic_{language}_finepdfs' or row['language'] != language
            or p.get('source') != f'baltic_{language}_finepdfs'
            or p.get('row') != doc['row'] or p.get('url') != doc['url']
            or p.get('file_sha256') != parquet_sha
            or row['task'] not in TRANSFORM_TASKS):
        raise ValueError('Exact document provenance mismatch')
    return doc


def accepted_review(db, row):
    key = digest(['audit', audit_payload(row, MODEL)])
    result = db.execute('SELECT status,result FROM jobs WHERE id=?', (key,)).fetchone()
    if result is None or result[0] != 'done':
        return None, key
    review = json.loads(result[1])
    validate_audit(review)
    return (review if review['keep'] else None), key


def build(root, evidence, output, language='lt'):
    docs, parquet_sha, evidence_sha = scope(language)
    component = f'transform-baltic_{language}_finepdfs'
    root, evidence, output = map(lambda p: Path(p).resolve(), (root, evidence, output))
    if output.exists() or output.is_relative_to(root):
        raise ValueError('Fresh output outside live root required')
    checked(evidence / 'receipt.json', evidence_sha)
    epin = load(evidence / 'receipt.json')
    if epin['documents'] != docs or epin['document_license'] != 'cc-by-4.0':
        raise ValueError('Unreviewed rights scope')
    for name, sha in epin['files'].items():
        if Path(name).name != name:
            raise ValueError('Unsafe evidence attachment')
        checked(evidence / name, sha)
    sealpath = root / 'audit-ready' / component / 'receipt.json'
    seal = load(sealpath)
    checked(seal['path'], seal['sha256'])
    source_receipt = root / f'receipts/baltic_{language}_finepdfs.json'
    receipt = load(source_receipt)
    if (receipt['repo'], receipt['revision']) != (REPO, REVISION):
        raise ValueError('Wrong source revision')
    source = next(p for p in receipt['files'] if p['sha256'] == parquet_sha)
    checked(source['path'], parquet_sha)
    # Read just the two original rows and confirm the embedded document notices.
    import pyarrow.parquet as pq
    parquet = pq.ParquetFile(source['path'])
    originals = {}
    offset = 0
    for group in range(parquet.num_row_groups):
        n = parquet.metadata.row_group(group).num_rows
        wanted = [(key, doc) for key, doc in docs.items() if offset <= doc['row'] < offset+n]
        if wanted:
            table = parquet.read_row_group(group, columns=['id', 'url', 'text'])
            for key, doc in wanted:
                raw = table.slice(doc['row']-offset, 1).to_pylist()[0]
                if (raw['id'] != key or raw['url'] != doc['url']
                        or (language == 'lt' and 'Creative Commons Attribution 4.0' not in raw['text'])
                        or (language == 'lv' and 'Elements of Escape Games in Latvian History Lessons' not in raw['text'])):
                    raise ValueError('Source document/license evidence mismatch')
                originals[key] = digest(raw)
        offset += n
    if set(originals) != set(docs):
        raise ValueError('Missing original documents')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + output.name, dir=output.parent))
    counts, selected, excluded = Counter(), defaultdict(list), []
    try:
        with sqlite3.connect((root / 'audit/jobs.sqlite').as_uri()+'?mode=ro', uri=True, timeout=1) as db:
            db.execute('PRAGMA query_only=ON')
            for row in rows(seal['path']):
                counts['scanned'] += 1
                doc = grant(row, language)
                if doc is None:
                    counts['rights_not_verified'] += 1
                    excluded.append(dict(id=row['id'], record_sha256=digest(row), reason='document_rights_not_verified'))
                    continue
                review, job = accepted_review(db, row)
                if review is None:
                    counts['not_positive_completed_audit'] += 1
                    excluded.append(dict(id=row['id'], record_sha256=digest(row), job=job,
                                         reason='no_positive_completed_original_audit'))
                    continue
                validate_messages(row['messages'])
                if row.get('tools') or row.get('reverse_messages') or row['messages'][-1]['role'] != 'assistant':
                    raise ValueError('Unexpected conversation contract')
                counts['accepted'] += 1
                selected[row['task']].append((row, doc, review, job))
        if counts['scanned'] != seal['counts']['ready'] or not selected:
            raise ValueError('Incomplete/empty selection')
        write_json(stage / 'exclusions.json', dict(counts=counts, rows=excluded))
        packages = []
        for task, items in sorted(selected.items()):
            name = f'dfm13-wave3-finepdfs-{language}-exact-ccby-v1-' + task
            folder = stage / name
            (folder / 'data').mkdir(parents=True)
            attribution = []
            with (folder / 'data/train.jsonl').open('w') as out:
                for row, doc, review, job in items:
                    record = dict(row, admission_authorized=True, target_message_index=len(row['messages'])-1,
                                  quality_status='accepted', audit=review,
                                  rights_evidence=dict(document_license='cc-by-4.0', database_license='odc-by-1.0',
                                      original_record_sha256=digest(row), original_audit_job=job,
                                      evidence_receipt_sha256=file_hash(evidence/'receipt.json')))
                    out.write(json.dumps(record, ensure_ascii=False)+'\n')
                    attribution.append(dict(candidate_id=row['id'], **doc,
                        document_id=row['provenance']['source_document_id'],
                        original_source_row_sha256=originals[row['provenance']['source_document_id']]))
            write_json(folder/'attribution.json', attribution)
            shutil.copyfile(stage/'exclusions.json', folder/'exclusions.json')
            for filename in epin['files']:
                shutil.copyfile(evidence/filename, folder/filename)
            shutil.copyfile(evidence/'receipt.json', folder/'rights-receipt.json')
            notice = ('Document text: CC BY 4.0; FinePDFs-Edu database: ODC-By 1.0. '
                      'Neither license is asserted for other documents. Attribution and original PDF URLs '
                      'are in attribution.json. Preserve both licenses and notices. '
                      'Changes: extraction, window selection and mechanical '+task+' exercise; '
                      'corrupted/reordered exercise inputs are not authentic publisher statements. '
                      'FinePDFs-Edu by Hynek Kydlicek, Guilherme Penedo and Leandro von Werra (Hugging Face), '
                      'revision '+REVISION+'. Existing automated Gemma audit only, not certified gold. '
                      'Messages unchanged from audited candidates; supervise target_message_index only.\n')
            (folder/'NOTICE.txt').write_text(notice)
            (folder/'README.md').write_text(f'---\nlicense: cc-by-4.0\nlanguage:\n- {language}\nconfigs:\n'
                '- config_name: default\n  data_files:\n  - split: train\n    path: data/train.jsonl\n---\n\n'
                '# Exact-document FinePDFs subset\n\n'+notice+
                '\nSource database: https://huggingface.co/datasets/'+REPO+'/tree/'+REVISION+
                '\nDatabase notice: Contains information from FinePDFs-Edu, made available under '
                'the Open Data Commons Attribution License (ODC-By).\n')
            files = {str(p.relative_to(folder)): file_hash(p) for p in folder.rglob('*') if p.is_file()}
            record = dict(name=name.replace('-', '_'), repo_id=REPO, revision=REVISION,
                hf_repo_id='schneiderkamplab/'+name, license='cc-by-4.0', database_license='odc-by-1.0',
                task=task, rows=len(items), rendered_tokens=sum(r['rendered_tokens'] for r,_,_,_ in items),
                output=str(output/name/'data/train.jsonl'), output_sha256=files['data/train.jsonl'],
                files=files, repeat=1, uploaded=False, tokenization_performed=False,
                target_policy='final_assistant_only_native_gemma', input_sha256=seal['sha256'],
                rights_receipt_sha256=file_hash(evidence/'receipt.json'), publisher_sha256=file_hash(__file__))
            write_json(folder/'manifest.json', record)
            packages.append(dict(path=name, manifest_sha256=file_hash(folder/'manifest.json')))
        write_json(stage/'publication.json', dict(packages=packages, counts=counts,
                   evidence_receipt_sha256=file_hash(evidence/'receipt.json'),
                   source_receipt_sha256=file_hash(source_receipt), seal_sha256=file_hash(sealpath)))
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return load(output/'publication.json')


def publish(output, registry, api=None, download=None, language='lt'):
    _, _, evidence_sha = scope(language)
    if api is None:
        from huggingface_hub import HfApi, hf_hub_download
        api, download = HfApi(), hf_hub_download
    output, registry = Path(output).resolve(), Path(registry)
    with lock(output/'.publish.lock'):
        records = []
        for item in load(output/'publication.json')['packages']:
            folder = output/item['path']
            if folder.parent != output or not item['path'].startswith(f'dfm13-wave3-finepdfs-{language}-exact-ccby-v1-'):
                raise ValueError('Unexpected package scope')
            checked(folder/'manifest.json', item['manifest_sha256'])
            r = load(folder/'manifest.json')
            if r['hf_repo_id'] != 'schneiderkamplab/'+item['path'] or r['license'] != 'cc-by-4.0':
                raise ValueError('Wrong publication target/terms')
            if r.get('rights_receipt_sha256') != evidence_sha:
                raise ValueError('Unreviewed evidence receipt')
            checked(folder/'rights-receipt.json', evidence_sha)
            files = dict(r['files'], **{'manifest.json': item['manifest_sha256']})
            for name, sha in files.items():
                path = (folder/name).resolve()
                if not path.is_relative_to(folder):
                    raise ValueError('Unsafe attachment')
                checked(path, sha)
            api.create_repo(r['hf_repo_id'], repo_type='dataset', exist_ok=True)
            commit = api.upload_folder(repo_id=r['hf_repo_id'], repo_type='dataset', folder_path=folder,
                                       allow_patterns=list(files), commit_message='Exact-document rights-verified accepted subset')
            for name, sha in files.items():
                checked(download(repo_id=r['hf_repo_id'], filename=name, repo_type='dataset', revision=commit.oid), sha)
            r.update(status='accepted_uploaded', uploaded=True, hf_revision=commit.oid,
                     export_manifest=str(folder/'manifest.json'), export_manifest_sha256=item['manifest_sha256'])
            records.append(r)
        with lock(registry.with_suffix('.lock')):
            config = load(registry)
            for r in records:
                old = next((e for e in config['additions'] if e['name'] == r['name']), None)
                if old and old['output_sha256'] != r['output_sha256']:
                    raise ValueError('Refuse to replace existing source')
                if old:
                    old.update({k:v for k,v in r.items() if k not in ('tokenization_performed',)})
                else:
                    config['additions'].append(r)
            write_json(registry, config)
        write_json(output/'integrated.json', dict(records=records))
    return records


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['build', 'publish'])
    p.add_argument('--root', type=Path, default=Path('data/dfm13/baltic'))
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--registry', type=Path, default=Path('config/dfm13_sources.json'))
    p.add_argument('--language', choices=['lt', 'lv'], default='lt')
    a = p.parse_args()
    print(json.dumps(build(a.root,a.evidence,a.output,a.language) if a.action=='build'
                     else publish(a.output,a.registry,language=a.language)))
