"""CPU-only, evidence-bound copies of eight historical English headline metrics."""
import csv
import json
from pathlib import Path

from dfm12.io import file_hash, load, write_json
from scripts.log_dfm5_headline_averages import ENGLISH_KEYS

PLAN = Path('logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725/plan.tsv')
ROOT = Path('data/eval/dfm11-xl-epoch10-english-euroeval-20260930')
STEP = 2877261


def build(root=ROOT, keys=ENGLISH_KEYS):
    if root.exists():
        raise ValueError('Canonical output must be new')
    with PLAN.open() as handle:
        jobs = list(csv.DictReader(handle, delimiter='\t'))
    export = next(r for r in jobs if r['job_id']=='dfm11-xl-e10-epoch_10-export-600290')
    meta = json.loads(export['metadata_json'])
    assert export['status']=='done' and meta['ckpt_tag']=='epoch_10' and meta['no_ema'] is False
    state_path = Path(meta['ckpt_path'])/'checkpoint_state_epoch_10.json'
    state = load(state_path)
    assert state['step']==STEP and state['epoch']==10 and state['tag']=='epoch_10'
    hf = Path(meta['hf_export_dir'])
    assert hf.is_dir()
    prepared, evidence = [], []
    for key in keys:
        if not key.startswith('euroeval/'):
            continue
        dataset = key.split('/')[3]
        matches = [r for r in jobs if r['action'] in ('eval_euroeval','eval_euroeval_batched_ifeval') and r['name']==dataset
                   and r['job_id'].startswith('dfm11-xl-e10-epoch_10-')]
        assert len(matches)==1
        job = matches[0]
        details = json.loads(job['metadata_json'])
        assert job['status']=='done' and export['job_id'] in job['deps'].split(',')
        assert details['ckpt_tag']=='epoch_10' and details['eval_epoch']==10 and details['no_ema'] is False
        assert Path(details['ckpt_path']).resolve()==Path(meta['ckpt_path']).resolve()
        assert Path(details['hrm_hf_export_dir']).resolve()==hf.resolve()
        source = Path(job['log_dir'])/'merged_metrics.json'
        metrics = load(source)
        assert metrics['euroeval/epoch']==10 and metrics.get('euroeval/train_step') in (None,0,STEP)
        value = metrics[key]
        assert type(value) in (int,float) and 0 <= value <= 100
        logs = [p for p in (source.parent/'server.log',source.parent/'euroeval.log',source.parent/'merge_and_wandb_sync.log') if p.exists()]
        prepared.append((dataset,{key:value,'euroeval/epoch':10.0,'euroeval/train_step':STEP}))
        evidence.append(dict(dataset=dataset,key=key,value_unchanged=value,source=str(source.resolve()),
            source_sha256=file_hash(source),original_step=metrics.get('euroeval/train_step'),job=job,
            log_pins={str(p.resolve()):file_hash(p) for p in logs}))
    assert len(prepared)==sum(k.startswith('euroeval/') for k in keys)
    receipt = dict(epoch=10,step=STEP,ema=True,operation='copy unchanged scores; bind checkpoint metadata from completed export/eval plan and checkpoint state',
        original_artifacts_modified=False,wandb_modified=False,plan=str(PLAN.resolve()),plan_sha256=file_hash(PLAN),
        export_job=export,checkpoint_state=state,checkpoint_state_path=str(state_path.resolve()),checkpoint_state_sha256=file_hash(state_path),
        hf_export=str(hf.resolve()),hf_metadata_pins={str(p.resolve()):file_hash(p) for p in
            (hf/'config.json',hf/'tokenizer_config.json',hf/'chat_template.jinja')},metrics=evidence)
    for dataset, metrics in prepared:
        write_json(root/dataset/'merged_metrics.json', metrics)
    receipt['output_pins'] = {str(p.relative_to(root)):file_hash(p) for p in root.glob('*/merged_metrics.json')}
    write_json(root/'provenance.json',receipt)
    print(root.resolve())


if __name__=='__main__':
    build()
