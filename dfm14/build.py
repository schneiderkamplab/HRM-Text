"""Tokenize additions, remove exact inherited targets and sample full DFM14."""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import yaml

from dfm12.io import file_hash, load, lock, write_json
from dfm12.build_training import combine, FIELDS
from dfm14.release import ROOT, EXPORT, prepare, package, upload
from dfm14.release_inputs import checked

BASE = Path('data/sampled_dfm13')
OUTPUT = Path('data/sampled_dfm14')
TOKENS = ROOT/'tokenized'
TREE = ROOT/'tokenized_selected'


def arrays(path):
    return {k:np.load(path/(k+'.npy'),mmap_mode='r') for k in FIELDS}


def signature(tokens, indices):
    """Cheap vectorized shortlist only; every match requires full token equality."""
    a = {k:np.asarray(v,dtype=np.uint64) for k,v in indices.items()}
    h = a['inst_len'] * np.uint64(0x9E3779B185EBCA87) ^ a['resp_len']
    for prefix in ('inst','resp'):
        start, length = a[prefix+'_start'], a[prefix+'_len']
        if np.any(length == 0):
            raise ValueError('Empty target or prompt')
        for offset in (0,1,2,3,4,5,6,7):
            # Template suffixes and classification labels are often identical.
            # Probe throughout the content, not just the chat-format suffix.
            position = start+(length-1)*offset//7
            h = (h ^ tokens[position].astype(np.uint64)) * np.uint64(0x100000001B3)
    return h


def tokenize(workers):
    info=load(BASE/'metadata.json')['tokenizer_info']
    manifest=load(EXPORT/'manifest.json')
    contract=dict(manifest_sha256=file_hash(EXPORT/'manifest.json'),
        tokenizer={k:file_hash(info[k]) for k in ('tokenizer_path','chat_template_path')})
    done=ROOT/'tokenization.json'
    if done.exists():
        if load(done)['contract']!=contract:
            raise ValueError('Tokenization inputs changed')
        return
    subprocess.run([sys.executable,'scripts/tokenize_chat_template.py',str(ROOT/'training'),
        '-o',str(TOKENS),'--tokenizer-path',info['tokenizer_path'],
        '--chat-template',info['chat_template_path'],'--max-seq-len','4096','--workers',str(workers)],check=True)
    counts=defaultdict(lambda:dict(rows=0,tokens=0,parts=[]))
    for part in sorted(TOKENS.iterdir()):
        if not part.is_dir():
            continue
        source=part.name.split('__')[0]
        a=arrays(part)
        n=len(a['inst_len'])
        if any(len(v)!=n for v in a.values()):
            raise ValueError('Invalid tokenizer arrays')
        counts[source]['rows']+=n
        counts[source]['tokens']+=int(a['inst_len'].sum())+int(a['resp_len'].sum())
        counts[source]['parts'].append(str(part.resolve()))
    for entry in manifest['packages']:
        if counts[entry['name']]['rows']!=entry['rows']:
            raise ValueError('Tokenization changed accepted population: '+entry['name'])
    write_json(done,dict(contract=contract,sources=dict(counts)))


def sources():
    tokenized=load(ROOT/'tokenization.json')['sources']
    result=[]
    for package in load(EXPORT/'manifest.json')['packages']:
        result.append(dict(package,**tokenized[package['name']]))
    dala=load('data/dfm14/local-audited-dala-additions.json')
    if not dala['publication_verified'] or not dala['train_only']:
        raise ValueError('DaLA release not verified')
    checked(dala['registry']['path'],dala['registry']['sha256'])
    info=load(BASE/'metadata.json')['tokenizer_info']
    for entry in dala['additions']:
        if entry['split']!='train' or not entry['uploaded'] or not entry['hf_revision']:
            raise ValueError('Invalid DaLA training component')
        for field,key in [('tokenizer','tokenizer_path'),('template','chat_template_path')]:
            if entry[field]['sha256']!=file_hash(info[key]):
                raise ValueError('DaLA tokenizer/template differs from inherited data')
        parts=sorted({str(Path(path).parent) for path in entry['array_pins']})
        for path,pin in entry['array_pins'].items():
            sha=pin if isinstance(pin,str) else pin['sha256']
            checked(path,sha)
        result.append(dict(name=entry['name'],repeat=entry['repeat'],rows=entry['rows'],
            tokens=entry['tokens'],parts=parts,hf_repo_id=entry['hf_repo_id'],hf_revision=entry['hf_revision']))
    return result


