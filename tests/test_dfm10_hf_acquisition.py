from pathlib import Path
import pytest
from scripts.acquire_dfm10_hf import safe_file


def test_reject_escape(tmp_path):
    for rel in ('../public.jsonl', '/public.jsonl', 'data/../../public.jsonl'):
        with pytest.raises(ValueError):
            safe_file(tmp_path, rel)


def test_reject_symlink_escape(tmp_path):
    root = tmp_path / 'download'
    root.mkdir()
    (root / 'data').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        safe_file(root, 'data/local.jsonl')


def test_accept_download_path(tmp_path):
    assert safe_file(tmp_path, 'data/train.jsonl.gz') == tmp_path / 'data/train.jsonl.gz'


def test_restore_preserves_original_source_and_tools():
    from scripts.unpack_dfm10_hf import restore
    original = {'source': 'original', 'id': 'a'}
    row = {'metadata': original, 'source': {'source_file': 'train.jsonl'},
           'messages': [{'role': 'assistant', 'tool_calls': [{'id': 'x'}]}],
           'tools': [{'name': 'tool'}], 'condition': 'direct'}
    restored = restore(row)
    assert restored['source'] == 'original'
    assert restored['messages'] == row['messages']
    assert restored['tools'] == row['tools']
    assert original == {'source': 'original', 'id': 'a'}


def test_unpack_rejects_duplicate_source_rows(tmp_path):
    import gzip
    import json
    from scripts.acquire_dfm10_hf import sha
    from scripts.unpack_dfm10_hf import unpack
    source = tmp_path / 'acquisitions/repo'
    (source / 'metadata').mkdir(parents=True)
    manifest = source / 'metadata/manifest.json'
    manifest.write_text(json.dumps({'source_root': 'old/path', 'rows': 2}))
    payload = source / 'train.jsonl.gz'
    row = {'source': {'source_file': 'train.parquet', 'source_row': 1},
           'messages': [{'role': 'user', 'content': 'hello'}]}
    with gzip.open(payload, 'wt') as f:
        f.write((json.dumps(row)+'\n')*2)
    receipt = {'download_path': str(source), 'manifest_sha256': sha(manifest),
               'repo_id': 'owner/repo', 'revision': 'a'*40,
               'files': [{'file': payload.name, 'bytes': payload.stat().st_size,
                          'sha256': sha(payload)}]}
    with pytest.raises(ValueError, match='Duplicate or reordered'):
        unpack(receipt, tmp_path)
    assert not (tmp_path / 'unpacked/repo/receipt.json').exists()


def test_hrm_restoration_keeps_condition():
    from scripts.materialize_dfm10_hf import hrm
    row = {'condition':'summarize', 'messages':[{'role':'user','content':'source'}, {'role':'assistant','content':'summary'}]}
    assert hrm(row) == {'condition':'summarize','instruction':'source','response':'summary'}
    row['messages'].append({'role':'user','content':'extra'})
    with pytest.raises(ValueError):
        hrm(row)


def test_inherited_exports_do_not_replace_dfm10_additions():
    from scripts.dfm10_export_scope import inherited
    assert inherited('schneiderkamplab/dfm10-sapient-flan-t0-filtered-sft')
    assert inherited('schneiderkamplab/dfm10-natural-instructions-filtered-sft')
    for name in ('sapient-qrecc-ii-repaired','sapient-scibench-repaired',
                 'scientific-summaries-repaired','nemotron-terminal-sft',
                 'opus-da-en-repaired'):
        assert not inherited('schneiderkamplab/dfm10-'+name)


def test_tidsskrift_gold_recovery_preserves_order_and_messages(tmp_path):
    import json
    from scripts.map_dfm10_hf import recover_tidsskrift_gold
    rows=[{'source_id':str(i),'row_origin':'gold_author_abstract',
           'training_tokens':100,'messages':[{'role':'user','content':f'article {i}'},
                                            {'role':'assistant','content':f'abstract {i}'}]} for i in range(9)]
    source=tmp_path/'hf.jsonl';target=tmp_path/'gold.jsonl'
    source.write_text('\n'.join(json.dumps(x) for x in [{'row_origin':'synthetic'}]+rows)+'\n')
    assert recover_tidsskrift_gold(source,target)==9
    actual=[json.loads(x) for x in target.read_text().splitlines()]
    assert [x['source_id'] for x in actual]==[str(i) for i in range(9)]
    assert [x['messages'] for x in actual]==[x['messages'] for x in rows]
    assert all('row_origin' not in x and 'training_tokens' not in x for x in actual)
    source.write_text(json.dumps(rows[0])+'\n')
    with pytest.raises(ValueError):recover_tidsskrift_gold(source,target)


def test_native_parquet_preserves_multiturn_schema(tmp_path):
    import json
    import pyarrow.parquet as pq
    from scripts.materialize_dfm10_hf import materialize
    row={'messages':[{'role':'user','content':'æøå'}, {'role':'assistant','content':'reply'},
                     {'role':'user','content':'follow-up'}, {'role':'assistant','content':'answer'}],
         'source_file':'task.parquet','upstream_metadata':'{"agent":"example"}'}
    source=tmp_path/'hf.jsonl';target=tmp_path/'native.parquet'
    source.write_text(json.dumps(row)+'\n')
    materialize(source,target,native=True)
    assert pq.read_table(target).to_pylist()==[row]
    row['messages'][1]['tool_calls']=[{'id':'extra'}]
    source.write_text(json.dumps(row)+'\n')
    with pytest.raises(ValueError,match='refusing field loss'):
        materialize(source,target,native=True)
