import json
from pathlib import Path

import numpy as np
import pytest

from scripts import assemble_dfm13_additions as m


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def arrays(path):
    path.mkdir(parents=True, exist_ok=True)
    values = dict(tokens=[1, 2, 3, 4, 5], inst_start=[0], inst_len=[2], resp_start=[2], resp_len=[3])
    for field, data in values.items():
        np.save(path / (field + '.npy'), np.array(data, dtype=np.uint32))


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'native_encoder', lambda info: lambda row, final_only=True: [([1, 2], [3, 4, 5])])
    base = tmp_path / 'base'; base.mkdir()
    tokenizer = tmp_path / 'tokenizer.json'; tokenizer.write_text('{}')
    template = tmp_path / 'template.jinja'; template.write_text('test template')
    info = dict(tokenizer_path=str(tokenizer), chat_template_path=str(template),
                vocab_size=32, enable_thinking=False, template_mode='jinja_chat_template')
    write(base / 'metadata.json', dict(tokenizer_info=info, max_seq_len=4097, total_length=5))
    arrays(base / 'epoch_10'); np.save(base / 'tokens.npy', np.array([1, 2, 3, 4, 5]))
    name = 'dfm13_wave4_test_en'; source = tmp_path / 'export/data/train.jsonl'
    write(source, dict(messages=[dict(role='user', content='Q'), dict(role='assistant', content='A')], target_message_index=1))
    entry = dict(name=name, output=str(source), output_sha256=m.checksum(source), rows=1, rendered_tokens=5,
        repeat=2, target_policy='final_assistant_only_native_gemma', hf_repo_id='example/test',
        status='accepted_uploaded', uploaded=True, hf_revision='fixed-revision', tokenization_performed=True,
        manifest=str(tmp_path / 'publication.json'), tokenized_path=str(tmp_path / 'tokenized'),
        tokenization_receipt=str(tmp_path / 'verified.json'), tokenized_tokens=5, tokenized_rows=1)
    write(tmp_path / 'publication.json', entry)
    export = dict(entry, uploaded=False, tokenization_performed=False); export.pop('status'); export.pop('hf_revision')
    write(source.parent.parent / 'manifest.json', export)
    root = tmp_path / 'tokenized'; arrays(root / 'part-000000.jsonl')
    write(root / 'tokenizer_info.json', info)
    write(root / 'completion.json', dict(rows=1, files=1, skipped_rows_this_run=0, max_seq_len=4096))
    write(tmp_path / 'verified.json', dict(pins=dict(source_sha256=entry['output_sha256'],
        tokenizer_sha256=m.checksum(tokenizer), template_sha256=m.checksum(template)), rows=1, tokens=5, output=str(root)))
    registry = tmp_path / 'registry.json'; write(registry, dict(inherits='dfm12', additions=[entry]))
    return dict(base=base, registry=registry, entry=entry, output=tmp_path / 'assembly', root=tmp_path)


def run(f):
    return m.assemble(f['registry'], f['base'], f['output'])


@pytest.fixture
def blkt_fixture(fixture, monkeypatch):
    from dfm12 import blkt_publish as bp, blkt_export as be
    f = fixture
    e = f['entry']
    e.update(name='dfm13_wave3_transform_baltic_lt_blkt_denoising_newgenltu',
        repo_id=be.REPO, revision=be.REVISION, task='denoising',
        hf_repo_id='schneiderkamplab/dfm13-wave3-transform-baltic-lt-blkt-denoising-newgenltu',
        publication_status='verified', preparation_sha256=bp.PREPARATION_SHA,
        preparation_data_sha256='fixture-source-hash', model_use_conditions=bp.MODEL_CONDITIONS,
        admission_authorized=True, license='NewGenLTU Open RAIL-D 1.0')
    monkeypatch.setattr(bp, 'TASKS', {'denoising': 1})
    folder = Path(e['output']).parent.parent
    attachments = ('LICENSE.txt', 'NOTICE.txt', 'USE_CONDITIONS.md', 'SOURCE_README.md',
                   'attribution.jsonl', 'README.md')
    for name in attachments:
        (folder / name).write_text(name)
    monkeypatch.setattr(be, 'LICENSE_SHA', m.checksum(folder / 'LICENSE.txt'))
    e['files'] = {name: m.checksum(folder / name) for name in (*attachments, 'data/train.jsonl')}
    e.pop('manifest')
    export = folder / 'manifest.json'
    e['export_manifest'] = str(export)
    write(export, e)
    e['export_manifest_sha256'] = m.checksum(export)
    write(folder.parent / (folder.name + '.verified.json'), e)
    write(f['registry'], dict(inherits='dfm12', additions=[e]))
    return f


