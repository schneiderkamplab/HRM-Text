import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval_scheduler"))
from eval_scheduler.model import Action, Job
from eval_scheduler.monitor import compact_job_id, task_first_label


def test_task_and_checkpoint_precede_long_campaign():
    job = Job("long-campaign-prefix-eval-600316", Action.EVAL_DFM_IFEVAL,
              "dfm_ifeval", "ifeval-da", shard=5, shards=32,
              metadata={"model_prefix": "very-long-model-prefix",
                        "ckpt_tag": "step_2750000", "no_ema": False})
    assert task_first_label(job).startswith(
        "dfm_ifeval:ifeval-da shard 5/32 | step_2750000:ema")
    assert compact_job_id(job.job_id).endswith("eval-600316")
    assert len(compact_job_id(job.job_id)) == 24
    assert compact_job_id("eval-1") == "eval-1"
