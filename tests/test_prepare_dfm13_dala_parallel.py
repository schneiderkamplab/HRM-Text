import gzip
import json
from pathlib import Path
import pytest
from dfm12.io import write_json,file_hash
from dfm12.dala_compact_assembly import prepare as serial
from scripts.prepare_dfm13_dala_parallel import prepare


def source(root):
    root.mkdir()
    shard=root/'rows.jsonl.gz'
    with gzip.open(shard,'wt') as f:
        f.write(json.dumps({'split':'train','view':'representative','text':'native'})+'\n')
    receipt=root/'export.json'
    write_json(receipt,{'files':[dict(path=str(shard),relative='train/acceptability/part.gz',sha256=file_hash(shard))]})
    registry=root/'registry.json'
    entries=[dict(name='source'+str(i),task='acceptability',rows=1,tokens=4,
                  export_receipt=dict(path=str(receipt),sha256=file_hash(receipt))) for i in range(2)]
    write_json(registry,{'additions':entries})
    write_json(root/'complete.json',dict(success=True,registry=dict(path=str(registry),sha256=file_hash(registry))))


def test_parallel_matches_serial_and_retains_existing(tmp_path):
    finalized=tmp_path/'source';source(finalized)
    old=serial(finalized,tmp_path/'views')
    stats={e['name']:Path(e['output']).stat().st_ino for e in old}
    new=prepare(finalized,tmp_path/'views',workers=2)
    assert old==new
    assert stats=={e['name']:Path(e['output']).stat().st_ino for e in new}


def test_changed_existing_view_rejected(tmp_path):
    finalized=tmp_path/'source';source(finalized)
    entries=serial(finalized,tmp_path/'views')
    Path(entries[0]['output']).write_text('wrong\n')
    with pytest.raises(ValueError,match='differs'):prepare(finalized,tmp_path/'views',workers=2)
