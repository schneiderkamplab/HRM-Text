import sqlite3
import pytest
from dfm12.io import write_json, file_hash, load
from scripts.advance_wave4_selections import freeze


def test_wait_then_freeze(tmp_path):
    root = tmp_path / 'wave4'
    budget = tmp_path / 'budget.json'
    assert freeze(root, budget) is None
    marker = root / 'parallel-preparation.json'
    write_json(marker, {'status': 'direct_and_pivot_preparation_finished'})
    candidate = root / 'audit-ready/direct-en-fa/candidates.jsonl'
    candidate.parent.mkdir(parents=True)
    candidate.write_text('{}\n')
    sha = file_hash(candidate)
    write_json(candidate.parent / 'receipt.json', {'path': str(candidate), 'sha256': sha})
    (root / 'audit').mkdir()
    with sqlite3.connect(root / 'audit/jobs.sqlite') as db:
        db.execute('CREATE TABLE components(name TEXT,sha TEXT)')
        db.execute('INSERT INTO components VALUES(?,?)', ('direct-en-fa', sha))
        db.execute('INSERT INTO components VALUES(?,?)', ('wikipedia-fa', 'ignored'))
    report = tmp_path / 'report.json'
    write_json(report, {})
    write_json(budget, {'source_report': str(report), 'source_report_sha256': file_hash(report)})
    manifest = freeze(root, budget)
    assert load(manifest)['components'] == [{'component': 'direct-en-fa', 'sha256': sha}]
    assert freeze(root, budget) == manifest
    write_json(marker, {'status': 'direct_and_pivot_preparation_finished', 'changed': True})
    with pytest.raises(ValueError, match='preparation changed'):
        freeze(root, budget)