def test_blkt_conditions_survive_assembly(blkt_fixture):
    result = run(blkt_fixture)
    assert result['totals']['ready_sources'] == 1
    assert result['ready_additions'][0]['model_use_conditions'] == blkt_fixture['entry']['model_use_conditions']
    assert result['ready_additions'][0]['publication_contract'] == 'blkt-newgenltu-verified-v1'
    assert any(p.endswith('/USE_CONDITIONS.md') for p in result['files'])


def test_blkt_attachment_drift_blocks(blkt_fixture):
    (Path(blkt_fixture['entry']['output']).parent.parent / 'NOTICE.txt').write_text('changed')
    assert run(blkt_fixture)['totals']['ready_sources'] == 0


def test_blkt_conditions_missing_blocks(blkt_fixture):
    entry = blkt_fixture['entry']
    entry.pop('model_use_conditions')
    write(blkt_fixture['registry'], dict(inherits='dfm12', additions=[entry]))
    assert run(blkt_fixture)['totals']['ready_sources'] == 0


def test_blkt_missing_status_not_bypassed(blkt_fixture):
    entry = dict(blkt_fixture['entry'])
    entry.pop('status')
    assert m.unready_reason(entry) == 'not_accepted_uploaded_with_revision'


def test_distinct_budget_bases_and_multiturn_parity(fixture, monkeypatch):
    f = fixture; entry = f['entry']; entry['rendered_tokens'] = 8
    source = Path(entry['output'])
    write(source, dict(messages=[dict(role='user', content='Q'), dict(role='assistant', content='A'),
        dict(role='user', content='Followup'), dict(role='assistant', content='Answer')],
        target_message_index=3, rendered_tokens=8))
    entry['output_sha256'] = m.checksum(source)
    write(f['registry'], dict(inherits='dfm12', additions=[entry]))
    write(Path(entry['manifest']), entry)
    write(source.parent.parent / 'manifest.json', entry)
    receipt = json.loads(Path(entry['tokenization_receipt']).read_text())
    receipt['pins']['source_sha256'] = entry['output_sha256']
    write(Path(entry['tokenization_receipt']), receipt)
    monkeypatch.setattr(m, 'native_encoder', lambda info: lambda row, final_only=True:
        [([1, 2], [3, 4, 5])] if final_only else [([1], [2, 3]), ([1, 2], [3, 4, 5])])
    result = run(f)['ready_additions'][0]
    assert result['token_metrics']['training']['tokens'] == 5
    assert result['token_metrics']['preflight']['tokens'] == 8
    assert result['native_token_parity']['rows'][0]['all_assistant_rendered_tokens'] == 8


@pytest.mark.parametrize('encoded', [([9, 2], [3, 4, 5]), ([1, 2], [3, 4, 9]), ([1]*4096, [3, 4])])
def test_native_mismatch_or_untruncated_overflow_rejected(fixture, monkeypatch, encoded):
    monkeypatch.setattr(m, 'native_encoder', lambda info: lambda row, final_only=True: [encoded])
    assert run(fixture)['totals']['ready_sources'] == 0


def test_real_encoder_keeps_history_and_does_not_truncate(tmp_path):
    from tokenizers import Tokenizer, models, pre_tokenizers
    tokenizer = Tokenizer(models.WordLevel({'[UNK]': 0, 'user': 1, 'assistant': 2,
        'first': 3, 'answer': 4, 'followup': 5, 'final': 6, 'end': 7}, unk_token='[UNK]'))
    tokenizer.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    path = tmp_path / 'tokenizer.json'; tokenizer.save(str(path))
    template = tmp_path / 'template.jinja'
    template.write_text("{% for m in messages %}{{ m.role }} {{ m.content }} end {% endfor %}"
                        "{% if add_generation_prompt %}assistant {% endif %}")
    encode = m.native_encoder(dict(tokenizer_path=str(path), chat_template_path=str(template)))
    row = dict(messages=[dict(role='user', content='first'), dict(role='assistant', content='answer'),
        dict(role='user', content='followup'), dict(role='assistant', content='final')], target_message_index=3)
    final = encode(row)
    assert final == [([1, 3, 7, 2, 4, 7, 1, 5, 7, 2], [6, 7])]
    assert len(encode(row, False)) == 2
    row['messages'][0]['content'] = ' '.join(['first'] * 4100)
    assert sum(map(len, encode(row)[0])) > 4096


