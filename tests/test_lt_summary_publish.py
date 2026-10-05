import copy
import csv
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from dfm12 import lt_summary_publish as pub
from dfm12 import baltic_lt_summary_privacy as privacy
from dfm12.io import file_hash, load, write_json
from dfm12.jobs import Queue
from scripts.prepare_dfm13_baltic import messages
from scripts import assemble_dfm13_additions as assembler
from scripts.tokenize_wave_releases import eligible


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root, screening = tmp_path / 'root', tmp_path / 'screening'
    source = root / 'downloads' / privacy.COMPONENT
    csvpath = source / 'csv/train/it.csv'
    csvpath.parent.mkdir(parents=True)
    upstream = dict(text='Public technology report', summary_abstract='A short summary')
    with csvpath.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(upstream))
        writer.writeheader()
        writer.writerow(upstream)
    for name in ('LICENSE.txt', 'README.md'):
        (source / name).write_text('Source ' + name)
    monkeypatch.setattr(pub, 'LICENSE_SHA', file_hash(source / 'LICENSE.txt'))
    monkeypatch.setattr(pub, 'CARD_SHA', file_hash(source / 'README.md'))
    original = dict(id='pass', language='lt', messages=messages(upstream, 'summary'),
        rendered_tokens=20, provenance=dict(repo=pub.REPO, revision=pub.REVISION,
            file=str(csvpath), file_sha256=file_hash(csvpath), row=0))
    originals = [dict(copy.deepcopy(original), id=k) for k in ('pass', 'repair', 'privacy', 'manual', 'quality')]
    candidate = root / 'audit-ready' / privacy.COMPONENT / 'candidates.jsonl'
    candidate.parent.mkdir(parents=True)
    candidate.write_text(''.join(json.dumps(r) + '\n' for r in originals))
    write_json(candidate.parent / 'receipt.json', dict(path=str(candidate), sha256=file_hash(candidate), counts={'ready': 5}))
    dbpath = root / 'release' / privacy.COMPONENT / 'ledger.sqlite'
    dbpath.parent.mkdir(parents=True)
    result = dict(keep=True, language_quality=5, coherence=5, usefulness=5, reason='public',
        credentials=False, direct_sensitive_pii=False, uncertain=False)
    screening.mkdir()
    write_json(screening / 'manual-holds.json', {'manual': 'uncertain private context'})
    queue = Queue(screening / 'jobs.sqlite')
    with sqlite3.connect(dbpath) as db:
        db.execute('CREATE TABLE rows(id TEXT,status TEXT,record TEXT,review TEXT)')
        for original in originals:
            final = copy.deepcopy(original)
            state = 'accepted'
            if original['id'] == 'repair':
                final['id'] = 'repaired-id'
                final['messages'][1]['content'] = 'Repaired complete summary'
                final['provenance']['repair_parent'] = original['id']
                state = 'accepted_repair'
            if original['id'] == 'quality':
                state = 'repair_rejected'
            db.execute('INSERT INTO rows VALUES(?,?,?,?)', (original['id'], state, json.dumps(final), json.dumps(result)))
            pin = dict(input_sha256=file_hash(candidate), provenance=original['provenance'])
            job = queue.add('audit', privacy.payload(final, pin))
            answer = dict(result, keep=False, uncertain=True) if original['id'] == 'privacy' else result
            queue.db.execute("UPDATE jobs SET status='done',result=? WHERE id=?", (json.dumps(answer), job))
    queue.close()
    report = privacy.prepare(root, screening, False)
    monkeypatch.setattr(pub, 'REPORT_SHA', file_hash(screening / 'report.json'))
    monkeypatch.setattr(pub, 'COUNTS', report['counts'])
    return root, screening, tmp_path / 'publication', tmp_path / 'registry.json'


def test_build_exact_acceptance_and_repairs(setup):
    root, screening, output, _ = setup
    record = pub.build(root, screening, output)
    folder = output / pub.NAME.replace('_', '-')
    exported = list(pub.rows(folder / 'data/train.jsonl'))
    assert [r['id'] for r in exported] == ['pass', 'repaired-id']
    assert all(r['target_message_index'] == 1 for r in exported)
    assert record['rows'] == 2
    assert set(record['files']) == pub.ATTACHMENTS
    pub.verify_package(folder, file_hash(folder / 'manifest.json'))


