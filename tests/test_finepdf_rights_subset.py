import copy
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from dfm12 import finepdf_rights_subset as m
from dfm12.io import digest, file_hash, write_json
from dfm12.jobs import audit_payload


def candidate():
    key, doc = next(iter(m.DOCS.items()))
    return dict(id='candidate', component=m.COMPONENT, language='lt', task='denoising',
                messages=[dict(role='user', content='Example'), dict(role='assistant', content='Target')],
                provenance=dict(source='baltic_lt_finepdfs', source_document_id=key,
                    row=doc['row'], url=doc['url'], file_sha256=m.PARQUET_SHA))


def test_exact_grant_not_domain():
    row = candidate()
    assert m.grant(row)
    row['provenance']['source_document_id'] = 'another-document-same-domain'
    assert m.grant(row) is None


def test_lv_scope_is_separate_exact_article():
    key, doc = next(iter(m.LV_DOCS.items()))
    row = candidate()
    row.update(component='transform-baltic_lv_finepdfs', language='lv')
    row['provenance'].update(source='baltic_lv_finepdfs', source_document_id=key,
        row=doc['row'], url=doc['url'], file_sha256=m.scope('lv')[1])
    assert m.grant(row, 'lv') == doc
    assert m.grant(row, 'lt') is None
    row['provenance']['row'] += 1
    with pytest.raises(ValueError):
        m.grant(row, 'lv')


def test_unreviewed_language_refused():
    with pytest.raises(ValueError):
        m.scope('en')


@pytest.mark.parametrize('key,value', [('row', 1), ('url', 'https://gamlec.eu/other.pdf'),
                                     ('file_sha256', 'changed'), ('source', 'other')])
def test_changed_provenance_refused(key, value):
    row = candidate()
    row['provenance'][key] = value
    with pytest.raises(ValueError, match='provenance'):
        m.grant(row)


@pytest.mark.parametrize('status,keep', [('pending', True), ('failed', True), ('done', False), ('done', True)])
def test_only_exact_completed_positive_audit(status, keep):
    row = candidate()
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,status TEXT,result TEXT)')
    review = dict(keep=keep, reason='Reviewed', language_quality=5, coherence=5, usefulness=5)
    key = digest(['audit', audit_payload(row, m.MODEL)])
    db.execute('INSERT INTO jobs VALUES(?,?,?)', (key, status, json.dumps(review)))
    assert bool(m.accepted_review(db, row)[0]) == (status == 'done' and keep)
    changed = copy.deepcopy(row)
    changed['messages'][-1]['content'] = 'Changed after review'
    assert m.accepted_review(db, changed)[0] is None
    db.close()


def test_bad_scores_not_accepted():
    row = candidate()
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,status TEXT,result TEXT)')
    review = dict(keep=True, reason='Bad', language_quality=5, coherence=2, usefulness=5)
    key = digest(['audit', audit_payload(row, m.MODEL)])
    db.execute('INSERT INTO jobs VALUES(?,?,?)', (key, 'done', json.dumps(review)))
    with pytest.raises(ValueError):
        m.accepted_review(db, row)
    db.close()


def publication(tmp_path, monkeypatch):
    output = tmp_path/'output'
    name = 'dfm13-wave3-finepdfs-lt-exact-ccby-v1-denoising'
    folder = output/name
    folder.mkdir(parents=True)
    (folder/'NOTICE.txt').write_text('Document CC BY; database ODC BY')
    (folder/'rights-receipt.json').write_text('{}')
    evidence_sha = file_hash(folder/'rights-receipt.json')
    monkeypatch.setattr(m, 'EVIDENCE_SHA', evidence_sha)
    record = dict(name=name.replace('-', '_'), hf_repo_id='schneiderkamplab/'+name,
                  license='cc-by-4.0', output_sha256='unchanged', tokenization_performed=False,
                  rights_receipt_sha256=evidence_sha,
                  files={'NOTICE.txt':file_hash(folder/'NOTICE.txt'), 'rights-receipt.json':evidence_sha})
    write_json(folder/'manifest.json', record)
    write_json(output/'publication.json', dict(packages=[dict(path=name,
               manifest_sha256=file_hash(folder/'manifest.json'))]))
    registry = tmp_path/'registry.json'
    write_json(registry, dict(additions=[dict(name='unrelated', value=7)]))
    api = SimpleNamespace(create_repo=lambda *a, **k: None,
                          upload_folder=lambda **k: SimpleNamespace(oid='commit'))
    return output, folder, registry, api


def test_remote_attachments_and_unrelated_registry_preserved(tmp_path, monkeypatch):
    output, folder, registry, api = publication(tmp_path, monkeypatch)
    checked = []
    def download(**kwargs):
        checked.append(kwargs['filename'])
        return folder/kwargs['filename']
    records = m.publish(output, registry, api, download)
    assert set(checked) == {'NOTICE.txt', 'manifest.json', 'rights-receipt.json'}
    assert records[0]['status'] == 'accepted_uploaded'
    assert json.loads(registry.read_text())['additions'][0] == dict(name='unrelated', value=7)


def test_remote_failure_never_integrates(tmp_path, monkeypatch):
    output, folder, registry, api = publication(tmp_path, monkeypatch)
    before = registry.read_bytes()
    wrong = tmp_path/'wrong'
    wrong.write_text('changed')
    with pytest.raises(ValueError, match='Hash mismatch'):
        m.publish(output, registry, api, lambda **k: wrong)
    assert registry.read_bytes() == before


def test_missing_evidence_not_built(tmp_path):
    with pytest.raises(FileNotFoundError):
        m.build(tmp_path/'live', tmp_path/'missing', tmp_path/'output')
    assert not (tmp_path/'output').exists()
