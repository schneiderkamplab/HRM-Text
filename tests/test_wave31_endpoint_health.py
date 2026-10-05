import io
import json
from pathlib import Path
import pytest
from dfm12 import wave31_endpoint_health as m


def document(root='/snapshot', **kwargs):
    return {'data': [dict(id=m.MODEL, root=root, max_model_len=32768, **kwargs)]}


@pytest.mark.parametrize('field,value', [('id','old'), ('root','/other'), ('root',''),
    ('root','relative'), ('max_model_len', True), ('max_model_len','32768'),
    ('max_model_len',8192)])
def test_mismatch(field,value):
    doc=document();doc['data'][0][field]=value
    with pytest.raises(ValueError):m.validate(doc, '/snapshot')


def test_exact_and_symlink(tmp_path):
    target=tmp_path/'snapshot';target.mkdir()
    alias=tmp_path/'alias';alias.symlink_to(target)
    assert m.validate(document(str(alias)),target)
    with pytest.raises(ValueError):m.validate({'data':document()['data']*2},'/snapshot')


@pytest.mark.parametrize('valid', [True, False])
def test_gate_before_command(tmp_path,monkeypatch,valid):
    ready=tmp_path/'ready.json';receipt=tmp_path/'health.json'
    ready.write_text(json.dumps(dict(model=m.MODEL,all_files_verified=True,snapshot='/snapshot')))
    doc=document('/snapshot' if valid else '/other')
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda *a,**k:io.StringIO(json.dumps(doc)))
    calls=[]
    monkeypatch.setattr(m.subprocess,'run',lambda cmd,**kw:calls.append(cmd))
    monkeypatch.setattr('sys.argv',['gate','--endpoint','http://mock/v1','--ready',str(ready),
        '--receipt',str(receipt),'--','python','consumer.py'])
    if valid:
        m.main();assert calls==[['python','consumer.py']];assert receipt.exists()
    else:
        with pytest.raises(ValueError):m.main()
        assert not calls and not receipt.exists()
