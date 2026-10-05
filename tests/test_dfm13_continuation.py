"""CPU-only checks of dataset merge and epoch-finalization bookkeeping."""
import json
from pathlib import Path

import numpy as np

from scripts import build_dfm13_remote as builder
from scripts import continue_dfm13_xxl_wide as campaign
from eval_scheduler.eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan


def test_merge_preserves_offsets_and_lengths(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'BUILD', tmp_path)
    builder.write(tmp_path/'sources.json', {})
    for name, size in [('base', 8), ('extra', 4)]:
        p=tmp_path/name
        p.mkdir()
        np.save(p/'tokens.npy',np.arange(size,dtype=np.uint32))
        builder.write(p/'metadata.json',dict(max_seq_len=4097,tokenizer_info={},total_length=4))
        for epoch in range(3):
            out=p/f'epoch_{epoch}'
            out.mkdir()
            for field, value in dict(inst_start=[0],inst_len=[2],resp_start=[2],resp_len=[2]).items():
                np.save(out/(field+'.npy'),np.array(value,dtype=np.uint64))
    builder.merge(tmp_path/'base',tmp_path/'extra',tmp_path/'out',{})
    for epoch in range(3):
        p=tmp_path/'out'/f'epoch_{epoch}'
        assert sorted(np.load(p/'inst_start.npy'))==[0,8]
        assert sorted(np.load(p/'resp_start.npy'))==[2,10]
    assert builder.read(tmp_path/'out/metadata.json')['total_length']==8


def test_final_epoch_skips_unreached_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign,'PLAN',tmp_path)
    monkeypatch.setattr(campaign,'complete',lambda path,tag:tag=='epoch_3')
    p=campaign.PREFIX
    jobs=[Job(job_id=p+'train-1200000',action=Action.TRAIN_UNTIL_STEP,
              family='training',name='step_1200000',status=JobStatus.RUNNING),
          Job(job_id=p+'1200000-eval',action=Action.EVAL_STANDARD,
              family='standard',name='MATH',metadata={'dfm13_boundary':1200000}),
          Job(job_id=p+'train-1250000',action=Action.TRAIN_UNTIL_STEP,
              family='training',name='step_1250000',metadata={'dfm13_boundary':1250000}),
          Job(job_id=p+'epoch_3-wait-2484101',action=Action.WAIT_CHECKPOINT,
              family='post',name='epoch_3',deps=('old',))]
    write_plan(tmp_path/'plan.tsv',jobs)
    campaign.finalize(1200000)
    out=read_plan(tmp_path/'plan.tsv')
    assert out[0].status==JobStatus.RUNNING
    assert all(j.status==JobStatus.SKIPPED for j in out[1:3])
    assert out[3].deps==(p+'train-1200000',)


def test_fractional_epoch_uses_current_dataset_rows(tmp_path,monkeypatch):
    monkeypatch.setattr(campaign,'PLAN',tmp_path)
    monkeypatch.setattr(campaign,'DATA',tmp_path)
    monkeypatch.setattr(campaign,'complete',lambda path,tag:tag=='step_800000')
    monkeypatch.setattr(campaign,'state',lambda tag:{'global_row_cursor_in_epoch':25})
    (tmp_path/'epoch_2').mkdir()
    np.save(tmp_path/'epoch_2/inst_start.npy',np.zeros(100,dtype=np.uint64))
    j=Job(job_id=campaign.PREFIX+'800000-eval',action=Action.EVAL_STANDARD,
          family='standard',name='MATH',metadata={'dfm13_boundary':800000})
    write_plan(tmp_path/'plan.tsv',[j])
    campaign.finalize(800000)
    assert read_plan(tmp_path/'plan.tsv')[0].metadata['eval_epoch']==2.25