def test_source_preflight_sum_is_checked(fixture):
    f = fixture; entry = f['entry']; source = Path(entry['output'])
    row = json.loads(source.read_text()); row['rendered_tokens'] = 9; write(source, row)
    entry['output_sha256'] = m.checksum(source)
    write(f['registry'], dict(inherits='dfm12', additions=[entry]))
    write(Path(entry['manifest']), entry); write(source.parent.parent / 'manifest.json', entry)
    result = run(f)
    assert result['unready_additions'][0]['detail'] == 'Source preflight sum mismatch'


def test_verified_subset_has_no_epochs_and_preserves_inputs(fixture):
    f = fixture; original = f['registry'].read_bytes(); before = m.checksum(f['base'] / 'epoch_10/inst_start.npy')
    result = run(f)
    assert result['totals'] == dict(ready_sources=1, unready_sources=0, rows=1, tokens=5)
    assert result['complete_dfm13'] is False and result['sampling_performed'] is False
    assert not list(f['output'].glob('epoch_*'))
    assert not (f['output'] / 'tokens.npy').exists()
    assert f['registry'].read_bytes() == original == (f['output'] / 'registry.snapshot.json').read_bytes()
    assert m.checksum(f['base'] / 'epoch_10/inst_start.npy') == before
    link = f['output'] / 'tokenized_additions/dfm13_wave4_test_en__part-000000.jsonl'
    assert link.is_symlink()
    assert len(result['ready_additions'][0]['parts'][0]['arrays']) == 5
    assert json.loads((f['output'] / 'repeat_mapping.json').read_text()) == [dict(prefix='dfm13_wave4_test_en__', repeat=2)]
    assert m.verify_assembly(f['output'])['totals'] == result['totals']


def test_all_unready_entries_are_reported(fixture):
    f = fixture; ready = f['entry']
    entries = [ready, dict(name='arena', tokenization_performed=False), dict(name='hendrycks_math_worked'),
               dict(ready, name='dfm13_wave3_pending', status='pending'),
               dict(ready, name='dfm13_wave3_untokenized', tokenization_performed=False),
               dict(ready, name='dfm13_wave3_disabled', repeat=0)]
    write(f['registry'], dict(inherits='dfm12', additions=entries))
    result = run(f)
    assert len(result['unready_additions']) == 5
    assert {r['name'] for r in result['unready_additions']} == {r['name'] for r in entries[1:]}


@pytest.mark.parametrize('field,values', [
    ('inst_start', [1]), ('resp_start', [1]), ('resp_len', [4]),
    ('inst_len', [-1]), ('tokens', [1, 2, 3, 4, 99]), ('resp_start', [2, 3]),
])
def test_bad_arrays_are_not_linked(fixture, field, values):
    f = fixture
    np.save(f['root'] / 'tokenized/part-000000.jsonl' / (field + '.npy'), np.array(values, dtype=np.int64))
    result = run(f)
    assert result['totals']['ready_sources'] == 0
    assert result['unready_additions'][0]['reason'] == 'verification_failed'
    assert not list((f['output'] / 'accepted_inputs').iterdir())


@pytest.mark.parametrize('file,field,value', [
    ('publication.json', 'hf_revision', 'wrong'), ('publication.json', 'rows', 2),
    ('export/manifest.json', 'output_sha256', 'wrong'), ('verified.json', 'tokens', 99),
    ('tokenized/completion.json', 'skipped_rows_this_run', 1),
])
def test_receipt_mismatches_fail_closed(fixture, file, field, value):
    path = fixture['root'] / file; data = json.loads(path.read_text()); data[field] = value; write(path, data)
    assert run(fixture)['totals']['ready_sources'] == 0


def test_source_hash_mismatch(fixture):
    Path(fixture['entry']['output']).write_text('{}\n')
    result = run(fixture)
    assert result['totals']['ready_sources'] == 0
    assert 'Hash mismatch' in result['unready_additions'][0]['detail']


