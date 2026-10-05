"""Read-only verified DFM12 inventory delta and full-base reference for DFM13."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .build_training import registered_packages,package_data_files
from .io import file_hash,load,write_json

FIELDS=('tokens','inst_start','inst_len','resp_start','resp_len')


def classify(old,new):
    a={r['name']:r for r in old};b={r['name']:r for r in new}
    if len(a)!=len(old) or len(b)!=len(new) or set(a)-set(b):
        raise ValueError('Duplicate names or omitted inherited source')
    result={}
    for name,row in b.items():
        result[name]=('new' if name not in a else 'unchanged' if
            a[name].get('manifest_sha256')==row.get('manifest_sha256') else 'replacement')
    return result


def contract(info):
    if info.get('enable_thinking') is not False or info.get('template_mode')!='jinja_chat_template':
        raise ValueError('Native no-thinking contract required')
    return dict(vocab_size=info['vocab_size'],enable_thinking=False,template_mode=info['template_mode'],
        **{key+'_sha256':file_hash(info[key]) for key in ('tokenizer_path','chat_template_path')})


def part_reference(part,source):
    meta=load(part/'metadata.json');stat=source.stat()
    if (meta.get('max_seq_len')!=4096 or meta['source_size']!=stat.st_size
            or meta['source_mtime']!=int(stat.st_mtime)):
        raise ValueError('Tokenization source/contract drift: '+str(part))
    arrays={k:np.load(part/(k+'.npy'),mmap_mode='r',allow_pickle=False) for k in FIELDS}
    n=len(arrays['inst_len']);size=len(arrays['tokens'])
    if any(len(arrays[k])!=n for k in FIELDS[1:]):
        raise ValueError('Index cardinality mismatch')
    if n:
        ix=np.unique(np.linspace(0,n-1,min(64,n),dtype=np.int64))
        for prefix in ('inst','resp'):
            if np.any(arrays[prefix+'_start'][ix]+arrays[prefix+'_len'][ix]>size):
                raise ValueError('Sampled pointer outside tokens')
        if np.any(arrays['inst_len'][ix]+arrays['resp_len'][ix]>4096):
            raise ValueError('Sampled row exceeds context')
    return dict(task=part.name,path=str(part.resolve()),source=str(source.resolve()),rows=n,tokens=size,
        metadata_sha256=file_hash(part/'metadata.json'),arrays={k:dict(path=str((part/(k+'.npy')).resolve()),
            shape=list(arrays[k].shape),dtype=str(arrays[k].dtype),bytes=(part/(k+'.npy')).stat().st_size,
            mtime_ns=(part/(k+'.npy')).stat().st_mtime_ns) for k in FIELDS},
        validation='completion_receipt_source_stat_binding_headers_and64sampled_bounds_not_full_payload_hash')


def prepare(output):
    from scripts.assemble_dfm13_additions import base_reference
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    build=Path('data/dfm12/training-build-completed-campaign-20260929')
    old_path=Path('data/dfm12/training-build/sources.json');new_path=build/'sources.json'
    old,new=load(old_path),load(new_path);kinds=classify(old,new)
    if {k:sum(v==k for v in kinds.values()) for k in ('new','replacement','unchanged')}!={'new':292,'replacement':9,'unchanged':80}:
        raise ValueError('Approved292+9 snapshot drift')
    tokenroot=Path('data/tokenized_dfm12_additions-completed-campaign-20260929')
    base=Path('data/sampled_dfm11').resolve();pins={};base_ref,info=base_reference(base,pins)
    token_contract=contract(info)
    if contract(load(tokenroot/'tokenizer_info.json'))!=token_contract:
        raise ValueError('Inherited and latest tokenizers differ')
    exported=[r for r in new if 'export_root' in r]
    config=dict(export_roots=sorted({r['export_root'] for r in exported}),
        package_overrides={r['name']:r['export_root'] for r in exported})
    registered={p['name']:(p,d) for p,d in registered_packages(config)}
    if set(registered)!={r['name'] for r in exported}:
        raise ValueError('Published inventory mismatch')
    local_pointer=load('data/dfm12/local-audited-dala-additions.json')
    local_path=Path(local_pointer['path']);local=load(local_path)
    if file_hash(local_path)!=local_pointer['sha256'] or local.get('user_authorized_local_integration') is not True:
        raise ValueError('Local audited DaLA authorization drift')
    local_by_name={r['name']:r for r in local['components']}
    registry_path=Path('config/dfm13_sources.json');registry_hash=file_hash(registry_path);registry=load(registry_path)
    overlaps=[];sources=[];part_count=0
    tree=output/'tokenized_latest_dfm12';tree.mkdir()
    for row in new:
        name=row['name'];source_parts={};publication={}
        if name in registered:
            package,directory=registered[name];manifest_path=directory/'metadata/manifest.json';manifest=load(manifest_path)
            if file_hash(manifest_path)!=row['manifest_sha256']:
                raise ValueError('Replacement provenance drift')
            source_parts={Path(e['file']).name:dict(path=str((directory/e['file']).resolve()),sha256=e['sha256'])
                for e in package_data_files(manifest)}
            publication=dict(status='verified_published',manifest=str(manifest_path.resolve()),manifest_sha256=row['manifest_sha256'])
        else:
            local_row=local_by_name[name]
            if row['integration_sha256']!=file_hash(local_path):raise ValueError('Local integration changed')
            source_parts={Path(e['path']).name:e for e in local_row['data_files']}
            publication=dict(status='authorized_audited_local_no_upload_required',integration=str(local_path),integration_sha256=file_hash(local_path))
        parts=[]
        for filename,source_record in sorted(source_parts.items()):
            source=build/'accepted_inputs'/name/filename
            if source.resolve(strict=True)!=Path(source_record['path']).resolve(strict=True):
                raise ValueError('Staged input points to wrong source')
            part=tokenroot/(name+'__'+filename)
            ref=part_reference(part,source);ref['source_sha256_from_verified_publication']=source_record['sha256']
            parts.append(ref);(tree/part.name).symlink_to(part.resolve());part_count+=1
        hashes={r['sha256'] for r in source_parts.values()}
        for addition in registry['additions']:
            reasons=[]
            if row.get('hf_repo_id') and row['hf_repo_id']==addition.get('hf_repo_id'):reasons.append('same_published_repo')
            if addition.get('output_sha256') in hashes:reasons.append('same_export_bytes')
            if addition.get('output') and str(Path(addition['output']).resolve()) in {r['path'] for r in source_parts.values()}:reasons.append('same_export_path')
            if reasons:overlaps.append(dict(dfm12_source=name,dfm13_source=addition['name'],reasons=reasons,action='include_once'))
        sources.append(dict(**row,delta=kinds[name],publication=publication,parts=parts,
            rows=sum(p['rows'] for p in parts),tokens=sum(p['tokens'] for p in parts)))
        write_json(output/'progress.json',dict(phase='preparing',sources=len(sources),parts=part_count))
    actual={p.name for p in tokenroot.iterdir() if p.is_dir()}
    if actual!={p['task'] for r in sources for p in r['parts']}:
        raise ValueError('Tokenized inventory has missing/extra parts')
    # Publishers legitimately advance the registry during a long CPU scan.
    # Reconcile against one final immutable byte snapshot, not mixed versions.
    registry_bytes=registry_path.read_bytes()
    registry_hash=hashlib.sha256(registry_bytes).hexdigest()
    registry=json.loads(registry_bytes)
    overlaps=[]
    for row in sources:
        hashes={p['source_sha256_from_verified_publication'] for p in row['parts']}
        paths={p['source'] for p in row['parts']}
        for addition in registry['additions']:
            reasons=[]
            if row.get('hf_repo_id') and row['hf_repo_id']==addition.get('hf_repo_id'):reasons.append('same_published_repo')
            if addition.get('output_sha256') in hashes:reasons.append('same_export_bytes')
            if addition.get('output') and str(Path(addition['output']).resolve()) in paths:reasons.append('same_export_path')
            if reasons:overlaps.append(dict(dfm12_source=row['name'],dfm13_source=addition['name'],reasons=reasons,action='include_once'))
    write_json(tree/'tokenizer_info.json',info)
    write_json(output/'repeat_mapping.json',{r['name']+'__':r['repeat'] for r in sources})
    write_json(output/'dfm13_registry.snapshot.json',registry)
    manifest=dict(schema='dfm12-full-inheritance-reference-v1',ready=True,base=base_ref,
        supersedes_sampled_base='data/sampled_dfm12',composition='DFM11_base_plus_latest381_DFM12_packages_once',
        no_epoch_sampling=True,live_training_unchanged=True,tokenizer_contract=token_contract,
        sources=sources,delta_counts={k:sum(v==k for v in kinds.values()) for k in ('new','replacement','unchanged')},
        tokenized_tree=str(tree),parts=part_count,rows=sum(r['rows'] for r in sources),stored_tokens=sum(r['tokens'] for r in sources),
        exact_component_overlaps=overlaps,dfm13_registry_sha256=registry_hash,
        registry_snapshot_sha256=file_hash(output/'dfm13_registry.snapshot.json'),
        input_pins={str(p.resolve()):file_hash(p) for p in (old_path,new_path,build/'prefix_config.yaml',tokenroot/'completion.json',local_path,Path(__file__))},
        base_pins=pins,replacement_policy='Do not append to sampled_dfm12; its nine obsolete identities are omitted by reconstructing from DFM11',
        repeat_policy='Preserve approved381-source snapshot weights; no sampling performed; live identity_repeat0 not changed',
        dedup_scope='Exact component repo/export-path/export-hash only; not whole-corpus row or semantic dedup',
        raw_openhermes_excluded=True,raw_openhermes_evidence='docs/reports/dfm13_inherited_dfm12_base_check_20261004.json')
    write_json(output/'inheritance.json',manifest)
    write_json(output/'complete.json',dict(inheritance_sha256=file_hash(output/'inheritance.json'),ready=True,sources=len(sources),parts=part_count))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    result=prepare(parser.parse_args().output)
    print({k:result[k] for k in ('ready','delta_counts','rows','stored_tokens','parts','exact_component_overlaps')})
