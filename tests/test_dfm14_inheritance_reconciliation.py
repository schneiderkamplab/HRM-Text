import json
from pathlib import Path

import numpy as np
import pytest

from dfm14.reconcile_inheritance import source_repeat, validate


def dataset(tmp_path):
    np.save(tmp_path/'tokens.npy', np.arange(20, dtype=np.uint32))
    epoch = tmp_path/'epoch_0'
    epoch.mkdir()
    for name, values in dict(inst_start=[0,5], inst_len=[2,3],
                             resp_start=[2,8], resp_len=[1,2]).items():
        np.save(epoch/(name+'.npy'), np.array(values, dtype=np.uint64))
    (tmp_path/'metadata.json').write_text(json.dumps(dict(total_length=8)))
    return tmp_path


def test_full_validation_allows_short_classification_target(tmp_path):
    result = validate(dataset(tmp_path), epochs=1)
    assert result == [dict(epoch=0, rows=2, tokens=8)]


def test_bounds_fail_closed(tmp_path):
    dataset(tmp_path)
    np.save(tmp_path/'epoch_0/resp_start.npy', np.array([21,8], dtype=np.uint64))
    with pytest.raises(ValueError, match='outside'):
        validate(tmp_path, epochs=1)
    assert not (tmp_path/'validated.json').exists()


def test_metadata_accounting(tmp_path):
    dataset(tmp_path)
    (tmp_path/'metadata.json').write_text(json.dumps(dict(total_length=99)))
    with pytest.raises(ValueError, match='accounting'):
        validate(tmp_path, epochs=1)


def test_identity_policy_preserves_other_repeats():
    assert source_repeat('dfm12-identity-xl-full-bp-en__',10)==0
    assert source_repeat('dfm12-identity-xxl-wide-en__',10)==0
    assert source_repeat('hendrycks_math_worked__',5)==5
    assert source_repeat('setur_fo_instruct__',10)==10
    assert source_repeat('dfm12-dala-en__',1)==1


def test_keep_all_policy_does_not_read_filtered_indices(tmp_path, monkeypatch):
    from dfm14 import build
    base=tmp_path/'base'
    base.mkdir()
    (base/'metadata.json').write_text(json.dumps({'tokenizer_info':{}}))
    part=tmp_path/'original'
    part.mkdir()
    monkeypatch.setattr(build,'ROOT',tmp_path/'build')
    monkeypatch.setattr(build,'BASE',base)
    monkeypatch.setattr(build,'TREE',tmp_path/'nonexistent_filtered_tree')
    tree,policy=build.selection_policy([dict(name='example',repeat=2,parts=[str(part)])],keep_all=True)
    assert policy==[dict(prefix='example__part-000000',repeat=2,long_context='drop')]
    assert (tree/'example__part-000000').resolve()==part


@pytest.mark.parametrize('clients,free,expected',[
    ('',180000,True),('GPU-3, 12345\n',180000,False),('',170000,False),
])
def test_training_waits_for_external_gpu_clients(monkeypatch,clients,free,expected):
    from types import SimpleNamespace
    from dfm14 import continue_training as module
    def run(argv,**kwargs):
        output=clients if '--query-compute-apps=gpu_uuid,pid' in argv else '\n'.join(
            f'{i}, GPU-{i}, {free}' for i in range(8))
        return SimpleNamespace(stdout=output)
    monkeypatch.setattr(module.subprocess,'run',run)
    assert module.training_gpus_free() is expected


def test_plan_preserves_training_contract_and_old_averages():
    from dfm14.continue_training import PLAN, build_plan, read_plan, PREFIX, Action
    if not (PLAN/'plan.tsv').exists():
        pytest.skip('Local campaign fixture not present')
    jobs=read_plan(PLAN/'plan.tsv')
    if not any(j.job_id=='xxlw-dfm13-train-900000' for j in jobs):
        pytest.skip('Original campaign already replaced')
    run=dict(start_step=870000,end_step=990123,resume='/private/resume',historical_epoch=2.28)
    revised=build_plan(jobs,run)
    new=[j for j in revised if j.job_id.startswith(PREFIX)]
    train=next(j for j in new if j.action==Action.TRAIN_UNTIL_STEP)
    assert 'data=dfm14' in train.metadata['command']
    assert 'wandb_run_id=dfm10-xxl-wide' in train.metadata['command']
    assert train.metadata['resume_from_tag']=='step_870000'
    assert train.metadata['resume_ckpt_path']=='/private/resume'
    block=[j for j in new if j.metadata.get('dfm14_boundary')==900000]
    averages=[j for j in block if j.action==Action.AVERAGE]
    assert len(averages)==2
    assert sum('multilingual_manifest' in j.metadata for j in averages)==1
    native=[j for j in block if j.action==Action.EVAL_DFM and
            j.metadata.get('dfm_single_tasks_config','').endswith('dfm_evals_dfm14.yaml')]
    assert len(native)==128
    assert all(j.metadata['wandb_run_id']=='dfm10-xxl-wide' for j in native)
    assert not any(j.status.value=='running' for j in new)
