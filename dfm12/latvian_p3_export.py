"""Review-only, rights-separated P3 export. No upload, registration or admission."""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time

from .baltic_sources_cpu import P3_CONFIGS, P3_REPO, P3_REVISION
from .io import digest, file_hash, load, write_json
from .jobs import validate_audit
from .records import validate_messages

GRANTS = {
    'ARC-Challenge': ('cc-by-sa-4.0', 'arc'),
    'ARC-Easy': ('cc-by-sa-4.0', 'arc'),
    'QuaRTz': ('cc-by-4.0', 'quartz'),
    'WebQuestions': ('cc-by-4.0', 'webquestions'),
}
EVIDENCE_URLS = {
    'arc': 'https://huggingface.co/datasets/allenai/ai2_arc/raw/main/README.md',
    'quartz': 'https://huggingface.co/datasets/allenai/quartz/raw/main/README.md',
    'webquestions': 'https://nlp.stanford.edu/software/sempre/',
    'cc-by-4.0': 'https://creativecommons.org/licenses/by/4.0/legalcode.txt',
    'cc-by-sa-4.0': 'https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt',
}
HOLDS = {'MRPC': 'restricted_msr_terms', 'WikiQA': 'restricted_research_terms',
         'OpenBookQA': 'unverified_data_grant', 'QuaRel': 'unverified_primary_grant'}


def check(value, message):
    if not value:
        raise ValueError(message)


def verified_file(path, expected, pins):
    path = Path(path).resolve(strict=True)
    actual = file_hash(path)
    check(actual == expected, f'Input hash mismatch: {path}')
    pins[str(path)] = actual
    return path


def rights_family(record):
    p = record['provenance']
    check((p['repo'], p['revision'], p['split']) == (P3_REPO, P3_REVISION, 'train'), 'Wrong source pin/split')
    config, sep, filename = p['file'].partition('/')
    check(sep and filename == 'train-00000-of-00001.parquet' and config in P3_CONFIGS, 'Unknown selected configuration')
    family = P3_CONFIGS[config]
    check(p['family'] == family, 'Configuration/family mismatch')
    check(type(p['row']) is int and p['row'] >= 0, 'Invalid source ordinal')
    return family


def validate_lineage(key, row, original, status):
    check(row['language'] == 'lv' and row['task'] == 'instruction' and row['component'] == 'latvian-p3', 'Wrong component')
    validate_messages(row['messages'])
    check(row['messages'][-1]['role'] == 'assistant' and not row.get('tools') and not row.get('reverse_messages'), 'Unsupported target structure')
    provenance = dict(row['provenance'])
    parent = provenance.pop('repair_parent', None)
    check(provenance == original['provenance'], 'Original provenance changed')
    if status == 'accepted':
        check(row['id'] == key and row['messages'] == original['messages'] and parent is None, 'Accepted original changed')
    else:
        check(parent == key and row['id'] == digest([key, 'corrective-v1', row['messages']]), 'Invalid repair lineage')
        check(len(row['messages']) == len(original['messages']) and row['messages'] != original['messages'], 'Invalid repair turns')
        for before, after in zip(original['messages'], row['messages']):
            check(before['role'] == after['role'] and (before['role'] == 'assistant' or before == after), 'Repair changed source context')


