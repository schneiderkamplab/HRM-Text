from pathlib import Path
import subprocess
import sys

import numpy as np

from dfm12.build_training import FIELDS, merge_epoch, combine
from dfm12.io import write_json, load


def test_identity_disabled_for_both_profiles():
    import pytest
    from dfm12.build_training import source_repeat
    config = load('dfm12/training_sources.json')
    for profile in ('xl', 'xxl-wide'):
        assert source_repeat(config, f'dfm12-identity-{profile}-full-bp-en') == 0
    assert source_repeat(config, 'dfm12-opus-en-sv') == 1
    with pytest.raises(ValueError):
        source_repeat({'identity_repeat': -1}, 'dfm12-identity-test')


def test_unpublished_disabled_package_cannot_be_enabled(tmp_path):
    import pytest
    from dfm12.build_training import registered_packages
    name = 'dfm12-identity-xxl-wide-full-bp-ca'
    write_json(tmp_path / name / 'metadata/manifest.json', {'data_files': []})
    write_json(tmp_path / 'manifest.json', {'packages': [{'name': name, 'rows': 1}]})
    write_json(tmp_path / 'metadata/upload-receipts.json', {})
    with pytest.raises(ValueError, match='must remain disabled'):
        registered_packages({'export_roots': [str(tmp_path)], 'identity_repeat': 10,
                             'local_only_disabled_packages': [name]})


def test_explicit_replacement_does_not_double_count(tmp_path):
    import pytest
    from dfm12.build_training import registered_packages
    from dfm12.io import file_hash
    roots = [tmp_path / 'old', tmp_path / 'new']
    name = 'dfm12-identity-test'
    for root in roots:
        manifest = root / name / 'metadata/manifest.json'
        write_json(manifest, {'data_files': []})
        write_json(root / 'manifest.json', {'packages': [
            {'name': name, 'rows': 1, 'validation': {'valid': True}}]})
        write_json(root / 'metadata/upload-receipts.json', {'schneiderkamplab/' + name:
            {'status': 'verified', 'manifest_sha256': file_hash(manifest)}})
    config = {'export_roots': list(map(str, roots)), 'package_overrides': {name: str(roots[1])}}
    assert registered_packages(config)[0][1] == roots[1] / name
    assert len(registered_packages(config)) == 1
    write_json(roots[1] / 'manifest.json', {'packages': [{'name': name, 'rows': 0}]})
    with pytest.raises(ValueError, match='Empty replacement'):
        registered_packages(config)
    config['export_roots'] = [str(roots[0])]
    with pytest.raises(ValueError, match='Missing replacement'):
        registered_packages(config)


def test_native_manifest_selects_only_training_data():
    import pytest
    from dfm12.build_training import package_data_files
    manifest = {'schema': 'dfm12-multilingual-completed-export-v1', 'files': {
        'data/train-tool-dialogue.jsonl.gz': {'sha256': 'abc'},
        'metadata/audits-tool-dialogue.jsonl.gz': {'sha256': 'def'}}}
    assert package_data_files(manifest) == [{'file': 'data/train-tool-dialogue.jsonl.gz', 'sha256': 'abc'}]
    manifest['files']['data/../../escape'] = {'sha256': 'bad'}
    with pytest.raises(ValueError, match='Unsafe'):
        package_data_files(manifest)


def test_identity_publication_required(tmp_path):
    import pytest
    from dfm12.build_training import registered_packages
    from dfm12.io import file_hash
    name = 'dfm12-identity-xl-full-bp-en'
    path = tmp_path / name / 'metadata/manifest.json'
    write_json(path, {'schema': 'dfm12-identity21-accepted-export-v1', 'rows': 2000})
    write_json(tmp_path / 'manifest.json', {'packages': [{'name': name, 'rows': 2000}]})
    receipt = {'status': 'verified', 'manifest_sha256': file_hash(path), 'remote_rows': 2000, 'revision': 'abc'}
    write_json(tmp_path / 'upload-receipts.json', {'schneiderkamplab/' + name: receipt})
    assert len(registered_packages({'export_roots': [str(tmp_path)]})) == 1
    receipt['remote_rows'] = 1000
    write_json(tmp_path / 'upload-receipts.json', {'schneiderkamplab/' + name: receipt})
    with pytest.raises(ValueError, match='Unverified'):
        registered_packages({'export_roots': [str(tmp_path)]})


