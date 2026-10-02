import json
import gzip
import pytest
from dfm12.export_european import Package
from dfm12.export_validator import validate,validate_language


def test_native_and_reverse_are_preserved(tmp_path):
    p=Package(tmp_path,'opus-fi-et',[])
    record=dict(id='one',component='opus-fi-et',language='fi',reverse_language='et',task='translation',
        messages=[dict(role='user',content='Translate'),dict(role='assistant',content='Answer')],
        reverse_messages=[dict(role='user',content='Reverse'),dict(role='assistant',content='Answer')],
        provenance=dict(repo='example/source',license='cc-by-4.0'))
    audit=dict(keep=True,language_quality=5,coherence=5,usefulness=5,reason='Good')
    p.add(('job',json.dumps(dict(record=record)),'done',json.dumps(audit),1,None))
    record['id']='two';audit['keep']=False
    p.add(('job2',json.dumps(dict(record=record)),'done',json.dumps(audit),1,None))
    result=p.finish()
    assert result['rows']==2 and result['accepted_records']==1
    assert validate(p.destination)['valid']
    with gzip.open(p.destination/'data/train-00000.jsonl.gz','rt') as f:rows=[json.loads(x) for x in f]
    assert {r['language'] for r in rows}=={'fi','et'}
    assert all('audit' not in r and 'provenance' not in r for r in rows)


def test_original_language_gate_unchanged():
    with pytest.raises(ValueError):validate_language({'language':'fi'})
    validate_language({'language':'fi'},european=True)
    with pytest.raises(ValueError):validate_language({'language':'unknown'},european=True)
