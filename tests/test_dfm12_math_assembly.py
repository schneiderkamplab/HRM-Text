import json
from pathlib import Path

import pytest

from dfm12 import math_assembly as m
from scripts import assemble_dfm13_additions as a
from test_assemble_dfm13_additions import fixture, write


@pytest.fixture
def math_fixture(fixture, monkeypatch):
    f = fixture; base = f['root']; source = Path(f['entry']['output'])
    raw = base / 'raw'
    raw.mkdir()
    for name in ('train.parquet', 'test.parquet', 'README.md'):
        (raw / name).write_text(name)
    metadata = source.parent / 'metadata'
    metadata.mkdir()
    (metadata / 'screening.jsonl').write_text('')
    record = dict(id='math-0', messages=[dict(role='user', content='Q'), dict(role='assistant', content='A')],
        target_message_index=1, chat_template_kwargs={'enable_thinking': False},
        metadata=dict(source=m.REPO, revision=m.REVISION, split='train', config='algebra',
            source_file='algebra/train.parquet', source_file_sha256=a.checksum(raw / 'train.parquet'),
            source_row_index=0))
    write(source, record)
    root = base / 'tokenized'
    (root / 'part-000000.jsonl').rename(root / m.PART)
    write(root / 'completion.json', dict(rows=1, files=1, skipped_rows_this_run=0, max_seq_len=None))
    info = json.loads((root / 'tokenizer_info.json').read_text())
    manifest = dict(schema='dfm13-math-worked-v1', name=m.NAME, repo_id=m.REPO, revision=m.REVISION,
        license='mit', rows=1, hard_truncation=False, test_rows_in_output=0,
        train_sha256=a.checksum(source), screening_sha256=a.checksum(metadata / 'screening.jsonl'),
        license_evidence=dict(path=str(raw / 'README.md'), sha256=a.checksum(raw / 'README.md')),
        source_files=[dict(config='algebra',split=s,path=str(raw / (s+'.parquet')),
                           sha256=a.checksum(raw / (s+'.parquet')),rows=1) for s in ('train','test')],
        pins={str(Path(info[k]).resolve()): a.checksum(Path(info[k])) for k in ('tokenizer_path','chat_template_path')},
        repeat=1, corpus_overlap='Historical repeat 1; share problems intentionally with RLVR',
        overlap_policy='exact and whitespace train/test screening', exclusions={})
    write(metadata / 'manifest.json', manifest)
    receipt = dict(rows=1,tokens=5,prompt_tokens=2,target_tokens=3,max_sequence_tokens=5,
        sequences_over_4096=0,hard_truncation=False,regex_fix=False,output=str(root),
        converted_manifest_sha256=a.checksum(metadata/'manifest.json'),
        files={str(p):a.checksum(p) for p in root.rglob('*') if p.is_file()})
    write(metadata / 'tokenization-receipt.json', receipt)
    monkeypatch.setattr(m,'MANIFEST_SHA',a.checksum(metadata/'manifest.json'))
    monkeypatch.setattr(m,'RECEIPT_SHA',a.checksum(metadata/'tokenization-receipt.json'))
    monkeypatch.setattr(m,'ROWS',1); monkeypatch.setattr(m,'TOKENS',5)
    entry=dict(name=m.NAME,repo_id=m.REPO,revision=m.REVISION,license='mit',split='train',configs=['algebra'],
        rows=1,tokens=5,repeat=5,hard_truncation=False,output=str(source),output_sha256=a.checksum(source),
        target_policy='worked_solution_single_assistant_target',manifest=str(metadata/'manifest.json'),
        manifest_sha256=m.MANIFEST_SHA,tokenization_receipt=str(metadata/'tokenization-receipt.json'),
        tokenization_receipt_sha256=m.RECEIPT_SHA,tokenized_output=str(root),
        corpus_overlap='Not whole-corpus deduplicated; share problems intentionally with RLVR; repeat 5')
    f['entry']=entry
    write(f['registry'],dict(inherits='dfm12',additions=[entry]))
    return f


def verify(f):
    pins={}
    info=json.loads((f['base']/'metadata.json').read_text())['tokenizer_info']
    return a.verify_entry(f['entry'],a.token_contract(info,pins),pins)


def test_existing_arrays_and_repeat_preserved(math_fixture):
    f=math_fixture
    before={str(p):a.checksum(p) for p in Path(f['entry']['tokenized_output']).rglob('*') if p.is_file()}
    result=verify(f)
    assert (result['rows'],result['tokens'],result['repeat'])==(1,5,5)
    assert result['conversion_repeat']==1
    assert result['screening']['whole_corpus_deduplicated'] is False
    assert 'share problems intentionally' in result['corpus_overlap']
    assert before=={str(p):a.checksum(p) for p in Path(f['entry']['tokenized_output']).rglob('*') if p.is_file()}


def test_dispatch_and_manifest_conditions(math_fixture):
    f=math_fixture
    assert a.unready_reason(f['entry']) is None
    result=a.assemble(f['registry'],f['base'],f['output'])
    assert result['totals']['ready_sources']==1
    assert result['ready_additions'][0]['repeat']==5
    assert result['ready_additions'][0]['corpus_overlap']==f['entry']['corpus_overlap']
    assert json.loads((f['output']/'repeat_mapping.json').read_text())[0]['repeat']==5


@pytest.mark.parametrize('field,value',[('repeat',1),('repeat',True),('split','test'),
    ('revision','wrong'),('hard_truncation',True),('tokens',6),('corpus_overlap','deduplicated'),
    ('manifest_sha256','wrong'),('tokenization_receipt_sha256','wrong')])
def test_contract_drift_rejected(math_fixture,field,value):
    math_fixture['entry'][field]=value
    with pytest.raises(ValueError): verify(math_fixture)


def test_array_drift_rejected(math_fixture):
    p=Path(math_fixture['entry']['tokenized_output'])/m.PART/'tokens.npy'
    with p.open('ab') as out: out.write(b'drift')
    with pytest.raises(ValueError,match='Hash mismatch'): verify(math_fixture)


def test_native_mismatch_rejected(math_fixture,monkeypatch):
    monkeypatch.setattr(a,'native_encoder',lambda info:lambda row,final_only=True:[([9,2],[3,4,5])])
    with pytest.raises(ValueError,match='parity mismatch'): verify(math_fixture)


def test_unknown_nonwave_stays_excluded():
    assert a.unready_reason(dict(name='not_math')).startswith('unsupported_non_wave')
