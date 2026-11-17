"""Restore historical capped tokenization for DeepDive and repaired DOLCI."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.acquire_dfm10_hf import sha,save
from scripts.replay_dfm_serial import equal_arrays
from scripts.rebuild_dfm5 import link
COMPONENTS={'deepdive','dolci_tool_use_repaired'}
FIELDS=('tokens','inst_start','inst_len','resp_start','resp_len')


def run(work, config):
    cfg=json.loads(config.read_text())
    tasks=[t for t in cfg['tasks'] if t['component'] in COMPONENTS]
    if len(tasks)!=14:raise ValueError('Expected DeepDive + 13 DOLCI tasks')
    from scripts.recover_dfm10_dolci_order import recover
    recover(work)
    recovery=work/'dolci_order_recovery/verified.json'
    restored=json.loads(recovery.read_text())['tasks']
    stage=work/'capped_tokenization_order_restored';sources=stage/'inputs';sources.mkdir(parents=True,exist_ok=True)
    policy={'max_seq_len':4096,'preserve_first_user':False,'adapter_sha256':sha(work/'native_adapter.py'),
            'template_sha256':sha(work/'chat_template.jinja'),'dolci_recovery_sha256':sha(recovery),
            'tasks':{t['task']:restored.get(t['task'],t)['sha256'] for t in tasks}}
    policy_path=stage/'policy.json'
    if policy_path.exists() and json.loads(policy_path.read_text())!=policy:raise ValueError('Capped policy changed')
    save(policy_path,policy)
    if (stage/'published.json').exists():
        saved=json.loads((stage/'published.json').read_text())
        if saved['policy_sha256']!=sha(policy_path):raise ValueError('Published policy changed')
        return
    for task in tasks:
        reference=json.loads((ROOT/'data/tokenized_dfm10'/task['task']/'metadata.json').read_text())
        if reference.get('max_seq_len')!=4096 or reference.get('preserve_first_user') is not False:
            raise ValueError('Historical capped settings differ')
        source=Path(restored[task['task']]['path']) if task['task'] in restored else work/'sources'/task['task']
        if sha(source)!=policy['tasks'][task['task']]:raise ValueError('Capped HF source changed')
        link(source,sources/task['task'],[work])
    output=stage/'tokenized'
    subprocess.run([sys.executable,str(work/'native_adapter.py'),str(sources),'-o',str(output),
        '--tokenizer-path',str(work/'tokenizer/tokenizer.json'),'--chat-template',str(work/'chat_template.jinja'),
        '--workers','14','--max-seq-len','4096'],check=True)
    findings=[]
    for task in tasks:
        name=task['task']
        try:
            for f in FIELDS:
                equal_arrays(np.load(output/name/(f+'.npy'),mmap_mode='r'),
                             np.load(ROOT/'data/tokenized_dfm10'/name/(f+'.npy'),mmap_mode='r'),name+'/'+f)
            findings.append({'task':name,'status':'matched'})
        except ValueError as exc:
            findings.append({'task':name,'status':'mismatch','error':str(exc)})
    save(stage/'comparison.json',findings)
    if any(f['status']!='matched' for f in findings):raise ValueError('Capped token comparison failed; see comparison.json')
    archive=stage/'uncapped-history';archive.mkdir(exist_ok=True)
    for task in tasks:
        target=work/'tokenized'/task['task'];fixed=(output/task['task']).resolve()
        if target.is_symlink() and target.resolve()==fixed:continue
        if target.exists():target.rename(archive/task['task'])
        target.symlink_to(fixed,target_is_directory=True)
    save(stage/'published.json',{'status':'matched','tasks':14,'arrays_per_task':5,'policy_sha256':sha(policy_path)})
    print('Restored and exactly verified all 14 capped task outputs',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    a=p.parse_args();run(a.work.resolve(),a.config.resolve())
