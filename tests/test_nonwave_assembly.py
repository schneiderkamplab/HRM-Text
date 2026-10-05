import copy
import json

import pytest

from dfm12 import nonwave_assembly as adapter
from scripts import assemble_dfm13_additions as assembly


def entry(name='jjzha_skillspan'):
    return dict(name=name, repeat=1, status='accepted_uploaded', publication_status='verified',
                hf_repo_id='example/repo', hf_revision='a'*40, tokenization_performed=True,
                tokenized_path='tokens', tokenization_receipt='receipt.json',
                tokenization_receipt_sha256='b'*64)


@pytest.mark.parametrize('name', sorted(adapter.NAMES))
def test_exact_scope_has_explicit_token_gate(name):
    e = entry(name)
    assert adapter.unready_reason(e) is None
    e['tokenization_performed'] = False
    assert assembly.unready_reason(e) == 'nonwave_target_only_tokenization_not_ready'


@pytest.mark.parametrize('field', ['tokenized_path', 'tokenization_receipt', 'tokenization_receipt_sha256'])
def test_incomplete_token_receipt_blocked(field):
    e = entry(); del e[field]
    assert adapter.unready_reason(e) == 'nonwave_target_only_tokenization_not_ready'


@pytest.mark.parametrize('repeat', [True, 0, -1, '1'])
def test_repeat_policy(repeat):
    e = entry(); e['repeat'] = repeat
    assert adapter.unready_reason(e) == 'invalid_or_zero_nonwave_repeat'


def test_unknown_nonwave_still_denied():
    assert assembly.unready_reason(entry('jjzha_unknown')).startswith('unsupported_non_wave')
    assert assembly.unready_reason(entry('repochat')) == 'research_only_source_excluded_by_user_policy'


def test_completed_overcontext_artifacts_not_admitted():
    e = entry(); e['tokenized_sequences_over_4096'] = 1
    assert assembly.unready_reason(e) == 'nonwave_full_native_rows_exceed_4096_no_truncation'
    with pytest.raises(ValueError, match='not ready'):
        assembly.verify_entry(e, {}, {})


def test_shared_release_cache_revalidates_changed_inputs(monkeypatch, tmp_path):
    state={'ledger': (1, 2, 3)}; calls=[]
    monkeypatch.setattr(adapter,'release_state',lambda path:dict(state))
    monkeypatch.setattr('scripts.dfm13_arena_authorized_release.validate_release',
                        lambda path: calls.append(path) or {'verified': True})
    path=tmp_path/'release.json'
    adapter.checked_release(path);adapter.checked_release(path)
    assert len(calls)==1
    state['ledger']=(1,2,4);adapter.checked_release(path)
    assert len(calls)==2


def test_shared_release_cache_rejects_concurrent_change(monkeypatch,tmp_path):
    states=iter([{'ledger':1},{'ledger':2}])
    monkeypatch.setattr(adapter,'release_state',lambda path:next(states))
    monkeypatch.setattr('scripts.dfm13_arena_authorized_release.validate_release',lambda path:{})
    with pytest.raises(ValueError,match='changed during'):
        adapter.checked_release(tmp_path/'release.json')


def test_dispatch_preserves_hold_gate(monkeypatch):
    monkeypatch.setattr('dfm12.wave_publication_holds.entry_quality_hold', lambda e: True)
    with pytest.raises(ValueError, match='quality_hold'):
        assembly.verify_entry(entry(), {}, {})
    assert assembly.unready_reason(entry()) == 'quality_hold_source_fidelity'


def fixture(status='accepted', pending=True, source='jjzha/skillspan'):
    row = dict(id='one', messages=[dict(role='user', content='Question'),
                                 dict(role='assistant', content='Answer')], target_message_index=1,
               metadata=dict(source=source, source_dataset='source', audit_required=True))
    proof = dict(audit=dict(verdict='keep'), reaudit=dict(verdict='keep'))
    exported = copy.deepcopy(row)
    exported['metadata'].update(audit_required=False, quality_status=status,
        quality_method='model_review' if pending else 'source_specific_validation')
    return exported, (json.dumps(row), status, json.dumps(proof)), dict(status='pending_audit' if pending else 'prepared')


@pytest.mark.parametrize('status,pending', [('accepted', True), ('accepted_repair', True), ('accepted', False)])
def test_ledger_exact_replay(status, pending):
    adapter.jjzha_row(*fixture(status, pending))


@pytest.mark.parametrize('status', ['pending', 'rejected', 'failed'])
def test_nonaccepted_cannot_be_published(status):
    with pytest.raises(ValueError, match='unresolved/rejected'):
        adapter.jjzha_row(*fixture(status))


