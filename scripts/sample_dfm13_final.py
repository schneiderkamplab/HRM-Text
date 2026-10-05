"""Wait for the final verified composition, sample one epoch, and scan bounds."""
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import yaml
from dfm12.io import load, write_json, lock, file_hash
from dfm12.build_training import combine, FIELDS
from scripts.assemble_dfm13_additions import verify_assembly
from scripts.assemble_dfm13_final_successor import ROOT as ASSEMBLY

ROOT=Path('data/dfm13/sampling-20261005-v1')
OUTPUT=Path('data/sampled_dfm13')
STAGING=Path('data/sampled_dfm13.building-20261005-v1')
RECONCILIATION=Path('data/dfm13/all-source-finalization-20261004-v1/sampling-reconciliation.json')


def validate_sample(root):
    meta=load(root/'metadata.json')
    tokens=np.load(root/'tokens.npy',mmap_mode='r')
    vocab=meta['tokenizer_info']['vocab_size']
    if tokens.ndim!=1 or tokens.dtype.kind not in 'iu':raise ValueError('Invalid token array')
    for start in range(0,len(tokens),8_000_000):
        chunk=tokens[start:start+8_000_000]
        if np.any(chunk<0) or np.any(chunk>=vocab):raise ValueError('Token outside vocabulary')
    arrays={k:np.load(root/'epoch_0'/(k+'.npy'),mmap_mode='r') for k in FIELDS}
    n=len(arrays['inst_len']);total=0
    if any(a.ndim!=1 or len(a)!=n or a.dtype.kind not in 'iu' for a in arrays.values()):
        raise ValueError('Index shape/dtype mismatch')
    for start in range(0,n,1_000_000):
        a={k:v[start:start+1_000_000] for k,v in arrays.items()}
        if any(np.any(v<0) for v in a.values()):raise ValueError('Negative index')
        for prefix in ('inst','resp'):
            pos=a[prefix+'_start'];length=a[prefix+'_len']
            if np.any(pos>len(tokens)) or np.any(length>len(tokens)-pos):raise ValueError('Token bounds')
        if np.any(a['resp_len']<2) or np.any(a['inst_len']>meta['max_seq_len']) or np.any(a['resp_len']>meta['max_seq_len']-a['inst_len']):
            raise ValueError('Context or response length')
        total+=int(a['inst_len'].sum())+int(a['resp_len'].sum())
    if total!=meta['total_length']:raise ValueError('Token total mismatch')
    return dict(rows=n,stored_tokens=len(tokens),epoch_tokens=total,max_seq_len=meta['max_seq_len'],
                full_token_vocabulary_scan=True,full_index_bounds_scan=True)


