from scripts.gate_dfm12_training_on_final_averages import TRAIN, extend
from eval_scheduler.model import Action, Job, JobStatus
from eval_scheduler.runtime import dependencies_satisfied


def test_all_finalizers_before_training_and_no_eval_changes():
    def job(identifier, action, tag='step_2900000', **kwargs):
        return Job(job_id=identifier, action=action, family='test', name=identifier,
                   log_dir='/tmp/test', metadata={'ckpt_tag': tag,
                   'eval_step': 2877261 if tag == 'epoch_10' else 2900000}, **kwargs)
    original = [job('eval', Action.EVAL_DFM, status=JobStatus.DONE),
                job('avg-baseline', Action.AVERAGE, 'epoch_10', deps=('eval',)),
                job('avg-current', Action.AVERAGE, deps=('eval',)),
                job('teardown', Action.TEARDOWN_EVAL, status=JobStatus.DONE),
                job(TRAIN, Action.TRAIN_UNTIL_STEP, deps=('teardown',))]
    result, finalizers, _ = extend(original)
    assert result[:4] == original[:4]
    assert {'avg-baseline', 'avg-current', 'teardown'} <= set(finalizers[0].deps)
    assert finalizers[1].deps == (finalizers[0].job_id,)
    train = next(j for j in result if j.job_id == TRAIN)
    assert not dependencies_satisfied(train, result)
    failed = [j.with_updates(status=JobStatus.FAILED) if j.job_id == finalizers[-1].job_id else j for j in result]
    assert not dependencies_satisfied(train, failed)
    done = [j.with_updates(status=JobStatus.DONE) if j.job_id == finalizers[-1].job_id else j for j in result]
    assert dependencies_satisfied(train, done)
