"""Private W4 admission parser: retain proven parsing for only gate signals."""
import asyncio
from pathlib import Path
from types import FunctionType
from . import wave4_batched_runtime as previous
from .multilingual_quarter import admission_metrics as original_metrics
from .io import load,file_hash

NAMES=('vllm:kv_cache_usage_perc','vllm:gpu_cache_usage_perc','vllm:num_requests_waiting')


def admission_metrics(text):
    selected=[]
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('{'):
            # Quoted-name OpenMetrics extension: retain general parser semantics.
            return original_metrics(text)
        for name in NAMES:
            if line.startswith(name) and len(line)>len(name) and line[len(name)] in '{ \t':
                selected.append(line)
                break
            if line.startswith('# TYPE '+name+' ') or line.startswith('# HELP '+name+' '):
                selected.append(line)
                break
    return original_metrics('\n'.join(selected)+'\n')


def controller(owner=None):
    c=previous.controller(owner)
    if owner is not None:
        from .multilingual_quarter import AdmissionGate
        if c.AdmissionGate.admit.__globals__ is AdmissionGate.admit.__globals__:
            raise ValueError('Private admission globals required')
        c.AdmissionGate.admit.__globals__['admission_metrics']=admission_metrics
        original_write=c.write_json
        def write(path,value):
            if path.name=='runtime.json':
                value=dict(value,admission_parser_runtime_module='dfm12.wave4_admission_fast')
            return original_write(path,value)
        c.write_json=write
    return c


async def run(root,launch_mode):
    root=Path(root);manifest=load(root/'manifest.json')
    if (manifest.get('admission_parser_runtime_module')!='dfm12.wave4_admission_fast'
            or manifest['implementation_pins'].get(str(Path(__file__).resolve()))!=file_hash(__file__)):
        raise ValueError('Explicit fast-admission successor pin required')
    # Rebind only private run globals; original batch verification remains intact.
    runner=FunctionType(previous.run.__code__,dict(previous.run.__globals__,controller=controller),
                        previous.run.__name__,previous.run.__defaults__,previous.run.__closure__)
    await runner(root,launch_mode)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    p.add_argument('--launch-mode',choices=['independent','completed'],required=True)
    a=p.parse_args();asyncio.run(run(a.root,a.launch_mode))
