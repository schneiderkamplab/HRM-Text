"""Add semantic metrics to completed current-campaign DaLA artifacts and sync only new keys."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from scripts.merge_dfm_eval_shards import iter_sample_records, semantic_dala_metrics

ROOTS = {
    'epoch_10': (2877261, 10.0, ['logs/dfm_evals/dfm12_multilingual/epoch_10',
                                'logs/dfm_evals/dfm11_XL_epoch10/epoch_10']),
    'step_2900000': (2900000, 10.050805366878901,
                    ['logs/dfm_evals/dfm12_multilingual/step_2900000',
                     'logs/dfm_evals/dfm12_XL_epoch11/step_2900000']),
}


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--sync',action='store_true')
    args=parser.parse_args()
    rows=[]
    for tag,(step,epoch,roots) in ROOTS.items():
        row={'dfm_eval/epoch':epoch,'dfm_eval/train_step':step}
        tasks=[]
        for root in roots:
            for path in sorted(Path(root).glob('*/merged_metrics.json')):
                task=path.parent.name
                if task!='dala' and not task.startswith('dala_'):continue
                before=path.read_bytes(); payload=json.loads(before)
                if payload['epoch']!=epoch:raise ValueError('Checkpoint mismatch')
                inputs=[Path(p) for p in payload['inputs']]
                samples=list(iter_sample_records(inputs))
                if len(samples)!=payload['num_samples']:raise ValueError('Count mismatch')
                language='da' if task=='dala' else task.removeprefix('dala_')
                scores=semantic_dala_metrics(samples,language)
                new={f'dfm_eval/{task}/{k}':v for k,v in scores.items()}
                old=payload['metrics'].copy()
                for k,v in new.items():
                    if k in old and old[k]!=v:raise ValueError('Version collision: '+k)
                payload['metrics'].update(new)
                assert all(payload['metrics'][k]==v for k,v in old.items())
                backup=path.with_name('merged_metrics.before-semantic-v1.json')
                if not backup.exists():backup.write_bytes(before)
                if path.read_bytes()!=before:raise ValueError('Concurrent merge changed artifact')
                with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as f:
                    json.dump(payload,f,indent=2);f.flush();os.fsync(f.fileno());temp=f.name
                os.replace(temp,path)
                row.update(new);tasks.append(task)
                print(tag,task,'F1',round(scores['semantic_v1/macro_f1']*100,2),flush=True)
        rows.append(row)
        print(tag,'completed tasks rescored:',len(tasks),flush=True)
    receipt=Path('logs/diagnostics/epoch10_dala_label_formats/semantic_v1_rows.json')
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(rows,indent=2)+'\n')
    if args.sync:
        import wandb
        run=wandb.init(entity='peter-sk-sdu',project='DFM5',
            id='dfm8-xl-from-dfm6-dfm7-epoch5-clean-full',resume='must')
        try:
            run.define_metric('dfm_eval/epoch')
            for key in sorted(set().union(*(set(row) for row in rows))-{'dfm_eval/epoch'}):
                run.define_metric(key,step_metric='dfm_eval/epoch',summary='last')
            for row in rows:
                if len(row)>2:run.log(row,commit=True)
        finally:run.finish()


if __name__=='__main__':main()
