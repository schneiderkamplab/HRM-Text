import copy
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dfm12 import multilingual_production_seeds as seeds
from dfm12.io import digest


@pytest.fixture
def db(tmp_path):
    connection = seeds.connect(tmp_path)
    yield connection
    connection.close()


def conversation(pairs=1):
    return {'messages': [m for _ in range(pairs) for m in
        ({'role': 'user', 'content': 'Please explain the supplied example.'},
         {'role': 'assistant', 'content': 'This is a complete answer to the example.'})]}


def test_exact_public_schema_and_one_based_no_holes(db):
    assert [r[1] for r in db.execute('PRAGMA table_info(seeds)')] == ['pool','seq','source_id','payload']
    for key in ('one','one','two'):
        seeds.insert(db, 'nb', {'id':key, 'text':key}, key, key)
    assert db.execute('SELECT seq,source_id FROM seeds ORDER BY seq').fetchall() == [(1,'one'),(2,'two')]


def test_native_global_document_and_oh_conservative_exclusion(db):
    source = dict(id='old-window', repo='native-repo', source_id='doc-1', file='a.parquet',
                  row_group=0, row_in_group=1)
    seeds.exclude(db, dict(language_code='nb', family='grounded-instruct', source=source))
    new_window = dict(source, id='different-window', text='New part of the same document.')
    assert not seeds.insert(db, 'nn', new_window, seeds.doc_keys(source)[0], 'new-hash')
    seeds.exclude(db, dict(language_code='nb', family='openhermes', source={'id':'used-oh'}))
    assert not seeds.insert(db, 'openhermes', {'id':'used-oh'}, 'used-oh','used-oh')
    assert seeds.insert(db, 'openhermes', {'id':'new-oh'}, 'new-oh','new-oh')
    assert db.execute("SELECT count(*) FROM available_seeds WHERE pool='openhermes'").fetchone()[0] == 7


@pytest.mark.parametrize('pairs', [1,2,3,4,5,6])
def test_oh_complete_pairs_no_mutation(pairs):
    row = conversation(pairs)
    before = copy.deepcopy(row)
    assert seeds.eligible_openhermes(row) == row['messages']
    assert row == before


@pytest.mark.parametrize('mutation', ['odd','seven','roles','system','tools','extra','user901','assistant2401','total','empty'])
def test_oh_rejects_without_truncating(mutation):
    row = conversation()
    if mutation == 'odd': row['messages'].pop()
    if mutation == 'seven': row = conversation(7)
    if mutation == 'roles': row['messages'][0]['role'] = 'assistant'
    if mutation == 'system': row['messages'].insert(0, {'role':'system','content':'Rules.'})
    if mutation == 'tools': row['tools'] = [{'function':{}}]
    if mutation == 'extra': row['messages'][0]['extra'] = 'not stripped'
    if mutation == 'user901': row['messages'][0]['content'] = 'u' * 901
    if mutation == 'assistant2401': row['messages'][1]['content'] = 'a' * 2401
    if mutation == 'total':
        row = conversation(3)
        for message in row['messages']:
            message['content'] = 'a' * (900 if message['role']=='user' else 2400)
    if mutation == 'empty': row['messages'][1]['content'] = ' '
    before = copy.deepcopy(row)
    assert seeds.eligible_openhermes(row) is None
    assert row == before


def test_native_window_complete_boundaries_deterministic():
    sentence = 'This is a complete sentence with enough native text for a bounded window. '
    text = sentence * 100
    result = seeds.native_window(text, 27)
    assert result == seeds.native_window(text, 27)
    passage, offset = result
    assert 500 <= len(passage) <= 2400
    assert text[offset:offset+len(passage)] == passage
    assert passage.startswith('This') and passage.endswith('.')
    assert seeds.native_window('word ' * 600, 27) is None  # No complete boundary within budget.
    assert seeds.native_window('Short.',27) is None


def test_stratified_files_groups_and_resume_commits(db, tmp_path, monkeypatch):
    data_root = tmp_path / 'data'
    files = []
    for number in range(2):
        relative = f'file-{number}.parquet'
        path = data_root/'downloads/dynaword-fo'/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist([dict(id=f'{number}-{i}', text=(f'Document {number} {i} sentence. ' * 120))
                                            for i in range(12)]), path, row_group_size=6)
        files.append(relative)
    monkeypatch.setattr(seeds, 'selected_source', lambda root,name: dict(repo='fixture',revision='pinned',files=files))
    source, schedule = seeds.native_tasks(db,data_root,'fo',27)
    assert len(schedule)==4 and schedule[0][0] != schedule[1][0]
    seeds.build_native(db,data_root,'fo',8,27,2)
    original = db.execute('SELECT seq,payload FROM seeds ORDER BY seq').fetchall()
    assert len(original)==8
    assert len({json.loads(p)['file'] for _,p in original})==2
    seeds.build_native(db,data_root,'fo',30,27,2)
    assert db.execute('SELECT seq,payload FROM seeds ORDER BY seq LIMIT 8').fetchall()==original
    assert db.execute('SELECT count(*) FROM seeds').fetchone()[0]==24
    result = json.loads(db.execute("SELECT value FROM build_state WHERE key='fo'").fetchone()[0])
    assert result['shortfall']==6
    assert db.execute('SELECT min(seq),max(seq) FROM seeds').fetchone()==(1,24)


def test_oh_round_robin_and_resume_preserve_full_records(db,tmp_path):
    paths=[]
    for file in range(2):
        path=tmp_path/f'oh-{file}.jsonl'
        with path.open('w') as stream:
            for row in range(5):
                item=conversation()
                item['messages'][0]['content'] += f' File {file}, row {row}.'
                stream.write(json.dumps(item)+'\n')
        paths.append(path)
    seeds.build_openhermes(db,paths,4,27,1)
    before=db.execute('SELECT seq,payload FROM seeds ORDER BY seq').fetchall()
    assert len({json.loads(p)['file'] for _,p in before})==2
    seeds.build_openhermes(db,paths,20,27,1)
    assert db.execute('SELECT seq,payload FROM seeds ORDER BY seq LIMIT 4').fetchall()==before
    assert db.execute('SELECT count(*) FROM seeds').fetchone()[0]==10


def test_pin_detects_drift(db,tmp_path):
    path=tmp_path/'source'
    path.write_text('first')
    sha=seeds.pin(db,path,'fixture')
    assert seeds.pin(db,path,'fixture')==sha
    path.write_text('changed')
    with pytest.raises(ValueError,match='Input changed'):
        seeds.pin(db,path,'fixture')


def test_spec_stream_array_and_map(db,tmp_path):
    spec=dict(language_code='nb',family='openhermes',source={'id':'used'})
    for value in ([spec], {'slot':spec}):
        path=tmp_path/'specifications.json'
        path.write_text(json.dumps(value))
        assert list(seeds.json_items(path))==[spec]
