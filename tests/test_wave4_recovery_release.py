import json
import pytest
from dfm12.wave4_recovery_release import allowance,package
from dfm12.io import digest,write_json,file_hash,load


def test_lb_uncapped_other_languages_keep_original_quotas():
    assert allowance(dict(language='lb',target=4000,accepted=4000),6440)==6440
    assert allowance(dict(language='fa',target=6000,accepted=601),29957)==5399
    assert allowance(dict(language='fa',target=6000,accepted=6000),10)==0


def test_package_original_unchanged_resumable_and_hash_checked(tmp_path):
    source=tmp_path/'candidate.json';candidate=dict(messages=[dict(role='assistant',content='answer')],tools=[])
    write_json(source,candidate);sha=file_hash(source)
    proof=dict(candidate_path=str(source),pins={str(source):sha},fingerprint=digest(candidate),language='lb',family='math-code')
    args=(tmp_path/'release','id',json.dumps(proof))
    assert package(args)==package(args)
    assert file_hash(source)==sha
    assert load(tmp_path/'release/accepted/id.json')==candidate
    write_json(source,dict(candidate,tools=['changed']))
    with pytest.raises(ValueError,match='drift'):package(args)
