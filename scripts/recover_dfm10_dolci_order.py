"""Recover case-sensitive dictionary insertion order from pinned HF raw DOLCI."""
import argparse
import json
import os
from itertools import zip_longest
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.acquire_dfm10_hf import save,sha


def restore_mapping_order(published, raw):
    """Keep published values/list order; recover only raw HF mapping order."""
    if isinstance(published, dict):
        if not isinstance(raw, dict) or published.keys() != raw.keys():
            raise ValueError('Raw/published mapping schema differs')
        return {k: restore_mapping_order(published[k], raw[k]) for k in raw}
    if isinstance(published, list):
        if not isinstance(raw, list) or len(published) != len(raw):
            raise ValueError('Raw/published list schema differs')
        return [restore_mapping_order(p, r) for p, r in zip(published, raw)]
    return published


def recover(work):
    stage=work/'dolci_order_recovery';stage.mkdir(exist_ok=True)
    if (stage/'verified.json').exists():
        receipt=json.loads((stage/'verified.json').read_text())
        if receipt['hf_inputs_sha256']!=sha(stage/'hf-inputs.json'):
            raise ValueError('HF recovery provenance changed')
        for item in receipt['tasks'].values():
            if sha(Path(item['path']))!=item['sha256']:
                raise ValueError('Recovered DOLCI payload changed')
        return
    lock=json.loads((ROOT/'config/data/dfm7_hf_rebuild.json').read_text())
    selected=[v for v in lock['inputs'].values() if v.get('friendly') in ('dolci_instruct_sft_tool_use','dolci_instruct_sft_tool_use_sa')]
    if len(selected)!=7:raise ValueError('Expected seven pinned HF DOLCI inputs')
    input_root=stage/'raw'
    for item in selected:
        source=Path(item['path']).resolve(strict=True)
        if not source.is_relative_to((ROOT/'data/rebuild_hf_dfm/later-acquisition/downloads').resolve()):
            raise ValueError('DOLCI raw source is not an isolated HF acquisition')
        if sha(source)!=item['sha256']:raise ValueError('DOLCI HF input changed')
        target=input_root/item['friendly']/item['rel'];target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.symlink_to(source)
    save(stage/'hf-inputs.json',selected)
    scripts=stage/'code/scripts';scripts.mkdir(parents=True,exist_ok=True)
    (scripts/'__init__.py').write_text('')
    for name in ['repair_dolci_tool_use.py','prepare_dfm7_special_sources.py','build_dolci_tool_use_tokenizer_staging.py']:
        (scripts/name).write_bytes(subprocess.check_output(['git','show','ccbb215:scripts/'+name],cwd=ROOT))
    repaired=stage/'repaired'
    if not (stage/'converted.json').exists():
        subprocess.run([sys.executable,str(scripts/'repair_dolci_tool_use.py'),'--input-root',str(input_root),'--output-root',str(repaired),'--workers','7','--force'],check=True,cwd=stage)
        save(stage/'converted.json',{'revision':'ccbb215','code':{p.name:sha(p) for p in scripts.glob('*.py')}})
    split=stage/'split'
    if not (split/'staging_manifest.json').exists():
        subprocess.run([sys.executable,str(scripts/'build_dolci_tool_use_tokenizer_staging.py'),'--input-root',str(repaired),'--output-root',str(split)],check=True,cwd=stage)
    original=json.loads((ROOT/'config/data/dfm10_hf_rebuild.json').read_text())
    tasks=[t for t in original['tasks'] if t['component']=='dolci_tool_use_repaired'];outputs={}
    for task in tasks:
        name=task['task'];relative=name.split('__',1)[1].replace('__','/')
        path=split/'dolci_tool_use_repaired'/relative
        published=work/'sources'/name
        cfg=json.loads((work/'hf_recipe.json').read_text())
        expected=next(t['sha256'] for t in cfg['tasks'] if t['task']==name)
        if sha(published)!=expected:raise ValueError('Published HF payload changed')
        restored=stage/'restored'/name;restored.parent.mkdir(exist_ok=True)
        with published.open() as pf,path.open() as rf,restored.open('w') as out:
            for p,r in zip_longest(pf,rf):
                if p is None or r is None:raise ValueError('Raw/published row count differs')
                value=restore_mapping_order(json.loads(p),json.loads(r))
                out.write(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')
        path=restored
        digest=sha(path)
        if digest!=task['sha256'] or path.stat().st_size!=task['source_size']:
            raise ValueError('Recovered DOLCI differs from historical source: '+name)
        outputs[name]={'path':str(path),'sha256':digest,'bytes':path.stat().st_size}
    if len(outputs)!=13:raise ValueError('Recovered DOLCI task inventory differs')
    save(stage/'verified.json',{'status':'source_sha256_matched','tasks':outputs,'hf_inputs_sha256':sha(stage/'hf-inputs.json'),'converter_revision':'ccbb215'})
    print('All 13 DOLCI sources match historical SHA-256 exactly',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    recover(p.parse_args().work.resolve())
