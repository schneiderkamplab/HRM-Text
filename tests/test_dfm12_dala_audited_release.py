import json
from pathlib import Path
import pytest
from dfm12.dala_audited_release import prepare_language,validate_additions
from dfm12.io import file_hash,write_json
import hf_package_runtime as runtime
import sqlite3
from dfm12.scandi_overlap import text_hash


def test_train_only_shared_screen_and_controls(tmp_path):
    package=tmp_path/'package';(package/'metadata').mkdir(parents=True);(package/'provenance').mkdir()
    config=dict(prompts={'acceptability':'Is this German sentence correct?','correction':'Correct this German sentence.'},sample_source_judgments={})
    write_json(package/'metadata/config.json',config);write_json(package/'metadata/validation.json',{'status':'passed'})
    pairs=[]
    for i,text in enumerate(('Das Kind spielt.','Der Hund spielt.')):
        pairs.append(dict(language='de',split='train',pair_id=str(i),document_id=str(i),document_sha256=str(i),original=text,corrupted=text.replace('spielt','spielen'),edits=[dict(corruption_type='agreement')],source_name='test',url='test',license='CC0',quality_status='automated_pair_audit_pass',audit={'result':dict(decision='pass',original_correct='yes',corrupted_incorrect='yes',edit_is_grammar_or_spelling='yes',meaning_preserved='yes')}))
    path=package/'provenance/train.pairs.jsonl.gz'
    with runtime.compressed_writer(path) as f:
        for row in pairs:f.write(runtime.encode(row))
    write_json(package/'metadata/manifest.json',{'files':{'provenance/train.pairs.jsonl.gz':{'sha256':file_hash(path)}}})
    held=tmp_path/'held.sqlite';c=sqlite3.connect(held);c.executescript('CREATE TABLE held(hash TEXT PRIMARY KEY);CREATE TABLE documents(hash TEXT PRIMARY KEY);');c.execute('INSERT INTO held VALUES (?)',(text_hash(pairs[1]['original']),));c.commit();c.close()
    ref=tmp_path/'ref.sqlite';c=sqlite3.connect(ref);c.executescript('CREATE TABLE files(path TEXT,sha256 TEXT);CREATE TABLE fingerprints(kind TEXT,hash TEXT);');c.close();write_json(tmp_path/'refs.json',{'files':[]})
    result=prepare_language(('de',str(package),str(tmp_path/'output'),str(held),str(ref),str(tmp_path/'refs.json')))
    assert result['counts']['retained_pairs']==1
    assert result['counts']['excluded:heldout_sentence']==1
    for comp in result['components']:
        rows=list(runtime.read_gzip(comp['data_files'][0]['path']))
        assert len(rows)==2 and all('audit_context' not in r for r in rows)
        assert all('Der Hund' not in r['messages'][0]['content'] for r in rows)
        if comp['task']=='acceptability':assert [r['messages'][1]['content'] for r in rows]==['yes','no']
        else:assert [r['messages'][1]['content'] for r in rows]==['Das Kind spielt.']*2


def test_incomplete_not_admitted(tmp_path):
    p=tmp_path/'integration.json';write_json(p,{'status':'preparing'})
    with pytest.raises(ValueError,match='incomplete'):validate_additions(p)
