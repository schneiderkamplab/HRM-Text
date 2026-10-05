"""Narrow verified DFM13 admission for the two published TLPC task packages."""
from pathlib import Path

from .tlpc_release import CONTRACT, NAMES


def unready(entry):
    if entry.get('name') not in NAMES.values() or entry.get('publication_contract')!=CONTRACT:
        return 'unsupported_tlpc_source'
    if (entry.get('status')!='accepted_uploaded' or entry.get('publication_status')!='verified'
            or entry.get('uploaded') is not True or not entry.get('hf_revision')):
        return 'tlpc_publication_not_verified'
    if entry.get('tokenization_performed') is not True:
        return 'tlpc_tokenization_not_complete'
    if entry.get('repeat')!=1:
        return 'tlpc_repeat_must_be_one'
    return None


def verify(entry,contract,pins,api=None):
    if api is None:
        from scripts import assemble_dfm13_additions as api
    import json
    import numpy as np
    from .tlpc_sources import REPO,REVISION
    api.require(unready(entry) is None,'TLPC source not ready')
    api.require((entry['repo_id'],entry['revision'],entry['license'])==(REPO,REVISION,'cc-by-nc-sa-4.0'),'TLPC provenance/license changed')
    api.require(entry['target_policy']=='all_assistant_targets_native_gemma_full_history','TLPC target masking changed')
    source=api.pin(entry['output'],pins,entry['output_sha256']);folder=source.parent.parent
    manifest=api.read_json(entry['export_manifest'],pins,entry['export_manifest_sha256'])
    for key,value in manifest.items():
        api.require(entry.get(key)==value,'TLPC manifest field drift: '+key)
    api.require(entry['hf_repo_id']=='schneiderkamplab/'+entry['name'].replace('_','-'),'TLPC HF identity')
    for relative,sha in manifest['files'].items():
        path=(folder/relative).resolve()
        api.require(path.is_relative_to(folder),'TLPC package path escape');api.pin(path,pins,sha)
    approval=api.read_json(entry['release_authorization'],pins,entry['release_authorization_sha256'])
    release_root=Path(entry['validation_receipt']).parent
    api.require(approval.get('allow_scoped_overlap_release') is True and approval.get('upload_and_register') is True,
                'TLPC scoped release authority missing')
    api.pin(release_root/'packages.json',pins,approval['release_sha256'])
    api.pin(entry['selection'],pins,entry['selection_sha256'])
    validation=api.read_json(entry['validation_receipt'],pins,entry['validation_receipt_sha256'])
    api.require(validation.get('complete') is True,'TLPC raw validation incomplete')
    for result in validation['results']:
        api.pin(result['path'],pins,result['sha256'])
    published=api.read_json(release_root/(entry['name']+'-published.json'),pins)
    api.require(published==entry,'TLPC verified publication receipt mismatch')
    token=api.read_json(entry['tokenization_receipt'],pins,entry['tokenization_receipt_sha256'])
    api.require(token['source_sha256']==entry['output_sha256'] and token['regex_fix'] is False
                and token['hard_truncation'] is False and token['sequences_over_4096']==0,'TLPC token policy')
    root=Path(entry['tokenized_path']).resolve()
    api.require(Path(token['output']).resolve()==root,'TLPC token path')
    for path,sha in token['files'].items():
        api.require(Path(path).resolve().is_relative_to(root),'TLPC token path escape');api.pin(path,pins,sha)
    api.require({str(p.resolve()) for p in root.rglob('*') if p.is_file()}==set(token['files']),'TLPC token inventory')
    info=api.read_json(root/'tokenizer_info.json',pins)
    api.require(api.token_contract(info,pins)==contract,'TLPC native tokenizer mismatch')
    completion=api.read_json(root/'completion.json',pins)
    api.require(completion['rows']==entry['training_targets'] and completion['max_seq_len'] is None
                and completion['skipped_rows_this_run']==0,'TLPC dropped/expanded/truncated targets')
    parts=[dict(api.verify_arrays(p,contract['vocab_size'],pins),path=str(p),link_name=entry['name']+'__'+p.name)
           for p in sorted(root.iterdir()) if p.is_dir()]
    n=sum(p['rows'] for p in parts);tokens=sum(p['tokens'] for p in parts)
    api.require(n==entry['training_targets']==entry['tokenized_rows']==token['rows'],'TLPC target count')
    api.require(tokens==entry['rendered_tokens']==entry['tokenized_tokens']==token['tokens'],'TLPC token count')
    count=targets=0;ids=set();sample=[]
    with source.open() as stream:
        for line in stream:
            row=json.loads(line);api.require(row['id'] not in ids,'Duplicate TLPC ID');ids.add(row['id'])
            count+=1;targets+=sum(m['role']=='assistant' for m in row['messages'])
            if len(sample)<3:sample.append(row)
    api.require(count==entry['rows']==entry['expected_target'] and targets==n,'TLPC conversation quota')
    # Verify full native prefixes and targets, including all three chat targets.
    encode=api.native_encoder(info);first=Path(parts[0]['path'])
    arrays={field:np.load(first/(field+'.npy'),mmap_mode='r') for field in api.FIELDS}
    ordinal=0
    for row in sample:
        for prompt,response in encode(row,final_only=False):
            for kind,expected in [('inst',prompt),('resp',response)]:
                start=int(arrays[kind+'_start'][ordinal]);length=int(arrays[kind+'_len'][ordinal])
                api.require(arrays['tokens'][start:start+length].tolist()==list(expected),'TLPC native target parity')
            ordinal+=1
    return dict(name=entry['name'],source=str(source),repeat=1,rows=n,conversations=count,tokens=tokens,
        parts=parts,tokenized_root=str(root),hf_repo_id=entry['hf_repo_id'],hf_revision=entry['hf_revision'],
        license=entry['license'],publication_contract=CONTRACT,target_policy=entry['target_policy'],
        quality_basis='automated independent audit; scoped exact overlap; not certified gold',
        native_token_parity={'targets_checked':ordinal,'all_assistant_targets':True})
