"""Record explicit provisional manual source assessments, never model verdicts."""
import argparse,re
from pathlib import Path
from dfm12.io import rows,load,file_hash,lock
from scripts.dfm16_story_calibration import immutable,sha
from scripts.dfm16_staged_stories import validate_source,initial_request
from scripts.dfm16_staged_validation import verify_freeze
from scripts.dfm16_staged_validation_campaign import ROOT

CHANGES={'en':['Add a brief description of the setting without changing the events','Describe the characters’ feelings more clearly without changing the events'],
'ja':['出来事を変えずに、周囲の様子を短く描写してください','出来事を変えずに、登場人物の気持ちをよりはっきり描写してください']}

def record(root,language,annotations):
    verify_freeze(root,language)
    path=root/language/'validation/families.jsonl'
    selected=list(rows(path))
    for assessment in annotations:
        index=assessment['index']; raw=selected[index]; task=raw['task']
        identifier=f'{language}-{index:04d}'
        result=dict(id=identifier,index=index,family=raw['family'],task=task,
            sample_sha256=file_hash(path),source_sha256=sha(raw['text']),
            reviewer='assistant-manual',provisional=True,assessment=assessment)
        if assessment['status']=='clear':
            source=dict(text=raw['text'],language=language,review='clear',reviewer='assistant-manual',provisional=True,
                sha256=sha(raw['text']),facts=[t.strip() for t in re.split(r'(?<=[.!?])\s+|(?<=。)',raw['text']) if t.strip()],
                narration=assessment.get('narration','unspecified'),preconditions=assessment['reason'])
            row=dict(id=identifier,audit_id=identifier,language=language,task=task,variant=index%3,family=raw['family'],source=source,
                background_seed=raw['text'],provenance=raw['provenance'],slots_reviewed=True,cohort='validation',arm='odin')
            for key in ('topic','question','reference_answer','answer_support'):
                if key in assessment:row[key]=assessment[key]
            if task=='revision':row['changes']=CHANGES[language]
            validate_source(row);initial_request(row);result['generation_input']=row
        elif assessment['status']!='rejected':raise ValueError('explicit source status required')
        immutable(root/language/'validation/source-review'/f'{index:04d}.json',result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--language',required=True);p.add_argument('--annotations',type=Path,required=True);p.add_argument('--root',type=Path,default=ROOT)
    args=p.parse_args()
    with lock(args.root/'.controller.lock'):record(args.root,args.language,load(args.annotations))
