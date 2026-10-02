import gzip
import json
import sqlite3

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dfm12 import european_synthetic_seeds as seeds
from dfm12.io import load, write_json


def fixture(tmp_path):
    root, oh = tmp_path/'sources', tmp_path/'dfm8-openhermes-en'
    inventory = {}
    for lang in seeds.LANGUAGES:
        name = 'text-'+lang
        path = root/'downloads'/name/'train.parquet'
        path.parent.mkdir(parents=True)
        records = [dict(id=str(i), text=('Document '+str(i)+' '+lang+' has a distinct factual sentence. ')*30,
            url='https://example.test/'+lang+'/'+str(i), **{'pt.auto':True, 'pt.pt.auto':True,
            'pt.mean.confidence.auto':.95, 'pt.pt.mean.confidence.auto':.95,
            'dc.rights.uri':'https://creativecommons.org/licenses/by/4.0/'}) for i in range(4)]
        pq.write_table(pa.Table.from_pylist(records), path, row_group_size=2)
        inventory[name] = dict(repo='amalia-llm/CorEGe-PT' if lang=='pt_pt' else 'wikimedia/wikipedia',
            language=lang, kind='documents', revision='fixed-revision', files=['train.parquet'],
            status='review' if lang=='pt_pt' else 'ready')
        if lang=='pt_pt':
            write_json(root/'approvals'/f'{name}.json', dict(revision='fixed-revision', files=['train.parquet'],
                evidence='fixture reviewed rights/variant filter', document_filter='corege_pt'))
    write_json(root/'sources.lock.json', dict(sources=inventory))
    (oh/'data').mkdir(parents=True)
    (oh/'README.md').write_text('DFM8 repaired OpenHermes dataset.')
    with gzip.open(oh/'data/train-00000.jsonl.gz', 'wt') as handle:
        for i in range(4):
            handle.write(json.dumps(dict(language='en',source='dfm8_openhermes_en',row_id=str(i),
                messages=[dict(role='user',content=f'Explain topic {i}.'),
                          dict(role='assistant',content=f'Topic {i} has a short example.')]))+'\n')
    return root, oh


def test_incremental_resume_and_language_view(tmp_path):
    source, oh = fixture(tmp_path)
    root = tmp_path/'seeds'
    result = seeds.prepare(root, source, oh, native_target=2, oh_target=2, batch_size=1, max_rows=5)
    assert result['state']['phase']=='paused_at_scan_bound'
    result = seeds.prepare(root, source, oh, native_target=2, oh_target=2, batch_size=1)
    assert result['counts']=={**dict.fromkeys(seeds.LANGUAGES,2),'openhermes':2}
    with sqlite3.connect(root/'seeds.sqlite') as db:
        assert db.execute('SELECT count(*) FROM languages').fetchone()[0]==12
        assert db.execute("SELECT count(*) FROM available_seeds WHERE pool='openhermes'").fetchone()[0]==24
    again = seeds.prepare(root, source, oh, native_target=2, oh_target=2, batch_size=1)
    assert again['counts']==result['counts']
    assert not again['generation_launched']


def test_provider_contract_without_modifying_production_files(tmp_path, monkeypatch):
    from dfm12 import multilingual_seeds
    from dfm12.multilingual_production_specs import SourceProvider, SeedUnavailable
    source, oh = fixture(tmp_path)
    root = tmp_path/'seeds'
    seeds.prepare(root, source, oh, native_target=1, oh_target=1, batch_size=1)
    for lang,name in seeds.LANGUAGES.items():
        monkeypatch.setitem(multilingual_seeds.LANGUAGES,lang,name)
    provider = SourceProvider(root,tmp_path/'generation',{'campaign':'fixture'})
    try:
        spec = provider.next_spec('de','grounded-instruct',0)
        assert spec['source']['document_url'].startswith('https://')
        assert provider.next_spec('de','grounded-instruct',0)==spec
        with pytest.raises(SeedUnavailable):
            provider.next_spec('de','summary-rewrite',1)
        english = provider.next_spec('pt_pt','openhermes',0)
        assert english['source']['language']=='en'
        assert provider.next_spec('fr','openhermes',0)['source']['id']==english['source']['id']
    finally:
        provider.close()


def test_input_drift_rejected(tmp_path):
    source, oh = fixture(tmp_path)
    root = tmp_path/'seeds'
    seeds.prepare(root,source,oh,native_target=1,oh_target=1,batch_size=1)
    (oh/'README.md').write_text('changed source notice')
    with pytest.raises(ValueError,match='Pinned source changed'):
        seeds.prepare(root,source,oh,native_target=1,oh_target=1,batch_size=1)


def test_portuguese_fails_closed_and_offsets_are_real():
    source = dict(repo='amalia-llm/CorEGe-PT',revision='fixed',review_receipt={'document_filter':'corege_pt'})
    row = dict(id='one',text='A substantial source sentence ends here. '*40,
        **{'pt.auto':True,'pt.pt.auto':True,'pt.mean.confidence.auto':.95,
           'pt.pt.mean.confidence.auto':.95,'dc.rights.uri':'https://creativecommons.org/licenses/by/4.0/'})
    payload, reason = seeds.native_payload(row,source,'pt_pt','train.parquet',0,0,'sha',42)
    assert reason is None
    assert row['text'][payload['offset']:payload['offset']+len(payload['text'])]==payload['text']
    assert not payload['paragraph_boundaries_claimed']
    for change in ({'pt.pt.auto':False},{'pt.pt.mean.confidence.auto':.5},
                   {'dc.rights.uri':'https://creativecommons.org/licenses/by-nd/4.0/'}):
        assert seeds.native_payload(dict(row,**change),source,'pt_pt','train.parquet',0,0,'sha',42)[0] is None


def test_oh_english_only_and_no_truncation():
    row = dict(language='en',source='dfm8_openhermes_en',messages=[
        dict(role='user',content='Question?'),dict(role='assistant',content='Answer.')])
    payload, _ = seeds.oh_payload(row,'source',0,'sha')
    assert payload['messages']==row['messages']
    assert seeds.oh_payload(dict(row,language='da'),'source',0,'sha')[0] is None
    row['messages'][1]['content']='a'*2401
    assert seeds.oh_payload(row,'source',0,'sha')[0] is None


def test_shortfall_is_not_filled_by_repeated_sources(tmp_path):
    source, oh = fixture(tmp_path)
    result = seeds.prepare(tmp_path/'seeds',source,oh,native_target=10,oh_target=10,batch_size=2)
    assert result['state']['phase']=='complete_with_reported_shortfalls'
    assert result['counts']['openhermes']==4
    assert result['state']['openhermes']['shortfall']==6
