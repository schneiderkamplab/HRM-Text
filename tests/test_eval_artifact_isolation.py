import pytest
from eval_scheduler.preflight import check_artifact_isolation
from eval_scheduler.store import _validate_graph
from eval_scheduler.model import Job, Action


def job(name, checkpoint, tag='step_50000', export='exports/shared', log='logs/shared'):
    return Job(job_id=name, action=Action.EVAL_DFM, family="dfm", name=name, log_dir=log,
               metadata={'ckpt_path':checkpoint,'ckpt_tag':tag,'hf_export_dir':export})


def test_same_checkpoint_shards_can_share_artifacts(tmp_path):
    assert not check_artifact_isolation([job('a','checkpoints/a'),job('b','checkpoints/a')],tmp_path)


@pytest.mark.parametrize('second', [
    job('b','checkpoints/b'),
    job('b','checkpoints/a',tag='step_100000'),
    job('b','checkpoints/b',export='exports/distinct'),
    job('b','checkpoints/b',log='logs/distinct'),
])
def test_reject_cross_checkpoint_artifact_sharing(tmp_path,second):
    assert check_artifact_isolation([job('a','checkpoints/a'),second],tmp_path)


def test_normalizes_relative_and_absolute_paths(tmp_path):
    a=job('a','checkpoints/a')
    b=job('b','checkpoints/b',export=str(tmp_path/'exports/shared'),log='logs/distinct')
    assert check_artifact_isolation([a,b],tmp_path)


def test_graph_validation_rejects_collision_before_dispatch():
    with pytest.raises(ValueError,match='artifact collision'):
        _validate_graph([job('a','checkpoints/a'),job('b','checkpoints/b')])
