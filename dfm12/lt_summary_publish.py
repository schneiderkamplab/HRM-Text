"""Accepted-only, content-bound LT summary publication. Never uploads held text."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

from . import baltic_lt_summary_privacy as privacy
from .blkt_export import checked
from .blkt_publish import MODEL_CONDITIONS as COMMON_CONDITIONS
from .io import digest, file_hash, load, lock, rows, write_json
from .jobs import validate_audit

REPO = 'VytautoDidziojoUniversitetas/LT_Summarisation_Corpus'
REVISION = '42ff26844cd2b3d26880f631ab498da1568cda15'
REPORT_SHA = '7d33c1ddafa70e2a4aafb2d0c2508e4df9e6689a0a711a3777c8e7ad41806f7e'
LICENSE_SHA = 'd492ba6dacd136b822e2e19d0e6665e29c56a596c1fba86b49eed29bca5c2022'
CARD_SHA = 'aa515c0812fa8d26c929c709edf654c6ce3f8c522186763029c9665f8e5c3091'
NAME = 'dfm13_wave3_baltic_lt_summary_newgenltu'
REPO_ID = 'schneiderkamplab/' + NAME.replace('_', '-')
COUNTS = dict(model_pass_not_certified=1740, privacy_hold=205, manual_hold=1, quality_hold=66)
MODEL_CONDITIONS = dict(COMMON_CONDITIONS,
    license_url=f'https://huggingface.co/datasets/{REPO}/blob/{REVISION}/LICENSE.txt')
ATTACHMENTS = {'data/train.jsonl', 'attribution.jsonl', 'privacy-receipt.json',
               'LICENSE.txt', 'SOURCE_README.md', 'README.md', 'NOTICE.txt', 'USE_CONDITIONS.md'}


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def select(root, screening):
    """Validate complete coverage and each current final against its completed job."""
    checked(screening / 'report.json', REPORT_SHA)
    report = load(screening / 'report.json')
    seal = load(root / 'audit-ready' / privacy.COMPONENT / 'receipt.json')
    checked(seal['path'], seal['sha256'])
    originals = {r['id']: r for r in rows(seal['path'])}
    holds = load(screening / 'manual-holds.json')
    items = {r['original_id']: r for r in report['rows']}
    if (len(items) != len(report['rows']) or set(items) != set(originals)
            or len(originals) != sum(COUNTS.values()) or report['counts'] != COUNTS
            or report['input_sha256'] != seal['sha256'] or set(holds) - set(originals)):
        raise ValueError('Incomplete privacy population')
    with readonly(root / 'release' / privacy.COMPONENT / 'ledger.sqlite') as db:
        quality = {r[0]: r[1:] for r in db.execute('SELECT id,status,record,review FROM rows')}
    if set(quality) != set(originals):
        raise ValueError('Incomplete quality population')
    selected, receipts, source_tables, counts = [], [], {}, {}
    with readonly(screening / 'jobs.sqlite') as db:
        for key, original in originals.items():
            item = items[key]
            state, raw, review = quality[key]
            if state != item['quality_status']:
                raise ValueError('Quality state changed')
            if state not in ('accepted', 'accepted_repair'):
                if state != 'repair_rejected' or item['status'] != 'quality_hold':
                    raise ValueError('Unresolved quality row')
                counts['quality_hold'] = counts.get('quality_hold', 0) + 1
                continue
            final = json.loads(raw)
            privacy.validate_final(original, final)
            audit = json.loads(review)
            validate_audit(audit)
            if audit['keep'] is not True:
                raise ValueError('Quality not accepted')
            prov = original['provenance']
            path = Path(prov['file']).resolve()
            if ((prov['repo'], prov['revision']) != (REPO, REVISION)
                    or path.parent != (root / 'downloads' / privacy.COMPONENT / 'csv/train').resolve()
                    or path.name not in ('it.csv', 'medicina.csv', 'teise.csv', 'ziniasklaida.csv')):
                raise ValueError('Unapproved source')
            if path not in source_tables:
                checked(path, prov['file_sha256'])
                with path.open() as handle:
                    source_tables[path] = (prov['file_sha256'], list(csv.DictReader(handle)))
            if source_tables[path][0] != prov['file_sha256']:
                raise ValueError('Inconsistent source pin')
            from scripts.prepare_dfm13_baltic import messages
            if messages(source_tables[path][1][prov['row']], 'summary') != original['messages']:
                raise ValueError('Original differs from upstream row')
            pin = dict(input_sha256=seal['sha256'], provenance=prov)
            payload = privacy.payload(final, pin)
            job = digest(['audit', payload])
            found = db.execute('SELECT status,payload,result FROM jobs WHERE id=?', (job,)).fetchone()
            if not found or found[0] != 'done' or json.loads(found[1]) != payload:
                raise ValueError('Missing exact completed privacy job')
            result = json.loads(found[2])
            status = privacy.decision(final, pin, payload['binding'], result, key in holds)
            if (status != item['status'] or job != item['job_id']
                    or any(item.get(k) != v for k, v in payload['binding'].items())):
                raise ValueError('Stale privacy receipt')
            counts[status] = counts.get(status, 0) + 1
            if status != 'model_pass_not_certified':
                continue
            record = dict(final, admission_authorized=True, audit_status=state,
                quality_status=state, audit=audit, target_message_index=len(final['messages']) - 1,
                publication_conditions='LICENSE.txt and USE_CONDITIONS.md')
            if record['messages'][-1]['role'] != 'assistant' or record['language'] != 'lt':
                raise ValueError('Invalid final target')
            selected.append(record)
            receipts.append(dict(original_id=key, candidate_id=final['id'],
                **payload['binding'], messages_sha256=digest(final['messages']),
                published_record_sha256=digest(record), job_id=job,
                status=status, flags={k: result[k] for k in privacy.FLAGS}))
    if counts != COUNTS or len(selected) != COUNTS['model_pass_not_certified']:
        raise ValueError('Selection count mismatch')
    return selected, dict(report_sha256=REPORT_SHA, counts=counts,
        manual_holds_sha256=file_hash(screening / 'manual-holds.json'),
        pii_free_certified=False, records=receipts)


def build(root, screening, output):
    root, screening, output = map(lambda p: Path(p).resolve(), (root, screening, output))
    if output.exists():
        raise ValueError('Use a fresh publication directory')
    with lock(root / 'release' / privacy.COMPONENT / '.lock'), lock(screening / '.prepare.lock'):
        selected, receipt = select(root, screening)
        source = root / 'downloads' / privacy.COMPONENT
        checked(source / 'LICENSE.txt', LICENSE_SHA)
        checked(source / 'README.md', CARD_SHA)
        output.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.' + output.name, dir=output.parent))
        try:
            folder = stage / NAME.replace('_', '-')
            (folder / 'data').mkdir(parents=True)
            for filename, values in (('data/train.jsonl', selected), ('attribution.jsonl', [
                    dict(candidate_id=r['id'], **r['provenance'],
                         attribution='Vytautas Magnus University and Vilnius University (2026)',
                         source_title='Abstract Corpora for Artificial Intelligence') for r in selected])):
                with (folder / filename).open('w') as handle:
                    for row in values:
                        handle.write(json.dumps(row, ensure_ascii=False) + '\n')
            write_json(folder / 'privacy-receipt.json', receipt)
            shutil.copyfile(source / 'LICENSE.txt', folder / 'LICENSE.txt')
            shutil.copyfile(source / 'README.md', folder / 'SOURCE_README.md')
            (folder / 'NOTICE.txt').write_text(
                'Modified derivative, 2026-10-03: train-only selection, native conversation formatting, '
                'automated quality/privacy screening and seven machine-generated assistant repairs. '
                'Individual quality_status marks repairs. No source/user text changed. '
                'Metadata and this documentation are machine-assisted.\n'
                'Attribution: Vytautas Magnus University and Vilnius University. 2026. '
                'Abstract Corpora for Artificial Intelligence. Project 02-101-K-0001, '
                'funded by the European Union - NextGenerationEU, New Generation Lithuania, '
                'Recovery and Resilience Facility and Lithuanian State Budget. '
                'See unchanged SOURCE_README.md for full notices/citation; source row provenance '
                'is in attribution.jsonl. Missing individual authors/URLs are not invented.\n')
            (folder / 'USE_CONDITIONS.md').write_text(
                '# Mandatory Downstream Conditions\n\n'
                'The attached LICENSE.txt in full, including ALL Attachment A restrictions, '
                'is binding on recipients and derivatives, not optional guidance. Section 3 and '
                '5(i) require these restrictions as conditions precedent in downstream agreements; '
                'pass the full license and notices onward. No endorsement or additional rights. '
                'Section 5(v): model training, language technology development and training datasets only. '
                'Section 4: model outputs may not contravene the license. Attachment A10(a) forbids '
                'personal-data extraction; A10(b) requires adequate trained-model limitations against '
                'output of artifact personal information. A4 requires applicable machine-generation '
                'and autonomous-interaction disclosures; A6 restricts medical/clinical use with its '
                'stated oversight exceptions. All other restrictions remain binding. These are '
                'use/model obligations, not a claim that any model safeguards have been certified.\n')
            (folder / 'README.md').write_text(
                '---\nlicense: other\nlicense_name: newgenltu-openrail-d-1.0\n'
                f'license_link: {MODEL_CONDITIONS["license_url"]}\nlanguage:\n- lt\n'
                'configs:\n- config_name: default\n  data_files:\n  - split: train\n'
                '    path: data/train.jsonl\n---\n\n# Lithuanian Summaries\n\n'
                f'{len(selected)} accepted conversations from {REPO}, revision {REVISION}. '
                'Full mandatory [license](LICENSE.txt), [conditions](USE_CONDITIONS.md), '
                '[notices](NOTICE.txt) and unchanged [source card](SOURCE_README.md) accompany this derivative. '
                'Automated quality screening and privacy review cover exact full final messages, '
                'including source/user text and repaired answers. All privacy/manual/quality holds '
                'are excluded. Privacy screening is fallible, NOT PII-free certification or exhaustive '
                'human review; medical-record screening was inconsistent. Six records received '
                'independent manual inspection, not all accepted records. Public names are not '
                'blanket-rejected. No exhaustive contamination claim. Machine repairs are marked. '
                'Supervise only target_message_index, with native Gemma template and thinking disabled.\n')
            files = {str(p.relative_to(folder)): file_hash(p) for p in folder.rglob('*') if p.is_file()}
            record = dict(name=NAME, hf_repo_id=REPO_ID, repo_id=REPO, revision=REVISION,
                license='NewGenLTU Open RAIL-D 1.0', task='instruction', rows=len(selected),
                rendered_tokens=sum(r['rendered_tokens'] for r in selected), repeat=1,
                files=files, output=str(output / folder.name / 'data/train.jsonl'),
                output_sha256=files['data/train.jsonl'], target_policy='final_assistant_only_native_gemma',
                admission_authorized=True, model_use_conditions=MODEL_CONDITIONS,
                privacy_report_sha256=REPORT_SHA, tokenization_performed=False, uploaded=False,
                publisher_sha256=file_hash(__file__))
            write_json(folder / 'manifest.json', record)
            write_json(stage / 'publication.json', dict(path=folder.name,
                manifest_sha256=file_hash(folder / 'manifest.json')))
            stage.rename(output)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return record


def verify_package(folder, expected):
    checked(folder / 'manifest.json', expected)
    record = load(folder / 'manifest.json')
    if (record['name'] != NAME or record['hf_repo_id'] != REPO_ID
            or (record['repo_id'], record['revision']) != (REPO, REVISION)
            or record['rows'] != COUNTS['model_pass_not_certified']
            or record['privacy_report_sha256'] != REPORT_SHA
            or record['model_use_conditions'] != MODEL_CONDITIONS
            or set(record['files']) != ATTACHMENTS
            or record['files']['LICENSE.txt'] != LICENSE_SHA
            or record['files']['SOURCE_README.md'] != CARD_SHA):
        raise ValueError('Unexpected summary publication contract')
    for name, sha in record['files'].items():
        checked(folder / name, sha)
    receipt = load(folder / 'privacy-receipt.json')
    data = list(rows(folder / 'data/train.jsonl'))
    bound = {r['candidate_id']: r for r in receipt['records']}
    if (len(bound) != len(data) or len(data) != record['rows']
            or len({r['id'] for r in data}) != len(data)
            or receipt['counts'] != COUNTS or receipt['report_sha256'] != REPORT_SHA):
        raise ValueError('Incomplete published privacy coverage')
    for row in data:
        item = bound[row['id']]
        if (item['published_record_sha256'] != digest(row)
                or item['messages_sha256'] != digest(row['messages'])
                or item['status'] != 'model_pass_not_certified'
                or any(item['flags'][k] is not False for k in privacy.FLAGS)):
            raise ValueError('Published privacy binding mismatch')
    return record


def publish(output, registry, api=None, download=None):
    if api is None:
        from huggingface_hub import HfApi, hf_hub_download
        api, download = HfApi(), hf_hub_download
    output, registry = Path(output).resolve(), Path(registry)
    with lock(output / '.publish.lock'):
        package = load(output / 'publication.json')
        if package['path'] != NAME.replace('_', '-'):
            raise ValueError('Unexpected package')
        folder = output / package['path']
        record = verify_package(folder, package['manifest_sha256'])
        files = dict(record['files'], **{'manifest.json': package['manifest_sha256']})
        api.create_repo(REPO_ID, repo_type='dataset', exist_ok=True)
        commit = api.upload_folder(repo_id=REPO_ID, repo_type='dataset', folder_path=folder,
            allow_patterns=list(files), commit_message='Publish accepted privacy-screened Lithuanian summaries with full terms')
        for name, sha in files.items():
            checked(download(repo_id=REPO_ID, filename=name, repo_type='dataset', revision=commit.oid), sha)
        record.update(uploaded=True, status='accepted_uploaded', publication_status='verified',
            hf_revision=commit.oid, export_manifest=str(folder / 'manifest.json'),
            export_manifest_sha256=package['manifest_sha256'])
        write_json(output / (folder.name + '.verified.json'), record)
        with lock(registry.with_suffix('.lock')):
            config = load(registry)
            previous = [r for r in config['additions'] if r['name'] == NAME]
            if previous:
                if len(previous) != 1 or previous[0]['output_sha256'] != record['output_sha256']:
                    raise ValueError('Existing summary source differs')
                record = dict(previous[0], **{k: v for k, v in record.items() if k != 'tokenization_performed'})
            config['additions'] = [r for r in config['additions'] if r['name'] != NAME] + [record]
            write_json(registry, config)
        write_json(output / 'integrated.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/baltic'))
    parser.add_argument('--screening', type=Path, default=Path('data/dfm13/baltic/privacy/baltic_lt_summary-v1'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--registry', type=Path, default=Path('config/dfm13_sources.json'))
    args = parser.parse_args()
    if args.build:
        build(args.root, args.screening, args.output)
    if args.upload:
        publish(args.output, args.registry)


if __name__ == '__main__':
    main()