def deduplicate(entries):
    """Keep inherited occurrences unchanged, omit identical added supervised pairs."""
    receipt=ROOT/'deduplication.json'
    contract=dict(base_metadata_sha256=file_hash(BASE/'metadata.json'),sources=entries)
    if receipt.exists():
        done=load(receipt)
        if done['contract']!=contract:
            raise ValueError('Deduplication inputs changed')
        return done
    parts=[]; hashes=[]; offset=0
    for entry in entries:
        for number,value in enumerate(entry['parts']):
            path=Path(value); a=arrays(path); t=np.load(path/'tokens.npy',mmap_mode='r')
            h=signature(t,a); hashes.append(h)
            parts.append(dict(source=entry['name'],path=str(path),offset=offset,rows=len(h),number=number))
            offset+=len(h)
    all_hashes=np.concatenate(hashes); del hashes
    order=np.argsort(all_hashes,kind='stable'); sorted_hashes=all_hashes[order]
    excluded=np.zeros(offset,dtype=bool)
    part_ends=np.array([p['offset']+p['rows'] for p in parts])
    cache={}

    def target(index):
        pi=int(np.searchsorted(part_ends,index,side='right')); part=parts[pi]
        if pi not in cache:
            path=Path(part['path']);cache[pi]=(arrays(path),np.load(path/'tokens.npy',mmap_mode='r'))
        a,t=cache[pi];row=index-part['offset']
        return a,t,row

    tokens=np.load(BASE/'tokens.npy',mmap_mode='r')
    epochs=sorted(BASE.glob('epoch_[0-9]*'))
    for epoch in epochs:
        base=arrays(epoch);n=len(base['inst_len'])
        for start in range(0,n,250000):
            values={k:v[start:start+250000] for k,v in base.items()}
            h=signature(tokens,values)
            left=np.searchsorted(sorted_hashes,h,side='left');right=np.searchsorted(sorted_hashes,h,side='right')
            for row in np.flatnonzero(right>left):
                for index in order[left[row]:right[row]]:
                    if excluded[index]:
                        continue
                    a,t,i=target(int(index))
                    if all(int(a[k][i])==int(values[k][row]) for k in ('inst_len','resp_len')) and all(
                        np.array_equal(t[int(a[p+'_start'][i]):int(a[p+'_start'][i])+int(a[p+'_len'][i])],
                            tokens[int(values[p+'_start'][row]):int(values[p+'_start'][row])+int(values[p+'_len'][row])])
                        for p in ('inst','resp')):
                        excluded[index]=True
            cache.clear()
            if start%5000000==0:
                write_json(ROOT/'progress.json',dict(phase='exact_inherited_target_scan',epoch=epoch.name,
                    done=min(start+250000,n),total=n,excluded=int(excluded.sum()),time=time.time()))
                print('inherited scan',epoch.name,start,'/',n,'excluded',int(excluded.sum()),flush=True)
    TREE.mkdir(parents=True,exist_ok=True)
    summary=defaultdict(lambda:dict(rows=0,tokens=0,excluded=0))
    for part in parts:
        path=Path(part['path']);a=arrays(path)
        mask=~excluded[part['offset']:part['offset']+part['rows']]
        directory=TREE/(part['source']+f'__part-{part["number"]:06d}')
        directory.mkdir(parents=True,exist_ok=True)
        link=directory/'tokens.npy'
        if not link.exists():
            link.symlink_to((path/'tokens.npy').resolve())
        for field,arr in a.items():
            np.save(directory/(field+'.npy'),arr[mask])
        s=summary[part['source']];s['rows']+=int(mask.sum());s['excluded']+=int((~mask).sum())
        s['tokens']+=int(a['inst_len'][mask].sum())+int(a['resp_len'][mask].sum())
    write_json(TREE/'tokenizer_info.json',load(BASE/'metadata.json')['tokenizer_info'])
    result=dict(contract=contract,sources=dict(summary),inherited_exact_targets_removed=int(excluded.sum()),
                inherited_epochs_checked=[p.name for p in epochs],
                comparison='full prompt and response token equality; fingerprint used only as shortlist')
    write_json(receipt,result)
    return result


def selection_policy(entries, *, keep_all=False):
    """Recover retained ordinals without rescanning tokens or modifying originals."""
    original_tree=ROOT/'tokenized_original'
    original_tree.mkdir(parents=True,exist_ok=True)
    policy=[]
    for entry in entries:
        for number,value in enumerate(entry['parts']):
            path=Path(value).resolve()
            name=entry['name']+f'__part-{number:06d}'
            rule=dict(prefix=name,repeat=entry['repeat'],long_context='drop')
            if not keep_all:
                kept=arrays(TREE/name)
                original=arrays(path)
                starts=original['inst_start']
                if np.any(starts[1:]<=starts[:-1]):
                    raise ValueError('Non-unique/non-monotonic original starts: '+str(path))
                indices=np.searchsorted(starts,kept['inst_start'])
                if np.any(indices>=len(starts)) or any(
                    not np.array_equal(original[k][indices],kept[k]) for k in FIELDS):
                    raise ValueError('Selection does not reproduce retained rows: '+name)
                selection=TREE/name/'selection.npy'
                temporary=selection.with_suffix('.tmp.npy')
                np.save(temporary,indices)
                temporary.replace(selection)
                rule['selection_indices_path']=str(selection.resolve())
            link=original_tree/name
            if not link.exists():
                link.symlink_to(path,target_is_directory=True)
            elif link.resolve()!=path:
                raise ValueError('Original source link changed: '+name)
            policy.append(rule)
    write_json(original_tree/'tokenizer_info.json',load(BASE/'metadata.json')['tokenizer_info'])
    return original_tree,policy


