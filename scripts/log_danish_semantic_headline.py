"""Publish a complete, equal-family Danish semantic headline from Inspect logs."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evaluation.danish_semantic_reasoning_eval import FAMILIES,parse_answer
from inspect_ai.log import read_eval_log

PREFIX='headline_danish_semantic_v1'

def aggregate(model,manifest):
    for path, expected_hash in manifest.get('software_sha256', {}).items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected_hash, f'Frozen evaluation code changed: {path}'
    data=Path(manifest['data_dir']);raw=(data/'records.jsonl').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==manifest['records_sha256'],'Data changed after freeze'
    records=[json.loads(line) for line in raw.splitlines()]
    metrics={};details={}
    for family in FAMILIES:
        expected={r['id']:r for r in records if r['family']==family and (family!='danwic' or r['subset']=='danwic_poly_selection')}
        paths=sorted((Path(model['result_root'])/family/'inspect').glob('*.eval'))
        if len(paths)!=1:raise ValueError(f'{family}: expected exactly one complete Inspect log, found {len(paths)}')
        log=read_eval_log(paths[0]);assert log.status=='success',f'{family}: failed log'
        assert log.eval.task_args.get('family')==family
        assert len(log.samples or [])==len(expected),f'{family}: incomplete population'
        seen=set();correct=valid=0
        for sample in log.samples:
            sid=str(sample.id);assert sid in expected and sid not in seen,'unexpected/duplicate sample'
            seen.add(sid);row=expected[sid]
            assert sample.error is None,'transport/scoring error is not a valid model answer'
            assert sample.target==row['target'],'gold mismatch'
            assert sample.input==row['input'],'prompt mismatch'
            answer=parse_answer(sample.output.completion,row['labels'])
            valid+=answer is not None;correct+=answer==row['target']
        assert seen==set(expected)
        accuracy=correct/len(expected)
        metrics.update({f'{PREFIX}/{family}':accuracy,f'{PREFIX}/{family}/count':len(expected),f'{PREFIX}/{family}/valid_format':valid/len(expected)})
        details[family]={'correct':correct,'valid':valid,'count':len(expected),'accuracy':accuracy,'log':str(paths[0]),'sha256':hashlib.sha256(paths[0].read_bytes()).hexdigest()}
    metrics[f'{PREFIX}/overall']=sum(details[x]['accuracy'] for x in FAMILIES)/7
    metrics[f'{PREFIX}/family_count']=7
    metrics[f'{PREFIX}/sample_count']=sum(x['count'] for x in details.values())
    return metrics,details

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--model',required=True);p.add_argument('--no-wandb',action='store_true');a=p.parse_args()
    manifest=json.loads(a.manifest.read_text());model=manifest['models'][a.model]
    metrics,details=aggregate(model,manifest)
    report=Path(model['result_root'])/'headline.json'
    result={'model':model,'metrics':metrics,'tasks':details,'records_sha256':manifest['records_sha256'],'publication':'pending'}
    report.write_text(json.dumps(result,indent=2))
    if not a.no_wandb:
        import wandb
        from scripts.wandb_writer_lock import wandb_writer_lock
        with wandb_writer_lock(model['wandb_run_id']):
            run=wandb.init(entity='peter-sk-sdu',project='DFM5',id=model['wandb_run_id'],name=model['display_name']+' — Danish semantics v1',resume='allow',config={'evaluation_protocol':PREFIX,'source':model,'dataset_sha256':manifest['records_sha256']})
            for key in metrics:run.define_metric(key)
            run.log(metrics,commit=True);run.finish()
        result['publication']='wandb_finished';report.write_text(json.dumps(result,indent=2))
    print(json.dumps(metrics))
if __name__=='__main__':main()