def run():
    os.chdir(Path(__file__).resolve().parents[1])
    with lock(ROOT/'.lock'):
        while True:
            ref=load('data/dfm13/authoritative-additions.json')
            comp=load('data/dfm13/authoritative-composition.json')
            ready=(Path(ref['root']).resolve()==ASSEMBLY.resolve() and
                   comp['additions_sha256']==ref['assembly_sha256'])
            reconciliation=load(RECONCILIATION) if RECONCILIATION.exists() else {}
            reconciled=(reconciliation.get('all_specifications_disposed') is True and
                        reconciliation.get('sampling_authorized') is True and
                        reconciliation.get('assembly_sha256')==ref['assembly_sha256'])
            write_json(ROOT/'progress.json',dict(phase='waiting_final_verified_composition',ready=ready,
                        specification_reconciled=reconciled,reconciliation_path=str(RECONCILIATION),
                        epochs=1,output=str(OUTPUT),time=time.time()))
            if ready and reconciled:break
            time.sleep(30)
        root=Path(comp['root']);composition=load(root/'composition.json')
        if file_hash(root/'composition.json')!=comp['composition_sha256']:raise ValueError('Composition drift')
        verify_assembly(ASSEMBLY)
        from scripts.compose_dfm13_full_inheritance import inheritance
        inheritance(Path('data/dfm13/dfm12-full-inheritance-20261004-v2/handoff.json'))
        base=Path(composition['base']['path']).resolve()
        if base.name!='sampled_dfm11':raise ValueError('Must not duplicate historical DFM12')
        mapping=load(root/'repeat_mapping.json')
        if file_hash(root/'repeat_mapping.json')!=composition['repeat_mapping_sha256']:raise ValueError('Repeat policy drift')
        policy=ROOT/'prefix_config.yaml'
        policy.write_text(yaml.safe_dump([dict(prefix=k,repeat=v,long_context='drop') for k,v in sorted(mapping.items())]))
        sampled=ROOT/'sampled_additions'
        command=[sys.executable,'data_io/sample_tokenized.py',f'tokenized_path={Path(composition["tokenized_tree"]).resolve()}',
                 f'output_path={sampled.resolve()}',f'prefix_config_path={policy.resolve()}',
                 'epochs=1','concat_workers=1','skip_unmatched=true','default_long_context=drop',
                 'context_size='+str(load(base/'metadata.json')['max_seq_len'])]
        contract=dict(composition_sha256=comp['composition_sha256'],assembly_sha256=ref['assembly_sha256'],
                      reconciliation_sha256=file_hash(RECONCILIATION),
                      epochs=1,command=command,output=str(OUTPUT.resolve()),base=str(base))
        if (ROOT/'contract.json').exists() and load(ROOT/'contract.json')!=contract:raise ValueError('Sampling input drift')
        write_json(ROOT/'contract.json',contract)
        expected_rows=expected_tokens=0
        for part in sorted(Path(composition['tokenized_tree']).iterdir()):
            if not part.is_dir():continue
            matches=[v for k,v in mapping.items() if part.name.startswith(k)]
            if len(matches)!=1:raise ValueError('Missing or ambiguous source repeat')
            inst=np.load(part/'inst_len.npy',mmap_mode='r')
            resp=np.load(part/'resp_len.npy',mmap_mode='r')
            expected_rows+=len(inst)*matches[0]
            expected_tokens+=(int(inst.sum())+int(resp.sum()))*matches[0]
        write_json(ROOT/'progress.json',dict(phase='sampling_additions',time=time.time()))
        if not (sampled/'metadata.json').exists():subprocess.run(command,check=True)
        additions=validate_sample(sampled)
        if additions['rows']!=expected_rows or additions['epoch_tokens']!=expected_tokens:
            raise ValueError('Sampling dropped/truncated targets or changed repeats')
        write_json(ROOT/'additions-validation.json',additions)
        write_json(ROOT/'progress.json',dict(phase='combining_with_dfm11',time=time.time()))
        if np.load(base/'tokens.npy',mmap_mode='r').dtype!=np.load(sampled/'tokens.npy',mmap_mode='r').dtype:
            raise ValueError('Token store dtype mismatch')
        if OUTPUT.exists():raise ValueError('Final sampled destination already exists; verify independently, never overwrite')
        if not (STAGING/'metadata.json').exists():combine(base,sampled,STAGING,1)
        write_json(ROOT/'progress.json',dict(phase='full_output_scan',time=time.time()))
        result=validate_sample(STAGING)
        base_rows=len(np.load(base/'epoch_0/inst_len.npy',mmap_mode='r'))
        base_total=sum(int(np.load(base/'epoch_0'/(k+'.npy'),mmap_mode='r').sum()) for k in ('inst_len','resp_len'))
        if result['rows']!=base_rows+expected_rows or result['epoch_tokens']!=base_total+expected_tokens:
            raise ValueError('Merged epoch differs from exact base epoch0 plus weighted additions')
        if file_hash(root/'composition.json')!=comp['composition_sha256']:raise ValueError('Composition changed during sampling')
        if file_hash(RECONCILIATION)!=contract['reconciliation_sha256']:raise ValueError('Reconciliation changed')
        STAGING.rename(OUTPUT)
        write_json(ROOT/'completion.json',dict(complete=True,**contract,validation=result,training_changed=False))
        print('VERIFIED_SAMPLED',result,flush=True)


if __name__=='__main__':run()