@pytest.mark.parametrize('change', ['repair', 'partial', 'source', 'hold', 'pending'])
def test_stale_or_partial_never_builds(setup, change):
    root, screening, output, _ = setup
    dbpath = root / 'release' / privacy.COMPONENT / 'ledger.sqlite'
    if change in ('repair', 'partial'):
        with sqlite3.connect(dbpath) as db:
            row = json.loads(db.execute("SELECT record FROM rows WHERE id='repair'").fetchone()[0])
            if change == 'partial':
                row['messages'].pop(0)
            else:
                row['messages'][1]['content'] = 'Changed after review'
            db.execute("UPDATE rows SET record=? WHERE id='repair'", (json.dumps(row),))
    elif change == 'source':
        (root / 'downloads' / privacy.COMPONENT / 'csv/train/it.csv').write_text('changed')
    elif change == 'hold':
        write_json(screening / 'manual-holds.json', {'manual': 'hold', 'pass': 'new hold'})
    else:
        with sqlite3.connect(screening / 'jobs.sqlite') as db:
            db.execute("UPDATE jobs SET status='pending'")
    with pytest.raises(ValueError):
        pub.build(root, screening, output)
    assert not output.exists()


class FakeHF:
    def create_repo(self, *args, **kwargs):
        pass

    def upload_folder(self, **kwargs):
        self.folder = kwargs['folder_path']
        self.files = kwargs['allow_patterns']
        self.downloaded = []
        return SimpleNamespace(oid='commit123')

    def download(self, **kwargs):
        assert kwargs['revision'] == 'commit123'
        self.downloaded.append(kwargs['filename'])
        return self.folder / kwargs['filename']


def test_upload_all_hashes_registry_adapter_and_watcher(setup):
    root, screening, output, registry = setup
    pub.build(root, screening, output)
    write_json(registry, {'additions': [{'name': 'unrelated'}]})
    hf = FakeHF()
    record = pub.publish(output, registry, hf, hf.download)
    assert set(hf.downloaded) == pub.ATTACHMENTS | {'manifest.json'}
    assert eligible(record)
    assert load(registry)['additions'][0] == {'name': 'unrelated'}
    assembler.verify_lt_summary_publication(record, Path(record['output']), {})
    config = load(registry)
    config['additions'][1].update(tokenization_performed=True, tokenized_tokens=30)
    write_json(registry, config)
    pub.publish(output, registry, hf, hf.download)
    assert load(registry)['additions'][1]['tokenization_performed']
    assert load(registry)['additions'][1]['tokenized_tokens'] == 30
    record['model_use_conditions'] = {}
    with pytest.raises(ValueError):
        assembler.verify_lt_summary_publication(record, Path(record['output']), {})


def test_remote_corruption_never_integrates(setup, tmp_path):
    root, screening, output, registry = setup
    pub.build(root, screening, output)
    write_json(registry, {'additions': []})
    wrong = tmp_path / 'wrong'
    wrong.write_text('wrong attachment')
    with pytest.raises(ValueError):
        pub.publish(output, registry, FakeHF(), lambda **kwargs: wrong)
    assert load(registry) == {'additions': []}


def test_local_corruption_prevents_upload(setup):
    root, screening, output, registry = setup
    pub.build(root, screening, output)
    (output / pub.NAME.replace('_', '-') / 'privacy-receipt.json').write_text('{}')
    with pytest.raises(ValueError):
        pub.publish(output, registry, FakeHF(), None)


@pytest.mark.parametrize('change', ['messages', 'missing_receipt'])
def test_privacy_binding_checked_beyond_attachment_hashes(setup, change):
    root, screening, output, _ = setup
    pub.build(root, screening, output)
    folder = output / pub.NAME.replace('_', '-')
    manifest = load(folder / 'manifest.json')
    if change == 'messages':
        path = folder / 'data/train.jsonl'
        data = list(pub.rows(path))
        data[0]['messages'][0]['content'] = 'Changed source after screening'
        path.write_text(''.join(json.dumps(r) + '\n' for r in data))
        manifest['files']['data/train.jsonl'] = file_hash(path)
    else:
        path = folder / 'privacy-receipt.json'
        receipt = load(path)
        receipt['records'].pop()
        write_json(path, receipt)
        manifest['files']['privacy-receipt.json'] = file_hash(path)
    write_json(folder / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='privacy'):
        pub.verify_package(folder, file_hash(folder / 'manifest.json'))