def test_tokenizer_parity_required(fixture):
    path = fixture['root'] / 'verified.json'; receipt = json.loads(path.read_text())
    receipt['pins']['template_sha256'] = 'different'; write(path, receipt)
    assert run(fixture)['totals']['ready_sources'] == 0


def test_target_marker_required_even_when_source_hash_matches(fixture):
    f = fixture; path = Path(f['entry']['output']); row = json.loads(path.read_text()); row['target_message_index'] = 0; write(path, row)
    sha = m.checksum(path)
    for p in (f['registry'], f['root'] / 'publication.json', f['root'] / 'export/manifest.json'):
        data = json.loads(p.read_text()); entry = data['additions'][0] if 'additions' in data else data
        entry['output_sha256'] = sha; write(p, data)
    result = run(f)
    assert 'final target marker' in result['unready_additions'][0]['detail']


def test_no_existing_output_overwrite(fixture):
    run(fixture)
    with pytest.raises(ValueError, match='already exists'):
        run(fixture)


def test_duplicate_names_rejected(fixture):
    f = fixture; write(f['registry'], dict(inherits='dfm12', additions=[f['entry'], f['entry']]))
    with pytest.raises(ValueError, match='Duplicate registry'):
        run(f)


def test_output_cannot_be_inside_base(fixture):
    with pytest.raises(ValueError, match='overlaps'):
        m.assemble(fixture['registry'], fixture['base'], fixture['base'] / 'new')


@pytest.mark.parametrize('parent', ['tokenized', 'export'])
def test_output_cannot_modify_source_trees(fixture, parent):
    with pytest.raises(ValueError, match='overlaps'):
        m.assemble(fixture['registry'], fixture['base'], fixture['root'] / parent / 'new')


@pytest.mark.parametrize('relative', ['repeat_mapping.json', 'tokenized_additions/tokenizer_info.json', 'registry.snapshot.json'])
def test_generated_file_tampering_detected(fixture, relative):
    run(fixture); (fixture['output'] / relative).write_text('{}')
    with pytest.raises(ValueError, match='changed'):
        m.verify_assembly(fixture['output'])


def test_external_array_mutation_detected(fixture):
    run(fixture)
    path = fixture['root'] / 'tokenized/part-000000.jsonl/tokens.npy'
    np.save(path, np.array([5, 4, 3, 2, 1], dtype=np.uint32))
    with pytest.raises(ValueError, match='changed'):
        m.verify_assembly(fixture['output'])


def test_live_registry_can_advance_without_changing_snapshot(fixture):
    run(fixture)
    write(fixture['registry'], dict(inherits='dfm12', additions=[fixture['entry'], {'name': 'new_unrelated'}]))
    assert m.verify_assembly(fixture['output'])['totals']['ready_sources'] == 1


def test_withdrawn_source_blocks_historical_admission(fixture):
    run(fixture)
    write(fixture['registry'], dict(inherits='dfm12', additions=[]))
    with pytest.raises(ValueError, match='withdrawn'):
        m.verify_assembly(fixture['output'])


@pytest.mark.parametrize('field,value', [
    ('output_sha256', 'new-filtered-bytes'), ('hf_revision', 'replacement-commit'),
    ('tokenized_path', '/new/token/root'), ('tokenization_receipt_sha256', 'new-receipt'),
    ('rows', 2), ('subset_policy', 'manual_verified_44'), ('repeat', 3),
])
def test_replaced_source_blocks_before_array_rehash(fixture, monkeypatch, field, value):
    run(fixture)
    entry = dict(fixture['entry'], **{field: value})
    write(fixture['registry'], dict(inherits='dfm12', additions=[entry]))
    original = m.checksum
    def no_array_reads(path):
        assert Path(path).suffix != '.npy', 'Admission must fail before expensive array reads'
        return original(path)
    monkeypatch.setattr(m, 'checksum', no_array_reads)
    with pytest.raises(ValueError, match='superseded in current registry'):
        m.verify_assembly(fixture['output'])


def test_new_registry_hold_blocks_even_unknown_component(fixture):
    run(fixture)
    entry = dict(fixture['entry'], status='quality_hold_source_fidelity')
    write(fixture['registry'], dict(inherits='dfm12', additions=[entry]))
    with pytest.raises(ValueError, match='quality_hold_source_fidelity'):
        m.verify_assembly(fixture['output'])


