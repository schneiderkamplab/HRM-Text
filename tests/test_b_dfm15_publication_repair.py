from pathlib import Path
import pytest
from scripts.repair_b_dfm15_publication import link_tree


def test_archived_inference_shared_with_publication(tmp_path):
    source = tmp_path/'inference'
    (source/'inspect').mkdir(parents=True)
    (source/'inspect/example.eval').write_bytes(b'original')
    target = tmp_path/'canonical/task/shard_0/step_550000'
    links = []
    link_tree(source, target, links)
    assert (target/'inspect/example.eval').read_bytes() == b'original'
    assert source.exists()
    link_tree(source, target, links)
    assert len(links) == 1


def test_artifact_collision_never_overwrites(tmp_path):
    source=tmp_path/'source'; target=tmp_path/'target'
    source.write_text('new');target.write_text('existing')
    with pytest.raises(ValueError, match='collision'):
        link_tree(source,target,[])
    assert target.read_text() == 'existing'


def test_shards_combine_in_existing_task_directory(tmp_path):
    source=tmp_path/'source'; target=tmp_path/'target'
    source.mkdir();target.mkdir()
    (source/'shard_1.log').write_text('one')
    (target/'shard_0.log').write_text('zero')
    link_tree(source,target,[])
    assert sorted(p.name for p in target.iterdir()) == ['shard_0.log','shard_1.log']


def test_recursive_aggregate_discovery_sees_linked_metrics(tmp_path):
    source=tmp_path/'saved';source.mkdir()
    (source/'merged_metrics.json').write_text('{"metrics": {"accuracy": 0.5}}')
    root=tmp_path/'canonical'
    link_tree(source,root/'language/task',[])
    paths=list(root.glob('**/merged_metrics.json'))
    assert len(paths) == 1
    assert paths[0].resolve().is_relative_to(root)
    assert paths[0].read_bytes() == (source/'merged_metrics.json').read_bytes()


def test_replay_claims_only_cpu_jobs_and_preserves_running_training(tmp_path, monkeypatch):
    from scripts import repair_b_dfm15_publication as repair
    from eval_scheduler.model import Job, Action, JobStatus
    from eval_scheduler.store import SQLiteJobStore
    monkeypatch.setattr(repair,'DB',tmp_path/'jobs.sqlite')
    monkeypatch.setattr(repair,'PLAN',tmp_path)
    monkeypatch.setattr(repair,'OUT',tmp_path)
    store=SQLiteJobStore(repair.DB)
    jobs=[Job('train',Action.TRAIN_UNTIL_STEP,'training','train'),
          Job('b-dfm15-550000-publish',Action.EXPORT_DFM_RESULTS,'dfm','task'),
          Job('b-dfm15-550000-average',Action.AVERAGE,'average','all',deps=('b-dfm15-550000-publish',)),
          Job('b-dfm15-550000-inference',Action.EVAL_DFM,'dfm','task'),
          Job('b-dfm15-550000-terminal',Action.TERMINAL_BARRIER,'control','terminal',deps=('b-dfm15-550000-average',))]
    store.import_jobs(jobs)
    train=store.claim_jobs(['train'])['train']
    calls=[]
    def run(j,gpu):
        assert gpu is None and j.action in repair.CPU
        calls.append(j.job_id)
        return 0
    monkeypatch.setattr(repair.runtime,'run_job',run)
    assert not repair.replay(550000,2)
    assert calls==['b-dfm15-550000-publish','b-dfm15-550000-average','b-dfm15-550000-terminal']
    assert store.attempt_token('train')==train.token
    assert next(j for j in store.load_jobs() if j.job_id.endswith('-inference')).status==JobStatus.PENDING