@pytest.mark.parametrize('field', ['audit', 'reaudit'])
def test_missing_keep(field):
    row, job, prepared = fixture('accepted' if field == 'audit' else 'accepted_repair')
    with pytest.raises(ValueError, match='lacks keep'):
        adapter.jjzha_row(row, (job[0], job[1], '{}'), prepared)


def test_changed_export_rejected():
    row, job, prepared = fixture()
    row['messages'][1]['content'] = 'different'
    with pytest.raises(ValueError, match='differs'):
        adapter.jjzha_row(row, job, prepared)


def test_tasksource_stays_denied():
    row, job, prepared = fixture()
    original = json.loads(job[0]); original['metadata']['source_dataset'] = 'tasksource'
    with pytest.raises(ValueError, match='policy-denied'):
        adapter.jjzha_row(row, (json.dumps(original), job[1], job[2]), prepared)


def test_imdb_repair_preserves_binary_task():
    with pytest.raises(ValueError, match='IMDb'):
        adapter.jjzha_row(*fixture('accepted_repair', source='jjzha/imdb-dutch-instruct'))


def test_missing_ledger_row():
    row, _, prepared = fixture()
    with pytest.raises(ValueError, match='Missing'):
        adapter.jjzha_row(row, None, prepared)


def test_verify_does_not_read_payload_without_token_receipt():
    e = entry(); e['tokenization_performed'] = False
    with pytest.raises(ValueError, match='not ready'):
        adapter.verify(e, {}, {})


def test_unknown_preparation_not_audit_bypass():
    row, job, _ = fixture()
    with pytest.raises(ValueError, match='Unknown'):
        adapter.jjzha_row(row, job, dict(status='pending'))


@pytest.fixture
def token_fixture(tmp_path, monkeypatch):
    from dfm12.io import file_hash
    root = tmp_path/'tokens'; root.mkdir()
    part = root/'part-000000.jsonl'; part.mkdir()
    (part/'placeholder').write_text('array fixture')
    (root/'tokenizer_info.json').write_text('{}')
    (root/'completion.json').write_text(json.dumps(dict(rows=1, files=1,
        skipped_rows_this_run=0, max_seq_len=None)))
    source = tmp_path/'source.jsonl'; source.write_text('{}\n')
    e = entry(); e.update(output=str(source), output_sha256=file_hash(source), rows=1,
        tokenized_path=str(root), tokenized_rows=1, tokenized_tokens=3,
        target_policy='final_assistant_only_native_gemma')
    receipt = dict(schema='dfm13-nonwave-target-only-tokenization-v1',
        source_sha256=e['output_sha256'], target_policy=e['target_policy'],
        hard_truncation=False, regex_fix=False, output=str(root), rows=1, tokens=3,
        files={str(p):file_hash(p) for p in root.rglob('*') if p.is_file()})
    path = tmp_path/'receipt.json'
    def save():
        path.write_text(json.dumps(receipt))
        e.update(tokenization_receipt=str(path), tokenization_receipt_sha256=file_hash(path))
    save()
    monkeypatch.setattr(adapter, 'publication', lambda *a: dict(source=str(source)))
    monkeypatch.setattr(assembly, 'token_contract', lambda *a: dict(vocab_size=10))
    monkeypatch.setattr(assembly, 'verify_arrays', lambda *a: dict(rows=1, tokens=3))
    monkeypatch.setattr(assembly, 'verify_native_sample', lambda *a: dict(exact=True))
    return e, receipt, save, root


def test_verified_token_dispatch(token_fixture):
    e, _, _, _ = token_fixture
    result = assembly.verify_entry(e, dict(vocab_size=10), {})
    assert result['rows'] == 1 and result['tokens'] == 3
    assert result['native_token_parity'] == dict(exact=True)


@pytest.mark.parametrize('field,value', [('hard_truncation', True), ('regex_fix', True),
    ('source_sha256', 'wrong'), ('target_policy', 'all_assistants'), ('schema', 'unknown')])
def test_token_policy_tamper(token_fixture, field, value):
    e, receipt, save, _ = token_fixture
    receipt[field] = value; save()
    with pytest.raises(ValueError, match='policy/payload'):
        assembly.verify_entry(e, dict(vocab_size=10), {})


def test_token_inventory_tamper(token_fixture):
    e, _, _, root = token_fixture
    (root/'extra').write_text('unexpected')
    with pytest.raises(ValueError, match='inventory'):
        assembly.verify_entry(e, dict(vocab_size=10), {})


def test_token_counts_tamper(token_fixture):
    e, receipt, save, _ = token_fixture
    receipt['tokens'] = 4; save()
    with pytest.raises(ValueError, match='counts'):
        assembly.verify_entry(e, dict(vocab_size=10), {})
