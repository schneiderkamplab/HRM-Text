from types import SimpleNamespace
import pytest
from dfm12.io import load, write_json
from scripts import upload_dfm13_ready150 as uploader


@pytest.mark.parametrize('expected',[2,150])
def test_publisher_uses_sealed_queue_count(tmp_path,monkeypatch,expected):
    import huggingface_hub
    monkeypatch.setattr(huggingface_hub,'HfApi',lambda:SimpleNamespace(whoami=lambda:None))
    queue={'expected':expected,'packages':[{'repo':f'schneiderkamplab/test-{i}'} for i in range(expected)]}
    write_json(tmp_path/'queue.json',queue)
    write_json(tmp_path/'publication-receipts.json',{
        p['repo']:{'status':'verified'} for p in queue['packages']})
    monkeypatch.setattr(uploader,'freeze',lambda root:queue)
    uploader.publish(tmp_path)
    completion=load(tmp_path/'completion.json')
    assert completion['complete'] and completion['expected']==completion['verified']==expected
