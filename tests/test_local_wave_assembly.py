import json
from pathlib import Path
import pytest
import numpy as np
from scripts import assemble_dfm13_additions as api
from dfm12.local_wave_assembly import CONTRACT, unready
from test_assemble_dfm13_additions import fixture, write


@pytest.fixture
def local(fixture):
    f = fixture
    e = f['entry']
    e.update(name='dfm13_wave4_opus_en_sk', repeat=1, status='accepted_local_tokenized',
             uploaded=False, hf_revision=None, publication_contract=CONTRACT)
    source = Path(e['output'])
    row = json.loads(source.read_text())
    row.update(quality_status='accepted', audit=dict(keep=True, reason='verified',
               language_quality=5, coherence=5, usefulness=5))
    source.write_text(json.dumps(row)+'\n'+json.dumps(row)+'\n')
    e.update(rows=2, rendered_tokens=10, tokenized_rows=2, tokenized_tokens=10)
    tokenroot = Path(e['tokenized_path'])
    values = dict(tokens=[1,2,3,4,5,1,2,3,4,5], inst_start=[0,5], inst_len=[2,2],
                  resp_start=[2,7], resp_len=[3,3])
    for key, value in values.items():
        np.save(tokenroot/'part-000000.jsonl'/(key+'.npy'), np.array(value, dtype=np.uint32))
    write(tokenroot/'completion.json', dict(rows=2, files=1, skipped_rows_this_run=0, max_seq_len=4096))
    e['output_sha256'] = api.checksum(source)
    root = f['root']/'selection'
    selected = root/'accepted.jsonl'; write(selected, {})
    freeze = root/'combined-audit-manifest.json'; write(freeze, {})
    report = root/'report.json'; write(report, {})
    budget = root/'translations/token-budgets.json'
    write(budget, dict(source_report=str(report), source_report_sha256=api.checksum(report)))
    selection = root/'translation-release/en-sk/receipt.json'
    write(selection, dict(ready=True, pending_components=[], sha256=api.checksum(selected),
        path=str(selected), selected_pairs=1, combined_rendered_tokens=10, token_cap=10,
        audit_manifest_sha256=api.checksum(freeze), budget_receipt_sha256=api.checksum(budget)))
    e.update(selection_sha256=api.checksum(selected), selection_receipt=str(selection),
             selection_receipt_sha256=api.checksum(selection), attribution_files={})
    export = source.parent.parent/'manifest.json'
    write(export, e)
    e['export_manifest_sha256'] = api.checksum(export)
    receipt = Path(e['tokenization_receipt']); token = json.loads(receipt.read_text())
    token.update(rows=2, tokens=10)
    token['pins'].update(source_sha256=e['output_sha256'], export_manifest_sha256=e['export_manifest_sha256'],
                         selection_sha256=e['selection_sha256'])
    write(receipt, token)
    write(f['registry'], dict(inherits='dfm12', additions=[e]))
    return f


def test_native_local_assembly_preserves_pending(local):
    result = api.assemble(local['registry'], local['base'], local['output'])
    assert result['totals']['ready_sources'] == 1, result['unready_additions']
    source = result['ready_additions'][0]
    assert source['publication_pending'] and source['uploaded'] is False
    assert source['hf_revision'] is None
    api.verify_assembly(local['output'])


def test_local_drift_rejected(local):
    Path(local['entry']['selection_receipt']).write_text('{}')
    result = api.assemble(local['registry'], local['base'], local['output'])
    assert result['totals']['ready_sources'] == 0


def test_no_implicit_local_bypass():
    e = dict(name='dfm13_wave4_opus_en_sk', status='accepted_local_tokenized', uploaded=False)
    assert api.unready_reason(e) == 'not_accepted_uploaded_with_revision'
    e.update(publication_contract=CONTRACT, uploaded=True)
    assert unready(e) == 'invalid_local_publication_state'


def test_local_mask_violation_rejected(local):
    part = Path(local['entry']['tokenized_path'])/'part-000000.jsonl'
    np.save(part/'resp_start.npy', np.array([1,7], dtype=np.uint32))
    result = api.assemble(local['registry'], local['base'], local['output'])
    assert result['totals']['ready_sources'] == 0
    assert 'Noncontiguous' in result['unready_additions'][0]['detail']


def test_local_native_mismatch_rejected(local):
    part = Path(local['entry']['tokenized_path'])/'part-000000.jsonl'
    np.save(part/'tokens.npy', np.array([9,2,3,4,5,1,2,3,4,5], dtype=np.uint32))
    result = api.assemble(local['registry'], local['base'], local['output'])
    assert result['totals']['ready_sources'] == 0
    assert 'parity mismatch' in result['unready_additions'][0]['detail']