def test_registry_replacement_during_verification_blocks(fixture, monkeypatch):
    run(fixture)
    original = m.checksum
    def change_while_hashing(path):
        if Path(path).suffix == '.npy':
            write(fixture['registry'], dict(inherits='dfm12', additions=[
                dict(fixture['entry'], hf_revision='new-during-verification')]))
        return original(path)
    monkeypatch.setattr(m, 'checksum', change_while_hashing)
    with pytest.raises(ValueError, match='superseded in current registry'):
        m.verify_assembly(fixture['output'])


def test_base_is_required_on_cli(monkeypatch):
    monkeypatch.setattr('sys.argv', ['assemble', '--output', '/unused'])
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert exc.value.code == 2


def test_direct_cli_native_render_without_pythonpath(fixture):
    import os
    import subprocess
    import sys
    from tokenizers import Tokenizer, models, pre_tokenizers
    f = fixture
    tokenizer = Tokenizer(models.WordLevel({'[UNK]': 0, 'user': 1, 'Q': 2,
        'assistant': 3, 'A': 4, 'end': 5}, unk_token='[UNK]'))
    tokenizer.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    tokenizer.save(str(f['root'] / 'tokenizer.json'))
    (f['root'] / 'template.jinja').write_text(
        "{% for m in messages %}{{ m.role }} {{ m.content }} "
        "{% if m.role == 'assistant' %}end {% endif %}{% endfor %}"
        "{% if add_generation_prompt %}assistant {% endif %}")
    part = f['root'] / 'tokenized/part-000000.jsonl'
    for field, value in dict(inst_len=3, resp_start=3, resp_len=2).items():
        np.save(part / (field + '.npy'), np.array([value], dtype=np.uint32))
    receipt_path = Path(f['entry']['tokenization_receipt'])
    receipt = json.loads(receipt_path.read_text())
    receipt['pins'].update(tokenizer_sha256=m.checksum(f['root'] / 'tokenizer.json'),
        template_sha256=m.checksum(f['root'] / 'template.jinja'))
    write(receipt_path, receipt)
    env = dict(os.environ); env.pop('PYTHONPATH', None)
    result = subprocess.run([sys.executable, str(Path(m.__file__).resolve()),
        '--registry', str(f['registry']), '--base', str(f['base']), '--output', str(f['output'])],
        cwd=f['root'], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((f['output'] / 'assembly.json').read_text())
    assert manifest['totals']['ready_sources'] == 1, manifest['unready_additions']
    assert manifest['ready_additions'][0]['native_token_parity']['rows'][0]['exact_prompt_and_response_tokens']


def test_mutation_during_validation_prevents_publication(fixture, monkeypatch):
    original = m.verify_entry
    def mutate(*args):
        result = original(*args)
        (fixture['base'] / 'epoch_10/inst_len.npy').touch()
        return result
    monkeypatch.setattr(m, 'verify_entry', mutate)
    with pytest.raises(ValueError, match='Base epoch changed'):
        run(fixture)
    assert not fixture['output'].exists()


def test_no_policy_excluded_research_even_under_wave_name(fixture):
    f = fixture; entry = dict(f['entry'], name='dfm13_wave3_repochat')
    write(f['registry'], dict(inherits='dfm12', additions=[entry]))
    result = run(f)
    assert result['unready_additions'][0]['reason'] == 'research_only_source_excluded_by_user_policy'


def test_oversized_target_is_unready(fixture):
    part = fixture['root'] / 'tokenized/part-000000.jsonl'
    np.save(part / 'tokens.npy', np.ones(4097, dtype=np.uint32))
    np.save(part / 'resp_len.npy', np.array([4095], dtype=np.uint32))
    result = run(fixture)
    assert 'Oversize' in result['unready_additions'][0]['detail']


def test_unknown_shard_directory_rejected(fixture):
    (fixture['root'] / 'tokenized/extra').mkdir()
    assert 'Unexpected token shard' in run(fixture)['unready_additions'][0]['detail']


def test_license_provenance_mismatch(fixture):
    f = fixture; registry = json.loads(f['registry'].read_text())
    registry['additions'][0]['license'] = 'cc-by-4.0'; write(f['registry'], registry)
    assert 'Provenance mismatch: license' in run(f)['unready_additions'][0]['detail']