def test_multilingual_requires_bound_verification(tmp_path):
    import pytest
    from dfm12.build_training import registered_packages
    from dfm12.io import file_hash
    name = 'dfm12-multilingual-synthetic-de'
    path = tmp_path / name / 'metadata/manifest.json'
    write_json(path, {'schema': 'dfm12-multilingual-completed-export-v1', 'rows': 35000})
    write_json(tmp_path / 'manifest.json', {'packages': [{'name': name, 'rows': 35000}]})
    checksum = file_hash(path)
    write_json(tmp_path / 'metadata/upload-receipts.json', {'schneiderkamplab/' + name:
        {'status': 'verified', 'manifest_sha256': checksum}})
    verification = {'all_package_hashes_verified': True, 'all_training_audit_pairs_verified': True,
                    'manifest_sha256': file_hash(tmp_path / 'manifest.json'),
                    'packages': [{'rows': 35000, 'manifest_sha256': checksum}]}
    write_json(tmp_path / 'verification.json', verification)
    assert len(registered_packages({'export_roots': [str(tmp_path)]})) == 1
    verification['all_training_audit_pairs_verified'] = False
    write_json(tmp_path / 'verification.json', verification)
    with pytest.raises(ValueError, match='Unverified'):
        registered_packages({'export_roots': [str(tmp_path)]})


def test_registered_packages_reject_duplicates_and_changed_publication(tmp_path):
    import pytest
    from dfm12.build_training import registered_packages
    from dfm12.io import file_hash
    root = tmp_path / 'exports'
    manifest = root / 'dfm12-test/metadata/manifest.json'
    write_json(manifest, {'data_files': []})
    write_json(root / 'manifest.json', {'packages': [
        {'name': 'dfm12-test', 'rows': 1, 'validation': {'valid': True}}]})
    write_json(root / 'metadata/upload-receipts.json', {'schneiderkamplab/dfm12-test':
        {'status': 'verified', 'manifest_sha256': file_hash(manifest)}})
    assert len(registered_packages({'export_roots': [str(root)]})) == 1
    with pytest.raises(ValueError, match='Duplicate'):
        registered_packages({'export_roots': [str(root), str(root)]})
    write_json(manifest, {'data_files': [], 'changed': True})
    with pytest.raises(ValueError, match='changed'):
        registered_packages({'export_roots': [str(root)]})


def test_merge_preserves_rows_and_offsets_only_additions(tmp_path):
    base, added = tmp_path/'base', tmp_path/'added'
    base.mkdir()
    added.mkdir()
    aa = [[0, 3, 3, 2], [5, 2, 7, 4]]
    bb = [[0, 2, 2, 3]]
    for i, field in enumerate(FIELDS):
        np.save(base/(field+'.npy'), np.array([r[i] for r in aa],dtype=np.uint64))
        np.save(added/(field+'.npy'), np.array([r[i] for r in bb],dtype=np.uint64))
    out = tmp_path/'out'
    result = merge_epoch(base,added,out,100,0)
    actual = np.stack([np.load(out/(f+'.npy')) for f in FIELDS],axis=1)
    assert sorted(map(tuple,actual)) == sorted(map(tuple,aa+[[100,2,102,3]]))
    assert result == {'base':11,'additions':5,'base_rows':2,'added_rows':1}


def test_combine_validates_template_and_publishes_metadata_last(tmp_path):
    tokenizer = tmp_path/'tokenizer.json'
    template = tmp_path/'template.jinja'
    tokenizer.write_text('{}')
    template.write_text('test')
    meta = {'max_seq_len':4097, 'total_length':5, 'tokenizer_info':{
        'vocab_size':262144,'enable_thinking':False,'template_mode':'jinja_chat_template',
        'tokenizer_path':str(tokenizer),'chat_template_path':str(template)}}
    for name in ('base','added'):
        root = tmp_path/name
        (root/'epoch_0').mkdir(parents=True)
        write_json(root/'metadata.json',meta)
        np.save(root/'tokens.npy',np.arange(5,dtype=np.int32))
        for field,value in zip(FIELDS,(0,2,2,3)):
            np.save(root/'epoch_0'/(field+'.npy'),np.array([value],dtype=np.uint64))
    out = tmp_path/'combined'
    combine(tmp_path/'base',tmp_path/'added',out,1)
    assert load(out/'metadata.json')['total_length'] == 10
    assert load(out/'build-receipt.json')['additional_tokens_per_epoch'] == 5
    assert np.load(out/'tokens.npy').tolist() == [0,1,2,3,4]*2


def test_existing_sampler_applies_identity_repeat(tmp_path):
    root = tmp_path/'tokenized'
    task = root/'dfm12-identity-test__train.jsonl'
    task.mkdir(parents=True)
    write_json(root/'tokenizer_info.json',{'vocab_size':262144})
    np.save(task/'tokens.npy',np.arange(5,dtype=np.uint32))
    for field,value in zip(FIELDS,(0,2,2,3)):
        np.save(task/(field+'.npy'),np.array([value],dtype=np.uint64))
    policy = tmp_path/'policy.yaml'
    policy.write_text('- prefix: dfm12-identity-test__\n  repeat: 10\n')
    output = tmp_path/'sampled'
    subprocess.run([sys.executable,'data_io/sample_tokenized.py',f'tokenized_path={root}',
        f'output_path={output}',f'prefix_config_path={policy}','epochs=2','concat_workers=1',
        'skip_unmatched=true'],check=True,capture_output=True)
    assert load(output/'metadata.json')['total_length'] == 50
    assert len(np.load(output/'epoch_1/inst_len.npy')) == 10