def sample(entries,selected):
    sampled=ROOT/'sampled_additions'
    policy=ROOT/'prefix_config.yaml'
    original_tree,policies=selection_policy(entries,
        keep_all=selected.get('inherited_overlap_policy')=='keep_all')
    policy.write_text(yaml.safe_dump(policies))
    if not (sampled/'metadata.json').exists():
        subprocess.run([sys.executable,'data_io/sample_tokenized.py',f'tokenized_path={original_tree.resolve()}',
            f'output_path={sampled.resolve()}',f'prefix_config_path={policy.resolve()}',
            'epochs=3','concat_workers=1','skip_unmatched=true','default_long_context=drop',
            'context_size=4097','min_resp_length=1'],check=True)
    expected_rows=sum(selected['sources'][e['name']]['rows']*e['repeat'] for e in entries)
    expected_tokens=sum(selected['sources'][e['name']]['tokens']*e['repeat'] for e in entries)
    for epoch in range(3):
        a=arrays(sampled/f'epoch_{epoch}')
        if len(a['inst_len'])!=expected_rows or int(a['inst_len'].sum())+int(a['resp_len'].sum())!=expected_tokens:
            raise ValueError('Sampled addition rows/tokens differ from repeats')
    stage=OUTPUT.with_name(OUTPUT.name+'.building')
    if not OUTPUT.exists():
        if not (stage/'metadata.json').exists():
            combine(BASE,sampled,stage,3)
        # Bounds are checked in bounded chunks, including inherited one-token targets.
        token_count=len(np.load(stage/'tokens.npy',mmap_mode='r'))
        for epoch in range(3):
            a=arrays(stage/f'epoch_{epoch}');b=arrays(BASE/f'epoch_{epoch}')
            if len(a['inst_len'])!=len(b['inst_len'])+expected_rows:
                raise ValueError('Combined row count mismatch')
            total=0
            for start in range(0,len(a['inst_len']),1000000):
                v={k:x[start:start+1000000] for k,x in a.items()}
                for prefix in ('inst','resp'):
                    if np.any(v[prefix+'_start']>token_count) or np.any(v[prefix+'_len']>token_count-v[prefix+'_start']):
                        raise ValueError('Combined token index out of bounds')
                if np.any(v['inst_len']+v['resp_len']>4097) or np.any(v['resp_len']==0):
                    raise ValueError('Invalid combined target length')
                total+=int(v['inst_len'].sum())+int(v['resp_len'].sum())
            expected=int(b['inst_len'].sum())+int(b['resp_len'].sum())+expected_tokens
            if total!=expected:
                raise ValueError('Combined token count mismatch')
        stage.rename(OUTPUT)
    return dict(base_tokens_per_epoch=load(BASE/'metadata.json')['total_length'],
        added_tokens_per_epoch=expected_tokens,added_rows_per_epoch=expected_rows,
        total_tokens_per_epoch=load(OUTPUT/'metadata.json')['total_length'],epochs=3)


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--workers',type=int,default=16)
    args=p.parse_args()
    with lock(ROOT/'.build.lock'),lock(ROOT/'.lock'):
        if not (ROOT/'prepared.json').exists():
            prepare(ROOT,args.workers)
        package(ROOT,EXPORT)
        write_json(ROOT/'progress.json',dict(phase='tokenizing',time=time.time()))
        tokenize(args.workers)
        entries=sources()
        write_json(ROOT/'source-inventory.json',entries)
        selected=deduplicate(entries)
        write_json(ROOT/'progress.json',dict(phase='sampling',time=time.time()))
        report=sample(entries,selected)
        write_json(ROOT/'sampling.json',report)
        write_json(ROOT/'progress.json',dict(phase='publishing',time=time.time()))
        upload(EXPORT)
        publication=load(EXPORT/'upload-receipts.json')
        for entry in entries:
            if entry['hf_repo_id'] in publication:
                entry['hf_revision']=publication[entry['hf_repo_id']]['revision']
            if not entry.get('hf_revision'):
                raise ValueError('Unpublished source')
        write_json('config/dfm14_sources.json',dict(inherits='dfm13',base=str(BASE),additions=entries,
            selection_receipt=str(ROOT/'deduplication.json'),sampled=str(OUTPUT),**report))
        write_json(ROOT/'completion.json',dict(status='ready',**report,
            metadata_sha256=file_hash(OUTPUT/'metadata.json'),registry_sha256=file_hash('config/dfm14_sources.json'),
            publication_sha256=file_hash(EXPORT/'upload-receipts.json'),training_handoff_at_step=900000))
        print('DFM14 READY',json.dumps(report),flush=True)


if __name__=='__main__':main()