def export(root, output, evidence_manifest, change_date, allow_partial=False):
    date.fromisoformat(change_date)
    root = Path(root).resolve(strict=True); output = Path(output).resolve()
    check(not output.exists() and not output.is_relative_to(root) and not root.is_relative_to(output), 'Use a fresh isolated output outside source root')
    pins = {}
    sealed_path = root / 'audit-ready/latvian-p3/receipt.json'
    sealed = load(sealed_path); pins[str(sealed_path)] = file_hash(sealed_path)
    source = verified_file(sealed['path'], sealed['sha256'], pins)
    originals = {}
    with source.open() as handle:
        for line in handle:
            row = json.loads(line)
            check(row['id'] not in originals, 'Duplicate sealed ID')
            rights_family(row); originals[row['id']] = row
    check(len(originals) == sealed['counts']['ready'], 'Sealed count mismatch')
    selection_path = root / 'p3/selection.json'
    selection = load(selection_path); pins[str(selection_path)] = file_hash(selection_path)
    check((selection['repo'], selection['revision']) == (P3_REPO, P3_REVISION), 'Selection revision changed')
    for row in originals.values():
        p = row['provenance']; path = root / 'p3/download' / p['file']
        check(p['file'] in selection['selected'], 'File outside selected train configurations')
        if str(path.resolve()) not in pins:
            verified_file(path, p['file_sha256'], pins)
        check(pins[str(path.resolve())] == p['file_sha256'], 'Conflicting source hash')
    evidence_manifest = Path(evidence_manifest).resolve(strict=True)
    evidence = load(evidence_manifest); pins[str(evidence_manifest)] = file_hash(evidence_manifest)
    check(set(evidence) == set(EVIDENCE_URLS), 'Require all three primary grants and both full licenses')
    attachments = {}
    for key, url in EVIDENCE_URLS.items():
        item = evidence[key]
        check(item['url'] == url and item.get('reviewed_for') == key, 'Wrong evidence URL/review scope')
        date.fromisoformat(item['retrieved_date'])
        attachments[key] = verified_file(evidence_manifest.parent / item['path'], item['sha256'], pins)
        check(attachments[key].stat().st_size > 0, 'Empty rights evidence')
    card = root / 'p3/download/README.md'; pins[str(card)] = file_hash(card)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=output.name + '.', dir=output.parent) as temporary:
        stage = Path(temporary); counts = Counter(); statuses = Counter(); families = Counter()
        ledger = root / 'release/latvian-p3/ledger.sqlite'
        # A read transaction captures one consistent ledger view without updating live state.
        with sqlite3.connect(ledger.as_uri() + '?mode=ro', uri=True) as db, (stage/'ledger-snapshot.jsonl').open('w') as snapshot:
            db.execute('BEGIN')
            for key, raw, status, review, repair_job, reaudit_job in db.execute(
                    'SELECT id,record,status,review,repair_job,reaudit_job FROM rows ORDER BY id'):
                snapshot.write(json.dumps(dict(key=key, record=json.loads(raw), status=status,
                    review=json.loads(review) if review else None, repair_job=repair_job, reaudit_job=reaudit_job), ensure_ascii=False)+'\n')
                statuses[status] += 1
        check(sum(statuses.values()) == len(originals), 'Ledger/sealed count mismatch')
        unfinished = sum(v for k, v in statuses.items() if k not in (
            'accepted', 'accepted_repair', 'repair_rejected', 'audit_rejected',
            'excluded_unreviewed', 'excluded_invalid_repair'))
        check(allow_partial or unfinished == 0, 'Unfinished reviews require explicit --allow-partial')
        outputs = {}; packages = {}
        try:
            for license_id in ('cc-by-4.0', 'cc-by-sa-4.0'):
                folder = stage/license_id; (folder/'data').mkdir(parents=True)
                outputs[license_id] = (folder/'data/train.jsonl').open('w')
                shutil.copyfile(attachments[license_id], folder/'LICENSE.txt')
                (folder/'evidence').mkdir()
                shutil.copyfile(card, folder/'evidence/translated-source-README.md')
                for key in sorted({v[1] for v in GRANTS.values() if v[0] == license_id}):
                    shutil.copyfile(attachments[key], folder/'evidence'/f'{key}.txt')
                notice = (f'Review-only Latvian P3 adaptation, prepared {change_date}.\n'
                    f'Translated source: {P3_REPO}, revision {P3_REVISION}.\n'
                    'Translation by upstream matiss using TranslateGemma; P3 templates retained.\n'
                    'Local changes: quality selection, native-message formatting, and assistant-only corrections where marked accepted_repair.\n'
                    'Original dataset membership, file hashes, ordinals and repair parent remain in each row.\n'
                    'Constituent attribution and primary notices are retained in evidence/.\n'
                    f'License for this partition: {license_id}; {EVIDENCE_URLS[license_id]}\n'
                    'No additional restrictions imposed. ARC adaptations retain ShareAlike.\n'
                    'This package is pending review, not uploaded or authorized for training admission.\n')
                (folder/'NOTICE.txt').write_text(notice)
            seen = set()
            with (stage/'ledger-snapshot.jsonl').open() as snapshot, (stage/'dispositions.jsonl').open('w') as disposition:
                for line in snapshot:
                    item = json.loads(line); key = item['key']; row = item['record']; status = item['status']
                    check(key in originals and key not in seen, 'Unknown/duplicate ledger membership'); seen.add(key)
                    family = rights_family(originals[key]); bucket = GRANTS.get(family)
                    reason = HOLDS.get(family, 'unknown_constituent') if bucket is None else 'quality_not_accepted'
                    if bucket and status in ('accepted', 'accepted_repair'):
                        validate_lineage(key, row, originals[key], status)
                        validate_audit(item['review']); check(item['review']['keep'] is True, 'Missing positive audit')
                        check(status != 'accepted_repair' or (item['repair_job'] and item['reaudit_job']), 'Missing repair/re-audit jobs')
                        exported = dict(row, admission_authorized=False, target_message_index=len(row['messages'])-1,
                            quality_status=status, audit=item['review'],
                            export_rights=dict(license=bucket[0], constituent=family, evidence_key=bucket[1],
                                evidence_url=EVIDENCE_URLS[bucket[1]], change_date=change_date),
                            export_lineage=dict(ledger_id=key, record_sha256=digest(row),
                                repair_job=item['repair_job'], reaudit_job=item['reaudit_job']))
                        outputs[bucket[0]].write(json.dumps(exported, ensure_ascii=False)+'\n')
                        reason = 'prepared:'+bucket[0]; families[family] += 1
                    counts[reason] += 1
                    disposition.write(json.dumps(dict(ledger_id=key, family=family, status=status,
                        disposition=reason, record_sha256=digest(row)))+'\n')
        finally:
            for handle in outputs.values(): handle.close()
        for license_id in outputs:
            folder = stage/license_id
            files = {str(p.relative_to(folder)): file_hash(p) for p in sorted(folder.rglob('*')) if p.is_file()}
            packages[license_id] = dict(rows=counts['prepared:'+license_id], files=files,
                license=license_id, uploaded=False, admission_authorized=False)
            write_json(folder/'manifest.json', packages[license_id])
        for path, sha in pins.items():
            check(file_hash(Path(path)) == sha, 'Input changed during export')
        result = dict(schema='dfm13-latvian-p3-rights-preview-v1', uploaded=False, admission_authorized=False,
            review_required=True, partial=bool(unfinished), unfinished_rows=unfinished,
            counts=dict(counts), families=dict(families), ledger_statuses=dict(statuses),
            ledger_path=str(ledger), ledger_snapshot_sha256=file_hash(stage/'ledger-snapshot.jsonl'),
            dispositions_sha256=file_hash(stage/'dispositions.jsonl'), inputs=pins, packages=packages,
            evidence=evidence, change_date=change_date,
            limitations=['Automated quality acceptance is not human/native gold.',
                'Primary evidence snapshots follow the reviewed rights policy, not a blanket translated-P3 license.',
                'No tokenization, upload, registry mutation or training admission.'])
        write_json(stage/'manifest.json', result)
        stage.rename(output)
    return result


