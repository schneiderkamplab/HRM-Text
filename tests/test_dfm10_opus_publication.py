import json
from pathlib import Path
import pytest
from scripts import publish_dfm10_opus_rebuild as pub
from scripts.acquire_dfm10_hf import sha


def fixture(work, monkeypatch):
    monkeypatch.setattr(pub,'ROOT',work)
    (work/'payloads').mkdir()
    tasks=[]
    for n in range(64):
        name=f'opus__{n}.parquet'
        (work/'payloads'/name).write_bytes(b'fixture')
        tasks.append({'component':'opus_da_en_repaired','task':name,'source':f'payloads/{name}',
                      'hf_provenance':{'repo_id':'schneiderkamplab/dfm10-opus-da-en-repaired'}})
    (work/'hf_recipe.json').write_text(json.dumps({'recipe':'dfm10-hf-v2','tasks':tasks}))
    (work/'inputs-verified.json').write_text(json.dumps({'config_sha256':sha(work/'hf_recipe.json')}))
    (work/'all-token-comparison.json').write_text(json.dumps({'status':'matched','tasks':4351}))


def test_publication_gate_requires_exact_result(tmp_path, monkeypatch):
    fixture(tmp_path,monkeypatch)
    assert len(pub.verified_inputs(tmp_path)[1])==64
    (tmp_path/'all-token-comparison.json').write_text('{"status":"mismatch","tasks":4351}')
    with pytest.raises(ValueError):pub.verified_inputs(tmp_path)


def test_publication_rejects_changed_recipe(tmp_path,monkeypatch):
    fixture(tmp_path,monkeypatch)
    with (tmp_path/'hf_recipe.json').open('a') as f:f.write(' ')
    with pytest.raises(ValueError):pub.verified_inputs(tmp_path)


def test_wait_does_not_contact_hf_before_verification(tmp_path,monkeypatch):
    monkeypatch.setattr(pub,'WORK',tmp_path)
    def forbidden():pytest.fail('HF publication attempted before verification')
    monkeypatch.setattr(pub,'HfApi',forbidden)
    class EndWait(BaseException):pass
    def stop(seconds):raise EndWait()
    monkeypatch.setattr(pub.time,'sleep',stop)
    with pytest.raises(EndWait):pub.run(True)
    assert json.loads((tmp_path/'opus-publication-status.json').read_text())['status']=='waiting'
