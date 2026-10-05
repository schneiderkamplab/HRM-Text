import json
import sqlite3

import pytest
import yaml

from scripts.prepare_dfm13_baltic import messages, local_sources
from dfm12.io import file_hash
from dfm12 import baltic_synthetic_specs as specs
from dfm12 import european_synthetic_specs as european
from dfm12 import baltic_synthetic_campaign as campaign


def test_targets_and_isolation():
    config = yaml.safe_load(campaign.CONFIG.read_text())
    quotas = campaign.quotas(config)
    assert len(quotas) == 12
    assert sum(q['accepted_target'] for q in quotas) == 140000
    assert all('/dfm13-' in q['repo_id'] for q in quotas)
    assert 'lt' not in european.LANGUAGES
    assert 'lv' not in european.LANGUAGES
    assert campaign.controller().v6.LANGUAGES == specs.LANGUAGES


@pytest.mark.parametrize('language', ['lt','lv'])
@pytest.mark.parametrize('family', list(european.FAMILIES))
def test_native_spec_contract(language, family):
    seeds = {k:[dict(id='sample',text='A source document.',messages=[])] for k in ('lt','lv','openhermes')}
    spec = specs.spec_for(language, family, 0, 0, seeds,
        dict(contract_version=4,cohort='test-baltic',quotas={'openhermes':1}))
    assert spec['language_code'] == language
    assert spec['language'] == specs.LANGUAGES[language]
    assert spec['family'] == family


def test_keep_all_source_documents_and_leave_origin_untouched(tmp_path):
    original = tmp_path/'original.jsonl'
    original.write_text(json.dumps(dict(source_document_id='test-article',text='A text.',split='test'))+'\n')
    sha = file_hash(original)
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'sources':[dict(name='Wikipedia_lt',path=str(original),sha256=sha)]}))
    result = local_sources(tmp_path/'prepared',{'local_source_manifests':[str(manifest)]})
    assert result[0]['rows'] == 1
    assert result[0]['dala_source_holdouts_included']
    assert file_hash(original) == sha == file_hash(result[0]['path'])


def test_candidates_keep_multiturn_and_filter_aya_language():
    turns = [dict(role=role,content='Text') for role in ['user','assistant','user','assistant']]
    assert messages({'messages':turns},'chat') == turns
    assert messages({'language_code':'lav'},'aya') is None
    with pytest.raises(ValueError):
        messages({'messages':turns[:-1]},'chat')


def test_prepare_and_verify_ledger(tmp_path, monkeypatch):
    seeds = tmp_path/'seeds'
    seeds.mkdir()
    db = seeds/'seeds.sqlite'
    sqlite3.connect(db).close()
    (seeds/'receipt.json').write_text(json.dumps(dict(ready=True,sha256=file_hash(db))))
    monkeypatch.setattr(campaign.european,'_asset_paths',lambda _:[])
    root = tmp_path/'campaign'
    manifest = campaign.prepare(root,seeds,tmp_path)
    assert manifest['target'] == 140000
    assert campaign.verify(root)['groups'] == 12
    with sqlite3.connect(root/'jobs.sqlite') as connection:
        assert connection.execute('SELECT sum(target),sum(accepted),sum(active) FROM groups').fetchone() == (140000,0,0)
