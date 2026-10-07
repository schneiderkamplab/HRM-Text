import json
from pathlib import Path

import numpy as np
import pytest

from dfm12.io import file_hash, write_json
from dfm14.release import directions, package_name, repeat_for
from dfm14.release_inputs import accepted


def test_repeat_policy():
    assert repeat_for({'provenance':{'repo':'HuggingFaceTB/smoltalk','component':'smol-rewrite'}})==2
    assert repeat_for({'provenance':{'repo':'HuggingFaceTB/smoltalk','component':'smol-magpie-ultra'}})==1
    assert repeat_for({'provenance':{'repo':'HuggingFaceH4/ultrachat_200k','component':'ultrachat-nonoverlapping'}})==1
    assert repeat_for({'provenance':{'repo':'unknown'}})==1


def test_translation_directions():
    row=dict(id='pair',pair='ar-be',language='Arabic / Belarusian',
             messages=[{'role':'user','content':'forward'}],reverse_messages=[{'role':'user','content':'reverse'}])
    a,b=list(directions(row))
    assert a['language']=='be' and b['language']=='ar'
    assert a['id']!=b['id']
    assert a['messages']==row['messages'] and b['messages']==row['reverse_messages']


def test_names_reject_display_labels():
    with pytest.raises(ValueError):
        package_name({'language':'Arabic / Belarusian','task':'translation'},1)
    assert package_name({'language':'pt_pt','task':'translation'},1)=='dfm14-pt-pt-translation-r1'


def test_audit_keeps_only_accept_and_requires_all_decisions(tmp_path):
    source=tmp_path/'input.jsonl';journal=tmp_path/'results.jsonl';receipt=tmp_path/'receipt.json'
    source.write_text(''.join(json.dumps(dict(id=str(i),audit_id=str(i)))+'\n' for i in range(3)))
    records=[dict(audit_id=str(i),status='reviewed',review={'decision':d})
             for i,d in enumerate(['accept','repair','reject'])]
    journal.write_text(''.join(json.dumps(r)+'\n' for r in records))
    write_json(receipt,dict(input_sha256=file_hash(source),results_sha256=file_hash(journal)))
    job=dict(kind='audit',input=str(source),input_sha256=file_hash(source),rows=3,
        journal=str(journal),receipt=str(receipt),receipt_sha256=file_hash(receipt))
    assert [row['id'] for row,_ in accepted(job)]==['0']
    journal.write_text(json.dumps(records[0])+'\n')
    with pytest.raises(ValueError,match='Changed'):
        list(accepted(job))


@pytest.mark.parametrize('second_epoch',[False,True])
def test_native_inherited_dedup_verifies_complete_sequence(tmp_path,monkeypatch,second_epoch):
    from dfm14 import build
    base=tmp_path/'base';new=tmp_path/'new';root=tmp_path/'release';tree=root/'selected'
    base.mkdir();new.mkdir();root.mkdir();(base/'epoch_0').mkdir()
    # Equal shortlist tails, but different middle tokens must not be excluded.
    first=np.arange(30,dtype=np.uint32)+10
    second=first.copy();second[1]=99
    np.save(base/'tokens.npy',np.concatenate([first,second]))
    np.save(new/'tokens.npy',np.concatenate([first,second]))
    for directory,starts in [(base/'epoch_0',[0]),(new,[0,30])]:
        for field,values in dict(inst_start=starts,inst_len=[15]*len(starts),
                                 resp_start=[s+15 for s in starts],resp_len=[15]*len(starts)).items():
            np.save(directory/(field+'.npy'),np.asarray(values,dtype=np.uint64))
    if second_epoch:
        (base/'epoch_1').mkdir()
        for field,values in dict(inst_start=[30],inst_len=[15],resp_start=[45],resp_len=[15]).items():
            np.save(base/'epoch_1'/(field+'.npy'),np.asarray(values,dtype=np.uint64))
    write_json(base/'metadata.json',dict(tokenizer_info={}))
    monkeypatch.setattr(build,'BASE',base);monkeypatch.setattr(build,'ROOT',root);monkeypatch.setattr(build,'TREE',tree)
    result=build.deduplicate([dict(name='example',parts=[str(new)])])
    assert result['inherited_exact_targets_removed']==(2 if second_epoch else 1)
    assert result['sources']['example']['rows']==(0 if second_epoch else 1)
    assert np.load(tree/'example__part-000000/inst_start.npy').tolist()==([] if second_epoch else [30])
    original_tree,policy=build.selection_policy([dict(name='example',parts=[str(new)],repeat=1)])
    selected=np.load(policy[0]['selection_indices_path'])
    assert selected.tolist()==([] if second_epoch else [1])
    assert len(np.load(original_tree/'example__part-000000/tokens.npy'))==60
    assert len(np.load(original_tree/'example__part-000000/inst_start.npy'))==2
    if not second_epoch:
        import subprocess
        import sys
        import yaml
        policy_path=root/'policy.yaml'
        policy_path.write_text(yaml.safe_dump(policy))
        output=root/'sampled'
        subprocess.run([sys.executable,'data_io/sample_tokenized.py',
            f'tokenized_path={original_tree}',f'output_path={output}',
            f'prefix_config_path={policy_path}','epochs=1','concat_workers=1'],check=True,
            capture_output=True)
        sampled=build.arrays(output/'epoch_0')
        tokens=np.load(output/'tokens.npy')
        assert sampled['inst_start'].tolist()==[30]
        assert np.array_equal(tokens[30:60],second)


def test_legacy_accept_keeps_successful_check_records(tmp_path):
    journal=tmp_path/'attempts.jsonl';receipt=tmp_path/'receipt.json'
    spec=dict(start=0,end=1,job_id='legacy')
    record=dict(slot=0,attempt=4,language='ga',family='openhermes',spec_sha256='pinned',
        status='accepted',candidate=dict(id='old-accept'),checks=[dict(check='source_turn_roles',passed=True)],
        review=dict(source_usable='pass',turns={'1':{k:'pass' for k in
            ('language','grounding','fulfillment','format','authorization')}}))
    journal.write_text(json.dumps(record)+'\n')
    write_json(receipt,dict(job=spec,counts={'accepted':1},journal_sha256=file_hash(journal)))
    job=dict(kind='synthetic',name='legacy',job=spec,journal=str(journal),receipt=str(receipt),
             receipt_sha256=file_hash(receipt))
    assert list(accepted(job))[0][0]['id']=='old-accept'
    record['checks'][0]['passed']=False
    journal.write_text(json.dumps(record)+'\n')
    write_json(receipt,dict(job=spec,counts={'accepted':1},journal_sha256=file_hash(journal)))
    job['receipt_sha256']=file_hash(receipt)
    with pytest.raises(ValueError,match='failed its checks'):
        list(accepted(job))
