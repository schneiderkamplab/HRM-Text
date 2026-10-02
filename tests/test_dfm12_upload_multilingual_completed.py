import pytest

from dfm12 import upload_multilingual_completed as u
from dfm12.io import write_json, file_hash, load


def package(root):
    folder=root/'dfm12-multilingual-synthetic-de'
    folder.mkdir()
    (folder/'README.md').write_text('Local-only export; no upload authorized.\n')
    write_json(folder/'metadata/manifest.json',dict(rows=35000,files={}))
    write_json(root/'manifest.json',dict(packages=[dict(name=folder.name,language='de',rows=35000)]))
    write_json(root/'completion.json',dict(rows=35000,packages=1))
    write_json(root/'verification.json',dict(rows=35000,
        manifest_sha256=file_hash(root/'manifest.json'),completion_sha256=file_hash(root/'completion.json'),
        all_package_hashes_verified=True,all_training_audit_pairs_verified=True,
        packages=[dict(language='de',manifest_sha256=file_hash(folder/'metadata/manifest.json'))]))
    return folder


def test_verified_input_accepted(tmp_path):
    folder=package(tmp_path)
    assert list(u.validated_packages(tmp_path))[0][1]==folder


def test_changed_manifest_rejected(tmp_path):
    package(tmp_path)
    write_json(tmp_path/'manifest.json',{})
    with pytest.raises(ValueError,match='changed'):list(u.validated_packages(tmp_path))


def test_false_verification_rejected(tmp_path):
    package(tmp_path)
    path=tmp_path/'verification.json';record=load(path);record['all_training_audit_pairs_verified']=False
    write_json(path,record)
    with pytest.raises(ValueError,match='Unverified'):list(u.validated_packages(tmp_path))


def test_overlay_preserves_original_export(tmp_path):
    folder=package(tmp_path)
    original=(folder/'README.md').read_bytes();sha=file_hash(folder/'metadata/manifest.json')
    output=tmp_path/'publication';output.mkdir()
    evidence=dict(policy='No blanket relicensing.',sources=[],warnings=[])
    write_json(output/'source-license-evidence.json',evidence)
    files=u.publication_files(folder,output,evidence)
    assert (folder/'README.md').read_bytes()==original
    assert file_hash(folder/'metadata/manifest.json')==sha
    assert 'Published under explicit user authorization' in files['README.md'].read_text()
    assert files['metadata/manifest.json']==folder/'metadata/manifest.json'
    assert load(files['metadata/publication-authorization.json'])['manifest_sha256']==sha


def test_remote_inventory_mismatch_fails_before_download():
    class API:
        def list_repo_files(self,*args,**kwargs):return ['foreign']
    with pytest.raises(ValueError,match='inventory'):u.verify_remote(API(),'repo','sha',{},35000)


def test_portuguese_hub_card_changes_only_publication_metadata(tmp_path):
    import yaml
    folder=tmp_path/'dfm12-multilingual-synthetic-pt_pt';folder.mkdir()
    original='---\nlanguage:\n- pt_pt\n---\nNative pt_pt records.\n'
    (folder/'README.md').write_text(original)
    write_json(folder/'metadata/manifest.json',dict(language='pt_pt',rows=35000,files={}))
    output=tmp_path/'publication';output.mkdir()
    evidence=dict(policy='No blanket relicensing.',sources=[],warnings=[])
    write_json(output/'source-license-evidence.json',evidence)
    files=u.publication_files(folder,output,evidence)
    metadata=yaml.safe_load(files['README.md'].read_text().split('---',2)[1])
    assert metadata['language']==['pt'] and metadata['language_bcp47']==['pt-PT']
    assert (folder/'README.md').read_text()==original
    assert load(folder/'metadata/manifest.json')['language']=='pt_pt'
