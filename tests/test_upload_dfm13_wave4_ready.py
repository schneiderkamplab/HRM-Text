import pytest
from dfm12.io import write_json, file_hash
from scripts.upload_dfm13_wave4_ready import checked, freeze
from scripts.upload_dfm13_baltic_ready2 import freeze as freeze_baltic


def test_pin_mismatch(tmp_path):
    p=tmp_path/'payload';p.write_text('original')
    sha=file_hash(p)
    assert checked(p,sha)==p
    p.write_text('changed')
    with pytest.raises(ValueError):checked(p,sha)


def test_resume_requires_seal(tmp_path):
    write_json(tmp_path/'queue.json',{'expected':66})
    write_json(tmp_path/'seal.json',{'sha256':file_hash(tmp_path/'queue.json')})
    assert freeze(tmp_path,tmp_path/'unused')['expected']==66
    write_json(tmp_path/'queue.json',{'expected':65})
    with pytest.raises(ValueError):freeze(tmp_path,tmp_path/'unused')


def test_wave_scope_failclosed(tmp_path):
    h=tmp_path/'handoff.json'
    write_json(h,{'status':'66_of_66_ready_for_owner_upload','packages':65})
    with pytest.raises(ValueError):freeze(tmp_path/'root',h)


def test_baltic_never_includes_conditional_packages(tmp_path):
    h=tmp_path/'handoff.json'
    write_json(h,{'packages':[{'upload_ready':True,'hf_repo_id':'schneiderkamplab/conditional'}]})
    with pytest.raises(ValueError):freeze_baltic(tmp_path/'root',h)


def test_six_requires_completed_unchanged_handoff(tmp_path):
    h=tmp_path/'handoff.json'
    write_json(h,{'packages':[], 'sealed_release_unchanged':False})
    with pytest.raises(ValueError,match='Scoped successor incomplete'):
        freeze_baltic(tmp_path/'root',h,scoped_six=True)
