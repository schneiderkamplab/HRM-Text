"""Freeze raw semantic verdict extraction independently of metadata validation."""
import argparse
import importlib.util
from pathlib import Path

PATH=Path(__file__).with_name('dfm13_arena_audit.py')
spec=importlib.util.spec_from_file_location('_arena_comparison_base',PATH)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)


def decision(outcome,stages):
    if outcome['status']=='complete':
        return outcome['result']['verdict'],'validated_final'
    if stages.get('adjudicator',{}).get('verdict') in base.DISPOSITIONS:
        return stages['adjudicator']['verdict'],'unvalidated_adjudicator'
    a=stages.get('neutral',{}).get('verdict');b=stages.get('critic',{}).get('verdict')
    if a in base.DISPOSITIONS and a==b:return a,'unvalidated_initial_consensus'
    return None,'unresolved_initial_disagreement_or_missing'


def extract(root,group):
    root=Path(root).resolve();jobs=[base.strict_json(l) for l in (root/'jobs.jsonl').read_text().splitlines()]
    stages={};pins={}
    for path in (root/'raw').glob('*.request.json'):
        response_path=path.with_name(path.name.replace('.request.','.response.'))
        if not response_path.exists():continue
        request=base.load(path);metadata=request['metadata']
        if 'job' not in metadata:continue
        response=base.load(response_path);entry={}
        try:
            envelope=base.strict_json(response['raw_body_utf8']);choice=envelope['choices'][0]
            parsed=base.strict_json(choice['message']['content'])
            entry=dict(verdict=parsed.get('verdict') if parsed.get('verdict') in base.DISPOSITIONS else None,
                       parsed=parsed,finish_reason=choice.get('finish_reason'))
        except Exception as exc:entry['parse_error']=repr(exc)
        stage_path=root/'stages'/f"{metadata['job']}-{metadata['stage']}.json"
        stage=base.load(stage_path)
        entry.update(validation_status=stage['status'],validation_error=stage.get('error'),raw_response_path=str(response_path))
        key=(metadata['job'],metadata['stage'])
        if key in stages:raise ValueError('Multiple attempts require explicit selection')
        stages[key]=entry
        for p in (path,response_path,stage_path):pins[str(p)]=base.file_hash(p)
    records=[]
    for job in jobs:
        if job['thinking']:continue
        path=root/'outcomes'/f"{job['id']}.json";outcome=base.load(path)
        raw={role:stages[(job['id'],role)] for role in ('neutral','critic','adjudicator') if (job['id'],role) in stages}
        verdict,derivation=decision(outcome,raw)
        records.append(dict(source_id=job['source_id'],group=group,validated_status=outcome['status'],
            validated_verdict=outcome.get('result',{}).get('verdict') if outcome.get('result') else None,
            semantic_verdict=verdict,derivation=derivation,stages=raw))
        pins[str(path)]=base.file_hash(path)
    for name in ('manifest.json','seal.json','jobs.jsonl'):pins[str(root/name)]=base.file_hash(root/name)
    return records,pins


def freeze(output,heldout,controls,simple):
    output=Path(output)
    with base.lock(output.with_suffix('.lock')):
        if output.exists():raise ValueError('No overwrite of frozen extraction')
        for root in (Path(heldout),Path(simple)):
            receipt=base.load(root/'predictions-frozen.json')
            for section in ('artifacts','outcomes'):
                for p,h in receipt.get(section,{}).items():
                    if base.file_hash(p)!=h:raise ValueError('Prediction freeze drift')
        a,pins=extract(heldout,'heldout');b,more=extract(controls,'development');pins.update(more)
        simple_records=[]
        for path in (Path(simple)/'outcomes').glob('*.json'):
            record=base.load(path);simple_records.append(record);pins[str(path.resolve())]=base.file_hash(path)
        pins[str(Path(__file__).resolve())]=base.file_hash(Path(__file__))
        base.write_json(output,dict(version='semantic-extraction-v1',references_read=False,v4=a+b,
            simple=simple_records,pins=pins,policy='Validated final else parseable adjudicator else unanimous '
            'parseable initial verdict; otherwise unresolved. Unvalidated consensus is NOT adjudication '
            'or semantic certification. Preserve every raw review and validation error separately.'))
    return base.file_hash(output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--heldout',type=Path,required=True);p.add_argument('--controls',type=Path,required=True)
    p.add_argument('--simple',type=Path,required=True);a=p.parse_args()
    print(freeze(a.output,a.heldout,a.controls,a.simple))
