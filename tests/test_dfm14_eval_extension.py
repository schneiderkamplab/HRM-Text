from pathlib import Path
from scripts.schedule_dfm14_eval_extension import build, FLAG
from scripts.schedule_dfm13_wave34_baseline import Action, Job, JobStatus, check_graph
from scripts.dala_semantic import NATIVE, extract_semantic_label
from scripts.merge_dfm_eval_shards import semantic_dala_metrics


def test_new_language_semantic_labels():
    for lang in 'ga mt mk eu gl cy ru tr zh ar ja id ko hi vi he'.split():
        assert extract_semantic_label(' "Yes!" ', lang) == 'correct'
        assert extract_semantic_label('incorrect.', lang) == 'incorrect'
        assert extract_semantic_label('yes and no', lang) is None
        samples = []
        for target, labels in zip(('correct', 'incorrect'), NATIVE[lang]):
            for label in labels:
                output = ' "' + label + '." '
                assert extract_semantic_label(output, lang) == target
                samples.append(dict(target=target, metadata={'language': lang},
                                    output={'completion': output}))
        result = semantic_dala_metrics(samples, lang)
        assert result['semantic_v1/macro_f1'] == 1
        assert result['semantic_v1/invalid_rate'] == 0


def test_extension_preserves_training_and_gates_successor():
    jobs = []
    for step in (3250000, 3300000):
        meta = dict(eval_step=step, ckpt_tag=f'step_{step}', fix_mistral_regex=False,
                    wandb_run_id='dfm8-xl-from-dfm6-dfm7-epoch5-clean-full',
                    dfm_log_root=f'/tmp/dfm/{step}', euroeval_log_root=f'/tmp/euro/{step}')
        train = Job(job_id=f'train{step}', action=Action.TRAIN_UNTIL_STEP, family='training', name=str(step),
                    metadata=meta, status=JobStatus.RUNNING if step==3250000 else JobStatus.PENDING)
        export = Job(job_id=f'export{step}', action=Action.EXPORT_HF, family='export', name=str(step),
                     metadata=meta, deps=(train.job_id,))
        task = Job(job_id=f'eval{step}', action=Action.EVAL_DFM, family='dfm', name='dala_lt',
                   metadata=meta, deps=(export.job_id,), initial_batch=512)
        merge = Job(job_id=f'merge{step}', action=Action.MERGE_DFM, family='dfm', name='dala_lt',
                    metadata=meta, deps=(task.job_id,))
        avg = Job(job_id=f'avg{step}', action=Action.AVERAGE, family='post', name='average',
                  metadata={**meta,'multilingual_manifest':'old.json'}, deps=(merge.job_id,))
        jobs.extend([train,export,task,merge,avg])
    task = dict(name='dala_ga',suite='dala_ga',config='new.yaml',language='ga',max_tokens=32,shards=4)
    result = build(jobs,[task])
    assert result[0] == jobs[0]
    by = {j.job_id:j for j in result}
    assert 'dfm14-eval-3250000-average' in by['train3300000'].deps
    avg = by['dfm14-eval-3250000-average']
    assert 'avg3250000' in avg.deps
    assert 'dfm14-eval-3250000-dala_ga-merge' in avg.deps
    assert avg.metadata['population_require_complete'] is False
    for job in result:
        if job.metadata.get(FLAG) and job.action == Action.EVAL_DFM:
            assert job.initial_batch == 512
            assert job.metadata['language'] == 'ga'
    check_graph(result)
