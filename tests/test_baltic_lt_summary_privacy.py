import copy
import json
import sqlite3

import pytest

from dfm12.baltic_lt_summary_privacy import (
    COMPONENT, binding, decision, payload, prepare, validate_final,
)
from dfm12.io import file_hash, write_json
from dfm12.jobs import Queue, validate_audit


def record():
    return dict(id='original', messages=[dict(role='user', content='Full source article'),
                dict(role='assistant', content='Complete summary')], provenance={})


def passed():
    return dict(keep=True, reason='Public article', language_quality=5, coherence=5,
                usefulness=5, direct_sensitive_pii=False, credentials=False, uncertain=False)


@pytest.mark.parametrize('change', ['assistant', 'user', 'pin'])
def test_changed_content_invalidates(change):
    old = record()
    new = copy.deepcopy(old)
    pin = {'sha': 'one'}
    receipt = binding(old, pin)
    if change == 'pin':
        pin = {'sha': 'two'}
    else:
        new['messages'][change == 'assistant']['content'] += ' changed'
    assert decision(new, pin, receipt, passed()) == 'stale_hold'
    assert payload(old, {'sha': 'one'}) != payload(new, pin)


@pytest.mark.parametrize('flag', ['direct_sensitive_pii', 'credentials', 'uncertain'])
def test_flags_override_model_keep(flag):
    result = passed()
    result[flag] = True
    r = record()
    assert decision(r, {}, binding(r, {}), result) == 'privacy_hold'


def test_manual_and_missing_flags():
    r = record()
    assert decision(r, {}, binding(r, {}), passed(), True) == 'manual_hold'
    result = passed()
    del result['uncertain']
    assert decision(r, {}, binding(r, {}), result) == 'invalid_hold'


def test_full_payload_and_existing_validator():
    r = record()
    p = payload(r, {})
    assert json.loads(p['request']['messages'][1]['content']) == r
    validate_audit(passed())
    assert decision(r, {}, binding(r, {}), passed()) == 'model_pass_not_certified'


@pytest.mark.parametrize('change', ['partial', 'user', 'role', 'provenance'])
def test_partial_or_changed_source_rejected(change):
    old = record()
    new = copy.deepcopy(old)
    if change == 'partial':
        new['messages'].pop()
    elif change == 'user':
        new['messages'][0]['content'] = 'redacted subset'
    elif change == 'role':
        new['messages'][0]['role'] = 'assistant'
    else:
        new['provenance']['revision'] = 'different'
    with pytest.raises(ValueError):
        validate_final(old, new)


def test_queue_refresh_and_full_coverage(tmp_path):
    root = tmp_path / 'root'
    out = tmp_path / 'privacy'
    source = root / 'downloads' / COMPONENT / 'csv/train/it.csv'
    source.parent.mkdir(parents=True)
    source.write_text('source')
    r = record()
    r['provenance'] = dict(file=str(source), file_sha256=file_hash(source), revision='pinned')
    pending = copy.deepcopy(r)
    pending['id'] = 'pending'
    inputs = root / 'audit-ready' / COMPONENT / 'candidates.jsonl'
    inputs.parent.mkdir(parents=True)
    inputs.write_text(json.dumps(r) + '\n' + json.dumps(pending) + '\n')
    write_json(inputs.parent / 'receipt.json', dict(path=str(inputs), sha256=file_hash(inputs),
                                                   counts={'ready': 2}))
    ledger = root / 'release' / COMPONENT / 'ledger.sqlite'
    ledger.parent.mkdir(parents=True)
    db = sqlite3.connect(ledger)
    db.execute('CREATE TABLE rows(id TEXT,status TEXT,record TEXT)')
    db.execute('INSERT INTO rows VALUES(?,?,?)', (r['id'], 'accepted', json.dumps(r)))
    db.commit()
    first = prepare(root, out, False)
    assert first['counts'] == {'privacy_pending': 1, 'quality_hold': 1}
    q = Queue(out / 'jobs.sqlite')
    q.db.execute("UPDATE jobs SET status='done',result=?", (json.dumps(passed()),))
    assert prepare(root, out, False)['counts']['model_pass_not_certified'] == 1
    r['messages'][1]['content'] = 'New repaired final'
    db.execute('UPDATE rows SET record=?,status=?', (json.dumps(r), 'accepted_repair'))
    db.commit()
    refreshed = prepare(root, out, False)
    assert refreshed['counts'] == {'privacy_pending': 1, 'quality_hold': 1}
    assert not refreshed['publication_authorized']
    assert q.db.execute('SELECT count(*) FROM jobs').fetchone()[0] == 2
    write_json(out / 'manual-holds.json', {'original': 'Human privacy concern'})
    q.db.execute("UPDATE jobs SET status='done',result=?", (json.dumps(passed()),))
    assert prepare(root, out, False)['counts']['manual_hold'] == 1
    q.close()
    db.close()