def wait_for_quality(root, interval=60, timeout=86400):
    """Advance only P3's existing repair/re-audit queue; never start clients."""
    from .wave_repair import process
    check(interval > 0 and timeout > 0, 'Positive refresh interval/timeout required')
    deadline = time.monotonic() + timeout
    while True:
        try:
            process(Path(root), 'latvian-p3')
        except BlockingIOError:
            # Another monitor owns the existing nonblocking component lock.
            pass
        else:
            status = load(Path(root)/'release/latvian-p3/status.json')
            if status['terminal']:
                check(status['export_ready'], 'Terminal quality infrastructure failure; export blocked')
                return status
        check(time.monotonic() < deadline, 'Quality wait timed out; no export prepared')
        time.sleep(min(interval, max(0, deadline-time.monotonic())))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/baltic'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence-manifest', type=Path, required=True)
    parser.add_argument('--change-date', required=True)
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--wait-terminal', action='store_true')
    parser.add_argument('--refresh-seconds', type=float, default=60)
    parser.add_argument('--wait-timeout', type=float, default=86400)
    args = parser.parse_args()
    check(not (args.wait_terminal and args.allow_partial), 'Choose terminal wait or partial snapshot')
    if args.wait_terminal:
        wait_for_quality(args.root, args.refresh_seconds, args.wait_timeout)
    print(json.dumps(export(args.root, args.output, args.evidence_manifest, args.change_date, args.allow_partial), indent=2))


if __name__ == '__main__':
    main()
