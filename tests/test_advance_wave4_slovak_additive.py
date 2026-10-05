import json
import sqlite3
import pytest
from pathlib import Path
from dfm12.io import write_json,file_hash
from scripts.advance_wave4_slovak_additive import route_pair,select_pair,publication_guard


def test_routes():
    assert route_pair('sk-additive-v1-pivot-be-sk')==('pivot','be-sk')
    assert route_pair('institutional-en-sk-part2')==('institutional','en-sk')


def test_old_new_share_one_cap_and_dedup(tmp_path,monkeypatch):
    from dfm12 import wave_repair
    monkeypatch.setattr(wave_repair,'process',lambda *args:None)
    root=tmp_path/'add';base=tmp_path/'base';source=tmp_path/'budget-source';source.write_text('pinned')
    write_json(root/'translations/token-budgets.json',dict(source_report=str(source),source_report_sha256=file_hash(source),english_pair_cap=150,other_pair_cap=150))
    manifest=root/'manifest.json';write_json(manifest,{})
    entries=[]
    review=dict(keep=True,language_quality=5,coherence=5,usefulness=5,reason='fixture')
    for name,route in [('direct-en-sk','direct'),('sk-additive-v1-pivot-en-sk','pivot')]:
        entries.append(dict(component=name,route=route,sha256='pinned'))
        write_json(base/'audit-ready'/name/'receipt.json',{'sha256':'pinned'})
        folder=base/'release'/name;write_json(folder/'status.json',dict(export_ready=True,input_sha256='pinned'))
        with sqlite3.connect(folder/'ledger.sqlite') as db:
            db.execute('CREATE TABLE rows(id TEXT,record TEXT,review TEXT,status TEXT)')
            for n in range(2):
                row=dict(task='translation',language='sk',reverse_language='en',rendered_tokens=100,
                    messages=[dict(role='user',content='translate'),dict(role='assistant',content='slovak'+str(n))],
                    reverse_messages=[dict(role='user',content='translate'),dict(role='assistant',content='english'+str(n))])
                db.execute('INSERT INTO rows VALUES(?,?,?,?)',(str(n),json.dumps(row),json.dumps(review),'accepted'))
    result=select_pair(root,base,'en-sk',entries,manifest)
    assert result['ready'] and result['selected_pairs']==1 and result['combined_rendered_tokens']==100
    selected=json.loads(Path(result['path']).read_text())
    assert selected['component']=='direct-en-sk'


@pytest.mark.parametrize('conflict',['none','main_rows','main_selection','export','registry','additive_in_main'])
def test_publication_guard(tmp_path,monkeypatch,conflict):
    monkeypatch.chdir(tmp_path)
    root=tmp_path/'add';base=tmp_path/'base'
    write_json(base/'parallel-preparation.json',{'complete':True})
    entries=[]
    if conflict=='main_rows':
        entries=[dict(component='direct-en-sk',sha256='pinned')]
        write_json(base/'audit-ready/direct-en-sk/receipt.json',dict(sha256='pinned',counts={'ready':1}))
    if conflict=='additive_in_main':entries=[dict(component='sk-additive-v1-direct-en-sk',sha256='pinned')]
    write_json(base/'audit/translation-manifest.json',dict(components=entries,
        preparation_sha256=file_hash(base/'parallel-preparation.json')))
    if conflict=='main_selection':write_json(base/'translation-release/en-sk/receipt.json',dict(ready=True,selected_pairs=1))
    if conflict=='export':Path('exports_dfm13/dfm13-wave4-opus-en-sk').mkdir(parents=True)
    if conflict=='registry':write_json(Path('config/dfm13_sources.json'),dict(additions=[{'name':'dfm13_wave4_opus_en_sk'}]))
    if conflict=='none':
        publication_guard(root,base,'en-sk')
        assert (root/'translation-release/en-sk/publication-ownership.json').exists()
    else:
        with pytest.raises(ValueError):publication_guard(root,base,'en-sk')
