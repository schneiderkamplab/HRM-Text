import json
import sqlite3

import pytest

from dfm12.io import file_hash, write_json
from dfm12.wave_release import release, source_attribution


def test_transform_publication_is_task_specific_and_accepted_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / 'wave4'
    component = 'wikipedia-bg'
    download = root / 'downloads' / component
    download.mkdir(parents=True)
    write_json(download / 'wave4-download.json', dict(repo='wikimedia/wikipedia', revision='pinned'))
    (download / 'README.md').write_text('---\nlicense:\n- cc-by-sa-3.0\n- gfdl\n---\n')
    sealed = root / 'audit-ready' / component / 'candidates.jsonl'
    sealed.parent.mkdir(parents=True)
    sealed.write_text('sealed input\n')
    write_json(sealed.parent / 'receipt.json', dict(path=str(sealed)))
    ledger = root / 'release' / component
    ledger.mkdir(parents=True)
    review = dict(keep=True, language_quality=5, coherence=5, usefulness=5, reason='OK')
    with sqlite3.connect(ledger / 'ledger.sqlite') as db:
        db.execute('CREATE TABLE rows(id TEXT, record TEXT, status TEXT, review TEXT)')
        for i, (task, status) in enumerate([
            ('denoising', 'accepted'), ('span-filling', 'accepted'), ('denoising', 'rejected')
        ]):
            row = dict(id=str(i), task=task, language='bg', rendered_tokens=10,
                messages=[dict(role='user', content='Question'), dict(role='assistant', content='Answer')],
                provenance=dict(repo='wikimedia/wikipedia', revision='pinned', url='https://bg.wikipedia.org/wiki/Test'))
            db.execute('INSERT INTO rows VALUES(?,?,?,?)',
                (str(i), json.dumps(row), status, json.dumps(dict(review, keep=status == 'accepted'))))
    write_json(ledger / 'status.json', dict(export_ready=True, input_sha256=file_hash(sealed),
        counts={'accepted': 2, 'rejected': 1}))
    release(root, component, task='denoising')
    publication = json.loads((ledger / 'denoising/publication.json').read_text())
    assert publication['rows'] == 1
    assert publication['license'] == ['cc-by-sa-3.0', 'gfdl']
    assert not publication['uploaded']
    row = json.loads(open(publication['output']).read())
    assert row['task'] == 'denoising'
    assert row['target_message_index'] == 1
    assert row['provenance']['url'].endswith('/Test')
    assert row['provenance']['license_card_sha256'] == file_hash(download / 'README.md')
    with pytest.raises(ValueError, match='pin mismatch'):
        source_attribution(root, component, dict(repo='wikimedia/wikipedia', revision='wrong'), 'denoising')


def test_baltic_licenses_are_pinned_and_source_holds_enforced(tmp_path):
    root = tmp_path / 'baltic'
    component = 'baltic_lt_aya'
    card = root / 'downloads' / component / 'README.md'
    card.parent.mkdir(parents=True)
    card.write_text('---\nlicense: apache-2.0\n---\n')
    write_json(root / 'receipts' / (component + '.json'), dict(repo='CohereLabs/aya_dataset', revision='pin',
        files=[dict(path=str(card), sha256=file_hash(card))]))
    source = dict(repo='CohereLabs/aya_dataset', revision='pin')
    assert source_attribution(root, component, source, 'instruction')['license'] == 'apache-2.0'
    with pytest.raises(ValueError, match='source-hold review'):
        release(root, 'baltic_lt_summary')
    card.write_text('---\nlicense: mit\n---\n')
    with pytest.raises(ValueError, match='card changed'):
        source_attribution(root, component, source, 'instruction')


def test_baltic_euroblocks_retains_unspecified_license(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / 'data/dfm12/european-expansion-20260926'
    pin = dict(repo='utter-project/EuroBlocks-SFT-2512', revision='pin', files=['data/train.parquet'])
    write_json(base / 'sources.lock.json', {'sources': {'euroblocks': pin}})
    cards = tmp_path / 'data/dfm13/wave4/downloads/utter-project--EuroBlocks-SFT-2512'
    write_json(cards / 'wave4-download.json', pin)
    (cards / 'README.md').write_text('---\nlanguage: lt\n---\n')
    source = dict(repo=pin['repo'], revision='pin', file='data/train.parquet', split='train')
    result = source_attribution(tmp_path / 'baltic', 'baltic-euroblocks', source, 'instruction')
    assert result['license'] is None
    with pytest.raises(ValueError, match='file/split'):
        source_attribution(tmp_path / 'baltic', 'baltic-euroblocks', {**source, 'split': 'test'}, 'instruction')


def test_nested_lithuanian_qa_license(tmp_path):
    root = tmp_path / 'baltic'
    component = 'baltic_lt_qa'
    card = root / 'downloads' / component / 'README.md'
    card.parent.mkdir(parents=True)
    card.write_text('---\ndataset:\n  usage_and_licensing:\n    licensing_information: International (CC BY 4.0) license\n---\n')
    write_json(root / 'receipts' / (component + '.json'), dict(repo='neurotechnology/lithuanian-qa-v1',
        revision='pin', files=[dict(path=str(card), sha256=file_hash(card))]))
    result = source_attribution(root, component,
        dict(repo='neurotechnology/lithuanian-qa-v1', revision='pin'), 'instruction')
    assert result['license'] == 'cc-by-4.0'
