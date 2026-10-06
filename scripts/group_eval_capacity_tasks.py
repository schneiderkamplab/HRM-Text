"""Consolidate translated variants with the same generation contract for calibration."""
import copy
import hashlib
import json
from pathlib import Path
from collections import defaultdict
from dfm12.io import load, write_json

ROOT=Path('data/dfm13/xl3143-all-task-calibration')

def family(task):
    action,name=task['action'],task['name']
    if action=='eval_dfm':
        for prefix in ('gec_dala','dala'):
            if name==prefix or name.startswith(prefix+'_'):return prefix
    if action=='eval_euroeval':
        for prefix in ('multi-ifeval','multi-wiki-qa','winogrande','hellaswag','scala'):
            if name==prefix or name.startswith(prefix+'-'):return prefix
    return name

def main():
    manifest=load(ROOT/'manifest.json')
    judge=load(ROOT/'judge-rows.json')
    groups=defaultdict(list)
    for task in manifest['tasks']:
        if task['key']==judge['key']:task={**task,**judge}
        contract=sorted({(r['endpoint'],r['payload'].get('max_tokens'),
                          r['payload'].get('temperature',0),bool(r['payload'].get('tools')))
                         for r in task['rows']},key=str)
        groups[(task['action'],family(task),json.dumps(contract),task['utilization'])].append(task)
    tasks=[]
    for (action,name,contract,util),variants in groups.items():
        out=copy.deepcopy(variants[0])
        if len(variants)>1:
            out['key']=action+':'+name+'-shared-'+hashlib.sha256(contract.encode()).hexdigest()[:6]
        out['members']=[t['key'] for t in variants]
        out['rows']=[]
        # Include each language, its longest request, and its median; do not
        # calibrate each translated task again independently.
        for t in variants:
            rows=sorted(t['rows'],key=lambda r:r['prompt_tokens'])
            indices={0,len(rows)//2,len(rows)-1}
            out['rows'].extend(rows[i] for i in sorted(indices))
        if len(variants)==1:out['rows']=variants[0]['rows']
        out['prompt_p90']=max(t['prompt_p90'] for t in variants)
        tasks.append(out)
    write_json(ROOT/'grouped-manifest.json',dict(tasks=tasks,missing=[],original_task_count=len(manifest['tasks']),
               groups=len(tasks),group_policy='shared action/template family and generation contract; all languages represented'))
    print(len(manifest['tasks']),'tasks ->',len(tasks),'calibration groups')

if __name__=='__main__':main()
